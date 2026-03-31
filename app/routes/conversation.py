# app/routes/conversation.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.core.database import get_db
from app.model import Message, User, PrivateChat
from app.schemas.message_schemas import MessageOut
from app.schemas.conversation_schemas import (
    CreatePrivateChatRequest, 
    CreatePrivateChatResponse, 
    SendMessageRequest, 
    SendMessageResponse,
    ConversationListResponse,
    UserListItem
)
from app.core.security import get_current_user
from app.core.socket import sio, user_to_sid, emit_to_user, emit_to_sender

conv_router = APIRouter(tags=["conversations"])

@conv_router.get(
    "/conversations", 
    response_model=List[UserListItem],
    summary="Get all users for conversation sidebar",
    description="Returns a list of all users except the current user, including information about existing chats and last messages",
    responses={
        200: {
            "description": "Successfully retrieved user list",
            "content": {
                "application/json": {
                    "example": {
                        "users": [
                            {
                                "id": 2,
                                "name": "testuser",
                                "message": "Start a conversation...",
                                "time": "Now",
                                "avatar": "T",
                                "chat_id": None,
                                "has_chat": False
                            }
                        ]
                    }
                }
            }
        },
        401: {
            "description": "Unauthorized - Invalid or missing authentication token",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid token"
                    }
                }
            }
        },
        404: {
            "description": "User not found in database",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "User not found"
                    }
                }
            }
        }
    }
)
def get_user_conversations(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get all users except current user for the sidebar.
    
    This endpoint returns a comprehensive list of all users in the system except the current user.
    For each user, it includes:
    - User information (id, name, avatar)
    - Whether a chat already exists
    - Last message if chat exists
    - Chat ID if conversation exists
    - Unread message count for each conversation
    
    **Authentication Required**: Bearer token
    """
    
    # Handle both string username and User object
    if isinstance(current_user, str):
        user_obj = db.query(User).filter(User.id == current_user).first()
        if not user_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        current_user_id = user_obj.id
    else:
        current_user_id = current_user
    
    # Get all users except current user
    users = db.query(User).filter(User.id != current_user_id).all()
    
    if not users:
        return []
    
    result = []
    for user in users:
        # Check if there's an existing chat with this user
        existing_chat = db.query(PrivateChat).filter(
            ((PrivateChat.user_one_id == current_user_id) & (PrivateChat.user_two_id == user.id)) |
            ((PrivateChat.user_one_id == user.id) & (PrivateChat.user_two_id == current_user_id))
        ).first()
        
        # Get last message if chat exists
        last_message = None
        unread_count = 0
        if existing_chat:
            last_message = db.query(Message).filter(Message.chat_id == existing_chat.id).order_by(Message.sent_at.desc()).first()
            # Count unread messages sent by the other user (not current user)
            unread_count = db.query(Message).filter(
                Message.chat_id == existing_chat.id,
                Message.sender_id != current_user_id,
                Message.is_read == False
            ).count()
        
        result.append({
            "id": user.id,
            "name": user.username,
            "message": last_message.content if last_message else "Start a conversation...",
            "time": "Now" if not last_message else _format_time(last_message.sent_at),
            "avatar": user.username[0].upper(),
            "chat_id": existing_chat.id if existing_chat else None,
            "has_chat": existing_chat is not None,
            "unread_count": unread_count
        })
    
    return result

@conv_router.get("/conversation/{chat_id}", response_model=List[MessageOut])
def get_conversation_messages(
    chat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all messages in a private chat by chat_id"""
    
    # Verify the current user is part of the chat
    chat = db.query(PrivateChat).filter(
        (PrivateChat.id == chat_id) &
        ((PrivateChat.user_one_id == current_user) | (PrivateChat.user_two_id == current_user))
    ).first()
    
    if not chat:
        # Return empty list if no conversation exists or user not authorized
        return []
    
    # Get all messages in this chat, ordered by time
    messages = db.query(Message).filter(Message.chat_id == chat.id).order_by(Message.sent_at).all()
    
    result = [
        MessageOut(
            id=msg.id,
            sender=msg.sender.username,
            sender_id=msg.sender_id,
            content=msg.content,
            sent_at=msg.sent_at
        )
        for msg in messages
    ]
    return result




@conv_router.post(
    "/create_private_chat",
    response_model=CreatePrivateChatResponse,
    summary="Create a new private chat between two users",
    description="Creates a new private chat between two specified users. If a chat already exists between them, returns the existing chat.",
    responses={
        200: {
            "description": "Chat created or found successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "message": "Private chat created successfully"
                    }
                }
            }
        },
        400: {
            "description": "Bad request - Missing or invalid user IDs",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Both user IDs are required"
                    }
                }
            }
        },
        401: {
            "description": "Unauthorized - Invalid or missing authentication token",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid token"
                    }
                }
            }
        },
        404: {
            "description": "One or both users not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "User with ID 999 not found"
                    }
                }
            }
        }
    }
)
def create_private_chat(
    data: CreatePrivateChatRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
  
    
    # Get current user ID
    if isinstance(current_user, str):
        user_obj = db.query(User).filter(User.id == current_user).first()
        if not user_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        current_user_id = user_obj.id
    else:
        current_user_id = current_user
    
    user_one_id = data.user_one_id
    user_two_id = data.user_two_id
    
    # Validate user IDs
    if not user_one_id or not user_two_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both user IDs are required"
        )
    
    # Prevent users from creating chat with themselves
    if user_one_id == user_two_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create chat with yourself"
        )
    
    # Verify both users exist
    user_one = db.query(User).filter(User.id == user_one_id).first()
    user_two = db.query(User).filter(User.id == user_two_id).first()
    
    if not user_one:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_one_id} not found"
        )
    
    if not user_two:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_two_id} not found"
        )
    
    # Check if chat already exists
    existing_chat = db.query(PrivateChat).filter(
        ((PrivateChat.user_one_id == user_one_id) & (PrivateChat.user_two_id == user_two_id)) |
        ((PrivateChat.user_one_id == user_two_id) & (PrivateChat.user_two_id == user_one_id))
    ).first()
    
    if existing_chat:
        return CreatePrivateChatResponse(
            id=existing_chat.id,
            message="Chat already exists"
        )
    
    # Create new chat
    new_chat = PrivateChat(
        user_one_id=user_one_id,
        user_two_id=user_two_id
    )
    db.add(new_chat)
    db.commit()
    db.refresh(new_chat)
    
    return CreatePrivateChatResponse(
        id=new_chat.id,
        message="Private chat created successfully"
    )





@conv_router.post(
    "/send_message",
    response_model=SendMessageResponse,
    summary="Send a message to a user",
    description="Sends a message to a specified user in an existing chat. The user must be part of the chat.",
    responses={
        200: {
            "description": "Message sent successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "content": "Hello there!",
                        "sender_id": 1,
                        "sent_at": "2024-01-01T12:00:00",
                        "chat_id": 1
                    }
                }
            }
        },
        400: {
            "description": "Bad request - Missing required fields",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "receiver_id, content, and chat_id are required"
                    }
                }
            }
        },
        401: {
            "description": "Unauthorized - Invalid or missing authentication token",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid token"
                    }
                }
            }
        },
        403: {
            "description": "Forbidden - User is not part of this chat",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "You are not part of this chat"
                    }
                }
            }
        },
        404: {
            "description": "Chat not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Chat not found"
                    }
                }
            }
        }
    }
)
def send_message(
    data: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Send a message to a user in an existing chat.
    
    This endpoint allows a user to send a message to another user in an existing private chat.
    The sender must be part of the chat to send messages.
    
    **Authentication Required**: Bearer token
    **Required Fields**:
    - receiver_id: ID of the message receiver
    - content: Message content (1-1000 characters)
    - chat_id: ID of the chat to send message to
    
    **Validation**: User must be a participant in the specified chat.
    """
    
    # Get current user ID
    if isinstance(current_user, str):
        user_obj = db.query(User).filter(User.id == current_user).first()
        if not user_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        current_user_id = user_obj.id
    else:
        current_user_id = current_user
    
    receiver_id = data.receiver_id
    content = data.content
    chat_id = data.chat_id
    
    # Validate required fields
    if not receiver_id or not content or not chat_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="receiver_id, content, and chat_id are required"
        )
    
    # Validate content length
    if len(content.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty"
        )
    
    # Verify that the current user is part of this chat
    chat = db.query(PrivateChat).filter(
        ((PrivateChat.user_one_id == current_user_id) & (PrivateChat.user_two_id == receiver_id)) |
        ((PrivateChat.user_one_id == receiver_id) & (PrivateChat.user_two_id == current_user_id))
    ).filter(PrivateChat.id == chat_id).first()
    
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not part of this chat"
        )
    
    # Create new message
    new_message = Message(
        chat_id=chat_id,
        sender_id=current_user_id,
        content=content.strip()
    )
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    
    # Prepare message payload for Socket.IO
    message_payload = {
        "id": new_message.id,
        "content": new_message.content,
        "sender_id": new_message.sender_id,
        "sent_at": new_message.sent_at.isoformat(),
        "chat_id": new_message.chat_id
    }
    
    # Get sender username for socket message
    sender_user = db.query(User).filter(User.id == current_user_id).first()
    
    # # Emit message to receiver if they are online
    # import asyncio
    # asyncio.create_task(emit_to_user(receiver_id, "receive_message", {
    #     **message_payload,
    #     "user_name": sender_user.username,
    #     "user_id": current_user_id
    # }))
    
    # # Emit confirmation back to sender
    # asyncio.create_task(emit_to_sender(current_user_id, "message_sent_confirm", message_payload))
    
    return SendMessageResponse(
        id=new_message.id,
        content=new_message.content,
        sender_id=new_message.sender_id,
        sent_at=new_message.sent_at.isoformat(),
        chat_id=new_message.chat_id
    )

def _format_time(sent_at) -> str:
    """Format datetime for display"""
    from datetime import datetime
    now = datetime.utcnow()
    diff = now - sent_at
    
    if diff.days > 0:
        return f"{diff.days}d ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours}h ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes}m ago"
    else:
        return "Just now"
