# 🚀 Railway Environment Variables - Payment Configuration

**Copy-paste these exact variable names into Railway Dashboard**

---

## 🔑 Required Environment Variables

### Core Encryption & Security (MUST GENERATE)
```env
ENCRYPTION_KEY=gAAAAABm...generate-with-fernet...
ADMIN_API_KEY=a1b2c3d4...generate-with-secrets...
```

### Pricing
```env
PRO_AMOUNT=9.99
PRO_CURRENCY=USD
PRO_AMOUNT_PKR=2800.0
```

### Bank Transfer (HBL)
```env
HBL_ACCOUNT_NAME=TAYAB GHAFOOR
HBL_ACCOUNT_NUMBER=1234567890123456
```

### Mobile Transfer (Easypaisa)
```env
EASYPAISA_ACCOUNT_NAME=TAYAB GHAFOOR
EASYPAISA_ACCOUNT_NUMBER=+923001234567
```

### Admin Notifications
```env
ADMIN_NOTIFICATION_EMAIL=admin@yourdomain.com
```

---

## 📝 Quick Variable Checklist

| Variable | Status | Notes |
|----------|--------|-------|
| `ENCRYPTION_KEY` | 🔴 GENERATE | Fernet key - 44 chars starting with `gAAAAA` |
| `ADMIN_API_KEY` | 🔴 GENERATE | 64-char hex - use `secrets.token_hex(32)` |
| `PRO_AMOUNT` | ✅ USE | `9.99` (default) or update as needed |
| `PRO_CURRENCY` | ✅ USE | `USD` (default) or ISO code |
| `PRO_AMOUNT_PKR` | ✅ USE | `2800.0` (Pakistani Rupees) |
| `HBL_ACCOUNT_NAME` | ✅ UPDATE | `TAYAB GHAFOOR` (or actual name) |
| `HBL_ACCOUNT_NUMBER` | 🔴 ENTER | 16-digit HBL account number |
| `EASYPAISA_ACCOUNT_NAME` | ✅ UPDATE | `TAYAB GHAFOOR` (or actual name) |
| `EASYPAISA_ACCOUNT_NUMBER` | 🔴 ENTER | Phone number: `+92...` format |
| `ADMIN_NOTIFICATION_EMAIL` | 🔴 ENTER | Where payment proofs go |

---

## 🔧 How to Generate Missing Values

### 1️⃣ Generate ENCRYPTION_KEY (Fernet)
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
**Example output:**
```
gAAAAABm7OZ5E7Z8_3x9vL2wK9pQrZfHsJ5mN4dXvW3yU6bF0gH1jI2kL3mO4pQ5rS6tT7uV8wX9yZ0aB1cD2eE3fF4gG5hH6iI7jJ8kK9lL0mM1nN2oO3pP4qQ5rR6sS7tT8uV9wX0yZ1aB2cD3eE4fF=
```

### 2️⃣ Generate ADMIN_API_KEY (Hex Token)
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
**Example output:**
```
a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0
```

---

## 📱 Examples

### HBL Account Number
✅ CORRECT: `1234567890123456` (16 digits)  
❌ WRONG: `12345678901234` (14 digits)  
❌ WRONG: `1234-5678-9012-3456` (with dashes)  

### Easypaisa Phone Number
✅ CORRECT: `+923001234567` (with +92 country code)  
❌ WRONG: `03001234567` (without country code)  
❌ WRONG: `3001234567` (incomplete)  

---

## ⚙️ Railway Setup Steps

1. Go to Railway Dashboard → Your Project → Variables
2. Add all variables from the list above
3. For 🔴 GENERATE items, use the provided commands
4. For ✅ USE items, copy the defaults (update if needed)
5. For 🔴 ENTER items, put your actual values
6. Save & Redeploy

---

## ✅ Verification Checklist

After setting up on Railway, verify:

- [ ] All 10 variables are set (no empty strings)
- [ ] ENCRYPTION_KEY starts with `gAAAAA`
- [ ] ADMIN_API_KEY is 64 chars (hex digits only)
- [ ] HBL_ACCOUNT_NUMBER is exactly 16 digits
- [ ] EASYPAISA_ACCOUNT_NUMBER starts with `+92`
- [ ] ADMIN_NOTIFICATION_EMAIL is valid email format
- [ ] ENCRYPTION_KEY ≠ JWT_SECRET (different values)

---

## 🔐 Security Notes

⚠️ **NEVER** share these values in commits or public channels  
⚠️ ENCRYPTION_KEY and JWT_SECRET **MUST** be different  
⚠️ Rotate ADMIN_API_KEY periodically in production  
⚠️ Use Railway's secret variable feature (not plain text)  

---

## 📞 Payment Methods Supported

| Method | Variable | Format |
|--------|----------|--------|
| HBL Bank | HBL_ACCOUNT_NUMBER | 16-digit account |
| Easypaisa | EASYPAISA_ACCOUNT_NUMBER | +92 phone number |

Both are required for the payment system to work.

---

## 🆘 Troubleshooting

**Error: "ENCRYPTION_KEY must be different from JWT_SECRET"**
→ Generate a new ENCRYPTION_KEY (don't copy JWT_SECRET)

**Error: "ADMIN_API_KEY must be set in production"**
→ Generate ADMIN_API_KEY and add it to Railway variables

**Error: Payment endpoint returns 403**
→ Check that ADMIN_API_KEY is correct and X-Admin-Key header is set

---

## 📚 Related Files

- Database Migration: `alembic/versions/add_payment_audit_and_email_retry.py`
- Config Source: `config.py`
- Payment Routes: `routers/payment.py`
- Migration Guide: `DATABASE_MIGRATION_SUMMARY.md`
