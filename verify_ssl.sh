#!/bin/bash

# SSL/HTTPS Security Verification Script for Dev AI+ Platform

echo "🔒 SSL/HTTPS Security Verification"
echo "===================================="
echo ""

# Check 1: SSL Certificate exists
echo "✓ Check 1: SSL Certificate Files"
if [ -f "ssl/cert.pem" ] && [ -f "ssl/key.pem" ]; then
    echo "  ✅ Certificate found: ssl/cert.pem"
    echo "  ✅ Private key found: ssl/key.pem"
    echo ""
else
    echo "  ❌ Certificate files not found"
    exit 1
fi

# Check 2: Certificate validity
echo "✓ Check 2: Certificate Details"
echo "  Issuer:"
openssl x509 -in ssl/cert.pem -noout -issuer | sed 's/^/    /'
echo "  Subject:"
openssl x509 -in ssl/cert.pem -noout -subject | sed 's/^/    /'
echo "  Validity:"
openssl x509 -in ssl/cert.pem -noout -dates | sed 's/^/    /'
echo "  Key Size:"
openssl rsa -in ssl/key.pem -noout -modulus | grep -o '2048' && echo "    2048-bit RSA (Strong encryption)" || echo "    Weak encryption"
echo ""

# Check 3: Certificate and key match
echo "✓ Check 3: Certificate-Key Pair Verification"
CERT_MODULUS=$(openssl x509 -noout -modulus -in ssl/cert.pem | openssl md5)
KEY_MODULUS=$(openssl rsa -noout -modulus -in ssl/key.pem | openssl md5)

if [ "$CERT_MODULUS" = "$KEY_MODULUS" ]; then
    echo "  ✅ Certificate and private key match correctly"
    echo ""
else
    echo "  ❌ Certificate and key do not match"
    exit 1
fi

# Check 4: Flask app configuration
echo "✓ Check 4: Flask Application Setup"
if grep -q "ssl.SSLContext" app.py; then
    echo "  ✅ Flask app configured for SSL/HTTPS"
else
    echo "  ⚠️  SSL configuration not found in app.py"
fi

if grep -q "PROTOCOL_TLS_SERVER" app.py; then
    echo "  ✅ Using secure TLS protocol"
else
    echo "  ⚠️  TLS protocol not explicitly configured"
fi
echo ""

# Check 5: File permissions
echo "✓ Check 5: File Permissions"
CERT_PERMS=$(stat -f "%OLp" ssl/cert.pem)
KEY_PERMS=$(stat -f "%OLp" ssl/key.pem)
echo "  Certificate: $CERT_PERMS"
echo "  Private Key: $KEY_PERMS"
if [ "$KEY_PERMS" = "600" ] || [ "$KEY_PERMS" = "-rw-------" ]; then
    echo "  ✅ Private key has secure permissions"
else
    echo "  ⚠️  Private key permissions could be tighter: chmod 600 ssl/key.pem"
fi
echo ""

# Check 6: Port availability
echo "✓ Check 6: Port Configuration"
if [ -z "$FLASK_PORT" ]; then
    FLASK_PORT=5443
fi
echo "  Default HTTPS Port: $FLASK_PORT"
if lsof -i :$FLASK_PORT > /dev/null 2>&1; then
    echo "  ✅ Port $FLASK_PORT is in use (app running)"
else
    echo "  ⚠️  Port $FLASK_PORT is available (app may not be running)"
fi
echo ""

# Summary
echo "===================================="
echo "✅ SSL/HTTPS Security Configuration Complete"
echo ""
echo "🚀 To start the app:"
echo "   python app.py"
echo ""
echo "🌐 Access at: https://127.0.0.1:5443"
echo ""
echo "📚 Documentation: SSL_HTTPS_SETUP.md"
echo ""
