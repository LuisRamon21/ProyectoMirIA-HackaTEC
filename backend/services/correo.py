"""
Envio del codigo de verificacion de B.A.W.I. Comunidad por correo (SMTP).

Datos en el archivo .env (con Gmail se usa una "contraseña de aplicación", no la normal):
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=tucuenta@gmail.com
    SMTP_PASSWORD=abcdefghijklmnop

Si SMTP_USER o SMTP_PASSWORD estan vacios no se envia codigo: la cuenta se crea
al momento sin verificar el correo (backend/routers/comunidad.py).
"""
import os
import smtplib
import ssl
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()


class CorreoNoConfigurado(Exception):
    """Faltan SMTP_USER o SMTP_PASSWORD en .env."""


def correo_configurado() -> bool:
    return bool(os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))


def enviar_codigo(destino: str, nombre: str, codigo: str, minutos: int) -> None:
    """Envia el codigo. Lanza RuntimeError si el servidor de correo no lo acepta."""
    if not correo_configurado():
        raise CorreoNoConfigurado()
    usuario = os.getenv("SMTP_USER")
    mensaje = EmailMessage()
    mensaje["Subject"] = f"{codigo} es tu código de B.A.W.Í. Comunidad"
    mensaje["From"] = f"B.A.W.Í. Comunidad <{usuario}>"
    mensaje["To"] = destino
    mensaje.set_content(
        f"Hola, {nombre}:\n\n"
        f"Tu código para crear tu cuenta en B.A.W.Í. Comunidad es:\n\n"
        f"        {codigo}\n\n"
        f"Vence en {minutos} minutos. Si tú no pediste esta cuenta, ignora este correo.\n\n"
        f"B.A.W.Í. · Agua, talento y comunidad"
    )
    try:
        with smtplib.SMTP(os.getenv("SMTP_HOST", "smtp.gmail.com"), int(os.getenv("SMTP_PORT", "587")),
                          timeout=15) as servidor:
            servidor.starttls(context=ssl.create_default_context())
            servidor.login(usuario, os.getenv("SMTP_PASSWORD", "").replace(" ", ""))
            servidor.send_message(mensaje)
    except (smtplib.SMTPException, OSError) as error:
        raise RuntimeError(str(error)) from error