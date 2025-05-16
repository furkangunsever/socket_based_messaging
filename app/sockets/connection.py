from typing import Dict, Optional, List
from socketio import AsyncServer
from datetime import datetime

from app.core.logger import log
from app.models.user import User, UserSession

# Aktif kullanıcıları saklayan sözlük
# {socket_id: UserSession}
active_connections: Dict[str, UserSession] = {}

async def handle_connect(sio: AsyncServer, sid: str, data: Dict):
    """
    Yeni bir kullanıcı bağlantısını işler
    """
    try:
        username = data.get('username')
        if not username:
            await sio.emit('error', {'message': 'Kullanıcı adı gerekli'}, to=sid)
            return False
        
        # Kullanıcı nesnesi oluştur
        user = User(username=username)
        
        # Kullanıcıyı aktif bağlantılara ekle
        active_connections[sid] = UserSession(sid=sid, user=user)
        
        log.info(f"Kullanıcı bağlandı: {username} (sid: {sid})")
        
        # Kullanıcıya başarılı bağlantı bilgisini gönder
        await sio.emit('connect_response', {
            'status': 'success',
            'user': user.to_dict()
        }, to=sid)
        
        # Firebase'den odaları yükle ve senkronize et
        log.info(f"Firebase odaları senkronize ediliyor: {sid}")
        await sio.emit('sync_firebase_rooms', {}, to=sid)
        
        # Odaların listesini gönder - Lazy import ile döngüsel import önlendi
        from app.sockets.room import get_active_rooms
        rooms = get_active_rooms()
        log.info(f"Kullanıcı bağlantısında oda listesi gönderiliyor: {len(rooms)} oda")
        await sio.emit('rooms_list', rooms, to=sid)
        
        # Diğer kullanıcılara bildirim gönder
        await sio.emit('user_connected', {
            'user': user.to_dict()
        }, skip_sid=sid)
        
        return True
    except Exception as e:
        log.error(f"Bağlantı hatası: {str(e)}")
        await sio.emit('error', {'message': 'Bağlantı hatası oluştu'}, to=sid)
        return False

async def handle_disconnect(sio: AsyncServer, sid: str):
    """
    Kullanıcı bağlantı kesme işlemini yönetir
    """
    if sid in active_connections:
        user_session = active_connections[sid]
        user = user_session.user
        
        # Kullanıcı bir odadaysa, odadan çıkar
        if user.room_id:
            await sio.leave_room(sid, user.room_id)
            
            # Odadaki diğer kullanıcılara bildir
            await sio.emit('user_left_room', {
                'user_id': user.id,
                'username': user.username,
                'room_id': user.room_id
            }, room=user.room_id)
        
        # Aktif bağlantılardan kaldır
        del active_connections[sid]
        
        log.info(f"Kullanıcı bağlantısı kesildi: {user.username} (sid: {sid})")
        
        # Tüm kullanıcılara bildir
        await sio.emit('user_disconnected', {
            'user_id': user.id,
            'username': user.username
        })

def get_user_by_sid(sid: str) -> Optional[User]:
    """
    Socket ID ile kullanıcıyı döndürür
    """
    if sid in active_connections:
        return active_connections[sid].user
    return None

def get_users_in_room(room_id: str) -> List[User]:
    """
    Belirli bir odadaki tüm kullanıcıları döndürür
    """
    return [
        session.user for session in active_connections.values()
        if session.user.room_id == room_id
    ]

def get_all_active_users() -> List[User]:
    """
    Tüm aktif kullanıcıları döndürür
    """
    return [session.user for session in active_connections.values()]

def update_user_activity(sid: str):
    """
    Kullanıcının son etkinlik zamanını günceller
    """
    if sid in active_connections:
        active_connections[sid].user.last_activity = datetime.now()

def register_connection_events(sio: AsyncServer):
    """
    Socket.IO bağlantı olaylarını kaydetme
    """
    @sio.event
    async def connect(sid, environ, auth=None):
        """
        Yeni bir bağlantıyı yönetir
        """
        log.info(f"Yeni bağlantı: {sid}")
        
        # İlk bağlantıda auth bilgilerini bekle, işlem yapmadan geç
        return True

    @sio.event
    async def disconnect(sid):
        """
        Bağlantı kesme olayını yönetir
        """
        await handle_disconnect(sio, sid)

    @sio.event
    async def authenticate(sid, data):
        """
        Kullanıcı kimlik doğrulama
        """
        return await handle_connect(sio, sid, data)
        
    log.info("Socket.IO bağlantı olayları kaydedildi") 