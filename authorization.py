from passlib.context import CryptContext
from datetime import timedelta, datetime
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends
import os
from dotenv import load_dotenv
load_dotenv()
algorithm =os.getenv("algorithm")
secret_key = os.getenv("secret_key")

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

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from random import randint
from datetime import datetime,timedelta

otp_storage={}
def generate_otp(email:str,expire_minutes:int=5):
    otp = randint(100000, 999999) 
    expires_at=datetime.utcnow()+timedelta(minutes=expire_minutes)
    otp_storage[email]={"otp":otp,"expires_at":expires_at}
    return otp

def verify_otp(email:str,otp_input:int):
    record=otp_storage.get(email)
    if not record:
        return False
    if datetime.utcnow() >record['expires_at']:
        return False
    if record['otp']!=otp_input:
        return False
    del otp_storage[email]
    return True
def otp_email_body(email: str, otp: int, expiry_minutes: int = 5):
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

def send_otp_email(to_email:str,otp:int):
     send_email=os.getenv("send_email")
     send_password=os.getenv("send_password")
     body=otp_email_body(to_email,otp)
     msg=MIMEMultipart()
     msg['From']=send_email
     msg['To']=to_email
     msg['Subject']="Your OTP Code"
     msg.attach(MIMEText(body,'html'))

     with smtplib.SMTP_SSL('smtp.gmail.com',465) as server:
         server.login(send_email,send_password)
         server.send_message(msg)
