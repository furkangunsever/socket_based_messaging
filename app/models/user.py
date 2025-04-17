from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import uuid4

class User(BaseModel):
    """Kullanıcı veri modeli"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    username: str
    room_id: Optional[str] = None
    connected_at: datetime = Field(default_factory=datetime.now)
    last_activity: datetime = Field(default_factory=datetime.now)
    is_active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Kullanıcıyı sözlük formatına dönüştürür"""
        return {
            "id": self.id,
            "username": self.username,
            "room_id": self.room_id,
            "connected_at": self.connected_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "is_active": self.is_active
        }

class UserSession(BaseModel):
    """Oturum bilgisi tutan kullanıcı sınıfı"""
    sid: str  # Socket ID
    user: User 