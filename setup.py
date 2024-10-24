from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in document_signer_for_pdf/__init__.py
from document_signer_for_pdf import __version__ as version

setup(
	name="document_signer_for_pdf",
	version=version,
	description="Document Signer for PDF is a robust digital signing solution designed to streamline and secure the process of signing PDF documents. By integrating cutting-edge cryptographic techniques, it ensures the authenticity and integrity of digital documents, preventing tampering and guaranteeing that the signer\'s identity is verified. With a user-friendly interface and seamless integration into existing workflows, Document Signer for PDF is ideal for businesses, legal professionals, and individuals who need a reliable way to digitally sign and authenticate documents.",
	author="SVNIX Solutions",
	author_email="contact@svnix.solutions",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
