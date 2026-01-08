from OpenSSL import crypto

# Generate key
key = crypto.PKey()
key.generate_key(crypto.TYPE_RSA, 4096)

# Generate certificate
cert = crypto.X509()
cert.get_subject().C = "US"
cert.get_subject().ST = "State"
cert.get_subject().L = "City"
cert.get_subject().O = "PenTestLab"
cert.get_subject().CN = "localhost"
cert.set_serial_number(1000)
cert.gmtime_adj_notBefore(0)
cert.gmtime_adj_notAfter(365*24*60*60)  # 1 year
cert.set_issuer(cert.get_subject())
cert.set_pubkey(key)
cert.sign(key, 'sha256')

# Save files
with open("cert.pem", "wb") as f:
    f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
with open("key.pem", "wb") as f:
    f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))

print("✅ SSL certificates generated: cert.pem, key.pem")
