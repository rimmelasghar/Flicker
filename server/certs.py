"""Self-signed TLS certificate for the phone-facing listener.

Created on first start and kept in the data folder, so the phone only
accepts the certificate warning once. Regenerated when HOST_IP no longer
matches the certificate, or when it is close to expiry.
"""

import datetime as dt
import ipaddress
import logging
import os
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

CERT_FILE = "cert.pem"
KEY_FILE = "key.pem"
# Apple rejects TLS server certificates valid for more than 825 days.
VALID_DAYS = 825
RENEW_BEFORE = dt.timedelta(days=30)

log = logging.getLogger("flick")


def _needs_new(cert_path: Path, key_path: Path, host_ip: str) -> bool:
    if not cert_path.is_file() or not key_path.is_file():
        return True
    try:
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except (ValueError, x509.ExtensionNotFound):
        return True
    if ipaddress.ip_address(host_ip) not in san.get_values_for_type(x509.IPAddress):
        return True
    return cert.not_valid_after_utc - dt.datetime.now(dt.UTC) < RENEW_BEFORE


def _write_private(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)


def _generate(cert_path: Path, key_path: Path, host_ip: str) -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"Flick {host_ip}")])
    now = dt.datetime.now(dt.UTC)
    san = x509.SubjectAlternativeName(
        [
            x509.IPAddress(ipaddress.ip_address(host_ip)),
            x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
            x509.DNSName("localhost"),
        ]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=VALID_DAYS))
        .add_extension(san, critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
        )
        .sign(key, hashes.SHA256())
    )
    _write_private(
        key_path,
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def ensure_certificate(data_dir: Path, host_ip: str) -> tuple[Path, Path]:
    """Return (cert, key) paths, creating or replacing them if needed."""
    data_dir.mkdir(parents=True, exist_ok=True)
    cert_path, key_path = data_dir / CERT_FILE, data_dir / KEY_FILE
    if _needs_new(cert_path, key_path, host_ip):
        _generate(cert_path, key_path, host_ip)
        log.info("generated TLS certificate for %s", host_ip)
    return cert_path, key_path
