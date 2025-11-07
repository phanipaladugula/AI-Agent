from passlib.context import CryptContext
from datetime import timedelta, datetime
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
import os
from dotenv import load_dotenv
import redis # <-- NEW: Import Redis client
import smtplib # Keep import if you use SMTP/TLS, but prefer API services
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from random import randint
# Assuming you install the 'requests' library (often needed for email APIs)
# import requests 

load_dotenv()
algorithm = os.getenv("algorithm")
secret_key = os.getenv("secret_key")
redis_url = os.getenv("REDIS_URL") # <-- NEW: Read Redis URL

# --- JWT and Password Hashing (No Change) ---
pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(user_id: int, expire_time: int = 30) -> str:
    expire = datetime.utcnow() + timedelta(minutes=expire_time)
    payload = {
        "sub": str(user_id),
        "exp": expire
    }
    token = jwt.encode(payload, secret_key, algorithm=algorithm)
    return token

# --- Redis Configuration for OTP (Replaces otp_storage) ---
# Connect to Redis using the REDIS_URL environment variable
try:
    # Decode_responses=True makes it return strings instead of bytes
    r = redis.from_url(redis_url, decode_responses=True)
    r.ping() # Check connection
    print("Connected to Redis successfully!")
except Exception as e:
    print(f"Could not connect to Redis: {e}")
    # In a real app, you might crash or use a fallback. 
    # For now, we allow it to start for deployment testing.

def generate_otp(email:str, expire_minutes:int=5) -> int:
    otp = randint(100000, 999999) 
    # Key in Redis: otp:<email>
    redis_key = f"otp:{email}"
    
    # Store OTP with a time-to-live (TTL) in seconds
    r.setex(redis_key, timedelta(minutes=expire_minutes), otp)
    
    return otp

def verify_otp(email:str, otp_input:int) -> bool:
    redis_key = f"otp:{email}"
    
    # Get the OTP value (returns None if key doesn't exist or expired)
    stored_otp = r.get(redis_key)
    
    if not stored_otp:
        return False
        
    # Check if the stored OTP matches the input (stored_otp is a string)
    if str(stored_otp) != str(otp_input):
        return False
        
    # If successful, delete the key to prevent reuse
    r.delete(redis_key)
    return True
    
# --- Email Body (No Change) ---
def otp_email_body(email: str, otp: int, expiry_minutes: int = 5):
    # ... (body function remains the same)
    return f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #4CAF50;">Expense Tracker - OTP Verification</h2>
        <p>Hello,</p>
        <p>You requested an OTP for your email <b>{email}</b> in <b>Expense Tracker</b>.</p>
        <h1 style="color: #FF5722;">{otp}</h1>
        <p>This OTP will expire in <b>{expiry_minutes} minutes</b>. Please do not share it with anyone.</p>
        <hr>
        <p style="font-size: 12px; color: #777;">
          If you didn’t request this OTP or need help, contact us at 
          <a href="mailto:support@gmail.com">support@gmail.com</a>.
        </p>
      </body>
    </html>
    """

# --- Email Sending (Replaced with best practice placeholder) ---
def send_otp_email(to_email:str,otp:int):
    # CRITICAL: Do NOT use personal Gmail SMTP for production.
    # Replace this block with a call to a professional email service API (SendGrid, Mailgun, etc.)

    # If you must use SMTP, ensure you use a dedicated service account and secure credentials:
    send_email=os.getenv("SEND_EMAIL_USER") # Changed variable name
    send_password=os.getenv("SEND_EMAIL_PASSWORD") # Changed variable name
    
    # If you use a service like SendGrid, the code would look like:
    # sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
    # import sendgrid
    # sg = sendgrid.SendGridAPIClient(sendgrid_api_key)
    # response = sg.send(...)
    
    # Reverting to the SMTP method, but using better environment variables:
    body=otp_email_body(to_email,otp)
    msg=MIMEMultipart()
    msg['From']=send_email
    msg['To']=to_email
    msg['Subject']="Your OTP Code"
    msg.attach(MIMEText(body,'html'))

    try:
        # Note: You may need to change 'smtp.gmail.com',465 to your chosen SMTP server
        with smtplib.SMTP_SSL('smtp.gmail.com',465) as server:
            server.login(send_email,send_password)
            server.send_message(msg)
    except Exception as e:
        # Log the error, but don't crash the server
        print(f"Failed to send email to {to_email}. Error: {e}")
        # In a production app, you might raise an HTTPException here or log to a service
