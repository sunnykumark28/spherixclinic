"""
Gunicorn configuration for Spherix Clinic deployment (Render, Heroku, Railway, Fly.io, VPS).
"""
import os

# Port binding: Render injects PORT environment variable (defaults to 10000 on Render)
port = os.getenv("PORT", "5001")
bind = f"0.0.0.0:{port}"

# Concurrency & Worker Model
# Single worker with multi-threading keeps Flask-SocketIO in-memory rooms and WebSockets in sync
workers = int(os.getenv("WEB_CONCURRENCY", "1"))
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", "8"))
worker_connections = 1000

# Timeouts & Keep-alive
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
keepalive = 5

# WSGI application target: allows bare 'gunicorn' command to work automatically
wsgi_app = "app:application"

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")
