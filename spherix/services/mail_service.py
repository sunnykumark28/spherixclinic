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

def get_premium_otp_email_html(
    title="Password Reset Request",
    greeting="Hello,",
    message="We received a request for authentication. Please use the One-Time Password (OTP) below to proceed:",
    otp="123456",
    role_color="#0284c7",
    accent_bg="#f0f9ff",
    subject_label=None,
    validity_minutes=10,
    user_name=None
):
    """
    Generates an ultra-premium, modern, and responsive HTML email template for OTP delivery,
    password reset requests, and security verifications across Spherix Clinic.
    """
    # Clean and format greeting
    if user_name:
        clean_name = str(user_name).strip()
        if not clean_name.lower().startswith(('dr.', 'mr.', 'mrs.', 'ms.', 'prof.')):
            formatted_greeting = f"Hello, Mr./Mrs. {clean_name},"
        else:
            formatted_greeting = f"Hello {clean_name},"
    elif greeting:
        formatted_greeting = greeting if greeting.endswith((',', '!')) else f"{greeting},"
    else:
        formatted_greeting = "Hello, Valued Member,"

    # Split OTP into groups or spaced digits for readable presentation
    otp_str = str(otp).strip()
    year = datetime.now().year

    subject_section = ""
    if subject_label:
        subject_section = f"""
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 16px;">
            <tr>
                <td style="background-color: #f8fafc; border-left: 4px solid {role_color}; padding: 10px 14px; border-radius: 0 8px 8px 0;">
                    <span style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #64748b; display: block; margin-bottom: 2px;">Subject</span>
                    <span style="font-size: 14px; font-weight: 600; color: #1e293b;">{subject_label}</span>
                </td>
            </tr>
        </table>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>{title}</title>
    <!--[if mso]>
    <style type="text/css">
        body, table, td {{font-family: Arial, Helvetica, sans-serif !important;}}
    </style>
    <![endif]-->
</head>
<body style="margin: 0; padding: 0; background-color: #0b1120; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; color: #334155;">
    
    <!-- Outer Wrapper -->
    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background: linear-gradient(180deg, #0b1120 0%, #0f172a 100%); padding: 40px 16px;">
        <tr>
            <td align="center">
                
                <!-- Main Container -->
                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 540px; background-color: #ffffff; border-radius: 20px; overflow: hidden; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.1); border: 1px solid #e2e8f0;">
                    
                    <!-- Header Section with Brand -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 36px 32px 30px; text-align: center; border-bottom: 3px solid {role_color};">
                            
                            <!-- Clinic Emblem & Logo -->
                            <table role="presentation" border="0" cellpadding="0" cellspacing="0" align="center" style="margin: 0 auto 12px;">
                                <tr>
                                    <td style="background: linear-gradient(135deg, {role_color} 0%, #0284c7 100%); width: 44px; height: 44px; border-radius: 12px; text-align: center; vertical-align: middle; box-shadow: 0 4px 12px rgba(2, 132, 199, 0.35);">
                                        <span style="font-size: 22px; color: #ffffff; line-height: 44px;">✦</span>
                                    </td>
                                    <td style="padding-left: 12px; text-align: left; vertical-align: middle;">
                                        <div style="font-size: 22px; font-weight: 800; color: #ffffff; letter-spacing: 0.5px; line-height: 1.1;">
                                            SPHERIX<span style="color: #38bdf8;">CLINIC</span>
                                        </div>
                                        <div style="font-size: 10px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 2.2px; margin-top: 3px;">
                                            Global Digital Health Intelligence
                                        </div>
                                    </td>
                                </tr>
                            </table>

                            <!-- Security Pill Badge -->
                            <div style="display: inline-block; margin-top: 14px; background: rgba(56, 189, 248, 0.12); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 9999px; padding: 5px 14px;">
                                <span style="font-size: 11px; font-weight: 700; color: #38bdf8; text-transform: uppercase; letter-spacing: 1.5px;">
                                    🔒 Security Verification Notice
                                </span>
                            </div>

                        </td>
                    </tr>
                    
                    <!-- Content Body -->
                    <tr>
                        <td style="padding: 36px 32px 28px; background-color: #ffffff;">
                            
                            <!-- Title -->
                            <h1 style="margin: 0 0 16px 0; font-size: 22px; font-weight: 800; color: #0f172a; line-height: 1.3; letter-spacing: -0.3px;">
                                {title}
                            </h1>

                            <!-- Optional Subject Bar -->
                            {subject_section}
                            
                            <!-- Salutation -->
                            <p style="margin: 0 0 12px 0; font-size: 16px; font-weight: 600; color: #1e293b; line-height: 1.5;">
                                {formatted_greeting}
                            </p>
                            
                            <!-- Explanatory Message -->
                            <p style="margin: 0 0 24px 0; font-size: 14px; color: #475569; line-height: 1.6;">
                                {message}
                            </p>
                            
                            <!-- OTP Display Card -->
                            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 24px;">
                                <tr>
                                    <td align="center" style="background: linear-gradient(145deg, {accent_bg} 0%, #ffffff 100%); border: 2px solid {role_color}; border-radius: 16px; padding: 24px 16px; box-shadow: 0 8px 20px -4px rgba(2, 132, 199, 0.15);">
                                        
                                        <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; color: #64748b; margin-bottom: 8px;">
                                            Your One-Time Passcode (OTP)
                                        </div>

                                        <!-- OTP Monospace Digits -->
                                        <div style="font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace; font-size: 40px; font-weight: 900; letter-spacing: 10px; color: {role_color}; text-indent: 10px; line-height: 1.1; padding: 4px 0; user-select: all;">
                                            {otp_str}
                                        </div>

                                        <!-- Expiry Badge -->
                                        <div style="display: inline-block; margin-top: 12px; background-color: #fef3c7; border: 1px solid #fde68a; border-radius: 9999px; padding: 4px 12px;">
                                            <span style="font-size: 12px; font-weight: 700; color: #92400e;">
                                                ⏱️ Code expires in {validity_minutes} minutes
                                            </span>
                                        </div>

                                    </td>
                                </tr>
                            </table>
                            
                            <!-- Security Tips Box -->
                            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f8fafc; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 24px;">
                                <tr>
                                    <td style="padding: 16px 18px;">
                                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                                            <tr>
                                                <td style="vertical-align: top; width: 26px; padding-top: 2px;">
                                                    <span style="font-size: 18px;">🛡️</span>
                                                </td>
                                                <td style="padding-left: 8px;">
                                                    <div style="font-size: 13px; font-weight: 700; color: #0f172a; margin-bottom: 2px;">
                                                        Security Reminder
                                                    </div>
                                                    <div style="font-size: 12px; color: #64748b; line-height: 1.5;">
                                                        Never share this verification code with anyone. <strong>Spherix Clinic medical or administrative personnel will never ask for your OTP.</strong>
                                                    </div>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                            
                            <!-- Dismissal Disclaimer -->
                            <p style="margin: 0; font-size: 12px; color: #94a3b8; line-height: 1.5; text-align: center;">
                                If you did not initiate this password reset or account verification request, please ignore this email or reach out to our security team immediately.
                            </p>

                        </td>
                    </tr>
                    
                    <!-- Footer Section -->
                    <tr>
                        <td style="background-color: #0f172a; padding: 26px 32px; text-align: center; border-top: 1px solid #1e293b;">
                            
                            <!-- Clinic Metadata -->
                            <div style="font-size: 13px; font-weight: 700; color: #f1f5f9; margin-bottom: 4px;">
                                Spherix Clinic Global Health Intelligence
                            </div>
                            <div style="font-size: 11px; color: #94a3b8; line-height: 1.5; margin-bottom: 12px;">
                                HQ Motihari, Bihar State 845401, India &bull; Support: support@spherixclinic.com &bull; +91 933 4325 920
                            </div>

                            <!-- Encryption & Copyright -->
                            <div style="font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 1px;">
                                🔒 256-Bit TLS Encrypted Transmission &bull; &copy; {year} Spherix Clinic. All rights reserved.
                            </div>

                        </td>
                    </tr>

                </table>
                <!-- End Main Container -->

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
