from flask import Flask, request, jsonify, send_from_directory
import mysql.connector
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sys

db = mysql.connector.connect(
    host="localhost",
    user="root",          # your mysql username
    password="root",      # your mysql password
    database="resqnow"     # database name
)

cursor = db.cursor(dictionary=True)

from flask_bcrypt import Bcrypt
from flask_cors import CORS
from twilio.rest import Client
from dotenv import load_dotenv
import os

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)
print(f"Loading .env from: {env_path}")

app = Flask(__name__, static_folder='..', static_url_path='')
# Apply CORS only to API routes and allow all origins for them
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ==============================
# MYSQL CONFIG
# ==============================
app.config['MYSQL_HOST'] = os.getenv("MYSQL_HOST")
app.config['MYSQL_USER'] = os.getenv("MYSQL_USER")
app.config['MYSQL_PASSWORD'] = os.getenv("MYSQL_PASSWORD")
app.config['MYSQL_DATABASE'] = os.getenv("MYSQL_DB")


bcrypt = Bcrypt(app)

# ==============================
# TWILIO CONFIG
# ==============================
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")
TWILIO_ENABLED = os.getenv("TWILIO_ENABLED", "false").lower() == "true"
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

# Only initialize Twilio if credentials are configured AND explicitly enabled
if TWILIO_ENABLED and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        print("✅ TWILIO CONFIGURED - SMS/WhatsApp alerts enabled")
    except Exception as e:
        print(f"⚠️  TWILIO INITIALIZATION ERROR: {e}")
        print("   SMS/WhatsApp alerts will be skipped")
        twilio_client = None
else:
    twilio_client = None
    if TWILIO_ENABLED:
        print("⚠️  TWILIO ENABLED but credentials missing - SMS/WhatsApp will be skipped")
    else:
        print("ℹ️  TWILIO DISABLED - Email alerts only (set TWILIO_ENABLED=true to enable)")

if DEMO_MODE:
    print("🎭 DEMO MODE ENABLED - WhatsApp messages will be simulated for testing")
# ==============================
# EMAIL ALERT FUNCTION
# ==============================
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

print(f"Email configuration: EMAIL_USER={EMAIL_USER}, EMAIL_PASS={'*' * len(EMAIL_PASS) if EMAIL_PASS else 'NOT SET'}")

def send_email_alert(to_email, subject, message):
    try:
        if not EMAIL_USER or not EMAIL_PASS:
            print(f"❌ Email error: EMAIL_USER or EMAIL_PASS not configured")
            sys.stdout.flush()
            return False
            
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(message, 'plain'))

        print(f"📧 Connecting to Gmail SMTP server...")
        sys.stdout.flush()
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        
        print(f"📧 Logging in with {EMAIL_USER}...")
        sys.stdout.flush()
        server.login(EMAIL_USER, EMAIL_PASS)
        
        print(f"📧 Sending email to {to_email}...")
        sys.stdout.flush()
        server.send_message(msg)
        server.quit()

        print(f"✅ Email sent successfully to {to_email}")
        sys.stdout.flush()
        return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Email Auth Error: Invalid email or app password")
        print(f"   Details: {e}")
        sys.stdout.flush()
        return False
    except smtplib.SMTPException as e:
        print(f"❌ Email SMTP Error: {type(e).__name__}")
        print(f"   Details: {e}")
        sys.stdout.flush()
        return False
    except Exception as e:
        print(f"❌ Email error: {type(e).__name__}: {e}")
        import traceback
        print(traceback.format_exc())
        sys.stdout.flush()
        return False


# ==============================
# SERVE STATIC FILES
# ==============================
@app.route('/')
def index():
    return send_from_directory('..', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    try:
        return send_from_directory('..', filename)
    except:
        return jsonify({"error": "File not found"}), 404

# ==============================
# REGISTER USER
# ==============================
@app.route('/api/register', methods=['POST'])
def register():
    print("\n" + "="*50)
    print("📝 REGISTRATION REQUEST RECEIVED")
    print("="*50)
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON body provided"}), 400

        # Validate required fields
        required_fields = ['name', 'mobile', 'email', 'password']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        name = data['name']
        mobile = data['mobile']
        email = data['email']
        password = data['password']
        emergency_contacts = data.get('emergency_contacts', [])

        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO users (mobile, name, email, password_hash)
            VALUES (%s, %s, %s, %s)
        """, (mobile, name, email, password_hash))

        user_id = cursor.lastrowid

        # Insert emergency contacts if provided
        for contact in emergency_contacts:
            cursor.execute("""
                INSERT INTO emergency_contacts (user_id, contact_name, contact_phone, contact_email)
                VALUES (%s, %s, %s, %s)
            """, (user_id, contact.get('name'), contact.get('mobile'), contact.get('email')))

        db.commit()
        cursor.close()

        # ==============================
        # SEND REGISTRATION CONFIRMATION EMAILS
        # ==============================
        print("\n🔔 SENDING REGISTRATION EMAILS...")
        
        # Email 1: Confirmation to the registered user
        user_subject = "Welcome to ResQNow - Registration Successful!"
        user_message = f"""
Dear {name},

Welcome to ResQNow Emergency SOS System!

Your account has been successfully created. Here are your registration details:

📧 Email: {email}
📱 Mobile: {mobile}

You can now log in to your account and configure your emergency settings.

🔐 Security Tip: Never share your password with anyone.

Need Help? Reply to this email or contact us at resqnow18@gmail.com

Stay Safe,
ResQNow Team
© 2026 ResQNow Emergency SOS System. All Rights Reserved.
"""
        
        print(f"📧 Attempting to send registration email to user: {email}")
        result = send_email_alert(email, user_subject, user_message)
        if result:
            print(f"✅ User registration email sent successfully")
        else:
            print(f"❌ User registration email failed to send")

        # Email 2: Notification to each emergency contact
        for contact in emergency_contacts:
            if contact.get('email'):
                contact_subject = f"You've Been Added as Emergency Contact for {name}"
                contact_message = f"""
Dear {contact.get('name')},

You have been added as an Emergency Contact for {name} on the ResQNow Emergency SOS System.

🚨 IMPORTANT: WhatsApp Alert Setup (ONE-TIME STEP)

To receive instant WhatsApp SOS alerts:

1️⃣ Save this number in your phone:
📞 +1 415 523 8886

2️⃣ Open WhatsApp and send this message:
JOIN <your sandbox code>

3️⃣ You will receive a confirmation message.

⚠️ If this step is not completed, you will NOT receive WhatsApp emergency alerts.

What This Means:
• If {name} activates SOS, you will receive alerts immediately
• Alerts include location and emergency details
• Your quick response could save a life

Your Details on File:
📱 Mobile: {contact.get('mobile')}
📧 Email: {contact.get('email')}

Please ensure your contact details stay updated.

Thank you for being a trusted emergency contact ❤️

ResQNow Team
© 2026 ResQNow Emergency SOS System
"""

                print(f"📧 Attempting to send emergency contact email to: {contact.get('email')}")
                result = send_email_alert(contact.get('email'), contact_subject, contact_message)
                if result:
                    print(f"✅ Emergency contact email sent successfully to {contact.get('email')}")
                else:
                    print(f"❌ Emergency contact email failed for {contact.get('email')}")

        print("\n✅ REGISTRATION COMPLETED SUCCESSFULLY")
        print("="*50 + "\n")
        return jsonify({"message": "Registration successful", "ok": True}), 201

    except Exception as e:
        print(f"❌ Register error: {e}")
        return jsonify({"error": str(e)}), 500


# ==============================
# LOGIN
# ==============================
@app.route('/api/login', methods=['POST'])
def login():
    print("\n" + "="*50)
    print("🔐 LOGIN REQUEST RECEIVED")
    print("="*50)
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON body provided"}), 400

        mobile = data.get('mobile')
        password = data.get('password')

        if not mobile or not password:
            return jsonify({"error": "Missing mobile or password"}), 400

        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE mobile=%s", (mobile,))
        user = cursor.fetchone()
        cursor.close()

        if user and bcrypt.check_password_hash(user['password_hash'], password):
            # Send login confirmation email
            print(f"\n🔔 SENDING LOGIN EMAIL to {user['email']}...")
            email_subject = "Login Successful - ResQNow"
            email_message = f"""
Dear {user['name']},

Your account has been successfully accessed.

Login Details:
📱 Mobile: {user['mobile']}
⏰ Time: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🔐 Security Alert: If you did not log in, please change your password immediately and contact support at resqnow18@gmail.com

Stay Safe,
ResQNow Team
© 2026 ResQNow Emergency SOS System. All Rights Reserved.
"""
            
            result = send_email_alert(user['email'], email_subject, email_message)
            if result:
                print(f"✅ Login email sent successfully to {user['email']}")
            else:
                print(f"❌ Login email failed to send to {user['email']}")
            
            print("\n✅ LOGIN COMPLETED SUCCESSFULLY")
            print("="*50 + "\n")
            
            return jsonify({
                "message": "Login successful",
                "user_id": user['id'],
                "name": user['name'],
                "ok": True
            }), 200
        else:
            return jsonify({"error": "Invalid credentials"}), 401

    except Exception as e:
        print(f"❌ Login error: {e}")
        return jsonify({"error": str(e)}), 500


# ==============================
# SOS ALERT
# ==============================
@app.route('/api/sos/<int:user_id>', methods=['POST'])
def sos(user_id):
    data = request.json
    location = data.get("location", "Location unavailable")

    cursor = db.cursor(dictionary=True)

    # get user
    cursor.execute("SELECT name, email FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()

    # get all emergency contacts
    cursor.execute("""
        SELECT contact_name, contact_phone, contact_email
        FROM emergency_contacts
        WHERE user_id=%s
    """, (user_id,))
    contacts = cursor.fetchall()

    cursor.close()

    if not user or not contacts:
        return jsonify({"message": "User/contact not found"}), 404

    message_body = f"""
🚨 EMERGENCY SOS ALERT 🚨

{user['name']} needs help!

📍 Location:
{location}

Please contact immediately.
"""

    try:
        # SEND SMS + EMAIL + WHATSAPP to each contact
        for contact in contacts:

            # SMS (only if Twilio is configured)
            if contact['contact_phone'] and twilio_client:
                try:
                    twilio_client.messages.create(
                        body=message_body,
                        from_=TWILIO_PHONE,
                        to=contact['contact_phone']
                    )
                    print(f"✅ SMS sent to {contact['contact_phone']}")
                except Exception as sms_err:
                    print(f"⚠️  SMS error: {sms_err}")

            # WHATSAPP to emergency contact (only if Twilio is configured)
            if contact['contact_phone'] and twilio_client:
                try:
                    twilio_client.messages.create(
                        body=message_body,
                        from_='whatsapp:' + TWILIO_PHONE,
                        to='whatsapp:' + contact['contact_phone']
                    )
                    print(f"✅ WhatsApp sent to {contact['contact_phone']}")
                except Exception as wa_err:
                    print(f"⚠️  WhatsApp error: {wa_err}")

            # EMAIL to emergency contact
            if contact['contact_email']:
                send_email_alert(
                    contact['contact_email'],
                    "🚨 SOS Emergency Alert",
                    message_body
                )

        # EMAIL to user
        if user['email']:
            send_email_alert(
                user['email'],
                "🚨 SOS Activated",
                "Your SOS alert has been sent successfully.\nHelp is on the way."
            )

        return jsonify({"message": "SOS alerts sent via SMS & Email"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================
# New endpoint: accept POST to /api/sos/activate with username in body
# this helps the frontend which posts username + location instead of an id
@app.route('/api/sos/activate', methods=['POST'])
def sos_activate():
    try:
        data = request.json or {}
        username = data.get('username')
        location = data.get('location', 'Location unavailable')

        if not username:
            return jsonify({"error": "username required"}), 400

        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id, name, email FROM users WHERE name=%s", (username,))
        user = cursor.fetchone()

        if not user:
            cursor.close()
            return jsonify({"error": "User not found"}), 404

        # get emergency contacts
        cursor.execute("""
            SELECT contact_name, contact_phone, contact_email
            FROM emergency_contacts
            WHERE user_id=%s
        """, (user['id'],))
        contacts = cursor.fetchall()
        cursor.close()

        if not contacts:
            return jsonify({"message": "No emergency contacts configured", "ok": False}), 404

        message_body = f"""
🚨 EMERGENCY SOS ALERT 🚨

{user['name']} needs help!

📍 Location:
{location}

Please contact immediately.
"""

        alerts_sent = []
        alerts_failed = []

        # Send alerts to each contact
        for contact in contacts:
            try:
                # SMS (only if Twilio is configured)
                if contact['contact_phone']:
                    if twilio_client:
                        try:
                            phone = contact['contact_phone'].strip()
                            # Ensure phone number has country code
                            if not phone.startswith('+'):
                                phone = '+' + phone
                            
                            print(f"\n📱 Sending SMS to {phone}...")
                            twilio_client.messages.create(
                                body=message_body,
                                from_=TWILIO_PHONE,
                                to=phone
                            )
                            alerts_sent.append(f"SMS to {phone}")
                            print(f"✅ SMS sent successfully to {phone}")
                        except Exception as sms_err:
                            print(f"❌ SMS error for {contact['contact_phone']}: {sms_err}")
                            print(f"   Error type: {type(sms_err).__name__}")
                            print(f"   Error details: {str(sms_err)}")
                            
                            # Fallback to demo mode if enabled
                            if DEMO_MODE:
                                print(f"🎭 DEMO MODE: Simulating SMS send to {contact['contact_phone']}")
                                alerts_sent.append(f"SMS to {contact['contact_phone']} (simulated)")
                                print(f"✅ SMS simulated successfully to {contact['contact_phone']}\n")
                            else:
                                alerts_failed.append(f"SMS: {str(sms_err)}")
                    else:
                        print(f"⏭️  SMS skipped for {contact['contact_phone']} (Twilio not configured)")

                # WHATSAPP to emergency contact (only if Twilio is configured)
                if contact['contact_phone']:
                    if twilio_client:
                        try:
                            phone = contact['contact_phone'].strip()
                            # Ensure phone number has country code
                            if not phone.startswith('+'):
                                phone = '+' + phone
                            
                            print(f"\n📱 Sending WhatsApp to {phone}...")
                            twilio_client.messages.create(
                                body=message_body,
                                from_='whatsapp:' + TWILIO_PHONE,
                                to='whatsapp:' + phone
                            )
                            alerts_sent.append(f"WhatsApp to {phone}")
                            print(f"✅ WhatsApp sent successfully to {phone}")
                        except Exception as whatsapp_err:
                            print(f"❌ WhatsApp error for {contact['contact_phone']}: {whatsapp_err}")
                            print(f"   Error type: {type(whatsapp_err).__name__}")
                            print(f"   Error details: {str(whatsapp_err)}")
                            
                            # Fallback to demo mode if enabled
                            if DEMO_MODE:
                                print(f"🎭 DEMO MODE: Simulating WhatsApp send to {contact['contact_phone']}")
                                alerts_sent.append(f"WhatsApp to {contact['contact_phone']} (simulated)")
                                print(f"✅ WhatsApp simulated successfully to {contact['contact_phone']}\n")
                            else:
                                alerts_failed.append(f"WhatsApp: {str(whatsapp_err)}")
                    else:
                        print(f"⏭️  WhatsApp skipped for {contact['contact_phone']} (Twilio not configured)")

                # EMAIL to emergency contact
                if contact['contact_email']:
                    try:
                        send_email_alert(
                            contact['contact_email'],
                            "🚨 SOS Emergency Alert",
                            message_body
                        )
                        alerts_sent.append(f"Email to {contact['contact_email']}")
                    except Exception as email_err:
                        print(f"⚠️  Email error for {contact['contact_email']}: {email_err}")
                        alerts_failed.append(f"Email: {str(email_err)}")

            except Exception as contact_err:
                print(f"❌ Error processing contact: {contact_err}")
                alerts_failed.append(str(contact_err))

        # EMAIL to user
        try:
            if user['email']:
                send_email_alert(
                    user['email'],
                    "🚨 SOS Activated",
                    "Your SOS alert has been sent successfully.\nHelp is on the way."
                )
        except Exception as user_email_err:
            print(f"⚠️  Error sending confirmation to user: {user_email_err}")

        return jsonify({
            "message": "SOS alert processed",
            "ok": True,
            "alerts_sent": len(alerts_sent),
            "alerts_failed": len(alerts_failed),
            "details": alerts_sent + alerts_failed
        }), 200

    except Exception as e:
        print(f"❌ SOS Activate error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "ok": False}), 500

# RUN SERVER
# ==============================
if __name__ == "__main__":
    app.run(debug=True, port=5000, host='127.0.0.1')
