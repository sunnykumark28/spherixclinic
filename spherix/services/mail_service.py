import os
import ssl
import smtplib
import threading
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

from spherix.config import MAIL_SERVER, MAIL_PORT, MAIL_USE_TLS, MAIL_USERNAME, MAIL_PASSWORD
from spherix.services.database import TEMP_DATA

def get_premium_otp_email_html(title, greeting, message, otp, role_color='#2563eb', accent_bg='#eff6ff'):
    """Generates an ultra-premium, modern, and responsive HTML email template for OTP delivery."""
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; width: 100% !important;">
    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f8fafc; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 500px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03); border: 1px solid #e2e8f0;">
                    <tr>
                        <td style="background-color: #0f172a; padding: 32px; text-align: center;">
                            <div style="font-size: 24px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">
                                SPHERIX<span style="color: {role_color};">CLINIC</span>
                            </div>
                            <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 2px; margin-top: 4px;">Digital Health System</div>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px 32px;">
                            <h2 style="margin: 0 0 16px 0; font-size: 20px; font-weight: 700; color: #0f172a; line-height: 1.3;">{title}</h2>
                            <p style="margin: 0 0 12px 0; font-size: 15px; color: #475569; line-height: 1.5;">{greeting}</p>
                            <p style="margin: 0 0 28px 0; font-size: 15px; color: #475569; line-height: 1.5;">{message}</p>
                            
                            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 28px;">
                                <tr>
                                    <td align="center" style="background-color: {accent_bg}; border: 2px dashed {role_color}; border-radius: 12px; padding: 20px;">
                                        <span style="font-family: 'Courier New', Courier, monospace; font-size: 38px; font-weight: 800; letter-spacing: 6px; color: {role_color}; text-shadow: 1px 1px 0px rgba(255,255,255,0.8);">{otp}</span>
                                    </td>
                                </tr>
                            </table>
                            
                            <div style="background-color: #f1f5f9; border-radius: 8px; padding: 16px; margin-bottom: 24px;">
                                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                                    <tr>
                                        <td style="vertical-align: top; width: 24px; padding-top: 2px;">
                                            <span style="font-size: 16px; color: #64748b;">ℹ️</span>
                                        </td>
                                        <td style="font-size: 13px; color: #64748b; line-height: 1.45; padding-left: 8px;">
                                            This verification code is valid for <strong>10 minutes</strong>. For security, never share this code with anyone. Spherix staff will never ask for it.
                                        </td>
                                    </tr>
                                </table>
                            </div>
                            
                            <p style="margin: 0; font-size: 13px; color: #94a3b8; line-height: 1.5; text-align: center;">
                                If you did not make this request, please ignore this email or contact support if you have concerns.
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="background-color: #f8fafc; padding: 24px 32px; border-top: 1px solid #edf2f7; text-align: center; font-size: 12px; color: #64748b;">
                            <p style="margin: 0 0 8px 0; font-weight: 600;">Spherix Clinic Health Systems</p>
                            <p style="margin: 0; font-size: 11px; color: #94a3b8;">&copy; {datetime.now().year} Spherix Clinic. Secure clinical information system.</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def send_notification_email(to_email, subject, body, is_html=False, attachment_name=None, attachment_data=None):
    """Sends an email notification with automatic TLS/SSL fallback."""
    settings = TEMP_DATA.get('settings', {})
    
    server = settings.get('mail_server') or MAIL_SERVER or 'smtp.gmail.com'
    port = int(settings.get('mail_port') or MAIL_PORT or 587)
    use_tls_val = settings.get('mail_use_tls')
    use_tls = (use_tls_val == 'true' if use_tls_val else MAIL_USE_TLS)
    username = settings.get('mail_username') or MAIL_USERNAME
    password = settings.get('mail_password') or MAIL_PASSWORD

    if password and 'SG.Test' in password and MAIL_PASSWORD and 'SG.Test' not in MAIL_PASSWORD:
        password = MAIL_PASSWORD
        username = MAIL_USERNAME or username
        server = MAIL_SERVER or server

    if not all([server, username, password]):
        print(f"⚠️ Email sending is not configured. Server: '{server}', User: '{username}', Pass: {'***' if password else 'None'}")
        return False

    if attachment_data:
        msg = MIMEMultipart()
        if is_html:
            msg.attach(MIMEText(body, 'html'))
        else:
            msg.attach(MIMEText(body))
            
        part = MIMEApplication(attachment_data, Name=attachment_name)
        part['Content-Disposition'] = f'attachment; filename="{attachment_name}"'
        msg.attach(part)
    else:
        if is_html:
            msg = MIMEText(body, 'html')
        else:
            msg = MIMEText(body)

    msg['Subject'] = subject
    msg['From'] = f"Spherix Clinic <{username}>"
    msg['To'] = to_email

    context = ssl.create_default_context()
    ports_to_try = [port]
    if port != 465 and 465 not in ports_to_try:
        ports_to_try.append(465)
    if port != 587 and 587 not in ports_to_try:
        ports_to_try.append(587)

    last_error = None
    for p in ports_to_try:
        try:
            if p == 465:
                with smtplib.SMTP_SSL(server, 465, context=context, timeout=12) as smtp_server:
                    smtp_server.login(username, password)
                    smtp_server.send_message(msg)
                print(f"✅ Email sent successfully to {to_email} via Port 465 (SSL)")
                return True
            else:
                with smtplib.SMTP(server, p, timeout=12) as smtp_server:
                    smtp_server.ehlo()
                    if use_tls or p == 587:
                        smtp_server.starttls(context=context)
                        smtp_server.ehlo()
                    smtp_server.login(username, password)
                    smtp_server.send_message(msg)
                print(f"✅ Email sent successfully to {to_email} via Port {p} (STARTTLS)")
                return True
        except smtplib.SMTPAuthenticationError as e:
            print(f"⚠️ SMTP Authentication Error for {username} on port {p}: {e}")
            last_error = e
            break
        except Exception as e:
            last_error = e
            print(f"⚠️ Port {p} attempt failed: {e}. Retrying next port...")

    print(f"❌ Failed to send email to {to_email}: {last_error}")
    return False


def send_notification_email_async(to_email, subject, body, is_html=False, attachment_name=None, attachment_data=None):
    """Dispatches email notification asynchronously in a background thread."""
    t = threading.Thread(
        target=send_notification_email,
        args=(to_email, subject, body, is_html, attachment_name, attachment_data),
        daemon=True
    )
    t.start()
    return True
