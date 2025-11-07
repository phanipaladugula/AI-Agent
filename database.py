from sqlalchemy import create_engine, Column, String, Enum, Integer, TIMESTAMP, Index, Float, DateTime, ForeignKey, Date, Text, func
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, EmailStr
import enum
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
import os
from dotenv import load_dotenv
load_dotenv()

database_url = os.getenv("POSTGRES_URI")
engine = create_engine(database_url)
session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_db():
    db = session()
    try:
        yield db
    finally:
        db.close()

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True)
    password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    expenses = relationship("Expenses", back_populates="user", cascade="all,delete-orphan")
    messages = relationship("Messages", back_populates="user", cascade="all,delete-orphan")

class AmountType(enum.Enum):
    DEBIT = "debit"
    CREDIT = "credit"

class Expenses(Base):
    __tablename__ = "expenses"
    __table_args__ = (Index("idx_user_date", "user_id", "date"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    category = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    amount_type = Column(Enum(AmountType, native_enum=False), nullable=False)
    date = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow, server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="expenses")

class Messages(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="messages")


class UserCreate(BaseModel):
    email: EmailStr
    password: str

class AddExpense(BaseModel):
    category: str
    amount: float
    amount_type: AmountType
    date: Optional[date]

    class Config:
        from_attributes = True

class ExpenseOut(BaseModel):
    id: int
    category: str
    amount: float
    date: Optional[date]

    class Config:
        from_attributes = True

class update_expenses(BaseModel):
    category: Optional[str] = None
    amount: Optional[float] = None
    date: Optional[date] = None

class chat(BaseModel):
    query: str

class Delete_Multiple(BaseModel):
    items: List[int]
class RegisterStep1(BaseModel):
    email: EmailStr

class RegisterStep2(BaseModel):
    email: EmailStr
    otp: int
    password: str

