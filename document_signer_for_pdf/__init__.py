
__version__ = '0.0.1'

import importlib

pyhanko_spec = importlib.util.find_spec("pyhanko")
if pyhanko_spec is not None:
    from document_signer_for_pdf.document_signer_for_pdfs.patches import pdf
