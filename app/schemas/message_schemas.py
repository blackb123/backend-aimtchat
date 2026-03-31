from pydantic import BaseModel
from datetime import datetime

class MessageOut(BaseModel):
    id: int
    sender: str # We'll use sender.username
    sender_id:int 
    content: str
    sent_at: datetime

    class Config:
        orm_mode = True
