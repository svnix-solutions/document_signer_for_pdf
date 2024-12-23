import frappe
import io
import pdfkit

from distutils.version import LooseVersion

from PyPDF2 import PdfReader, PdfWriter
from pyhanko.sign import signers
from pyhanko import stamp
from frappe.utils import scrub_urls
from pyhanko.sign.fields import SigFieldSpec, FieldMDPSpec, FieldMDPAction, append_signature_field,MDPPerm
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

    if frappe.conf.signature_pem_file and frappe.conf.signature_key_file:
        filedata = sign_pdf(
            io.BytesIO(filedata), 
            pem_file=frappe.conf.signature_pem_file, 
            key_file=frappe.conf.signature_key_file, 
            ca_chain_files=frappe.conf.signature_ca_chain_files, 
            options=options
        )
    else:
        filedata = pdf.get_file_data_from_writer(writer)

    return filedata

def sign_pdf(input_pdf_io, pem_file, key_file, ca_chain_files=None, options=None):
    # Load the certificate and private key
    with open(pem_file, 'rb') as cert_file:
        cert = load_cert_from_pemder(pem_file)
    with open(key_file, 'rb') as k_file:
        key = load_private_key_from_pemder(key_file, passphrase=None)

    # Load CA chain if provided
    ca_chain = []
    if ca_chain_files:
        try:
            for ca_file in ca_chain_files:
                with open(ca_file, 'rb') as chain_file:
                    ca_chain.append(load_cert_from_pemder(ca_file))
            if len(ca_chain) == 0:
                raise ValueError("No CA chain certificates found in the provided CA chain files")
        except Exception as e:
            raise ValueError(f"Error loading CA chain: {e}")
    
    # Create a signer object
    signer = signers.SimpleSigner(signing_cert=cert, signing_key=key, cert_registry=ca_chain)

    # Create an IncrementalPdfFileWriter for the input PDF
    input_pdf_io.seek(0)
    pdf_writer = IncrementalPdfFileWriter(input_pdf_io)

    # Define a signature field with visible appearance
    signature_meta = signers.PdfSignatureMetadata(
        field_name='Signature1', reason='Document digitally signed'
    )

    pdf_signer = signers.PdfSigner(
        signature_meta, signer=signer, stamp_style=stamp.QRStampStyle(
            # Let's include the URL in the stamp text as well
            stamp_text='Signed by: %(signer)s\nTime: %(ts)s\nURL: %(url)s',
        ),
    )

    sig_field_spec = SigFieldSpec(
        sig_field_name='Signature1', 
        doc_mdp_update_value=MDPPerm.NO_CHANGES,
        box=(300, 200, 466, 250)
    )

    # Append the signature field to the PDF
    append_signature_field(pdf_writer, sig_field_spec)

    output_pdf_io = io.BytesIO()

    if options and "password" in options:
        pdf_writer.encrypt(options["password"])

    # Sign the PDF with a visible signature
    pdf_signer.sign_pdf(pdf_writer, output=output_pdf_io,appearance_text_params={'url': 'https://app.fuelbuddy.in'})

    # Return signed PDF as bytes
    return output_pdf_io.getvalue()

pdf.get_pdf = signed_get_pdf