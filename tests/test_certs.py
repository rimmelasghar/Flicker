import ipaddress

from cryptography import x509

from server.certs import ensure_certificate


def _san_ips(cert_path):
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    return san.get_values_for_type(x509.IPAddress)


def test_creates_cert_with_host_ip_in_san(tmp_path):
    cert_path, key_path = ensure_certificate(tmp_path, "192.168.1.50")
    assert key_path.is_file()
    assert ipaddress.ip_address("192.168.1.50") in _san_ips(cert_path)


def test_reuses_cert_when_host_ip_unchanged(tmp_path):
    cert_path, _ = ensure_certificate(tmp_path, "192.168.1.50")
    first = cert_path.read_bytes()
    ensure_certificate(tmp_path, "192.168.1.50")
    assert cert_path.read_bytes() == first


def test_regenerates_cert_when_host_ip_changes(tmp_path):
    cert_path, _ = ensure_certificate(tmp_path, "192.168.1.50")
    ensure_certificate(tmp_path, "192.168.1.77")
    assert ipaddress.ip_address("192.168.1.77") in _san_ips(cert_path)


def test_regenerates_unreadable_cert(tmp_path):
    cert_path, _ = ensure_certificate(tmp_path, "192.168.1.50")
    cert_path.write_text("garbage")
    ensure_certificate(tmp_path, "192.168.1.50")
    assert ipaddress.ip_address("192.168.1.50") in _san_ips(cert_path)
