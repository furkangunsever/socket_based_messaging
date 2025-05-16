import os
import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logger import log
from app.sockets.connection import register_connection_events
from app.sockets.room import register_room_events
from app.sockets.message import register_message_events
from app.core.config import load_config

# Environment değişkenlerini ve konfigürasyon ayarlarını yükle
config = load_config()

# FastAPI uygulaması oluştur
app = FastAPI(title="Socket.IO Mesajlaşma API")

# CORS ayarlarını yapılandır
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tüm domainlere izin ver (geliştirme için)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Socket.IO sunucusu oluştur
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=[],  # CORS ayarlarını FastAPI kullanıyor
    logger=True,
    engineio_logger=True
)

# Socket.IO uygulamasını oluştur
socket_app = socketio.ASGIApp(
    sio,
    socketio_path='socket.io',
)

# Socket.IO'yu FastAPI'ye bağla
app.mount("/", socket_app)

# Socket.IO olay işleyicilerini kaydet
register_connection_events(sio)
register_room_events(sio)
register_message_events(sio)

@app.get("/")
async def root():
    return {"message": "Socket.IO Mesajlaşma API Çalışıyor"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    log.info(f"Uygulama {port} portunda başlatılıyor")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True) 