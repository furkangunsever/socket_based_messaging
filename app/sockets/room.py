from typing import Dict, List, Optional
from socketio import AsyncServer
from uuid import uuid4
import hashlib
import asyncio

from app.core.logger import log
from app.models.user import User
from app.models.message import Message
from app.sockets.connection import get_user_by_sid, update_user_activity, get_users_in_room
from app.core.firebase import get_firebase_rooms, get_firebase_room_by_id, save_room_to_firebase

# Oda türleri
class RoomType:
    PUBLIC = "public"
    PRIVATE = "private"

# Aktif odalar
active_rooms: Dict[str, Dict] = {}

# Oda mesaj geçmişi
room_messages: Dict[str, List[Message]] = {}

async def load_rooms_from_firebase():
    try:
        log.info("Firebase'den odalar yükleniyor...")
        firebase_rooms = await get_firebase_rooms()
        for room_id, room_data in firebase_rooms.items():
            if room_id not in active_rooms:
                active_rooms[room_id] = {
                    'name': room_data.get('name', 'Oda'),
                    'type': room_data.get('type', RoomType.PUBLIC),
                    'password_hash': room_data.get('password_hash', ''),
                    'created_by': room_data.get('created_by', 'system'),
                    'created_at': room_data.get('created_at', '')
                }
                room_messages[room_id] = []
                log.info(f"Oda yüklendi: {room_id} - {room_data.get('name', 'Oda')}")
        log.info(f"Firebase'den {len(firebase_rooms)} oda yüklendi")
        log.info(f"Toplam aktif oda sayısı: {len(active_rooms)}")
    except Exception as e:
        log.error(f"Firebase'den oda yüklenirken hata: {str(e)}")

async def sync_rooms_from_client(sio: AsyncServer, sid: str, room_ids: List[str]):
    try:
        log.info(f"Oda senkronizasyonu isteği alındı: {room_ids}")
        for room_id in room_ids:
            if room_id not in active_rooms:
                try:
                    firebase_room = await get_firebase_room_by_id(room_id)
                    if firebase_room:
                        active_rooms[room_id] = {
                            'name': firebase_room.get('name', 'Isimsiz Oda'),
                            'type': firebase_room.get('type', 'public'),
                            'password_hash': firebase_room.get('password_hash', ''),
                            'created_by': firebase_room.get('created_by', 'system'),
                            'created_at': firebase_room.get('created_at', '')
                        }
                        room_messages[room_id] = []
                        log.info(f"Oda senkronize edildi: {room_id} - {firebase_room.get('name', 'Isimsiz Oda')}")
                except Exception as e:
                    log.error(f"Oda senkronizasyonu sırasında hata: {str(e)}")
        rooms = get_active_rooms()
        log.info(f"Senkronizasyon sonrası oda listesi gönderiliyor: {len(rooms)} oda")
        await sio.emit('rooms_list', rooms, to=sid)
        return True
    except Exception as e:
        log.error(f"Oda senkronizasyonu hatası: {str(e)}")
        return False

def hash_password(password: str) -> str:
    if not password:
        return ""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return True
    if not password:
        return False
    return hash_password(password) == hashed_password

async def handle_create_room(sio: AsyncServer, sid: str, data: Dict) -> Optional[str]:
    try:
        user = get_user_by_sid(sid)
        if not user:
            await sio.emit('error', {'message': 'Kullanıcı bulunamadı'}, to=sid)
            return None

        update_user_activity(sid)

        room_name = data.get('name', 'Yeni Oda')
        room_type = data.get('type', RoomType.PUBLIC)
        if room_type not in [RoomType.PUBLIC, RoomType.PRIVATE]:
            room_type = RoomType.PUBLIC

        password = data.get('password', '')
        password_hash = hash_password(password) if room_type == RoomType.PRIVATE and password else ""

        room_id = str(uuid4())
        room_data = {
            'name': room_name,
            'type': room_type,
            'password_hash': password_hash,
            'created_by': user.id,
            'created_at': user.last_activity.isoformat()
        }

        active_rooms[room_id] = room_data
        room_messages[room_id] = []

        log.info(f"Oda oluşturuldu: {room_name} (id: {room_id}, tür: {room_type}) - Oluşturan: {user.username}")

        firebase_data = dict(room_data)
        firebase_result = await save_room_to_firebase(room_id, firebase_data)
        if firebase_result:
            log.info(f"Oda Firebase'e kaydedildi: {room_id}")
        else:
            log.warning(f"Oda Firebase'e kaydedilemedi: {room_id}")

        await sio.emit('room_created', {
            'room_id': room_id,
            'name': room_name,
            'type': room_type,
            'is_password_protected': bool(password_hash),
            'created_by': user.id
        })

        await sio.emit('rooms_list', get_active_rooms())
        return room_id
    except Exception as e:
        log.error(f"Oda oluşturma hatası: {str(e)}")
        await sio.emit('error', {'message': 'Oda oluşturulurken hata oluştu'}, to=sid)
        return None

async def handle_join_room(sio: AsyncServer, sid: str, data: Dict) -> bool:
    try:
        room_id = data.get('room_id')
        if not room_id:
            await sio.emit('error', {'message': 'Oda ID belirtilmedi'}, to=sid)
            return False

        if room_id not in active_rooms:
            try:
                log.info(f"Oda aktif odalarda bulunamadı: {room_id}, Firebase'den kontrol ediliyor...")
                firebase_room = await get_firebase_room_by_id(room_id)
                if firebase_room:
                    active_rooms[room_id] = {
                        'name': firebase_room.get('name', 'Oda'),
                        'type': firebase_room.get('type', RoomType.PUBLIC),
                        'password_hash': firebase_room.get('password_hash', ''),
                        'created_by': firebase_room.get('created_by', 'system'),
                        'created_at': firebase_room.get('created_at', '')
                    }
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
        room_info = active_rooms[room_id]

        if room_info['type'] == RoomType.PRIVATE and room_info['password_hash']:
            password = data.get('password', '')
            if not verify_password(password, room_info['password_hash']):
                await sio.emit('error', {'message': 'Geçersiz oda şifresi'}, to=sid)
                return False

        if user.room_id:
            await handle_leave_room(sio, sid, {'room_id': user.room_id})

        await sio.enter_room(sid, room_id)
        user.room_id = room_id

        log.info(f"Kullanıcı odaya katıldı: {user.username} - Oda: {room_info['name']} (id: {room_id})")

        system_message = Message(
            room_id=room_id,
            user_id=user.id,
            username=user.username,
            content=f"{user.username} odaya katıldı",
            is_system_message=True
        )
        room_messages[room_id].append(system_message)

        await sio.emit('user_joined_room', {
            'user': user.to_dict(),
            'room': {
                'id': room_id,
                'name': room_info['name'],
                'type': room_info['type'],
                'is_password_protected': bool(room_info['password_hash'])
            }
        }, room=room_id)

        await sio.emit('message', system_message.to_dict(), room=room_id)

        await sio.emit('room_info', {
            'room': {
                'id': room_id,
                'name': room_info['name'],
                'type': room_info['type'],
                'is_password_protected': bool(room_info['password_hash'])
            },
            'users': [u.to_dict() for u in get_users_in_room(room_id)],
            'messages': [m.to_dict() for m in room_messages[room_id][-50:]]
        }, to=sid)

        return True
    except Exception as e:
        log.error(f"Odaya katılma hatası: {str(e)}")
        await sio.emit('error', {'message': 'Odaya katılırken hata oluştu'}, to=sid)
        return False

async def handle_leave_room(sio: AsyncServer, sid: str, data: Dict) -> bool:
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

        await sio.leave_room(sid, room_id)

        system_message = Message(
            room_id=room_id,
            user_id=user.id,
            username=user.username,
            content=f"{user.username} odadan ayrıldı",
            is_system_message=True
        )
        room_messages[room_id].append(system_message)

        old_room_id = user.room_id
        user.room_id = None

        log.info(f"Kullanıcı odadan ayrıldı: {user.username} - Oda: {active_rooms[old_room_id]['name']} (id: {old_room_id})")

        await sio.emit('user_left_room', {
            'user_id': user.id,
            'username': user.username,
            'room_id': old_room_id
        }, room=old_room_id)

        await sio.emit('message', system_message.to_dict(), room=old_room_id)

        if len(get_users_in_room(old_room_id)) == 0:
            log.info(f"Oda boş kaldı: {old_room_id}")

        return True
    except Exception as e:
        log.error(f"Odadan ayrılma hatası: {str(e)}")
        await sio.emit('error', {'message': 'Odadan ayrılırken hata oluştu'}, to=sid)
        return False

def get_active_rooms() -> List[Dict]:
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
    @sio.event
    async def create_room(sid, data):
        return await handle_create_room(sio, sid, data)

    @sio.event
    async def join_room(sid, data):
        return await handle_join_room(sio, sid, data)

    @sio.event
    async def leave_room(sid, data):
        return await handle_leave_room(sio, sid, data)

    @sio.event
    async def get_rooms(sid, data=None):
        update_user_activity(sid)
        if len(active_rooms) == 0:
            log.info("Aktif oda yok veya az, Firebase'den odalar yükleniyor...")
            await load_rooms_from_firebase()
        rooms = get_active_rooms()
        log.info(f"Oda listesi isteği: {len(rooms)} oda gönderildi")
        await sio.emit('rooms_list', rooms, to=sid)

    @sio.event
    async def sync_rooms(sid, data):
        room_ids = data.get('room_ids', [])
        return await sync_rooms_from_client(sio, sid, room_ids)

    @sio.event
    async def sync_firebase_rooms(sid, data=None):
        log.info(f"Firebase odaları senkronizasyonu başlatılıyor: {sid}")
        await load_rooms_from_firebase()
        rooms = get_active_rooms()
        await sio.emit('rooms_list', rooms, to=sid)
