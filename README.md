## Document Signer for PDFs

Document Signer for PDF is a robust digital signing solution designed to streamline and secure the process of signing PDF documents. By integrating cutting-edge cryptographic techniques, it ensures the authenticity and integrity of digital documents, preventing tampering and guaranteeing that the signer's identity is verified. With a user-friendly interface and seamless integration into existing workflows, Document Signer for PDF is ideal for businesses, legal professionals, and individuals who need a reliable way to digitally sign and authenticate documents.

#### How to use
add these to site_config.json, mind your parameters
```
"signature_key_file": "/workspace/development/frappe-bench/certs/key.pem",
 "signature_pem_file": "/workspace/development/frappe-bench/certs/file.pem",
 "signature_ca_chain_files": [
    "/workspace/development/frappe-bench/certs/chain/cert1.pem",
    "/workspace/development/frappe-bench/certs/chain/cert2.pem",
    "/workspace/development/frappe-bench/certs/chain/cert3.pem"
],
```

then install plugin 
```
$ bench get-app --branch main --resolve-deps svnix-solutions/document_signer_for_pdf
$ bench new-site \
....
--install-app=document_signer_for_pdf \
....

```
#### License

GPLv3