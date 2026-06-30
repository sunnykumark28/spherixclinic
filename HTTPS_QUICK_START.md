# 🔐 HTTPS/SSL Security - Quick Start Guide

## ✅ What's Been Set Up

Your **Spherix Clinic Health Platform** is now **fully secured with HTTPS/SSL**.

### Current Status:
- 🔒 **Protocol:** HTTPS (TLS enabled)
- 🌐 **URL:** `https://127.0.0.1:5443`
- 📄 **Certificate:** Self-signed X.509 (365 days valid)
- 🔑 **Key Size:** 2048-bit RSA
- ✅ **Flask Integration:** Complete

---

## 🚀 Quick Start

### Start the Secure Server
```bash
cd /Users/sunnykushwaha/Projects/dev_ai_plus
python app.py
```

✨ **Output will show:**
```
🔒 SSL enabled - Using certificates:
   📄 Certificate: ssl/cert.pem
   🔑 Private Key: ssl/key.pem

🚀 Starting Spherix Clinic Health Platform
📍 HTTPS Server: https://127.0.0.1:5443
```

### Access the App
Open your browser and navigate to:
```
https://127.0.0.1:5443
```

⚠️ **Note:** You'll see a security warning because it's self-signed. Click "Advanced" → "Proceed" to continue.

---

## 📊 Files Created

| File | Purpose |
|------|---------|
| `ssl/cert.pem` | SSL Certificate (public) |
| `ssl/key.pem` | Private Key (secure) |
| `SSL_HTTPS_SETUP.md` | Detailed configuration guide |
| `verify_ssl.sh` | Verification script |
| `app.py` | Updated with HTTPS support |

---

## 🔑 Default Credentials

```
👨‍💼 Admin:
   Email: admin@spherixclinic.com
   Password: admin@123

🏥 Hospital:
   Email: hospital@spherixclinic.com
   Password: hospital123
```

---

## ⚙️ Configuration Options

Control the app via environment variables:

```bash
# Standard HTTPS on port 5443
python app.py

# Custom port
FLASK_PORT=8443 python app.py

# Disable SSL (HTTP mode - NOT SECURE)
USE_SSL=False python app.py

# Production mode (debug off)
FLASK_DEBUG=False python app.py

# Allow external connections (not for production)
FLASK_HOST=0.0.0.0 python app.py

# All together
FLASK_PORT=5443 FLASK_HOST=127.0.0.1 FLASK_DEBUG=False python app.py
```

---

## 🧪 Verify HTTPS is Working

### Test 1: Command Line
```bash
curl -k https://127.0.0.1:5443
```

If you see HTML output, HTTPS is working! ✅

### Test 2: Check Certificate
```bash
openssl s_client -connect 127.0.0.1:5443
```
Press `Ctrl+C` to exit.

### Test 3: Show Certificate Details
```bash
openssl x509 -in ssl/cert.pem -text -noout
```

### Test 4: Python Test
```python
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
resp = requests.get('https://127.0.0.1:5443', verify=False)
print(f"Status: {resp.status_code}")  # Should print: Status: 200
```

---

## 🛡️ Security Features

✅ **TLS 1.2+** - Latest encryption protocol  
✅ **RSA 2048-bit** - Strong encryption keys  
✅ **Self-Signed Certs** - Good for development/testing  
✅ **Secure File Perms** - Private key protected (600)  
✅ **Certificate Validation** - Key-pair verified  
✅ **No HTTP** - Default runs on HTTPS only  
✅ **Environment Support** - Flexible configuration  

---

## 🔄 Browser Access

### Chrome/Edge Warning
You'll see this screen:
```
Your connection isn't private
Attackers might be trying to steal your information...
```

**Solution:**
1. Click **"Advanced"**
2. Click **"Proceed to 127.0.0.1 (unsafe)"**
3. Or use the keyboard shortcut: Type `thisisunsafe`

### Firefox
1. Click **"Advanced"**
2. Click **"Accept the Risk and Continue"**

### Safari
1. Click **"Show Details"**
2. Click **"Visit Website"**

---

## 📚 Key Routes Available

| Route | Purpose |
|-------|---------|
| `/` | Home page |
| `/check` | AI Symptom Diagnosis |
| `/check-symptoms` | Symptom checker form |
| `/doctors` | Doctor directory |
| `/hospitals` | Hospital listing |
| `/book_appointment` | Book appointment |
| `/doctor/login` | Doctor portal |
| `/patient/dashboard` | Patient dashboard |
| `/drugs` | Medication database |
| `/conditions` | Medical conditions |
| `/gallery` | Gallery & videos |
| `/about` | About us |

---

## 🚨 Troubleshooting

### Port Already in Use
```bash
# Kill process on port 5443
lsof -i :5443 | grep -v COMMAND | awk '{print $2}' | xargs kill -9
```

### Certificate Not Found
```bash
# Regenerate certificates
openssl req -x509 -newkey rsa:2048 -nodes -out ssl/cert.pem -keyout ssl/key.pem -days 365 -subj "/C=US/ST=California/L=Local/O=Spherix Clinic/CN=localhost"
```

### Connection Refused
```bash
# Make sure app is running
ps aux | grep python
```

### SSL Timeout
- Restart the app
- Check for Python errors in terminal
- Verify certificate files exist: `ls -la ssl/`

---

## 🆚 HTTP vs HTTPS Comparison

| Feature | HTTP | HTTPS (Current) |
|---------|------|-----------------|
| **Encryption** | ❌ None | ✅ TLS 1.2+ |
| **Data Privacy** | ❌ Plain text | ✅ Encrypted |
| **Browser Trust** | ❌ Not trusted | ⚠️ Self-signed |
| **Performance** | ✅ Faster | ~1% slower |
| **Production Ready** | ❌ No | ✅ Almost |
| **Developer** | ✅ Yes | ✅ Yes |

---

## 🎯 Next Steps

1. **Test locally**: Access `https://127.0.0.1:5443` in your browser
2. **Run automated tests**: Use `verify_ssl.sh` to check configuration
3. **For production**: Follow recommendations in `SSL_HTTPS_SETUP.md`
4. **Get proper certificates**: Use Let's Encrypt or commercial CA

---

## 📞 Quick Reference

```bash
# Start HTTPS server
python app.py

# View certificate
openssl x509 -in ssl/cert.pem -text -noout

# Check if running
curl -k https://127.0.0.1:5443

# Verify SSL config
bash verify_ssl.sh

# Stop server (from app terminal)
Ctrl+C
```

---

## 📋 Certificate Info

- **Generated:** April 9, 2026
- **Expires:** April 9, 2027  
- **Organization:** Spherix Clinic Health
- **Country:** US
- **Hosts:** localhost, 127.0.0.1

---

**🎉 Your application is now secure with HTTPS/SSL!**

For detailed documentation, see: `SSL_HTTPS_SETUP.md`
