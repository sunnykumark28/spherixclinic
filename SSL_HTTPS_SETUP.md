# 🔒 SSL/HTTPS Security Setup - Dev AI+ Health Platform

## ✅ Current Status

Your Dev AI+ application is now **secured with HTTPS/SSL** on **`https://127.0.0.1:5443`**

### Certificates Generated
- **Certificate:** `ssl/cert.pem` (Valid for 365 days)
- **Private Key:** `ssl/key.pem`
- **Generated:** April 9, 2026
- **Type:** Self-signed X.509 SSL certificate

---

## 🚀 Running the Secured Application

### Start with HTTPS Enabled (Default)
```bash
cd /Users/sunnykushwaha/Projects/dev_ai_plus
python app.py
```

**Output:**
```
🔒 SSL enabled - Using certificates:
   📄 Certificate: ssl/cert.pem
   🔑 Private Key: ssl/key.pem

📍 HTTPS Server: https://127.0.0.1:5443
```

### Command-Line Configuration

You can control HTTPS behavior with environment variables:

```bash
# Change port
FLASK_PORT=8443 python app.py

# Change host (allow external connections - NOT recommended for production)
FLASK_HOST=0.0.0.0 FLASK_PORT=5443 python app.py

# Disable SSL (run on HTTP - not secure)
USE_SSL=False FLASK_PORT=5000 python app.py

# Custom certificate paths
SSL_CERT_PATH=/path/to/cert.pem SSL_KEY_PATH=/path/to/key.pem python app.py

# Disable debug mode for production-like testing
FLASK_DEBUG=False FLASK_PORT=5443 python app.py
```

---

## 🌐 Access URLs

| Environment | URL | Certificate |
|---|---|---|
| **Development (Current)** | `https://127.0.0.1:5443` | Self-signed (warning in browser) |
| **HTTP (Insecure)** | `http://127.0.0.1:5000` | None |

### Browser SSL Warning
⚠️ **Expected:** Your browser will show a security warning because the certificate is self-signed.

**To bypass in Chrome/Edge:**
1. Click "Advanced"
2. Click "Proceed to 127.0.0.1 (unsafe)"

**For curl/command-line:**
```bash
curl -k https://127.0.0.1:5443  # -k ignores certificate verification
```

---

## 📋 Default Login Credentials

```
Admin:
  Email: admin@devai.plus
  Password: admin@123

Hospital:
  Email: hospital@devai.plus
  Password: hospital123
```

---

## 🔑 Certificate Details

View certificate information:
```bash
# Inspect certificate
openssl x509 -in ssl/cert.pem -text -noout

# Check certificate expiration
openssl x509 -in ssl/cert.pem -noout -dates

# Verify certificate and key match
openssl x509 -noout -modulus -in ssl/cert.pem | openssl md5
openssl rsa -noout -modulus -in ssl/key.pem | openssl md5
```

---

## 🛡️ Security Features Implemented

✅ **HTTPS/TLS Encryption** - All data transmitted over encrypted channel  
✅ **SSL Context Configuration** - Proper TLS protocol setup  
✅ **Self-Signed Certificates** - For development/testing  
✅ **Environment Variable Support** - Flexible configuration  
✅ **Error Handling** - Graceful fallback if SSL fails  
✅ **Port 5443** - Standard HTTPS port  

---

## 📊 Production Security Recommendations

### For Production Deployment:

1. **Use Proper SSL Certificates** (Not Self-Signed)
   ```bash
   # Option 1: Let's Encrypt (FREE)
   certbot certonly --standalone -d yourdomain.com
   
   # Option 2: Purchase from CA
   # Comodo, DigiCert, GoDaddy, etc.
   ```

2. **Update app.py**
   ```python
   SSL_CERT_PATH='/etc/letsencrypt/live/yourdomain.com/fullchain.pem'
   SSL_KEY_PATH='/etc/letsencrypt/live/yourdomain.com/privkey.pem'
   ```

3. **Use Production WSGI Server**
   ```bash
   # Option 1: Gunicorn with SSL
   gunicorn --certfile ssl/cert.pem --keyfile ssl/key.pem --bind 0.0.0.0:5443 app:app
   
   # Option 2: nginx as reverse proxy (recommended)
   # Forward traffic to Flask on internal port
   # nginx handles SSL externally
   ```

4. **Enable Security Headers** (Add to app.py)
   ```python
   @app.after_request
   def set_security_headers(response):
       response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
       response.headers['X-Content-Type-Options'] = 'nosniff'
       response.headers['X-Frame-Options'] = 'DENY'
       response.headers['X-XSS-Protection'] = '1; mode=block'
       return response
   ```

5. **Configure Firewall**
   ```bash
   # macOS - Block unnecessary ports
   sudo pfctl -ef /etc/pf.conf
   ```

6. **Auto-Renew Certificates** (Let's Encrypt)
   ```bash
   # Set up cron job
   certbot renew --quiet
   ```

---

## 🔍 Verify HTTPS is Working

### Test 1: curl with certificate verification disabled
```bash
curl -k https://127.0.0.1:5443
```

### Test 2: Check SSL protocol
```bash
openssl s_client -connect 127.0.0.1:5443
# Press Ctrl+C to exit
```

### Test 3: Check certificate chain
```bash
curl -I -k https://127.0.0.1:5443
# Look for HTTP/2 or HTTP/1.1 response
```

### Test 4: Test from Python
```python
import requests
from urllib3.exceptions import InsecureRequestWarning

# Suppress warnings for self-signed cert
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

response = requests.get('https://127.0.0.1:5443', verify=False)
print(response.status_code)  # Should be 200
```

---

## 🔗 SSL File Structure

```
dev_ai_plus/
├── app.py                 # Main Flask app (HTTPS enabled)
├── ssl/
│   ├── cert.pem          # SSL Certificate
│   └── key.pem           # Private Key
├── SSL_HTTPS_SETUP.md    # This file
└── ...
```

---

## ⚙️ Troubleshooting

### Issue: "Port already in use"
```bash
# Find process using port
lsof -i :5443

# Kill process
kill -9 <PID>
```

### Issue: "Certificate verification failed"
```bash
# Use -k flag with curl
curl -k https://127.0.0.1:5443

# Or disable SSL verification in code
requests.get('https://127.0.0.1:5443', verify=False)
```

### Issue: "Connection refused"
```bash
# Check if app is running
ps aux | grep python

# Start app manually
python app.py
```

### Issue: "SSL connection timeout"
```bash
# Restart app with debug output
FLASK_DEBUG=True python app.py

# Check logs for certificate loading errors
# Look at stdout/stderr output
```

---

## 📚 Environment Variables Reference

| Variable | Default | Example | Description |
|---|---|---|---|
| `FLASK_PORT` | 5001 | 5443 | Port to run on |
| `FLASK_HOST` | 127.0.0.1 | 0.0.0.0 | Host to bind to |
| `USE_SSL` | True | False | Enable/disable SSL |
| `FLASK_DEBUG` | True | False | Debug mode |
| `SSL_CERT_PATH` | ssl/cert.pem | /path/to/cert | Certificate path |
| `SSL_KEY_PATH` | ssl/key.pem | /path/to/key | Private key path |

---

## 🎯 Next Steps

1. ✅ **Development:** Use current setup (https://127.0.0.1:5443)
2. 🔄 **Testing:** Run integration tests with HTTPS
3. 📜 **QA:** Get SSL certificates validated
4. 🚀 **Production:** Implement recommendations above
5. 🔐 **Monitoring:** Set up SSL certificate expiration alerts

---

## 📞 Support

For issues or questions:
- Check application logs: `/tmp/flask_https.log`
- Review this documentation
- Check Flask/Werkzeug error messages in terminal

---

**Last Updated:** April 9, 2026  
**Certificate Expiration:** April 9, 2027
