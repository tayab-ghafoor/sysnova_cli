# Frontend Implementation Guide: Payment Flow with Receipt Upload

## Overview
The backend now sends clear guidance on what to do next. Your frontend should implement a **step-by-step payment wizard** that guides users from payment request → receipt upload → verification.

---

## 🎯 Backend Improvements Made

### 1. **Enhanced Response from `/pro/request`**
The endpoint now returns:
```json
{
  "reference_code": "PRO-CA4C01F76939",
  "payment_method": "hbl_bank_transfer",
  "bank_details": "Bank: HBL...",
  "amount": 9.99,
  "message": "To upgrade to Pro...",
  "next_step": "upload_proof",
  "next_step_description": "After transferring funds, upload your receipt and transaction ID",
  "upload_endpoint": "/api/v1/payment/pro/submit-proof",
  "required_fields": ["transaction_id", "payer_name", "screenshot"]
}
```

### 2. **New Endpoint: GET `/pro/proof-requirements`**
Returns what fields are needed before submission:
```json
{
  "reference_code": "PRO-CA4C01F76939",
  "payment_method": "hbl_bank_transfer",
  "fields_required": {
    "transaction_id": "Your bank/JazzCash/Easypaisa Transaction ID (10-16 digits)",
    "payer_name": "Full name of the person who sent the payment",
    "screenshot": "Clear screenshot of the transfer confirmation receipt...",
    "phone_number": "Phone number used for Easypaisa transfer" // only for Easypaisa
  },
  "instructions": [
    "Step 1: Log into your bank/JazzCash/Easypaisa app",
    "Step 2: Find your recent transfer...",
    "..."
  ]
}
```

### 3. **Enhanced Response from `/pro/submit-proof`**
Now returns clear status:
```json
{
  "message": "Payment proof submitted successfully!...",
  "reference_code": "PRO-CA4C01F76939",
  "status": "submitted",
  "next_action": "wait_for_admin_verification",
  "next_action_description": "Admin will verify your payment and activate Pro subscription.",
  "verification_window_hours": 24,
  "estimated_verification_time": "within 24 hours"
}
```

---

## 🛠️ Frontend Implementation Steps

### Step 1: Display Payment Details (After `/pro/request`)
```typescript
// After calling /pro/request
const response = await fetch('/api/v1/payment/pro/request?payment_method=hbl_bank_transfer');
const data = await response.json();

// Show payment details with bank account info
displayPaymentDetails({
  reference: data.reference_code,
  bankDetails: data.bank_details,
  amount: data.amount_pkr,
  message: data.message
});

// AUTO-SHOW: Upload form based on next_step
if (data.next_step === "upload_proof") {
  showUploadProofForm(data.reference_code);
}
```

### Step 2: Create a Multi-Part Form for Receipt Upload
The `/pro/submit-proof` endpoint requires **multipart/form-data**, NOT JSON.

```html
<form id="proofForm" enctype="multipart/form-data">
  <!-- Reference code (hidden) -->
  <input type="hidden" name="reference_code" value="PRO-CA4C01F76939">
  
  <!-- Transaction ID -->
  <div class="form-group">
    <label for="tid">Transaction ID (TID)*</label>
    <input 
      type="text" 
      id="tid" 
      name="transaction_id" 
      placeholder="Your 10-16 digit TID from bank/JazzCash/Easypaisa"
      minlength="3" 
      maxlength="100" 
      required
    >
    <small>Find this in your transfer confirmation receipt</small>
  </div>

  <!-- Payer Name -->
  <div class="form-group">
    <label for="payerName">Payer Full Name*</label>
    <input 
      type="text" 
      id="payerName" 
      name="payer_name" 
      placeholder="Your full name (account holder name)"
      minlength="1" 
      maxlength="200" 
      required
    >
  </div>

  <!-- Phone Number (for Easypaisa only) -->
  <div class="form-group" id="phoneGroup" style="display:none;">
    <label for="phone">Phone Number*</label>
    <input 
      type="tel" 
      id="phone" 
      name="phone_number" 
      placeholder="Phone number used for transfer"
      maxlength="20"
    >
  </div>

  <!-- Screenshot Upload -->
  <div class="form-group">
    <label for="screenshot">Receipt Screenshot*</label>
    <input 
      type="file" 
      id="screenshot" 
      name="screenshot" 
      accept="image/png,image/jpeg,image/webp"
      required
    >
    <small>
      Max 5MB. Accepted formats: PNG, JPG, WEBP.
      Must show: transaction amount, TID, and confirmation status
    </small>
  </div>

  <button type="submit" class="btn-primary">Submit Payment Proof</button>
</form>
```

### Step 3: Handle Multipart Form Submission
```typescript
async function submitProofForm(formElement) {
  // Create FormData from HTML form (handles multipart automatically)
  const formData = new FormData(formElement);
  
  try {
    const response = await fetch('/api/v1/payment/pro/submit-proof', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
        // DON'T set Content-Type - browser will set it with boundary
      },
      body: formData  // This is FormData, not JSON
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Submission failed');
    }

    const result = await response.json();
    
    // Show success and next steps
    showSuccessMessage({
      title: 'Payment Proof Submitted!',
      referenceCode: result.reference_code,
      message: result.message,
      nextAction: result.next_action_description,
      estimatedTime: result.estimated_verification_time
    });

    // Redirect to status page or show verification pending state
    setTimeout(() => {
      navigateTo('/payment/status?ref=' + result.reference_code);
    }, 3000);

  } catch (error) {
    showErrorMessage(error.message);
  }
}

formElement.addEventListener('submit', (e) => {
  e.preventDefault();
  submitProofForm(e.target);
});
```

### Step 4: Show Proof Requirements Before Upload
```typescript
async function displayProofRequirements() {
  try {
    const response = await fetch('/api/v1/payment/pro/proof-requirements', {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    const requirements = await response.json();
    
    // Display instructions
    showInstructions(requirements.instructions);
    
    // Enable phone field if Easypaisa
    if (requirements.payment_method === 'easypaisa_transfer') {
      document.getElementById('phoneGroup').style.display = 'block';
      document.querySelector('input[name="phone_number"]').required = true;
    }
    
  } catch (error) {
    console.error('Failed to get requirements:', error);
  }
}
```

### Step 5: Status Check After Submission
```typescript
async function checkPaymentStatus() {
  const response = await fetch('/api/v1/payment/pro/status', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  const status = await response.json();
  
  if (status.is_pro) {
    showMessage('🎉 Pro activated! Valid until: ' + status.pro_expiry);
  } else {
    showMessage('⏳ Waiting for admin verification...');
  }
}

// Poll every 5 seconds while on status page
const interval = setInterval(checkPaymentStatus, 5000);
```

---

## 📋 Complete User Flow (Frontend)

```
1. User clicks "Upgrade to Pro"
   ↓
2. Frontend calls: POST /pro/request?payment_method=hbl_bank_transfer
   ↓
3. Display payment details (bank account, TID, amount, reference code)
   ↓
4. AUTO-SHOW: Upload form (based on next_step = "upload_proof")
   ↓
5. Display step-by-step instructions from /pro/proof-requirements
   ↓
6. User fills form:
   - Transaction ID
   - Payer name
   - Phone number (if Easypaisa)
   - Screenshot file
   ↓
7. Frontend calls: POST /pro/submit-proof (as multipart/form-data)
   ↓
8. Show success: "Submitted! Reference: PRO-xxx. Wait 24 hours..."
   ↓
9. Show status checker (poll /pro/status every 5 seconds)
   ↓
10. Once admin approves → Show "Pro Activated!"
```

---

## ⚠️ Common Frontend Issues to Avoid

### ❌ **WRONG: Sending JSON instead of FormData**
```typescript
// WRONG - Will fail with image upload
const response = await fetch('/api/v1/payment/pro/submit-proof', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',  // ❌ WRONG
  },
  body: JSON.stringify({  // ❌ WRONG - can't send file as JSON
    transaction_id: "...",
    screenshot: fileObject  // File can't be serialized
  })
});
```

### ✅ **RIGHT: Using FormData**
```typescript
// RIGHT - Use FormData for multipart/form-data
const formData = new FormData();
formData.append('transaction_id', tidInput.value);
formData.append('payer_name', payerNameInput.value);
formData.append('screenshot', fileInput.files[0]);

const response = await fetch('/api/v1/payment/pro/submit-proof', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
    // Let browser set Content-Type with boundary
  },
  body: formData  // ✅ RIGHT
});
```

### ❌ **WRONG: Not handling next_step from response**
```typescript
// WRONG - Ignores backend guidance
const response = await fetch('/api/v1/payment/pro/request');
const data = await response.json();
displayPaymentInfo(data.message);  // Only shows message
// User doesn't know what to do next
```

### ✅ **RIGHT: Acting on next_step flag**
```typescript
// RIGHT - Follows backend guidance
const response = await fetch('/api/v1/payment/pro/request');
const data = await response.json();
displayPaymentInfo(data.message);

if (data.next_step === 'upload_proof') {
  showUploadForm();  // ✅ AUTO-SHOWS form
}
```

---

## 🔧 Example React Component

```jsx
import { useState } from 'react';

function PaymentUploadForm({ referenceCode, paymentMethod }) {
  const [formData, setFormData] = useState({
    transaction_id: '',
    payer_name: '',
    phone_number: '',
    screenshot: null
  });
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleFileChange = (e) => {
    setFormData({ ...formData, screenshot: e.target.files[0] });
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData({ ...formData, [name]: value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    const form = new FormData();
    form.append('transaction_id', formData.transaction_id);
    form.append('payer_name', formData.payer_name);
    if (paymentMethod === 'easypaisa_transfer') {
      form.append('phone_number', formData.phone_number);
    }
    form.append('screenshot', formData.screenshot);

    try {
      const res = await fetch('/api/v1/payment/pro/submit-proof', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: form
      });

      if (!res.ok) throw new Error('Upload failed');
      
      const result = await res.json();
      setSuccess(true);
      // Show result.message and result.next_action_description
    } catch (error) {
      alert('Error: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="success-box">
        <h3>✅ Payment Proof Submitted!</h3>
        <p>Reference: {referenceCode}</p>
        <p>Admin will verify within 24 hours.</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} encType="multipart/form-data">
      <input
        type="text"
        name="transaction_id"
        placeholder="Transaction ID (TID)"
        value={formData.transaction_id}
        onChange={handleInputChange}
        required
        minLength="3"
        maxLength="100"
      />
      
      <input
        type="text"
        name="payer_name"
        placeholder="Payer Full Name"
        value={formData.payer_name}
        onChange={handleInputChange}
        required
      />

      {paymentMethod === 'easypaisa_transfer' && (
        <input
          type="tel"
          name="phone_number"
          placeholder="Phone Number"
          value={formData.phone_number}
          onChange={handleInputChange}
        />
      )}

      <input
        type="file"
        name="screenshot"
        accept="image/*"
        onChange={handleFileChange}
        required
      />

      <button type="submit" disabled={loading}>
        {loading ? 'Uploading...' : 'Submit Payment Proof'}
      </button>
    </form>
  );
}

export default PaymentUploadForm;
```

---

## 📊 Backend Endpoints Summary

| Endpoint | Method | Purpose | Returns |
|----------|--------|---------|---------|
| `/pro/request` | POST | Request Pro upgrade with payment method | Payment details + next_step |
| `/pro/proof-requirements` | GET | Get required fields before upload | Fields, instructions |
| `/pro/submit-proof` | POST | Upload receipt + TID + payer name | Confirmation + next_action |
| `/pro/status` | GET | Check Pro status | is_pro, pro_expiry |

---

## 🎓 Summary

1. **Backend now signals what to do next** via `next_step` field
2. **Frontend should show upload form automatically** after payment request
3. **Use FormData for file upload**, NOT JSON
4. **Display step-by-step instructions** from `/pro/proof-requirements`
5. **Poll `/pro/status`** to show when Pro is activated
6. **Follow the flow diagram** to ensure users aren't lost

Your users will now have a **complete, intuitive payment experience** from request → upload → verification! 🚀
