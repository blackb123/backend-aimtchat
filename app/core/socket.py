# app/core/socket.py
import socketio
from typing import Dict

# Create Socket.IO server instance
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

# Map user_id -> sid for targeted messaging
user_to_sid: Dict[int, str] = {}

async def emit_to_user(user_id: int, event: str, data: dict):
    """Emit an event to a specific user if they are online"""
    receiver_sid = user_to_sid.get(user_id)
    if receiver_sid:
        await sio.emit(event, data, room=receiver_sid)
        return True
    return False

async def emit_to_sender(user_id: int, event: str, data: dict):
    """Emit an event to the sender if they are online"""
    sender_sid = user_to_sid.get(user_id)
    if sender_sid:
        await sio.emit(event, data, room=sender_sid)
        return True
    return False
