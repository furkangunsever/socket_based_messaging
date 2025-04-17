from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import uuid4

class Message(BaseModel):
    """Mesaj veri modeli"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    room_id: str
    user_id: str
    username: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    is_system_message: bool = False
    edited: bool = False
    edited_at: Optional[datetime] = None
    deleted: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Mesajı sözlük formatına dönüştürür"""
        return {
            "id": self.id,
            "room_id": self.room_id,
            "user_id": self.user_id,
            "username": self.username,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "is_system_message": self.is_system_message,
            "edited": self.edited,
            "edited_at": self.edited_at.isoformat() if self.edited_at else None,
            "deleted": self.deleted
        }

class MessageInput(BaseModel):
    """Mesaj gönderme işlemi için giriş modeli"""
    room_id: str
    content: str

class TypingStatus(BaseModel):
    """Kullanıcı yazma durumu modeli"""
    user_id: str
    room_id: str
    username: str
    is_typing: bool = True 