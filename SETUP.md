# ResQNow - Emergency SOS System

## Quick Setup & Testing

### 1. Fix Tracking Prevention Errors
The "Tracking Prevention blocked access to storage" messages come from Edge browser when accessing the frontend and backend from different ports.

**Solution: Access the app through Flask on port 5000 (not Live Server on 5500)**

```
http://127.0.0.1:5000/dashboard.html
http://127.0.0.1:5000/register.html
http://127.0.0.1:5000/login.html
```

### 2. Configure Credentials (Optional)
If you want SMS/WhatsApp alerts, create a `.env` file in the `backend_python/` folder:

```bash
cd backend_python
cp ../.env.example .env
# Edit .env with your Twilio and Gmail credentials
```

**Without Twilio configured:**
- SMS/WhatsApp alerts will be skipped
- Email alerts will still work (if Gmail is configured)
- SOS button will still function successfully

### 3. Run the Backend

```bash
cd backend_python
python -m pip install -r requirements.txt
python app.py
```

The server will start at `http://127.0.0.1:5000/`

### 4. Test the System

1. **Register** a new user at `http://127.0.0.1:5000/register.html`
   - Add yourself and at least one emergency contact
   - Emergency contacts need phone numbers (for SMS/WhatsApp) and emails

2. **Login** at `http://127.0.0.1:5000/login.html`
   - Verify localStorage shows: `user_id`, `username`, `token`

3. **Test SOS**
   - Open Dashboard at `http://127.0.0.1:5000/dashboard.html`
   - Press the SOS button
   - Check Flask terminal for logs:
     ```
     ✅ SMS sent to +1234567890
     ✅ WhatsApp sent to +1234567890
     ✅ Email sent to contact@email.com
     ```

## Features

- **SMS Alerts** - via Twilio (optional)
- **WhatsApp Alerts** - via Twilio WhatsApp API (optional)
- **Email Alerts** - via Gmail SMTP
- **Real-time Location** - captured at SOS press
- **Emergency Contacts** - manage multiple contacts per user
- **Account Security** - bcrypt password hashing

## Alert Channels Status

When you press SOS, the system will:
- ✅ Always send **Email** (if Gmail configured)
- ✅ Send **SMS** & **WhatsApp** (if Twilio configured)
- ✅ Send **Confirmation email** to the user

Even if one channel fails, others will still attempt to send.

## Database Schema

Tables needed in `resqnow` database:
- `users` (id, name, email, mobile, password_hash)
- `emergency_contacts` (id, user_id, contact_name, contact_phone, contact_email)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Tracking Prevention blocked..." | Use `http://127.0.0.1:5000` not 5500 |
| SMS/WhatsApp not sending | Check .env has TWILIO credentials |
| Emails not sending | Check .env has EMAIL_USER and EMAIL_PASS |
| 500 error on register | Check MySQL connection in .env |
| No emergency contacts error | Register with at least one contact filled |

## WhatsApp Setup for Twilio

For WhatsApp alerts to work, you need:

### 1. Twilio Account & WhatsApp Number
- Sign up at https://www.twilio.com/
- Get your Account SID and Auth Token
- Get a Twilio phone number (required for Twilio)
- Enable WhatsApp on your Twilio number

### 2. WhatsApp Sandbox Setup (for testing)
- Go to Twilio Console > Messaging > Try it out > Send an SMS
- Or: Messaging > WhatsApp > Sandbox
- Send "join [sandbox-name]" from your phone's WhatsApp to the provided number
- Your number will be added to the approved list

### 3. Configure in .env
```
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE=+1234567890  # Your Twilio number
```

### 4. Emergency Contact Phone Numbers
When registering contacts, use phone numbers with country code:
- ✅ Correct: `+12125551234` or `+919876543210`
- ❌ Wrong: `2125551234` or `(212) 555-1234`

### 5. Test WhatsApp
- Check Flask terminal for: `✅ WhatsApp sent successfully to +xxxxx`
- If it fails, you'll see: `❌ WhatsApp error: [error message]`
- Common errors:
  - "Invalid 'To' number" = number not approved in WhatsApp sandbox
  - "Authentication failed" = wrong Account SID/Auth Token
  - "Service unavailable" = WhatsApp not enabled on your Twilio number

