from typing import Dict, List, Optional
from socketio import AsyncServer
from uuid import uuid4
import hashlib
import asyncio

from app.core.logger import log
from app.models.user import User
from app.models.message import Message
from app.sockets.connection import get_user_by_sid, update_user_activity, get_users_in_room
from app.core.firebase import get_firebase_rooms, get_firebase_room_by_id

# Oda türleri
class RoomType:
    PUBLIC = "public"
    PRIVATE = "private"

# Aktif odalar
# {room_id: {
#   name: str, 
#   type: str, 
#   password_hash: str (optional), 
#   created_by: str, 
#   created_at: str
# }}
active_rooms: Dict[str, Dict] = {}

# Oda mesaj geçmişi
# {room_id: [Message]}
room_messages: Dict[str, List[Message]] = {}

async def load_rooms_from_firebase():
    """
    Firebase'den odaları yükler ve aktif odalara ekler
    """
    try:
        log.info("Firebase'den odalar yükleniyor...")
        # Firebase'den odaları al
        firebase_rooms = await get_firebase_rooms()
        
        # Her bir odayı aktif odalara ekle
        for room_id, room_data in firebase_rooms.items():
            if room_id not in active_rooms:
                active_rooms[room_id] = {
                    'name': room_data.get('name', 'Oda'),
                    'type': room_data.get('type', RoomType.PUBLIC),
                    'password_hash': room_data.get('password_hash', ''),
                    'created_by': room_data.get('created_by', 'system'),
                    'created_at': room_data.get('created_at', '')
                }
                # Mesaj geçmişi için yer aç
                room_messages[room_id] = []
                log.info(f"Oda yüklendi: {room_id} - {room_data.get('name', 'Oda')}")
                
        log.info(f"Firebase'den {len(firebase_rooms)} oda yüklendi")
        
        # Toplam aktif oda sayısını log'la
        log.info(f"Toplam aktif oda sayısı: {len(active_rooms)}")
    except Exception as e:
        log.error(f"Firebase'den oda yüklenirken hata: {str(e)}")

def hash_password(password: str) -> str:
    """
    Şifre için basit hash oluşturur
    """
    if not password:
        return ""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed_password: str) -> bool:
    """
    Şifre doğrulaması yapar
    """
    if not hashed_password:  # Şifre yoksa
        return True
    if not password:  # Şifre gerekliyse ama verilmediyse
        return False
    return hash_password(password) == hashed_password

async def handle_create_room(sio: AsyncServer, sid: str, data: Dict) -> Optional[str]:
    """
    Yeni bir oda oluşturur
    """
    try:
        user = get_user_by_sid(sid)
        if not user:
            await sio.emit('error', {'message': 'Kullanıcı bulunamadı'}, to=sid)
            return None
            
        update_user_activity(sid)
        
        room_name = data.get('name', 'Yeni Oda')
        room_type = data.get('type', RoomType.PUBLIC)
        
        # Oda türünü doğrula
        if room_type not in [RoomType.PUBLIC, RoomType.PRIVATE]:
            room_type = RoomType.PUBLIC
        
        # Şifre varsa hash'le
        password = data.get('password', '')
        password_hash = hash_password(password) if room_type == RoomType.PRIVATE and password else ""
        
        room_id = str(uuid4())
        
        # Odayı aktif odalara ekle
        active_rooms[room_id] = {
            'name': room_name,
            'type': room_type,
            'password_hash': password_hash,
            'created_by': user.id,
            'created_at': user.last_activity.isoformat()
        }
        
        # Mesaj geçmişi için yer aç
        room_messages[room_id] = []
        
        log.info(f"Oda oluşturuldu: {room_name} (id: {room_id}, tür: {room_type}) - Oluşturan: {user.username}")
        
        # Kullanıcıyı odaya katılmadan önce bilgilendir
        await sio.emit('room_created', {
            'room_id': room_id,
            'name': room_name,
            'type': room_type,
            'is_password_protected': bool(password_hash),
            'created_by': user.id
        })
        
        # Tüm istemcilere güncel oda listesini gönder
        await sio.emit('rooms_list', get_active_rooms())
        
        return room_id
    except Exception as e:
        log.error(f"Oda oluşturma hatası: {str(e)}")
        await sio.emit('error', {'message': 'Oda oluşturulurken hata oluştu'}, to=sid)
        return None

async def handle_join_room(sio: AsyncServer, sid: str, data: Dict) -> bool:
    """
    Kullanıcının odaya katılmasını işler
    """
    try:
        room_id = data.get('room_id')
        if not room_id:
            await sio.emit('error', {'message': 'Oda ID belirtilmedi'}, to=sid)
            return False
            
        # Oda aktif odalarda yoksa, Firebase'den kontrol et
        if room_id not in active_rooms:
            try:
                log.info(f"Oda aktif odalarda bulunamadı: {room_id}, Firebase'den kontrol ediliyor...")
                firebase_room = await get_firebase_room_by_id(room_id)
                if firebase_room:
                    # Firebase'de varsa aktif odalara ekle
                    active_rooms[room_id] = {
                        'name': firebase_room.get('name', 'Oda'),
                        'type': firebase_room.get('type', RoomType.PUBLIC),
                        'password_hash': firebase_room.get('password_hash', ''),
                        'created_by': firebase_room.get('created_by', 'system'),
                        'created_at': firebase_room.get('created_at', '')
                    }
                    # Mesaj geçmişi için yer aç
                    room_messages[room_id] = []
                    log.info(f"Oda Firebase'den yüklendi: {room_id} - {firebase_room.get('name', 'Oda')}")
                else:
                    log.warning(f"Oda Firebase'de bulunamadı: {room_id}")
                    await sio.emit('error', {'message': 'Geçersiz oda ID'}, to=sid)
                    return False
            except Exception as e:
                log.error(f"Firebase oda kontrolünde hata: {str(e)}")
                await sio.emit('error', {'message': 'Oda kontrolünde sunucu hatası'}, to=sid)
                return False
        
        user = get_user_by_sid(sid)
        if not user:
            await sio.emit('error', {'message': 'Kullanıcı bulunamadı'}, to=sid)
            return False
            
        update_user_activity(sid)
        
        # Oda bilgilerini al
        room_info = active_rooms[room_id]
        
        # Özel oda için şifre doğrulaması yap
        if room_info['type'] == RoomType.PRIVATE and room_info['password_hash']:
            password = data.get('password', '')
            if not verify_password(password, room_info['password_hash']):
                await sio.emit('error', {'message': 'Geçersiz oda şifresi'}, to=sid)
                return False
        
        # Kullanıcı başka bir odadaysa, önce o odadan çıkar
        if user.room_id:
            await handle_leave_room(sio, sid, {'room_id': user.room_id})
        
        # Kullanıcıyı odaya ekle
        await sio.enter_room(sid, room_id)
        user.room_id = room_id
        
        log.info(f"Kullanıcı odaya katıldı: {user.username} - Oda: {room_info['name']} (id: {room_id})")
        
        # Sistem mesajı oluştur
        system_message = Message(
            room_id=room_id,
            user_id=user.id,
            username=user.username,
            content=f"{user.username} odaya katıldı",
            is_system_message=True
        )
        
        # Mesajı geçmişe ekle
        room_messages[room_id].append(system_message)
        
        # Odadaki tüm kullanıcılara bildir
        await sio.emit('user_joined_room', {
            'user': user.to_dict(),
            'room': {
                'id': room_id,
                'name': room_info['name'],
                'type': room_info['type'],
                'is_password_protected': bool(room_info['password_hash'])
            }
        }, room=room_id)
        
        # Sistem mesajını gönder
        await sio.emit('message', system_message.to_dict(), room=room_id)
        
        # Kullanıcıya oda bilgilerini gönder
        await sio.emit('room_info', {
            'room': {
                'id': room_id,
                'name': room_info['name'],
                'type': room_info['type'],
                'is_password_protected': bool(room_info['password_hash'])
            },
            'users': [u.to_dict() for u in get_users_in_room(room_id)],
            'messages': [m.to_dict() for m in room_messages[room_id][-50:]]  # Son 50 mesaj
        }, to=sid)
        
        return True
    except Exception as e:
        log.error(f"Odaya katılma hatası: {str(e)}")
        await sio.emit('error', {'message': 'Odaya katılırken hata oluştu'}, to=sid)
        return False

async def handle_leave_room(sio: AsyncServer, sid: str, data: Dict) -> bool:
    """
    Kullanıcının odadan ayrılmasını işler
    """
    try:
        room_id = data.get('room_id')
        if not room_id or room_id not in active_rooms:
            await sio.emit('error', {'message': 'Geçersiz oda ID'}, to=sid)
            return False
            
        user = get_user_by_sid(sid)
        if not user or user.room_id != room_id:
            await sio.emit('error', {'message': 'Kullanıcı bu odada değil'}, to=sid)
            return False
            
        update_user_activity(sid)
        
        # Kullanıcıyı odadan çıkar
        await sio.leave_room(sid, room_id)
        
        # Sistem mesajı oluştur
        system_message = Message(
            room_id=room_id,
            user_id=user.id,
            username=user.username,
            content=f"{user.username} odadan ayrıldı",
            is_system_message=True
        )
        
        # Mesajı geçmişe ekle
        room_messages[room_id].append(system_message)
        
        # Kullanıcının oda bilgisini temizle
        old_room_id = user.room_id
        user.room_id = None
        
        log.info(f"Kullanıcı odadan ayrıldı: {user.username} - Oda: {active_rooms[old_room_id]['name']} (id: {old_room_id})")
        
        # Odadaki diğer kullanıcılara bildir
        await sio.emit('user_left_room', {
            'user_id': user.id,
            'username': user.username,
            'room_id': old_room_id
        }, room=old_room_id)
        
        # Sistem mesajını gönder
        await sio.emit('message', system_message.to_dict(), room=old_room_id)
        
        if len(get_users_in_room(old_room_id)) == 0:
            # Oda boş durumda ama silmiyoruz
            log.info(f"Oda boş kaldı: {old_room_id}")
        
        return True
    except Exception as e:
        log.error(f"Odadan ayrılma hatası: {str(e)}")
        await sio.emit('error', {'message': 'Odadan ayrılırken hata oluştu'}, to=sid)
        return False

def get_active_rooms() -> List[Dict]:
    """
    Aktif odaların listesini döndürür
    """
    result = []
    for room_id, room_data in active_rooms.items():
        users = get_users_in_room(room_id)
        result.append({
            'id': room_id,
            'name': room_data['name'],
            'type': room_data['type'],
            'is_password_protected': bool(room_data.get('password_hash', '')),
            'created_at': room_data['created_at'],
            'user_count': len(users)
        })
    return result

def register_room_events(sio: AsyncServer):
    """
    Socket.IO oda olaylarını kaydetme
    """
    @sio.event
    async def create_room(sid, data):
        """
        Yeni bir oda oluşturur
        
        Parametreler:
        - name: str - Oda adı
        - type: str - Oda türü ('public' veya 'private')
        - password: str - (İsteğe bağlı) Özel oda için şifre
        """
        return await handle_create_room(sio, sid, data)

    @sio.event
    async def join_room(sid, data):
        """
        Kullanıcının odaya katılmasını sağlar
        
        Parametreler:
        - room_id: str - Katılmak istenen odanın ID'si
        - password: str - (Gerekirse) Özel oda için şifre
        """
        return await handle_join_room(sio, sid, data)

    @sio.event
    async def leave_room(sid, data):
        """
        Kullanıcının odadan ayrılmasını sağlar
        
        Parametreler:
        - room_id: str - Ayrılmak istenen odanın ID'si
        """
        return await handle_leave_room(sio, sid, data)

    @sio.event
    async def get_rooms(sid):
        """
        Mevcut odaların listesini döndürür
        """
        update_user_activity(sid)
        rooms = get_active_rooms()
        log.info(f"Oda listesi isteği: {len(rooms)} oda gönderildi")
        await sio.emit('rooms_list', rooms, to=sid)
    
    # Firebase'den odaları yükle
    asyncio.create_task(load_rooms_from_firebase())
        
    log.info("Socket.IO oda olayları kaydedildi") 