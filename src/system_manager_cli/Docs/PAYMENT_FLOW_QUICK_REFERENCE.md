# Quick Reference: Payment Flow Integration

## 🚀 Quick Start for Frontend Developers

### The Problem Was
Users were told "submit your TID, payer name, and screenshot" but the app didn't actually ask for it. The backend had the endpoint but no guidance.

### The Solution
Backend now tells frontend **exactly** what to do next. Frontend just needs to listen and act.

---

## 📱 Three Main Steps for Frontend

### Step 1: After Getting Payment Details
```typescript
const response = await fetch('/api/v1/payment/pro/request?payment_method=hbl_bank_transfer');
const data = await response.json();

// Show payment info
showBankDetails(data.bank_details, data.amount_pkr);

// ✅ NEW: Listen to next_step and show upload form
if (data.next_step === 'upload_proof') {
  showUploadForm(data.reference_code, data.payment_method);
}
```

### Step 2: Get Upload Instructions
```typescript
const response = await fetch('/api/v1/payment/pro/proof-requirements');
const requirements = await response.json();

// Display step-by-step instructions to user
showInstructions(requirements.instructions);

// Show required fields based on payment method
renderForm(requirements.fields_required);
```

### Step 3: Submit Receipt (Use FormData, NOT JSON!)
```typescript
const formData = new FormData();
formData.append('transaction_id', '1234567890');
formData.append('payer_name', 'John Doe');
formData.append('screenshot', fileInput.files[0]);

const response = await fetch('/api/v1/payment/pro/submit-proof', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
    // ✅ DON'T set Content-Type - let browser handle it
  },
  body: formData  // ✅ FormData, not JSON
});

const result = await response.json();
// result.status = "submitted"
// result.next_action = "wait_for_admin_verification"
// Poll /pro/status to show when activated
```

---

## ⚡ Key API Changes

### `/pro/request` - Now Returns
```javascript
{
  // ... existing fields ...
  next_step: "upload_proof",                    // ← NEW: tells frontend what to do
  next_step_description: "...",                 // ← NEW: user-friendly explanation
  upload_endpoint: "/api/v1/payment/pro/submit-proof",  // ← NEW: where to send file
  required_fields: ["transaction_id", "payer_name", "screenshot"]  // ← NEW: what to ask for
}
```

### `/pro/proof-requirements` - NEW Endpoint
Returns instructions and field requirements:
```javascript
{
  reference_code: "PRO-xxx",
  payment_method: "hbl_bank_transfer",
  fields_required: {
    "transaction_id": "Your bank Transaction ID...",
    "payer_name": "Full name...",
    "screenshot": "Receipt screenshot..."
  },
  instructions: [
    "Step 1: Log into your bank app",
    "Step 2: Find your transfer",
    // ...
  ]
}
```

### `/pro/submit-proof` - Enhanced Response
```javascript
{
  message: "Payment proof submitted successfully!",
  reference_code: "PRO-xxx",
  status: "submitted",                    // ← NEW: clear status
  next_action: "wait_for_admin_verification",  // ← NEW: what's happening now
  next_action_description: "Admin will verify...",  // ← NEW: explanation
  verification_window_hours: 24,          // ← NEW: ETA
  estimated_verification_time: "within 24 hours"  // ← NEW: user-friendly ETA
}
```

---

## 🎨 UI Flow Recommendation

```
┌─────────────────────────────────────────┐
│  User clicks "Upgrade to Pro"            │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Step 1: Payment Method Selection        │
│ Call: POST /pro/request                 │
│ Display: Bank details + Amount          │
│ Reference: PRO-xxx                      │
│ [Show bank account info in box]         │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Step 2: Upload Receipt (AUTO-SHOW)      │
│ Call: GET /pro/proof-requirements       │
│ Display: Step-by-step instructions      │
│ [Show checklist]                        │
│ - Log into bank app                     │
│ - Transfer amount                       │
│ - Take screenshot                       │
│ - Fill form                             │
│ [Show form with fields]                 │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│ Step 3: Verification Pending            │
│ Call: POST /pro/submit-proof            │
│ Display: Confirmation + Timeline        │
│ "Your proof is submitted!               │
│  Admin will verify within 24 hours.     │
│  We'll send you an email when ready." │
│ [Show polling status]                   │
└──────────────┬──────────────────────────┘
               │
               ▼
        Every 5 seconds:
        Call: GET /pro/status
               │
       ┌───────┴────────┐
       │                │
       ▼                ▼
    Active        Not Active Yet
    [Show]        [Show countdown]
    "✅ Pro
     Active!"
```

---

## 🐛 Common Mistakes to Avoid

### ❌ Using JSON for File Upload
```javascript
// WRONG - Backend expects multipart/form-data
fetch('/api/v1/payment/pro/submit-proof', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },  // ❌ WRONG
  body: JSON.stringify({
    transaction_id: '123',
    screenshot: file  // ❌ Can't serialize File
  })
});
```

### ✅ Using FormData
```javascript
// RIGHT - Automatically sends multipart/form-data
const form = new FormData();
form.append('transaction_id', '123');
form.append('screenshot', file);  // ✅ FormData handles File

fetch('/api/v1/payment/pro/submit-proof', {
  method: 'POST',
  body: form,  // ✅ FormData
  headers: {
    'Authorization': `Bearer ${token}`
    // Don't set Content-Type - browser will add boundary
  }
});
```

### ❌ Ignoring next_step
```javascript
// WRONG - Doesn't follow backend guidance
const data = await fetch('/pro/request').then(r => r.json());
showMessage(data.message);  // Just shows message
// User doesn't know what to do next
```

### ✅ Acting on next_step
```javascript
// RIGHT - Follows backend guidance
const data = await fetch('/pro/request').then(r => r.json());
if (data.next_step === 'upload_proof') {
  showUploadForm();  // ✅ Auto-shows form
}
```

---

## 📊 Response Checklist

After each API call, check these new fields:

### After `/pro/request`
- [ ] Display `bank_details` or `easypaisa_details`
- [ ] Check `next_step` field
- [ ] If `next_step === "upload_proof"`, show upload form
- [ ] Store `reference_code` for later use

### Before `/pro/submit-proof`
- [ ] Call `/pro/proof-requirements` to get instructions
- [ ] Show `instructions` array as step-by-step checklist
- [ ] For Easypaisa: Show `phone_number` field

### After `/pro/submit-proof`
- [ ] Show `next_action_description` to user
- [ ] Display `estimated_verification_time`
- [ ] Start polling `/pro/status` every 5 seconds
- [ ] Update UI when `is_pro: true`

---

## 🔗 API Endpoints Reference

| Endpoint | Method | When to Call | Returns |
|----------|--------|--------------|---------|
| `/pro/request` | POST | User clicks "Upgrade" | Payment details + **next_step** |
| `/pro/proof-requirements` | GET | Before showing upload form | Instructions + fields |
| `/pro/submit-proof` | POST | User submits form | Confirmation + **next_action** |
| `/pro/status` | GET | Every 5 seconds (polling) | is_pro + expiry |

---

## 💾 Code Example (Vanilla JS)

```javascript
// Step 1: Request upgrade
async function startProUpgrade() {
  const res = await fetch('/api/v1/payment/pro/request?payment_method=hbl_bank_transfer');
  const data = await res.json();
  
  displayPaymentDetails(data);
  
  // ✅ AUTO-SHOW upload form if next_step indicates it
  if (data.next_step === 'upload_proof') {
    showUploadSection(data.reference_code, data.payment_method);
  }
}

// Step 2: Get upload requirements
async function showUploadSection(refCode, method) {
  const res = await fetch('/api/v1/payment/pro/proof-requirements');
  const requirements = await res.json();
  
  renderInstructions(requirements.instructions);
  renderForm(requirements.fields_required, method);
}

// Step 3: Handle form submission
document.getElementById('proofForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  
  const formData = new FormData(e.target);
  const res = await fetch('/api/v1/payment/pro/submit-proof', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
    body: formData
  });
  
  const result = await res.json();
  showSuccessMessage(result.next_action_description);
  
  // Step 4: Poll status
  const interval = setInterval(async () => {
    const status = await fetch('/api/v1/payment/pro/status')
      .then(r => r.json());
    
    if (status.is_pro) {
      clearInterval(interval);
      showProActivated();
    }
  }, 5000);
});
```

---

## 🎓 Testing the Flow

```bash
# 1. Request upgrade (use your token)
curl -X POST "http://localhost:8000/api/v1/payment/pro/request?payment_method=hbl_bank_transfer" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Expected: See next_step, upload_endpoint, required_fields

# 2. Get requirements
curl "http://localhost:8000/api/v1/payment/pro/proof-requirements" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Expected: See instructions and fields_required

# 3. Submit proof (requires multipart form)
curl -X POST "http://localhost:8000/api/v1/payment/pro/submit-proof" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "transaction_id=1234567890" \
  -F "payer_name=John Doe" \
  -F "screenshot=@/path/to/receipt.png"

# Expected: See status="submitted" and next_action
```

---

## 📞 Support

**Backend Changes Made:**
- ✅ Enhanced response schemas with guidance fields
- ✅ New `/pro/proof-requirements` endpoint
- ✅ Updated response messages

**Frontend Should:**
1. Listen to `next_step` field and show UI accordingly
2. Call `/pro/proof-requirements` to get instructions
3. Use FormData (not JSON) for file submission
4. Display `next_action` feedback after submission
5. Poll `/pro/status` to show Pro activation

**Result:** Complete, intuitive payment flow! 🎉
