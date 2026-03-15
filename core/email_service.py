"""
Servicio de envio de correos usando Resend.
https://resend.com/docs/send-with-python

Instalacion: pip install resend
Variable de entorno: RESEND_API_KEY=re_xxxxxxxxxxxx
"""

import resend
from core.config import get_settings


def _get_resend():
    settings = get_settings()
    resend.api_key = settings.RESEND_API_KEY
    return resend


def enviar_otp(correo: str, nombre: str, codigo: str, expire_min: int = 5) -> bool:
    """
    Envia el codigo OTP al correo del cliente.
    Retorna True si el envio fue exitoso.
    """
    r = _get_resend()

    html = _template_otp(nombre, codigo, expire_min)

    try:
        r.Emails.send({
            "from":    "Keypago <onboarding@resend.dev>",   # Cambiar por tu dominio verificado en Resend
            "to":      [correo],
            "subject": f"Tu codigo de acceso Keypago: {codigo}",
            "html":    html,
        })
        return True
    except Exception as e:
        # Loguear el error pero no exponer detalles al cliente
        print(f"[ERROR email] {e}")
        return False


def _template_otp(nombre: str, codigo: str, expire_min: int) -> str:
    """Template HTML del correo OTP."""
    digitos = "".join(
        f'<span style="'
        f'display:inline-block;'
        f'width:44px;height:56px;'
        f'line-height:56px;'
        f'text-align:center;'
        f'font-size:28px;font-weight:800;'
        f'background:#1c0e39;'
        f'color:#dcf128;'
        f'border-radius:8px;'
        f'margin:0 4px;'
        f'border:1px solid #2e2848;'
        f'">{d}</span>'
        for d in codigo
    )

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#0d091a;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0d091a;padding:40px 20px;">
    <tr>
      <td align="center">
        <table width="480" cellpadding="0" cellspacing="0"
               style="background:#14102b;border-radius:16px;border:1px solid #2e2848;overflow:hidden;max-width:480px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#1c0e39,#231e38);padding:28px 32px;">
              <table cellpadding="0" cellspacing="0">
                <tr>
                  <td style="background:#dcf128;width:36px;height:36px;border-radius:9px;
                              text-align:center;line-height:36px;font-size:18px;font-weight:900;
                              color:#0d091a;vertical-align:middle;">
                    K
                  </td>
                  <td style="padding-left:10px;font-size:20px;font-weight:800;color:#f0eef8;
                              letter-spacing:-0.02em;vertical-align:middle;">
                    keypago
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:32px 32px 24px;">
              <p style="margin:0 0 6px;font-size:13px;color:#9e98b8;text-transform:uppercase;
                         letter-spacing:0.08em;">
                Codigo de acceso
              </p>
              <h1 style="margin:0 0 16px;font-size:22px;font-weight:700;color:#f0eef8;">
                Hola, {nombre}
              </h1>
              <p style="margin:0 0 28px;font-size:15px;color:#9e98b8;line-height:1.6;">
                Usa este codigo para ingresar a tu portal Keypago.
                Es de un solo uso y expira en <strong style="color:#dcf128;">{expire_min} minutos</strong>.
              </p>

              <!-- Codigo -->
              <div style="text-align:center;margin:0 0 28px;">
                {digitos}
              </div>

              <!-- Alerta -->
              <div style="background:#1c0e39;border:1px solid #2e2848;border-radius:10px;
                           padding:14px 18px;margin-bottom:24px;">
                <p style="margin:0;font-size:13px;color:#9e98b8;line-height:1.5;">
                  <strong style="color:#f0eef8;">&#9888; Si no fuiste tu</strong>, ignora este correo.
                  Nadie de Keypago te pedira este codigo por telefono o chat.
                </p>
              </div>

              <p style="margin:0;font-size:13px;color:#6b638a;">
                Este codigo es valido por {expire_min} minutos y solo puede usarse una vez.
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:16px 32px 24px;border-top:1px solid #2e2848;">
              <p style="margin:0;font-size:11px;color:#3d3660;text-align:center;">
                keypago &mdash; Portal de Creditos &bull; No respondas este correo
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
