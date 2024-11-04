import frappe
import io
import pdfkit

from distutils.version import LooseVersion

from PyPDF2 import PdfReader, PdfWriter
from pyhanko.sign import signers
from frappe.utils import scrub_urls
from pyhanko.sign.fields import SigFieldSpec, FieldMDPSpec, FieldMDPAction
from pyhanko.sign.general import load_cert_from_pemder, load_private_key_from_pemder
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

from frappe.utils import pdf

PDF_CONTENT_ERRORS = [
	"ContentNotFoundError",
	"ContentOperationNotPermittedError",
	"UnknownContentError",
	"RemoteHostClosedError",
]

def signed_get_pdf(html, options=None, output: PdfWriter | None = None):
	html = scrub_urls(html)
	html, options = pdf.prepare_options(html, options)

	options.update({"disable-javascript": "", "disable-local-file-access": ""})

	filedata = ""
	if LooseVersion(pdf.get_wkhtmltopdf_version()) > LooseVersion("0.12.3"):
		options.update({"disable-smart-shrinking": ""})

	try:
		# Set filename property to false, so no file is actually created
		filedata = pdfkit.from_string(html, options=options or {}, verbose=True)

		# create in-memory binary streams from filedata and create a PdfReader object
		reader = PdfReader(io.BytesIO(filedata))
	except OSError as e:
		if any([error in str(e) for error in PDF_CONTENT_ERRORS]):
			if not filedata:
				print(html, options)
				frappe.throw(_("PDF generation failed because of broken image links"))

			# allow pdfs with missing images if file got created
			if output:
				output.append_pages_from_reader(reader)
		else:
			raise
	finally:
		pdf.cleanup(options)

	if "password" in options:
		password = options["password"]

	if output:
		output.append_pages_from_reader(reader)
		return output

	writer = PdfWriter()
	writer.append_pages_from_reader(reader)

	if "password" in options:
		writer.encrypt(password)

	print("Digital Signature")
	print(frappe.conf.signature_pem_file, frappe.conf.signature_key_file)
	if frappe.conf.signature_pem_file and frappe.conf.signature_key_file:
		filedata = sign_pdf(io.BytesIO(filedata), pem_file=frappe.conf.signature_pem_file, key_file=frappe.conf.signature_key_file)
	else:
		filedata = pdf.get_file_data_from_writer(writer)

	return filedata

def sign_pdf(input_pdf_io, pem_file, key_file, options=None):
    # Load the certificate and private key
    with open(pem_file, 'rb') as cert_file:
        cert = load_cert_from_pemder(pem_file)
    with open(key_file, 'rb') as k_file:
        key = load_private_key_from_pemder(key_file, passphrase=None)

    # Create a signer object
    signer = signers.SimpleSigner(signing_cert=cert, signing_key=key, cert_registry=None)

    # Create an IncrementalPdfFileWriter for the input PDF
    input_pdf_io.seek(0)
    pdf_writer = IncrementalPdfFileWriter(input_pdf_io)

    # Define a signature field
    signature_meta = signers.PdfSignatureMetadata(
        field_name='Signature1', reason='Document digitally signed'
    )

    output_pdf_io = io.BytesIO()

    # @TODO: encrypt if password is there
    # if "password" in options:
	# 	pdf_writer.encrypt(password)

    # Sign the PDF
    signers.sign_pdf(pdf_writer, signature_meta, signer, output=output_pdf_io)

    # Return signed PDF as bytes
    return output_pdf_io.getvalue()

pdf.get_pdf = signed_get_pdf