"""
Vercel Serverless Function Entrypoint for Spherix Clinic
Exposes the WSGI application instance for Vercel Python runtime.
"""
import os
import sys
import warnings

# Add project root directory to sys.path so spherix and sibling modules can be imported
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Flag runtime as serverless / vercel
os.environ['SERVERLESS'] = '1'
os.environ['VERCEL'] = '1'

# Suppress deprecation warnings in serverless logs
warnings.filterwarnings("ignore", category=FutureWarning, module="google")

# Import the main WSGI Flask application
from app import application

# Vercel entrypoint variable
app = application
handler = application
