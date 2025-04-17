import socketio
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.config import settings
from app.core.logger import log
from app.sockets.connection import register_connection_events
from app.sockets.message import register_message_events, register_message_edit_events
from app.sockets.room import register_room_events

# FastAPI uygulaması oluştur
app = FastAPI(title="Gerçek Zamanlı Sohbet Uygulaması")

# Socket.IO sunucusu oluştur
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",  # Geliştirme için. Prodüksiyonda güvenli hale getirin.
    **settings.get_socketio_config()
)

# FastAPI ile Socket.IO entegrasyonu
socket_app = socketio.ASGIApp(sio, app)

# Socket.IO event handler'larını kaydet
register_connection_events(sio)
register_message_events(sio)
register_message_edit_events(sio)
register_room_events(sio)

# API rotaları
@app.get("/", response_class=HTMLResponse)
async def index():
    """
    API ana sayfası
    """
    html_content = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>Gerçek Zamanlı Sohbet API</title>
            <style>
                body { 
                    font-family: Arial, sans-serif; 
                    max-width: 800px; 
                    margin: 0 auto; 
                    padding: 20px;
                }
                h1 { color: #333; }
                .endpoint { 
                    background: #f4f4f4; 
                    padding: 10px; 
                    margin-bottom: 10px; 
                    border-radius: 5px;
                }
                code {
                    background: #e4e4e4;
                    padding: 2px 4px;
                    border-radius: 3px;
                    font-family: monospace;
                }
                pre {
                    background: #e4e4e4;
                    padding: 10px;
                    border-radius: 5px;
                    overflow-x: auto;
                }
            </style>
        </head>
        <body>
            <h1>Gerçek Zamanlı Sohbet API</h1>
            <p>Socket.IO tabanlı sohbet uygulaması API'sine hoş geldiniz.</p>
            
            <h2>API Dokümantasyonu</h2>
            <p>API dokümantasyonu için <a href="/docs">bu bağlantıyı</a> ziyaret edin.</p>
            
            <h2>Socket.IO Olayları</h2>
            <div class="endpoint">
                <h3>connect</h3>
                <p>Kullanıcı bağlantısı</p>
            </div>
            <div class="endpoint">
                <h3>authenticate</h3>
                <p>Kullanıcı kimlik doğrulama</p>
                <p>Örnek: <code>socket.emit('authenticate', { username: 'test_user' });</code></p>
            </div>
            <div class="endpoint">
                <h3>broadcast_message</h3>
                <p>Tüm bağlı kullanıcılara mesaj gönderme</p>
                <pre>socket.emit('broadcast_message', { 
    username: 'test_user', 
    deviceId: 'device123', 
    message: 'Merhaba Dünya!',
    timestamp: '2023-05-20T15:30:45.123Z',
    source: 'mobile'
});</pre>
            </div>
            <div class="endpoint">
                <h3>create_room</h3>
                <p>Yeni sohbet odası oluşturma</p>
                <p><strong>Parametreler:</strong></p>
                <ul>
                    <li><code>name</code>: Oda adı</li>
                    <li><code>type</code>: Oda türü ('public' veya 'private')</li>
                    <li><code>password</code>: (İsteğe bağlı) Özel oda için şifre</li>
                </ul>
                <p><strong>Örnek (Herkese açık oda):</strong></p>
                <pre>socket.emit('create_room', { 
    name: 'Genel Sohbet', 
    type: 'public'
});</pre>
                <p><strong>Örnek (Şifreli özel oda):</strong></p>
                <pre>socket.emit('create_room', { 
    name: 'Özel Sohbet', 
    type: 'private',
    password: 'gizli123'
});</pre>
            </div>
            <div class="endpoint">
                <h3>join_room</h3>
                <p>Bir odaya katılma</p>
                <p><strong>Parametreler:</strong></p>
                <ul>
                    <li><code>room_id</code>: Katılmak istenen odanın ID'si</li>
                    <li><code>password</code>: (Gerekirse) Özel oda için şifre</li>
                </ul>
                <p><strong>Örnek (Herkese açık oda):</strong></p>
                <pre>socket.emit('join_room', { 
    room_id: 'oda_id'
});</pre>
                <p><strong>Örnek (Şifreli özel oda):</strong></p>
                <pre>socket.emit('join_room', { 
    room_id: 'oda_id',
    password: 'gizli123'
});</pre>
            </div>
            <div class="endpoint">
                <h3>leave_room</h3>
                <p>Bir odadan ayrılma</p>
                <pre>socket.emit('leave_room', { 
    room_id: 'oda_id'
});</pre>
            </div>
            <div class="endpoint">
                <h3>get_rooms</h3>
                <p>Mevcut odaların listesini alma</p>
                <pre>socket.emit('get_rooms', (rooms) => {
    console.log('Aktif odalar:', rooms);
});</pre>
            </div>
            <div class="endpoint">
                <h3>send_message</h3>
                <p>Oda içi mesaj gönderme</p>
                <pre>socket.emit('send_message', { 
    room_id: 'oda_id', 
    content: 'Merhaba Dünya!' 
});</pre>
            </div>
            <div class="endpoint">
                <h3>update_message</h3>
                <p>Gönderilen bir mesajı güncelleme</p>
                <pre>socket.emit('update_message', { 
    messageId: 'mesaj_id', 
    content: 'Güncellenmiş mesaj içeriği' 
});</pre>
            </div>
            <div class="endpoint">
                <h3>delete_message</h3>
                <p>Gönderilen bir mesajı silme</p>
                <pre>socket.emit('delete_message', { 
    messageId: 'mesaj_id'
});</pre>
            </div>
        </body>
    </html>
    """
    return html_content

@app.get("/health")
async def health_check():
    """
    Sağlık kontrolü endpoint'i
    """
    return {
        "status": "up",
        "services": {
            "api": "running",
            "socketio": "running"
        }
    }

# Uygulama başlatma
if __name__ == "__main__":
    log.info(f"Uygulama başlatılıyor: {settings.HOST}:{settings.PORT}")
    uvicorn.run(
        "app.main:socket_app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    ) 