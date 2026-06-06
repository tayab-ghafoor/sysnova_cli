# 🔐 Payment Configuration Variables for Railway

## Complete Environment Variables for Pro Subscription Payment System

### 1. **Encryption & Security**
```
ENCRYPTION_KEY=<Fernet encryption key - generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
ADMIN_API_KEY=<Strong secret for admin endpoints - generate with: python -c "import secrets; print(secrets.token_hex(32))">
```

### 2. **Pricing Configuration**
```
PRO_AMOUNT=9.99
PRO_CURRENCY=USD
PRO_AMOUNT_PKR=2800.0
```

### 3. **HBL Bank Transfer Details**
```
HBL_ACCOUNT_NAME=TAYAB GHAFOOR
HBL_ACCOUNT_NUMBER=<16-digit HBL account number>
```

### 4. **Easypaisa Transfer Details**
```
EASYPAISA_ACCOUNT_NAME=TAYAB GHAFOOR
EASYPAISA_ACCOUNT_NUMBER=<Phone number e.g., +923001234567>
```

### 5. **Admin Notification**
```
ADMIN_NOTIFICATION_EMAIL=<Admin email for payment proof submissions>
```

---

## 📋 Variable Reference Table

| Variable Name | Type | Required | Description | Example |
|---|---|---|---|---|
| `ENCRYPTION_KEY` | String (Fernet) | ✅ YES | Encryption key for payment receipts | `gAAAAABm...` |
| `ADMIN_API_KEY` | String (Hex) | ✅ YES | Authentication for admin endpoints | `a1b2c3d4...` |
| `PRO_AMOUNT` | Float | ✅ YES | Price in USD | `9.99` |
| `PRO_CURRENCY` | String (3-char) | ✅ YES | ISO 4217 currency code | `USD` |
| `PRO_AMOUNT_PKR` | Float | ✅ YES | Price in Pakistani Rupees | `2800.0` |
| `HBL_ACCOUNT_NAME` | String | ✅ YES | Account holder name (HBL) | `TAYAB GHAFOOR` |
| `HBL_ACCOUNT_NUMBER` | String (16 digit) | ✅ YES | HBL bank account | `1234567890123456` |
| `EASYPAISA_ACCOUNT_NAME` | String | ✅ YES | Account holder name (Easypaisa) | `TAYAB GHAFOOR` |
| `EASYPAISA_ACCOUNT_NUMBER` | String (Phone) | ✅ YES | Phone number for Easypaisa | `+923001234567` |
| `ADMIN_NOTIFICATION_EMAIL` | String (Email) | ✅ YES | Where payment proofs are sent | `admin@example.com` |

---

## 🔑 How to Generate Keys

### ENCRYPTION_KEY (Fernet)
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Output: `gAAAAABm7OZ5E7Z8_3x...` (starts with `gAAAAA`)

### ADMIN_API_KEY (Hex Token)
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
Output: `a1b2c3d4e5f6...` (64 character hex string)

---

## 🚀 Railway Setup Checklist

- [ ] Generate `ENCRYPTION_KEY` with Fernet
- [ ] Generate `ADMIN_API_KEY` with secrets.token_hex(32)
- [ ] Enter `HBL_ACCOUNT_NUMBER` (16 digits)
- [ ] Enter `EASYPAISA_ACCOUNT_NUMBER` (phone number with +92)
- [ ] Set `ADMIN_NOTIFICATION_EMAIL` to admin account
- [ ] Keep `PRO_AMOUNT_PKR` updated (currently 2800 PKR)
- [ ] Verify `PRO_CURRENCY` is correct (default USD)
- [ ] Ensure ENCRYPTION_KEY ≠ JWT_SECRET (security requirement)

---

## ⚠️ Important Notes

1. **Security**: ENCRYPTION_KEY must be different from JWT_SECRET
2. **Admin Access**: ADMIN_API_KEY must be passed in X-Admin-Key header for payment admin endpoints
3. **Pakistan Market**: PRO_AMOUNT_PKR is separate from PRO_AMOUNT for flexible pricing
4. **HBL Account**: Must be 16 digits exactly
5. **Easypaisa**: Should include country code (+92 for Pakistan)
6. **Production**: All fields except PRO_AMOUNT are required in production
