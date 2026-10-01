import os
import sys
import random
import secrets
from datetime import datetime, timezone

# Automatically configure unixODBC paths on macOS for Homebrew installations
if sys.platform == 'darwin' and not os.environ.get('ODBCSYSINI'):
    for prefix in ['/opt/homebrew/etc', '/usr/local/etc']:
        if os.path.exists(os.path.join(prefix, 'odbcinst.ini')):
            os.environ['ODBCSYSINI'] = prefix
            break

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    for sp in ['/opt/anaconda3/lib/python3.13/site-packages', '/opt/anaconda3/lib/python3.12/site-packages', '/opt/anaconda3/lib/python3.11/site-packages', '/opt/homebrew/lib/python3.11/site-packages', '/opt/homebrew/lib/python3.12/site-packages', '/usr/local/lib/python3.11/site-packages']:
        if os.path.exists(sp) and sp not in sys.path:
            sys.path.insert(0, sp)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        def load_dotenv(): pass

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class DateString(str):
    """A string subclass that supports .strftime() formatting without crashing."""
    def strftime(self, format_str):
        clean_val = str(self).strip()
        for fmt in (
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%d',
            '%d %b %Y',
            '%B %d, %Y',
            '%b %d, %Y',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%S.%f%z',
            '%H:%M:%S',
            '%H:%M',
            '%I:%M %p'
        ):
            try:
                dt = datetime.strptime(clean_val, fmt)
                return dt.strftime(format_str)
            except (ValueError, TypeError):
                continue
        try:
            dt = datetime.fromisoformat(clean_val.replace('Z', '+00:00'))
            return dt.strftime(format_str)
        except Exception:
            return clean_val

def ensure_safe_date(val):
    if val is None:
        return val
    if hasattr(val, 'strftime'):
        return val
    if isinstance(val, str):
        return DateString(val)
    return val

# Secret Key
# Production must provide a stable, private key. Local development gets a
# per-process key so a published default cannot be used to forge sessions.
_secret_key = os.environ.get('SECRET_KEY') or os.environ.get('FLASK_SECRET')
if not _secret_key and os.environ.get('FLASK_ENV', '').lower() == 'production':
    raise RuntimeError('SECRET_KEY must be set in production.')
SECRET_KEY = _secret_key or secrets.token_hex(32)

# Mail configuration
MAIL_SERVER = str(os.getenv('MAIL_SERVER', '')).strip(" '\"")
MAIL_PORT = int(str(os.getenv('MAIL_PORT', '587')).strip(" '\"") or 587)
MAIL_USE_TLS = str(os.getenv('MAIL_USE_TLS', 'True')).strip(" '\"").lower() == 'true'
MAIL_USERNAME = str(os.getenv('MAIL_USERNAME', '')).strip(" '\"")
MAIL_PASSWORD = str(os.getenv('MAIL_PASSWORD', '')).strip(" '\"")

# Database configuration
DATA_FILE = 'data_store.json'
SERVER = os.getenv('DB_SERVER', 'localhost')
DATABASE = os.getenv('DB_NAME', 'spherixclinic')
USERNAME = os.getenv('DB_USER', 'sa')
PASSWORD = os.getenv('DB_PASSWORD') or os.getenv('DB_PASS', '')
DRIVER = os.getenv('DB_DRIVER', '{ODBC Driver 17 for SQL Server}')

# Global Currency Rates & Symbols
GLOBAL_CURRENCY_RATES = {
    'INR': 1.0,
    'USD': 86.5,
    'EUR': 92.0,
    'GBP': 109.5,
    'AED': 23.55,
    'SGD': 64.8,
    'CAD': 60.5,
    'AUD': 54.2,
}

GLOBAL_CURRENCY_SYMBOLS = {
    'INR': '₹',
    'USD': '$',
    'EUR': '€',
    'GBP': '£',
    'AED': 'د.إ',
    'SGD': 'S$',
    'CAD': 'C$',
    'AUD': 'A$',
}

try:
    from countries_data import COUNTRIES_195, GLOBAL_COUNTRY_FLAGS, GLOBAL_COUNTRY_TIMEZONES, search_countries
except ImportError:
    COUNTRIES_195 = []
    GLOBAL_COUNTRY_FLAGS = {}
    GLOBAL_COUNTRY_TIMEZONES = {}
    def search_countries(q): return []

def get_currency_symbol(curr_code='INR'):
    return GLOBAL_CURRENCY_SYMBOLS.get(str(curr_code or 'INR').upper(), '₹')

def convert_currency(amount, from_curr='INR', to_curr='INR'):
    """Converts amount from from_curr to to_curr using pegged FX exchange rates."""
    try:
        val = float(amount or 0)
    except (ValueError, TypeError):
        return 0.0
    from_rate = GLOBAL_CURRENCY_RATES.get(str(from_curr).upper(), 1.0)
    to_rate = GLOBAL_CURRENCY_RATES.get(str(to_curr).upper(), 1.0)
    inr_val = val * from_rate
    return round(inr_val / to_rate, 2)

def format_dual_currency(amount_inr, doctor_curr='USD'):
    """Returns a formatted dual-currency string, e.g. '₹4,000 ($46.24 USD)'"""
    try:
        inr_val = float(amount_inr or 0)
    except:
        inr_val = 0.0
    sym_inr = GLOBAL_CURRENCY_SYMBOLS.get('INR', '₹')
    sym_doc = GLOBAL_CURRENCY_SYMBOLS.get(str(doctor_curr).upper(), '$')
    converted = convert_currency(inr_val, 'INR', doctor_curr)
    if str(doctor_curr).upper() == 'INR':
        return f"{sym_inr}{inr_val:,.0f}"
    return f"{sym_inr}{inr_val:,.0f} ({sym_doc}{converted:,.2f} {doctor_curr.upper()})"

def generate_user_license_id(role):
    """
    Generates a formal, role-specific License ID / Registration ID for each user type.
      - Doctor: MCI-YYYY-XXXXX-DL
      - Hospital: HOSP-LIC-YYYY-XXXXX
      - Patient: SPX-PAT-YYYY-XXXXX (Universal Digital Health ID)
      - Blood Donor: BD-LIC-YYYY-XXXXX (Certified Blood Registry ID)
      - Organ Donor: OD-LIC-YYYY-XXXXX (National Organ Registry Pledge License ID)
    """
    year = datetime.now().year
    rand_num = random.randint(10000, 99999)
    role_lower = str(role or '').lower()
    if 'doc' in role_lower:
        return f"MCI-{year}-{rand_num}-DL"
    elif 'hosp' in role_lower:
        return f"HOSP-LIC-{year}-{rand_num}"
    elif 'blood' in role_lower:
        return f"BD-LIC-{year}-{rand_num}"
    elif 'organ' in role_lower:
        return f"OD-LIC-{year}-{rand_num}"
    elif 'patient' in role_lower:
        return f"SPX-PAT-{year}-{rand_num}"
    else:
        return f"SPX-LIC-{year}-{rand_num}"

def get_actual_user_id(user_id):
    """Extract actual ID from Flask-Login prefixed ID (e.g., 'doctor-123' -> '123')."""
    if not user_id or not isinstance(user_id, str):
        return user_id
    prefixes = ('doctor-', 'patient-', 'staff-', 'hospital-', 'blood_donor-', 'organ_donor-')
    for prefix in prefixes:
        if user_id.startswith(prefix):
            id_val = user_id[len(prefix):]
            return int(id_val) if id_val.isdigit() else id_val
    return user_id

def parse_route_id(id_val):
    """Parses ID to integer if it represents a legacy numerical ID, otherwise returns the string."""
    return int(id_val) if isinstance(id_val, str) and id_val.isdigit() else id_val

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

BLOG_POSTS = [
    {
        "slug": "understanding-the-flu",
        "title": "Understanding the Flu vs. The Common Cold",
        "author": "Dr. Emily Carter",
        "date": "2023-10-15",
        "image": "https://images.unsplash.com/photo-1555895289-2a1b53295253?auto=format&fit=crop&w=400&q=80",
        "tags": ["flu", "common cold", "fever", "respiratory", "flu-like symptoms", "cough"],
        "excerpt": "It's that time of year again. Is it just a cold, or do you have the flu? Learn the key differences in symptoms and when to see a doctor."
    },
    {
        "slug": "managing-migraines",
        "title": "Effective Strategies for Managing Migraines",
        "author": "Dr. Ben Adams",
        "date": "2023-09-22",
        "image": "https://images.unsplash.com/photo-1597413543313-4d4f51a37262?auto=format&fit=crop&w=400&q=80",
        "tags": ["migraine", "headache", "neurology", "migraine with aura"],
        "excerpt": "Migraines can be debilitating. We explore the latest treatments, lifestyle changes, and trigger identification techniques to help you regain control."
    },
    {
        "slug": "heartburn-gerd-guide",
        "title": "A Patient's Guide to Heartburn and GERD",
        "author": "Dr. Sarah Jenkins",
        "date": "2023-11-01",
        "image": "https://images.unsplash.com/photo-1620702791037-6815d37c562a?auto=format&fit=crop&w=400&q=80",
        "tags": ["heartburn", "gastroenteritis", "gerd", "abdominal pain"],
        "excerpt": "Constant heartburn could be a sign of GERD. Understand the causes, symptoms, and how to manage this common digestive issue."
    },
    {
        "slug": "living-with-arthritis",
        "title": "Living Well with Arthritis: Tips for Joint Pain",
        "author": "Dr. Michael Lee",
        "date": "2023-08-18",
        "image": "https://images.unsplash.com/photo-1586424980993-20a27a072a1a?auto=format&fit=crop&w=400&q=80",
        "tags": ["arthritis", "joint pain", "orthopedics", "rheumatology"],
        "excerpt": "Arthritis doesn't have to stop you. Discover effective ways to manage joint pain, stay active, and improve your quality of life."
    },
    {
        "slug": "anxiety-and-stress",
        "title": "Coping with Anxiety in a High-Stress World",
        "author": "Dr. Jessica Chen",
        "date": "2023-10-05",
        "image": "https://images.unsplash.com/photo-1598704029893-5471329a93a4?auto=format&fit=crop&w=400&q=80",
        "tags": ["anxiety", "stress", "depression", "mental health", "insomnia"],
        "excerpt": "Learn practical, evidence-based techniques to manage anxiety and reduce stress in your daily life. Your mental well-being is a priority."
    }
]



def generate_captcha_text(length=5):
    """Generate a clean, unambiguous alphanumeric CAPTCHA text."""
    # Excludes easily confusable characters (0/O, 1/I/L, 5/S, 8/B) for effortless readability
    chars = "234679ACDEFHJKMNPRTWXYZ"
    return "".join(random.choices(chars, k=length))

def generate_captcha_image_bytes(text):
    """Generate a high-security visual CAPTCHA image with anti-bot distortions, crossing sine waves, character rotation, and noise."""
    from PIL import Image, ImageDraw, ImageFont
    import io, random, math, os

    width, height = 190, 54
    # Modern dark slate background
    bg_color = (15, 23, 42)
    img = Image.new('RGBA', (width, height), color=(*bg_color, 255))
    draw = ImageDraw.Draw(img)

    # 1. Background geometric noise & grid lines
    for _ in range(5):
        p1 = (random.randint(0, width), random.randint(0, height))
        p2 = (random.randint(0, width), random.randint(0, height))
        line_color = (random.randint(40, 80), random.randint(60, 110), random.randint(90, 150), 160)
        draw.line([p1, p2], fill=line_color, width=random.randint(1, 2))

    # 2. Cross-platform Font Resolution
    font_candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'fonts', 'DejaVuSans-Bold.ttf'),
        os.path.join(os.getcwd(), 'static', 'fonts', 'DejaVuSans-Bold.ttf'),
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
        '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
        '/System/Library/Fonts/Helvetica.ttc',
        '/Library/Fonts/Arial.ttf',
        'Arial.ttf',
        'DejaVuSans-Bold.ttf'
    ]
    font_path = None
    for p in font_candidates:
        if p and os.path.exists(p):
            font_path = p
            break

    # 3. High-contrast character palette with distinct security colors
    palette = [
        (52, 211, 153),   # emerald-400
        (56, 189, 248),   # sky-400
        (251, 191, 36),   # amber-400
        (244, 114, 182),  # pink-400
        (167, 139, 250),  # violet-400
        (250, 204, 21),   # yellow-400
        (236, 72, 153),   # rose-400
        (226, 232, 240),  # bright slate
    ]

    # 4. Render characters with random rotation, variable size, and jitter
    text_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    total_chars = len(text)
    slot_width = (width - 24) / total_chars

    for i, char in enumerate(text):
        char_size = random.randint(26, 32)
        if font_path:
            try:
                char_font = ImageFont.truetype(font_path, char_size)
            except Exception:
                char_font = ImageFont.load_default()
        else:
            char_font = ImageFont.load_default()

        char_box_size = 52
        char_img = Image.new('RGBA', (char_box_size, char_box_size), (0, 0, 0, 0))
        char_draw = ImageDraw.Draw(char_img)
        char_color = (*random.choice(palette), 255)

        try:
            bbox = char_draw.textbbox((0, 0), char, font=char_font)
            cw, ch = bbox[2] - bbox[0], bbox[3] - bbox[1]
            cx = (char_box_size - cw) // 2
            cy = (char_box_size - ch) // 2
        except Exception:
            cx, cy = 10, 8

        # Subtle shadow / edge for anti-segmentation
        char_draw.text((cx + 1, cy + 1), char, font=char_font, fill=(5, 10, 25, 180))
        char_draw.text((cx, cy), char, font=char_font, fill=char_color)

        # Distort angle (-24° to +24°)
        angle = random.randint(-24, 24)
        rotated = char_img.rotate(angle, expand=False, resample=Image.BILINEAR)

        pos_x = int(8 + i * slot_width + random.randint(-3, 3))
        pos_y = int(2 + random.randint(-2, 4))
        text_layer.paste(rotated, (pos_x, pos_y), rotated)

    # Composite characters over background
    img = Image.alpha_composite(img, text_layer)
    draw = ImageDraw.Draw(img)

    # 5. Crossing strike-through security sine waves
    for _ in range(3):
        points = []
        phase = random.uniform(0, 2 * math.pi)
        freq = random.uniform(0.025, 0.05)
        amp = random.randint(6, 11)
        base_y = random.randint(14, height - 14)
        for x in range(0, width, 2):
            y = int(base_y + amp * math.sin(freq * x + phase))
            points.append((x, max(2, min(height - 2, y))))
        curve_color = (*random.choice(palette), random.randint(160, 220))
        draw.line(points, fill=curve_color, width=random.randint(1, 2))

    # 6. Anti-bot noise speckles & cross marks
    for _ in range(80):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        c = (*random.choice(palette), random.randint(120, 200))
        draw.point((x, y), fill=c)
        if random.random() < 0.2:
            draw.line([(max(0, x - 1), y), (min(width - 1, x + 1), y)], fill=c, width=1)

    final_img = img.convert('RGB')
    buf = io.BytesIO()
    final_img.save(buf, format='PNG')
    return buf.getvalue()



import gzip
from io import BytesIO
from flask import request

def optimize_response(response):
    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response
    else:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'

    accept_encoding = request.headers.get('Accept-Encoding', '')
    if (
        response.status_code < 200 or 
        response.status_code >= 300 or 
        'gzip' not in accept_encoding.lower() or 
        'Content-Length' in response.headers and int(response.headers['Content-Length']) < 500
    ):
        return response

    content_type = response.headers.get('Content-Type', '')
    if 'text' not in content_type and 'javascript' not in content_type and 'json' not in content_type:
        return response

    try:
        response.direct_passthrough = False
        data = response.get_data()
        
        gzip_buffer = BytesIO()
        with gzip.GzipFile(mode='wb', fileobj=gzip_buffer) as gzip_file:
            gzip_file.write(data)
            
        gzip_data = gzip_buffer.getvalue()
        
        response.set_data(gzip_data)
        response.headers['Content-Encoding'] = 'gzip'
        response.headers['Content-Length'] = len(gzip_data)
        response.headers['Vary'] = 'Accept-Encoding'
    except Exception as e:
        pass
        
    return response


# Helper function to get actual user ID from Flask-Login ID
