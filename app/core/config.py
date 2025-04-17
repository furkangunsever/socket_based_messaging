import os
from typing import Dict, Any
from dotenv import load_dotenv
from pydantic import BaseModel

# .env dosyasını yükle
load_dotenv()

class Settings(BaseModel):
    """Uygulama ayarları sınıfı"""
    # Server
    HOST: str = os.getenv('HOST', '0.0.0.0')
    PORT: int = int(os.getenv('PORT', 8000))
    DEBUG: bool = os.getenv('DEBUG', 'False').lower() == 'true'
    
    # Socket.IO
    SOCKET_PING_TIMEOUT: int = int(os.getenv('SOCKET_PING_TIMEOUT', 60))
    SOCKET_PING_INTERVAL: int = int(os.getenv('SOCKET_PING_INTERVAL', 25))
    
    # Logging
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')

    def get_socketio_config(self) -> Dict[str, Any]:
        """Socket.IO yapılandırma parametrelerini döndürür"""
        return {
            'ping_timeout': self.SOCKET_PING_TIMEOUT,
            'ping_interval': self.SOCKET_PING_INTERVAL,
        }

# Ayarları uygulamanın diğer bölümlerinde kullanmak için
settings = Settings() 