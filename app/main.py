# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.orm import sessionmaker
from app.core.database import Base, engine
from app.model import User, Message, PrivateChat # Added PrivateChat
from app.routes import auth, message, conversation
from app.core.socket import sio, user_to_sid
from datetime import datetime
import socketio
import os

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

fastapi_app = FastAPI(lifespan=lifespan)

fastapi_app.include_router(auth.router, prefix="/auth", tags=["auth"])
fastapi_app.include_router(message.msg_router, prefix="/messages", tags=["messages"])
fastapi_app.include_router(conversation.conv_router, prefix="/conversations", tags=["conversations"])

# CORS middleware


fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------
# Socket.IO logic
# -------------------

@sio.event
async def connect(sid, environ, auth):
    user_id = auth.get("userId") if auth else None
    if not user_id:
        print("Connection refused: no user_id")
        return False
    
    # Convert to int
    user_id = int(user_id)

    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.is_online = True
        user_to_sid[user_id] = sid  
        db.commit()
        print(f"User {user.username} ONLINE, mapping: {user_to_sid}")
        
        # Broadcast to all clients that this user is online
        await sio.emit("user_status", {
            "user_id": user_id,
            "is_online": True,
            "username": user.username
        })
    else:
        print(f"User {user_id} not found")
        db.close()
        return False
    db.close()

@sio.event
async def disconnect(sid):
    """
    Find which user owned this sid and set them to Offline.
    """
    db = SessionLocal()
    # Find user_id by sid
    user_id = next((k for k, v in user_to_sid.items() if v == sid), None)
    
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.is_online = False
            user.last_seen = datetime.utcnow()
            db.commit()
            del user_to_sid[user_id]
            print(f"User {user.username} is now OFFLINE.")
            
            # Broadcast to all clients that this user is offline
            await sio.emit("user_status", {
                "user_id": user_id,
                "is_online": False,
                "username": user.username
            })
    db.close()

@sio.event
async def send_message(sid, data):
    db = SessionLocal()
    
    sender_id = next((k for k, v in user_to_sid.items() if v == sid), None)
    if not sender_id:
        return

    receiver_id = int(data['receiver_id']) 
    receiver_sid = user_to_sid.get(receiver_id)
    
    print(f"Receiver ID: {receiver_id}, Receiver SID: {receiver_sid}")
    
    # 2. Save to Database
    new_msg = Message(
        chat_id=data['chat_id'], 
        sender_id=sender_id, 
        content=data['content']
    )
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)

    # 3. Prepare Payload
    sender_user = db.query(User).filter(User.id == sender_id).first()
    payload = {
        "id": new_msg.id,
        "chat_id": new_msg.chat_id,
        "sender_id": sender_id,
        "content": new_msg.content,
        "sent_at": str(new_msg.sent_at),
        "user_name": sender_user.username,
        "user_id": sender_id,
        "tempId": data.get("tempId")

    }

    print(f"Prepared payload: {payload}")

    # Send to the receiver IF they are online
    receiver_sid = user_to_sid.get(data['receiver_id'])
    print(f"Receiver ID: {data['receiver_id']}, Receiver SID: {receiver_sid}")
    
    if receiver_sid:
        print(f"Emitting receive_message to receiver_sid: {receiver_sid}")
        await sio.emit("receive_message", payload, room=receiver_sid)
    else:
        print(f"Receiver {data['receiver_id']} is not online")
    
    # emit back to the sender so their UI updates/confirms
    print(f"Emitting message_sent_confirm to sender_sid: {sid}")
    await sio.emit("message_sent_confirm", payload, room=sid)

    db.close()

@sio.event
async def mark_messages_read(sid, data):
    """Mark all messages in a chat as read for the current user."""
    db = SessionLocal()
    
    try:
        user_id = next((k for k, v in user_to_sid.items() if v == sid), None)
        if not user_id:
            return
        
        chat_id = data.get('chat_id')
        if not chat_id:
            return
        
        # Mark all messages from other users as read in this chat
        db.query(Message).filter(
            Message.chat_id == chat_id,
            Message.sender_id != user_id,
            Message.is_read == False
        ).update({"is_read": True})
        
        db.commit()
        
        # Notify the sender(s) that their messages have been read
        # Find the other user in this chat
        chat = db.query(PrivateChat).filter(PrivateChat.id == chat_id).first()
        if chat:
            other_user_id = chat.user_one_id if chat.user_two_id == user_id else chat.user_two_id
            other_sid = user_to_sid.get(other_user_id)
            if other_sid:
                await sio.emit("messages_read", {
                    "chat_id": chat_id,
                    "reader_id": user_id
                }, room=other_sid)
                
    except Exception as e:
        print(f"Error marking messages as read: {e}")
    finally:
        db.close()

app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app, socketio_path="/socket.io")