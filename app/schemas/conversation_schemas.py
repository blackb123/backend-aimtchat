# app/schemas/conversation_schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List

class CreatePrivateChatRequest(BaseModel):
    """Request schema for creating a private chat between two users"""

    user_one_id: int = Field(..., description="ID of the first user in the chat")
    user_two_id: int = Field(..., description="ID of the second user in the chat")
    
    class Config:
        schema_extra = {
            "example": {
                "user_one_id": 1,
                "user_two_id": 2
            }
        }

class CreatePrivateChatResponse(BaseModel):
    """Response schema for creating a private chat"""

    id: int = Field(..., description="ID of the created or existing chat")
    message: str = Field(..., description="Status message about the chat creation")
    
    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "message": "Private chat created successfully"
            }
        }

class SendMessageRequest(BaseModel):
    """Request schema for sending a message"""

    receiver_id: int = Field(..., description="ID of the message receiver")
    content: str = Field(..., min_length=1, max_length=1000, description="Message content")
    chat_id: int = Field(..., description="ID of the chat to send message to")
    
    class Config:
        schema_extra = {
            "example": {
                "receiver_id": 2,
                "content": "Hello there!",
                "chat_id": 1
            }
        }

class SendMessageResponse(BaseModel):
    """Response schema for sending a message"""
    
    id: int = Field(..., description="ID of the created message")
    content: str = Field(..., description="Message content")
    sender_id: int = Field(..., description="ID of the message sender")
    sent_at: str = Field(..., description="Timestamp when message was sent")
    chat_id: int = Field(..., description="ID of the chat")
    
    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "content": "Hello there!",
                "sender_id": 1,
                "sent_at": "2024-01-01T12:00:00",
                "chat_id": 1
            }
        }

class UserListItem(BaseModel):
    """User item for conversation list"""

    id: int = Field(..., description="User ID")
    name: str = Field(..., description="Username")
    message: str = Field(..., description="Last message or placeholder")
    time: str = Field(..., description="Time of last message")
    avatar: str = Field(..., description="Avatar character")
    chat_id: Optional[int] = Field(None, description="Existing chat ID if any")
    has_chat: bool = Field(..., description="Whether chat exists with this user")
    
    class Config:
        schema_extra = {
            "example": {
                "id": 2,
                "name": "testuser",
                "message": "Start a conversation...",
                "time": "Now",
                "avatar": "T",
                "chat_id": None,
                "has_chat": False
            }
        }

class ConversationListResponse(BaseModel):
    """Response schema for conversation list endpoint"""
    
    users: List[UserListItem] = Field(..., description="List of users with chat info")
    
    class Config:
        schema_extra = {
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

# Keep existing schemas for backward compatibility
class ConversationItem(BaseModel):
    id: int
    name: str
    message: str
    time: str
    avatar: str
    chat_id: int
    isConversation: bool = True

class UserItem(BaseModel):
    id: int
    name: str
    avatar: str
    isConversation: bool = False

class ChatListResponse(BaseModel):
    conversations: List[ConversationItem]
    users: List[UserItem]
