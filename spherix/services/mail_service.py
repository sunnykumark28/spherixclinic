import os
import re
import ssl
import smtplib
import threading
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

from email.mime.image import MIMEImage

from spherix.config import MAIL_SERVER, MAIL_PORT, MAIL_USE_TLS, MAIL_USERNAME, MAIL_PASSWORD
from spherix.services.database import TEMP_DATA

BRAND_FONTS_HEAD_HTML = """
    <!-- Google Fonts for Spherix Brand Identity: Ballet, Iceland, Zen Dots -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Ballet:opsz@16..72&family=Iceland&family=Roboto+Slab:wght@400;500;600;700;800;900&family=Zen+Dots&display=swap" rel="stylesheet">
    <style type="text/css">
        @import url('https://fonts.googleapis.com/css2?family=Ballet:opsz@16..72&family=Iceland&family=Roboto+Slab:wght@400;500;600;700;800;900&family=Zen+Dots&display=swap');
        .brand-font-spherix, .font-iceland, .font-roboto-slab {
            font-family: 'Roboto Slab', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, serif !important;
        }
        .brand-font-clinic, .font-ballet {
            font-family: 'Ballet', 'Brush Script MT', 'Lucida Handwriting', cursive !important;
        }
        .brand-font-ghi, .font-zen-dots {
            font-family: 'Zen Dots', 'Courier New', 'Century Gothic', -apple-system, sans-serif !important;
        }
        @media only screen and (max-width: 480px) {
            .brand-logo-img { width: 44px !important; height: 44px !important; }
            .brand-spherix-title { font-size: 26px !important; }
            .brand-clinic-title { font-size: 28px !important; }
            .brand-ghi-subtitle { font-size: 8.5px !important; letter-spacing: 1.6px !important; }
        }
    </style>
    <!--[if mso]>
    <style type="text/css">
        body, table, td { font-family: Arial, Helvetica, sans-serif !important; }
        .brand-font-spherix { font-family: Arial, Helvetica, sans-serif !important; }
        .brand-font-clinic { font-family: 'Brush Script MT', cursive !important; }
        .brand-font-ghi { font-family: Arial, Helvetica, sans-serif !important; }
    </style>
    <![endif]-->
"""


def get_brand_header_table(role_color="#0284c7"):
    """Returns official header table with official logo, Roboto Slab Spherix, Ballet Clinic, and Zen Dots Global Health Intelligence."""
    return f"""
    <!-- Clinic Emblem & Logo with Official Brand Fonts -->
    <table role="presentation" border="0" cellpadding="0" cellspacing="0" align="center" style="margin: 0 auto 12px;">
        <tr>
            <td style="vertical-align: middle; padding-right: 14px;">
                <img src="cid:spherix_logo" alt="Spherix Clinic Logo" class="brand-logo-img" width="52" height="52" style="display: block; width: 52px; height: 52px; border-radius: 12px; object-fit: contain; box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4); border: 2px solid rgba(255, 255, 255, 0.2);" />
            </td>
            <td style="text-align: left; vertical-align: middle;">
                <div style="line-height: 1.15; margin: 0; padding: 0;">
                    <span class="brand-font-spherix font-roboto-slab brand-spherix-title" style="font-family: 'Roboto Slab', Georgia, serif !important; font-size: 32px; font-weight: 700; color: #ffffff; letter-spacing: 0.8px; display: inline-block; vertical-align: baseline;">Spherix</span>
                    <span class="brand-font-clinic font-ballet brand-clinic-title" style="font-family: 'Ballet', 'Brush Script MT', 'Lucida Handwriting', cursive !important; font-size: 34px; font-weight: 500; color: #38bdf8; margin-left: 4px; display: inline-block; vertical-align: baseline;">Clinic</span>
                </div>
                <div class="brand-font-ghi font-zen-dots brand-ghi-subtitle" style="font-family: 'Zen Dots', 'Courier New', 'Century Gothic', -apple-system, sans-serif !important; font-size: 9.5px; color: #94a3b8; font-weight: 400; text-transform: uppercase; letter-spacing: 2.2px; margin-top: 4px; line-height: 1.2;">
                    Global Health Intelligence
                </div>
            </td>
        </tr>
    </table>
    """


def get_brand_footer_table(year=None):
    """Returns official email footer table with Roboto Slab Spherix, Ballet Clinic, and Zen Dots Global Health Intelligence."""
    if not year:
        year = datetime.now().year
    return f"""
    <!-- Footer Section with Brand Identity -->
    <tr>
        <td style="background-color: #0f172a; padding: 26px 32px; text-align: center; border-top: 1px solid #1e293b;">
            <!-- Clinic Metadata with Brand Fonts -->
            <div style="margin-bottom: 8px; line-height: 1.3;">
                <span class="brand-font-spherix font-roboto-slab" style="font-family: 'Roboto Slab', Georgia, serif !important; font-size: 17px; font-weight: 700; color: #ffffff; letter-spacing: 0.5px;">Spherix</span>
                <span class="brand-font-clinic font-ballet" style="font-family: 'Ballet', 'Brush Script MT', cursive !important; font-size: 19px; font-weight: 500; color: #38bdf8; margin-left: 3px;">Clinic</span>
                <span style="color: #64748b; font-size: 12px; margin: 0 6px;">&bull;</span>
                <span class="brand-font-ghi font-zen-dots" style="font-family: 'Zen Dots', 'Courier New', sans-serif !important; font-size: 9.5px; color: #cbd5e1; text-transform: uppercase; letter-spacing: 1.6px;">Global Health Intelligence</span>
            </div>
            <div style="font-size: 11px; color: #94a3b8; line-height: 1.5; margin-bottom: 12px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                HQ Motihari, Bihar State 845401, India &bull; Support: support@spherixclinic.com &bull; +91 933 4325 920
            </div>

            <!-- Encryption & Copyright -->
            <div style="font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 1px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                🔒 256-Bit TLS Encrypted Transmission &bull; &copy; {year} <span class="brand-font-spherix font-roboto-slab" style="font-family: 'Roboto Slab', Georgia, serif !important; font-weight: 700; color: #94a3b8;">Spherix</span> <span class="brand-font-clinic font-ballet" style="font-family: 'Ballet', cursive; color: #38bdf8;">Clinic</span>. All rights reserved.
            </div>
        </td>
    </tr>
    """


BRAND_WORDS_REGEX = re.compile(
    r'(?<![@/\w])(?:'
    r'(Global\s+Health\s+Intelligence)|'
    r'(Spherix)\s+(Clinic)|'
    r'(Spherix)|'
    r'(Clinic)'
    r')\b(?!\.[a-zA-Z])',
    re.IGNORECASE
)


def enrich_brand_fonts_html(html_str):
    """
    Scans HTML text outside of tags and script/style/code blocks and wraps
    occurrences of 'Spherix', 'Clinic', and 'Global Health Intelligence' with
    their authentic brand typography:
      - 'Spherix': Iceland font
      - 'Clinic': Ballet font
      - 'Global Health Intelligence': Zen Dots font
    Idempotent: skips text nodes already wrapped inside brand font spans.
    """
    if not html_str or not isinstance(html_str, str):
        return html_str

    parts = re.split(r'(<[^>]+>)', html_str)
    in_skip = False
    inside_brand_tag = False

    for i in range(len(parts)):
        if i % 2 == 1:
            tag = parts[i].lower()
            if tag.startswith(('<style', '<script', '<title', '<code', '<pre')):
                in_skip = True
            elif tag.startswith(('</style', '</script', '</title', '</code', '</pre')):
                in_skip = False
            elif 'brand-font-' in tag:
                inside_brand_tag = not tag.startswith('</')
            elif tag.startswith('</'):
                inside_brand_tag = False
        elif not in_skip and not inside_brand_tag:
            def repl(m):
                if m.group(1):  # Global Health Intelligence
                    return f'<span class="brand-font-ghi font-zen-dots" style="font-family: \'Zen Dots\', \'Courier New\', \'Century Gothic\', -apple-system, sans-serif !important; letter-spacing: 1.5px; font-size: inherit;">{m.group(1)}</span>'
                elif m.group(2) and m.group(3):  # Spherix Clinic
                    return f'<span class="brand-font-spherix font-roboto-slab" style="font-family: \'Roboto Slab\', Georgia, serif !important; font-weight: 700; font-size: inherit;">{m.group(2)}</span> <span class="brand-font-clinic font-ballet" style="font-family: \'Ballet\', \'Brush Script MT\', \'Lucida Handwriting\', cursive !important; font-weight: 600; font-size: inherit;">{m.group(3)}</span>'
                elif m.group(4):  # Spherix
                    return f'<span class="brand-font-spherix font-roboto-slab" style="font-family: \'Roboto Slab\', Georgia, serif !important; font-weight: 700; font-size: inherit;">{m.group(4)}</span>'
                elif m.group(5):  # Clinic
                    return f'<span class="brand-font-clinic font-ballet" style="font-family: \'Ballet\', \'Brush Script MT\', \'Lucida Handwriting\', cursive !important; font-weight: 600; font-size: inherit;">{m.group(5)}</span>'
                return m.group(0)
            parts[i] = BRAND_WORDS_REGEX.sub(repl, parts[i])

    return ''.join(parts)



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

    brand_header = get_brand_header_table(role_color=role_color)
    brand_footer = get_brand_footer_table(year=year)

    rendered_otp_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>{title}</title>
    {BRAND_FONTS_HEAD_HTML}
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
                            
                            {brand_header}

                            <!-- Security Pill Badge -->
                            <div style="display: inline-block; margin-top: 10px; background: rgba(56, 189, 248, 0.12); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 9999px; padding: 5px 14px;">
                                <span style="font-size: 11px; font-weight: 700; color: #38bdf8; text-transform: uppercase; letter-spacing: 1.5px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
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
                                                 Code expires in {validity_minutes} minutes
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
                                                        Never share this verification code with anyone. <strong><span class="brand-font-spherix font-roboto-slab" style="font-family: 'Roboto Slab', Georgia, serif; font-weight: 700;">Spherix</span> <span class="brand-font-clinic font-ballet" style="font-family: 'Ballet', cursive; color: #0284c7;">Clinic</span> medical or administrative personnel will never ask for your OTP.</strong>
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
                    
                    {brand_footer}

                </table>
                <!-- End Main Container -->

            </td>
        </tr>
    </table>
    
</body>
</html>"""
    return enrich_brand_fonts_html(rendered_otp_html)




def get_clinic_logo_path():
    """Returns absolute path to the official Spherix Clinic logo image."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidates = [
        os.path.join(base_dir, 'static', 'images', 'spherix_clinic_logo.png'),
        os.path.join(base_dir, 'static', 'images', 'spherixclinic.jpg'),
        os.path.join(base_dir, 'static', 'images', 'spherix_clinic_logo.jpg'),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def get_branded_general_email_html(
    title="Official Clinical Notification",
    content_html="",
    greeting=None,
    role_color="#0284c7",
    badge_text=None,
    action_url=None,
    action_text=None
):
    """
    Renders any arbitrary notification, inquiry, appointment update, or announcement
    inside the official Spherix Clinic branded template with Iceland ('Spherix'),
    Ballet ('Clinic'), and Zen Dots ('Global Health Intelligence') typography.
    """
    year = datetime.now().year
    brand_header = get_brand_header_table(role_color=role_color)
    brand_footer = get_brand_footer_table(year=year)

    badge_markup = ""
    if badge_text:
        badge_markup = f"""
        <div style="display: inline-block; margin-top: 10px; background: rgba(56, 189, 248, 0.12); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 9999px; padding: 5px 14px;">
            <span style="font-size: 11px; font-weight: 700; color: #38bdf8; text-transform: uppercase; letter-spacing: 1.5px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                {badge_text}
            </span>
        </div>
        """

    greeting_markup = ""
    if greeting:
        greeting_markup = f"""
        <p style="margin: 0 0 16px 0; font-size: 16px; font-weight: 600; color: #1e293b; line-height: 1.5;">
            {greeting}
        </p>
        """

    cta_markup = ""
    if action_url and action_text:
        cta_markup = f"""
        <div style="text-align: center; margin: 28px 0;">
            <a href="{action_url}" target="_blank" style="background: linear-gradient(135deg, {role_color} 0%, #0f172a 100%); color: #ffffff; font-size: 14px; font-weight: 700; text-decoration: none; padding: 14px 34px; border-radius: 50px; display: inline-block; box-shadow: 0 8px 20px -4px rgba(0, 0, 0, 0.25); letter-spacing: 0.5px;">
                {action_text} &rarr;
            </a>
        </div>
        """

    rendered_general_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>{title}</title>
    {BRAND_FONTS_HEAD_HTML}
</head>
<body style="margin: 0; padding: 0; background-color: #0b1120; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; color: #334155;">
    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background: linear-gradient(180deg, #0b1120 0%, #0f172a 100%); padding: 40px 16px;">
        <tr>
            <td align="center">
                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 580px; background-color: #ffffff; border-radius: 20px; overflow: hidden; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.1); border: 1px solid #e2e8f0;">
                    
                    <!-- Header Section with Brand -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 34px 32px 28px; text-align: center; border-bottom: 3px solid {role_color};">
                            {brand_header}
                            {badge_markup}
                        </td>
                    </tr>
                    
                    <!-- Content Body -->
                    <tr>
                        <td style="padding: 36px 32px 30px; background-color: #ffffff;">
                            <h1 style="margin: 0 0 18px 0; font-size: 22px; font-weight: 800; color: #0f172a; line-height: 1.35; letter-spacing: -0.3px;">
                                {title}
                            </h1>

                            {greeting_markup}

                            <div style="font-size: 14px; line-height: 1.65; color: #334155;">
                                {content_html}
                            </div>

                            {cta_markup}

                            <p style="margin: 28px 0 0 0; font-size: 12px; color: #94a3b8; line-height: 1.5; text-align: center; border-top: 1px dashed #e2e8f0; padding-top: 18px;">
                                Need clinical or technical assistance? Contact our 24/7 dedicated support desk at <strong>support@spherixclinic.com</strong>.
                            </p>
                        </td>
                    </tr>
                    
                    {brand_footer}

                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""
    return enrich_brand_fonts_html(rendered_general_html)



def send_notification_email(to_email, subject, body, is_html=False, attachment_name=None, attachment_data=None, inline_images=None):
    """Sends an email notification with automatic TLS/SSL fallback, brand font enforcement, and inline CID image embedding."""
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

    # Prepare HTML & Plain-Text payloads with automatic brand formatting
    final_plain = body if not is_html else "Please view this official communication in an HTML-capable email client."
    
    if is_html:
        body_str = str(body)
        if '<html' in body_str.lower() or '<!doctype' in body_str.lower():
            # Inject Google Fonts if not already in head
            if 'family=Roboto+Slab' not in body_str and '</head>' in body_str:
                body_str = body_str.replace('</head>', f"{BRAND_FONTS_HEAD_HTML}\n</head>", 1)
            final_html = enrich_brand_fonts_html(body_str)
        else:
            final_html = get_branded_general_email_html(title=subject, content_html=body_str)
    else:
        # Wrap plain text in official branded HTML companion
        formatted_content = str(body).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
        final_html = get_branded_general_email_html(title=subject, content_html=f"<div style='font-size: 14px; line-height: 1.65; color: #334155;'>{formatted_content}</div>")

    # Auto-resolve Spherix logo if referenced in HTML content
    active_inline = list(inline_images or [])
    if 'cid:spherix_logo' in final_html and not any(cid == 'spherix_logo' for cid, _ in active_inline):
        logo_path = get_clinic_logo_path()
        if logo_path:
            active_inline.append(('spherix_logo', logo_path))

    # Build standard RFC 2387 multipart/related email for inline images + alternative HTML/plain
    related_part = MIMEMultipart('related')
    
    alt_part = MIMEMultipart('alternative')
    alt_part.attach(MIMEText(final_plain, 'plain'))
    alt_part.attach(MIMEText(final_html, 'html'))
    related_part.attach(alt_part)

    for cid, img_path in active_inline:
        if img_path and os.path.exists(img_path):
            try:
                with open(img_path, 'rb') as f:
                    img_bytes = f.read()
                subtype = 'png' if img_path.lower().endswith('.png') else 'jpeg'
                img_part = MIMEImage(img_bytes, _subtype=subtype)
                img_part.add_header('Content-ID', f'<{cid}>')
                img_part.add_header('Content-Disposition', 'inline', filename=os.path.basename(img_path))
                related_part.attach(img_part)
            except Exception as img_err:
                print(f"⚠️ Could not attach inline image {img_path}: {img_err}")

    if attachment_data:
        msg = MIMEMultipart('mixed')
        msg.attach(related_part)
        part = MIMEApplication(attachment_data, Name=attachment_name)
        part['Content-Disposition'] = f'attachment; filename="{attachment_name}"'
        msg.attach(part)
    else:
        msg = related_part

    msg['Subject'] = subject
    msg['From'] = f"Spherix Clinic <{username}>" if username else "Spherix Clinic <notifications@spherixclinic.com>"
    msg['To'] = to_email

    if not all([server, username, password]):
        print(f"⚠️ Email sending is not configured. Server: '{server}', User: '{username}', Pass: {'***' if password else 'None'}")
        return False

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


def send_notification_email_async(to_email, subject, body, is_html=False, attachment_name=None, attachment_data=None, inline_images=None):
    """Dispatches email notification asynchronously in a background thread."""
    t = threading.Thread(
        target=send_notification_email,
        args=(to_email, subject, body, is_html, attachment_name, attachment_data, inline_images),
        daemon=True
    )
    t.start()
    return True


def get_account_approval_email_html(
    entity_type="Doctor",
    name="Valued Member",
    account_id="N/A",
    license_number="N/A",
    login_url="https://spherixclinic.com",
    extra_details=None
):
    """
    Generates an ultra-premium HTML email template for sending official account verification credentials
    (including Account ID and Spherix License Number) and official Spherix Clinic Logo to
    Hospitals, Doctors, and Patients upon administrative approval.
    """
    entity_lower = str(entity_type).strip().lower()
    if 'hospital' in entity_lower:
        role_title = "Hospital / Medical Facility"
        badge_text = "🏥 Hospital Network Verified & Authorized"
        role_color = "#059669"
        accent_bg = "#ecfdf5"
        role_greeting = f"Dear Administration of {name},"
        welcome_msg = "We are pleased to inform you that your Hospital / Medical Facility account registration has been thoroughly inspected, verified, and officially approved by the Spherix Clinic Administration. Your facility is now officially activated on our global digital healthcare network."
        cta_text = "Access Hospital Portal"
        license_label = "Hospital Facility License No"
        next_steps_text = "Log in using your registered credentials. Visit your <strong>Hospital Dashboard</strong> to configure ward and ICU bed quotas, manage emergency walk-ins, and oversee clinical staff departments."
    elif 'patient' in entity_lower:
        clean_name = str(name).strip()
        role_title = "Patient / Health Member"
        badge_text = "🛡️ Spherix Health Account Verified"
        role_color = "#0284c7"
        accent_bg = "#f0f9ff"
        role_greeting = f"Dear {clean_name},"
        welcome_msg = "We are pleased to inform you that your Patient Health Account has been verified and approved by the Spherix Clinic Administration. Your Universal Spherix Digital Health License ID has been activated. You now have full access to our healthcare ecosystem."
        cta_text = "Access Patient Portal"
        license_label = "Universal Spherix Health License / ID"
        next_steps_text = "Log in using your Patient ID, registered email, or phone number. Visit your <strong>Patient Dashboard</strong> to consult top specialists, view lab reports, book emergency ambulance / ICU beds, and track your health vitals."
    else: # Doctor / Specialist
        clean_name = str(name).strip()
        if not clean_name.lower().startswith('dr.'):
            clean_name = f"Dr. {clean_name}"
        role_title = "Doctor / Medical Specialist"
        badge_text = "🩺 Medical Practitioner Verified & Licensed"
        role_color = "#2563eb"
        accent_bg = "#eff6ff"
        role_greeting = f"Dear {clean_name},"
        welcome_msg = "We are pleased to inform you that your medical credentials and clinician profile have been verified and approved by the Spherix Clinical Board. You are now officially licensed to practice on the Spherix Clinic platform to manage OPD queues, conduct video teleconsultations, and issue digital e-prescriptions."
        cta_text = "Access Doctor Workspace"
        license_label = "Medical Practitioner License No"
        next_steps_text = "Log in using your practitioner ID or email. Visit your <strong>Doctor Workspace</strong> to set your consultation schedule, review patient appointment requests, and access our AI differential diagnosis tools."

    year = datetime.now().year

    # Build extra details table if provided
    extra_rows = ""
    if extra_details and isinstance(extra_details, dict):
        for k, v in extra_details.items():
            if v:
                extra_rows += f"""
                <tr>
                    <td style="padding: 7px 0; font-size: 13px; color: #64748b; font-weight: 600; width: 45%;">{k}:</td>
                    <td style="padding: 7px 0; font-size: 13px; color: #0f172a; font-weight: 700; text-align: right;">{v}</td>
                </tr>
                """

    brand_header = get_brand_header_table(role_color=role_color)
    brand_footer = get_brand_footer_table(year=year)

    rendered_approval_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Account Verified &amp; Activated - Spherix Clinic</title>
    {BRAND_FONTS_HEAD_HTML}
</head>
<body style="margin: 0; padding: 0; background-color: #0b1120; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; color: #334155; -webkit-font-smoothing: antialiased;">
    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background: linear-gradient(180deg, #0b1120 0%, #0f172a 100%); padding: 40px 16px;">
        <tr>
            <td align="center">
                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 580px; background-color: #ffffff; border-radius: 24px; overflow: hidden; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.45); border: 1px solid #e2e8f0;">
                    
                    <!-- Header Section with Spherix Clinic Logo -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 36px 32px 30px; text-align: center; border-bottom: 4px solid {role_color};">
                            
                            {brand_header}

                            <!-- Role Verification Badge -->
                            <div style="display: inline-block; margin-top: 10px; background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 9999px; padding: 6px 18px;">
                                <span style="font-size: 11px; font-weight: 700; color: #ffffff; text-transform: uppercase; letter-spacing: 1.5px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                                    {badge_text}
                                </span>
                            </div>
                        </td>
                    </tr>

                    <!-- Body Content -->
                    <tr>
                        <td style="padding: 36px 32px 28px; background-color: #ffffff;">
                            
                            <h1 style="margin: 0 0 8px 0; font-size: 22px; font-weight: 800; color: #0f172a; line-height: 1.3;">
                                Account Verification Approved ✅
                            </h1>
                            <div style="font-size: 13px; font-weight: 700; color: {role_color}; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 20px;">
                                {role_title} Verification
                            </div>

                            <p style="margin: 0 0 14px 0; font-size: 15px; font-weight: 700; color: #1e293b; line-height: 1.5;">
                                {role_greeting}
                            </p>

                            <p style="margin: 0 0 24px 0; font-size: 14px; color: #475569; line-height: 1.6;">
                                {welcome_msg}
                            </p>

                            <!-- Credentials Box (Account ID & License Number) -->
                            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background: linear-gradient(145deg, {accent_bg} 0%, #ffffff 100%); border: 2px solid {role_color}; border-radius: 18px; margin-bottom: 26px; overflow: hidden; box-shadow: 0 6px 18px -4px rgba(0, 0, 0, 0.06);">
                                <tr>
                                    <td style="padding: 22px 24px;">
                                        <div style="font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 1.5px; color: {role_color}; margin-bottom: 14px; border-bottom: 1px dashed #cbd5e1; padding-bottom: 8px;">
                                            Official Network Credentials &amp; License Identifiers
                                        </div>

                                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                                            <tr>
                                                <td style="padding: 8px 0; font-size: 13px; color: #64748b; font-weight: 600; width: 45%;">Account / Member ID:</td>
                                                <td style="padding: 8px 0; text-align: right;">
                                                    <span style="font-family: 'SFMono-Regular', Consolas, Menlo, monospace; font-size: 14px; font-weight: 800; color: #0f172a; background: #ffffff; border: 1px solid #cbd5e1; padding: 4px 10px; border-radius: 8px; display: inline-block;">
                                                        {account_id}
                                                    </span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 8px 0; font-size: 13px; color: #64748b; font-weight: 600; width: 45%;">{license_label}:</td>
                                                <td style="padding: 8px 0; text-align: right;">
                                                    <span style="font-family: 'SFMono-Regular', Consolas, Menlo, monospace; font-size: 14px; font-weight: 800; color: {role_color}; background: #ffffff; border: 1px solid #cbd5e1; padding: 4px 10px; border-radius: 8px; display: inline-block;">
                                                        {license_number}
                                                    </span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding: 8px 0; font-size: 13px; color: #64748b; font-weight: 600;">Status:</td>
                                                <td style="padding: 8px 0; text-align: right;">
                                                    <span style="font-size: 12px; font-weight: 800; color: #059669; background: #dcfce7; padding: 3px 10px; border-radius: 9999px; display: inline-block;">
                                                        ● ACTIVE &amp; APPROVED
                                                    </span>
                                                </td>
                                            </tr>
                                            {extra_rows}
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <!-- CTA Button -->
                            <div style="text-align: center; margin: 28px 0;">
                                <a href="{login_url}" target="_blank" style="background: linear-gradient(135deg, {role_color} 0%, #0f172a 100%); color: #ffffff; font-size: 14px; font-weight: 700; text-decoration: none; padding: 14px 34px; border-radius: 50px; display: inline-block; box-shadow: 0 8px 20px -4px rgba(0, 0, 0, 0.25); letter-spacing: 0.5px;">
                                    {cta_text} &rarr;
                                </a>
                            </div>

                            <!-- Helpful Tips / Notice -->
                            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f8fafc; border-radius: 14px; border: 1px solid #e2e8f0; margin-bottom: 20px;">
                                <tr>
                                    <td style="padding: 16px 20px;">
                                        <div style="font-size: 12px; font-weight: 700; color: #0f172a; margin-bottom: 4px;">
                                            💡 Next Steps:
                                        </div>
                                        <div style="font-size: 12px; color: #64748b; line-height: 1.6;">
                                            {next_steps_text}
                                        </div>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 0; font-size: 12px; color: #94a3b8; line-height: 1.5; text-align: center;">
                                Need help getting started? Contact our 24/7 dedicated support desk at <strong>support@spherixclinic.com</strong>.
                            </p>
                        </td>
                    </tr>

                    {brand_footer}

                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""
    return enrich_brand_fonts_html(rendered_approval_html)



def send_approval_notification(entity_type, name, to_email, account_id, license_number, login_url, extra_details=None):
    """
    Sends an automated, styled approval email containing the entity's ID number,
    official Spherix License number, official clinic logo, and direct login URL to their registered email address.
    """
    if not to_email:
        return False
    
    subject = f"Official Account Verification & Spherix License ({entity_type} ID: {account_id}) - Spherix Clinic"
    html_content = get_account_approval_email_html(
        entity_type=entity_type,
        name=name,
        account_id=account_id,
        license_number=license_number,
        login_url=login_url,
        extra_details=extra_details
    )
    return send_notification_email_async(
        to_email=to_email,
        subject=subject,
        body=html_content,
        is_html=True
    )
