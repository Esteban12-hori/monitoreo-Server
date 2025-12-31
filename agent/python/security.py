import base64

def protect_token(token: str) -> str:
    """
    Ofusca el token para que no sea legible a simple vista en el archivo de configuración.
    Nota: Esto no es encriptación de grado militar, es para evitar lecturas casuales.
    """
    if not token: 
        return ""
    try:
        # Invierte el string y lo codifica en Base64
        encoded = base64.b64encode(token[::-1].encode("utf-8")).decode("utf-8")
        return f"enc_{encoded}"
    except Exception:
        return token

def reveal_token(token: str) -> str:
    """
    Desofusca el token si está protegido.
    """
    if not token:
        return ""
    if not token.startswith("enc_"):
        return token
    try:
        encoded = token[4:]
        decoded = base64.b64decode(encoded).decode("utf-8")
        return decoded[::-1]
    except Exception:
        return token
