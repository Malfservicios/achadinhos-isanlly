"""Cria a chave de assinatura do APK (uso unico). Fica em android/firma-local (fora do git)."""
import base64, datetime, secrets
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

dest = Path("android/firma-local")
if (dest / "achadinhos-firma.p12").exists():
    raise SystemExit("ja existe uma chave; nao sobrescrevo")
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Os Achadinhos da Isanlly"),
                  x509.NameAttribute(NameOID.COUNTRY_NAME, "BR")])
agora = datetime.datetime.now(datetime.timezone.utc)
cert = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(agora)
        .not_valid_after(agora + datetime.timedelta(days=365 * 30)).sign(key, hashes.SHA256()))
senha = secrets.token_urlsafe(18)
p12 = pkcs12.serialize_key_and_certificates(
    b"achadinhos", key, cert, None,
    serialization.PrivateFormat.PKCS12.encryption_builder()
    .kdf_rounds(50000).key_cert_algorithm(pkcs12.PBES.PBESv2SHA256AndAES256CBC).hmac_hash(hashes.SHA256())
    .build(senha.encode()))
(dest / "achadinhos-firma.p12").write_bytes(p12)
(dest / "SIGNING_KEY_BASE64.txt").write_text(base64.b64encode(p12).decode())
(dest / "SIGNING_PASSWORD.txt").write_text(senha)
huella = cert.fingerprint(hashes.SHA256()).hex().upper()
(dest / "huella-sha256.txt").write_text(":".join(huella[i:i + 2] for i in range(0, len(huella), 2)))
print("ok")
