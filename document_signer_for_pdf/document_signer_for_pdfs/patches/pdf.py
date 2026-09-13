import frappe
import io
import pdfkit
from datetime import date

from packaging.version import Version

try:  # Frappe v15+ ships pypdf
    from pypdf import PdfReader, PdfWriter
except ImportError:  # Frappe v14
    from PyPDF2 import PdfReader, PdfWriter
from pyhanko.sign import signers
from pyhanko import stamp
from frappe import _
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

def signed_get_pdf(html, options=None, output: PdfWriter | None = None, smart_shrinking: bool = False, **kwargs):
    """Drop-in replacement for frappe.utils.pdf.get_pdf that digitally signs the result.

    Signature mirrors Frappe v14/v15/v16; unknown future keyword arguments are accepted and ignored.
    """
    html = scrub_urls(html)
    html, options = pdf.prepare_options(html, options)

    options.update({"disable-javascript": "", "disable-local-file-access": ""})

    filedata = ""
    if not smart_shrinking and Version(pdf.get_wkhtmltopdf_version()) > Version("0.12.3"):
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

    # Pick certs based on invoice date: Neeraj before cutoff, FuelBuddy from cutoff onwards
    cutoff_str = frappe.conf.signature_cutoff_date
    cutoff_date = date.fromisoformat(cutoff_str)
    posting_date = None
    if frappe.form_dict.get('doctype') and frappe.form_dict.get('name'):
        posting_date = frappe.db.get_value(frappe.form_dict.doctype, frappe.form_dict.name, 'posting_date')
    invoice_date = posting_date or date.today()
    if invoice_date < cutoff_date:
        pem_file = frappe.conf.signature_pem_file
        key_file = frappe.conf.signature_key_file
        ca_chain_files = frappe.conf.signature_ca_chain_files
        signature_box = frappe.conf.signature_box
        signed_by = frappe.conf.signed_by
    else:
        pem_file = frappe.conf.fuelbuddy_signature_pem_file
        key_file = frappe.conf.fuelbuddy_signature_key_file
        ca_chain_files = frappe.conf.fuelbuddy_signature_ca_chain_files
        signature_box = frappe.conf.fuelbuddy_signature_box
        signed_by = frappe.conf.fuelbuddy_signed_by

    if pem_file and key_file:
        filedata = sign_pdf(
            io.BytesIO(filedata),
            pem_file=pem_file,
            key_file=key_file,
            ca_chain_files=ca_chain_files,
            signature_box=signature_box,
            signed_by=signed_by,
            options=options
        )
    else:
        filedata = pdf.get_file_data_from_writer(writer)

    return filedata

def sign_pdf(input_pdf_io, pem_file, key_file, ca_chain_files=None, signature_box=None, signed_by = None, options=None):
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
            stamp_text='Signed by: '+ signed_by+'\nFor: %(signer)s\nTime: %(ts)s\nURL: %(url)s',
        ),
    )

    sig_field_spec = SigFieldSpec(
        sig_field_name='Signature1',
        doc_mdp_update_value=MDPPerm.NO_CHANGES,
        box=(signature_box)
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
