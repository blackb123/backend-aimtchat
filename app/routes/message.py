# app/routes/messages.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.model import Message, User
from app.schemas.message_schemas import MessageOut  # Pydantic schema for response

msg_router = APIRouter(tags=["messages"])

# GET all messages (legacy - keep for compatibility)
@msg_router.get("/messages", response_model=List[MessageOut])
def get_messages(db: Session = Depends(get_db)):
    messages = db.query(Message).all()
    result = [
        MessageOut(
            id=msg.id,
            sender=msg.sender.username,
            sender_id=msg.sender_id ,
            content=msg.content,
            sent_at=msg.sent_at
        )
        for msg in messages
    ]
    return result