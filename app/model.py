# app/model.py
from .core.database import Base
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True) # Index for fast search
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # --- New Status Tracking ---
    is_online = Column(Boolean, default=False)
    # Relationships
    messages_sent = relationship("Message", back_populates="sender", cascade="all, delete-orphan")

class PrivateChat(Base):
    """Links exactly two users together in a unique chat session."""
    __tablename__ = "private_chats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_one_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_two_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to get all messages in this specific chat
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, ForeignKey("private_chats.id"), nullable=False) # Links to the chat room
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)

    # Back-populates
    chat = relationship("PrivateChat", back_populates="messages")
    sender = relationship("User", back_populates="messages_sent")