"""
Spherix Clinic - WSGI Application Entrypoint
Provides compatibility for WSGI servers (Gunicorn, uWSGI, Waitress).
"""
from app import app, application

if __name__ == '__main__':
    app.run()
