import os
import io
import re
import uuid
import base64
from io import BytesIO
from spherix.config import utcnow, allowed_file

UPLOAD_CACHE = {}

# Cloudinary permanent cloud storage
CLOUDINARY_AVAILABLE = False
_cld_uploader = None

try:
    import importlib
    _cld = importlib.import_module('cloudinary')
    _cld_uploader = importlib.import_module('cloudinary.uploader')
    
    cld_name = os.getenv('CLOUDINARY_CLOUD_NAME')
    cld_key = os.getenv('CLOUDINARY_API_KEY')
    cld_secret = os.getenv('CLOUDINARY_API_SECRET')
    
    if cld_name and cld_key and cld_secret:
        _cld.config(
            cloud_name=cld_name,
            api_key=cld_key,
            api_secret=cld_secret,
            secure=True
        )
        CLOUDINARY_AVAILABLE = True
except Exception:
    CLOUDINARY_AVAILABLE = False

def upload_to_cloudinary(file_bytes_or_stream, folder='spherixclinic/uploads', public_id=None):
    if not CLOUDINARY_AVAILABLE or not _cld_uploader:
        return None
    try:
        if isinstance(file_bytes_or_stream, (bytes, bytearray)):
            file_obj = io.BytesIO(file_bytes_or_stream)
        else:
            file_obj = file_bytes_or_stream

        options = {
            'folder': folder,
            'resource_type': 'auto',
            'overwrite': True,
        }
        if public_id:
            options['public_id'] = public_id

        res = _cld_uploader.upload(file_obj, **options)
        return res.get('secure_url') or res.get('url')
    except Exception as e:
        print(f"⚠️ Cloudinary upload warning: {e}")
        return None

def _write_bytes_safely(relative_dir, filename, data_bytes=None):
    if data_bytes is None:
        data_bytes = filename
        filename = relative_dir
        relative_dir = None
    if not isinstance(data_bytes, (bytes, bytearray)):
        return False
    success = False
    target_dirs = []

    # 1. Project root static/uploads
    cwd_static = os.path.join(os.getcwd(), 'static', 'uploads')
    target_dirs.append(os.path.join(cwd_static, relative_dir) if relative_dir else cwd_static)

    # 2. Flask app static_folder / uploads (if different)
    try:
        from flask import current_app
        if current_app and current_app.static_folder:
            app_static = os.path.join(current_app.static_folder, 'uploads')
            target_dirs.append(os.path.join(app_static, relative_dir) if relative_dir else app_static)
    except Exception:
        pass

    # 3. Dedicated spherix root static folder
    spherix_static = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'uploads')
    target_dirs.append(os.path.join(spherix_static, relative_dir) if relative_dir else spherix_static)

    for target_dir in target_dirs:
        try:
            os.makedirs(target_dir, exist_ok=True)
            file_path = os.path.join(target_dir, filename)
            with open(file_path, 'wb') as f:
                f.write(data_bytes)
            success = True
        except Exception:
            pass

    # Fallback to /tmp for serverless / lambda environments
    try:
        tmp_dir = os.path.join('/tmp', 'uploads', relative_dir) if relative_dir else os.path.join('/tmp', 'uploads')
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_file_path = os.path.join(tmp_dir, filename)
        with open(tmp_file_path, 'wb') as f:
            f.write(data_bytes)
        success = True
    except Exception:
        pass

    return success

def get_upload_bytes(key_or_filename):
    """Retrieves cached image bytes and MIME type from UPLOAD_CACHE."""
    if not key_or_filename:
        return None, None
    clean = str(key_or_filename).strip()
    base = os.path.basename(clean)
    if clean in UPLOAD_CACHE:
        return UPLOAD_CACHE[clean]
    if base in UPLOAD_CACHE:
        return UPLOAD_CACHE[base]
    return None, None


def save_user_profile_image(input_source, target_size=(500, 500), filename_prefix='user_profile', subfolder=None):
    """
    Standardized, high-fidelity profile image & logo processor with multi-tier storage.
    - Accepts Base64 data URL string or Werkzeug FileStorage / file object or raw bytes.
    - Auto-corrects EXIF orientation.
    - Crops/resizes with Lanczos filter to the fixed target_size (default 500x500 px).
    - Converts RGBA/P to RGB over white background (or preserves PNG if desired).
    - Caches in memory (UPLOAD_CACHE) for instant serving across ephemeral / serverless instances.
    - Safely writes to static/uploads or /tmp/uploads without crashing on read-only filesystems.
    - Returns saved filename.
    """
    if not input_source:
        return None

    try:
        from PIL import Image, ImageOps
    except ImportError:
        Image = None
        ImageOps = None

    raw_bytes = None
    is_png = False

    if isinstance(input_source, str):
        data_str = input_source.strip()
        if not data_str:
            return None
        if 'data:image' in data_str:
            try:
                header, encoded = data_str.split(',', 1)
                if 'png' in header.lower():
                    is_png = True
                raw_bytes = base64.b64decode(encoded)
            except Exception as e:
                print(f"Error decoding base64 image: {e}")
                return None
        else:
            try:
                raw_bytes = base64.b64decode(data_str)
            except Exception:
                return None
    elif hasattr(input_source, 'read'):
        filename = getattr(input_source, 'filename', '') or ''
        content_type = getattr(input_source, 'content_type', '') or ''
        if not filename and content_type == '':
            return None
        if filename.lower().endswith('.png') or 'png' in content_type.lower():
            is_png = True
        try:
            raw_bytes = input_source.read()
        except Exception as e:
            print(f"Error reading file stream: {e}")
            return None
    elif isinstance(input_source, (bytes, bytearray)):
        raw_bytes = bytes(input_source)
    else:
        return None

    if not raw_bytes or len(raw_bytes) == 0:
        return None

    timestamp = utcnow().strftime('%Y%m%d%H%M%S')
    unique_suffix = uuid.uuid4().hex[:8]
    ext = 'png' if is_png else 'jpg'
    safe_prefix = re.sub(r'[^a-zA-Z0-9_-]', '_', str(filename_prefix)) or 'profile'
    filename = f"{safe_prefix}_{timestamp}_{unique_suffix}.{ext}"
    rel_path = f"{subfolder}/{filename}" if subfolder else filename

    output_bytes = raw_bytes
    mimetype = 'image/png' if is_png else 'image/jpeg'

    if Image and ImageOps:
        try:
            bio = BytesIO(raw_bytes)
            img = Image.open(bio)

            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass

            target_w, target_h = target_size

            if not is_png:
                if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                    img = img.convert('RGBA')
                    bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
                    alpha_composite = Image.alpha_composite(bg, img)
                    img = alpha_composite.convert('RGB')
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
            else:
                if img.mode not in ('RGBA', 'RGB'):
                    img = img.convert('RGBA')

            img_w, img_h = img.size
            if img_w != target_w or img_h != target_h:
                try:
                    img = ImageOps.fit(img, (target_w, target_h), Image.Resampling.LANCZOS, centering=(0.5, 0.5))
                except AttributeError:
                    img = ImageOps.fit(img, (target_w, target_h), Image.LANCZOS, centering=(0.5, 0.5))

            out_bio = BytesIO()
            if is_png:
                img.save(out_bio, format='PNG', optimize=True)
                mimetype = 'image/png'
            else:
                img.save(out_bio, format='JPEG', quality=92, optimize=True)
                mimetype = 'image/jpeg'
            output_bytes = out_bio.getvalue()
        except Exception as img_err:
            print(f"PIL process image error in save_user_profile_image: {img_err}")
            output_bytes = raw_bytes

    UPLOAD_CACHE[filename] = (output_bytes, mimetype)
    UPLOAD_CACHE[rel_path] = (output_bytes, mimetype)

    _write_bytes_safely(subfolder, filename, output_bytes)

    cld_url = upload_to_cloudinary(output_bytes, folder=f"spherixclinic/{subfolder or 'profiles'}", public_id=filename.rsplit('.', 1)[0])
    if cld_url:
        UPLOAD_CACHE[cld_url] = (output_bytes, mimetype)
        return cld_url

    return rel_path