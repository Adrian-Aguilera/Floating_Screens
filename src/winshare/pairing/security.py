"""Authenticate a LAN session with a randomly generated shared key."""

import secrets
import ssl

IDENTITY = "floating-screens-v1"


def new_key() -> str:
    return secrets.token_hex(32)


def tls_context(key: str, *, server: bool) -> ssl.SSLContext:
    if not ssl.HAS_PSK:
        raise ValueError("Esta instalación de Python necesita soporte para TLS-PSK.")
    try:
        secret = bytes.fromhex(key.strip())
    except ValueError:
        secret = b""
    if len(secret) != 32:
        raise ValueError("La Security Key debe contener 64 caracteres hexadecimales.")

    if server:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.set_psk_server_callback(
            lambda identity: secret if identity == IDENTITY else b""
        )
    else:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.set_psk_client_callback(lambda _hint: (IDENTITY, secret))

    context.minimum_version = ssl.TLSVersion.TLSv1_3
    return context
