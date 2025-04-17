from typing import Dict, List, Optional, Tuple
from socketio import AsyncServer
from datetime import datetime

from app.core.logger import log
from app.models.message import Message, TypingStatus
from app.sockets.connection import get_user_by_sid, update_user_activity
from app.sockets.room import room_messages

# Mesaj ID'lerine doğrudan erişim için sözlük
# {message_id: (room_id, Message)}
message_by_id: Dict[str, Tuple[str, Message]] = {}

async def handle_send_message(sio: AsyncServer, sid: str, data: Dict) -> bool:
    """
    Kullanıcının mesaj göndermesini işler
    """
    try:
        user = get_user_by_sid(sid)
        if not user:
            await sio.emit('error', {'message': 'Kullanıcı bulunamadı'}, to=sid)
            return False
            
        room_id = data.get('room_id')
        content = data.get('content')
        
        if not room_id or not content or not user.room_id or user.room_id != room_id:
            await sio.emit('error', {'message': 'Geçersiz mesaj veya oda'}, to=sid)
            return False
            
        update_user_activity(sid)
        
        # Mesaj nesnesi oluştur
        message = Message(
            room_id=room_id,
            user_id=user.id,
            username=user.username,
            content=content
        )
        
        # Mesajı geçmişe ekle
        room_messages[room_id].append(message)
        
        # Mesaj ID'sine doğrudan erişim için sözlüğe ekle
        message_by_id[message.id] = (room_id, message)
        
        # Mesajı odadaki tüm kullanıcılara gönder
        message_dict = message.to_dict()
        await sio.emit('message', message_dict, room=room_id)
        
        log.info(f"Mesaj gönderildi: {user.username} - Oda: {room_id} - İçerik: {content[:30]}...")
        
        return True
    except Exception as e:
        log.error(f"Mesaj gönderme hatası: {str(e)}")
        await sio.emit('error', {'message': 'Mesaj gönderilirken hata oluştu'}, to=sid)
        return False

async def handle_update_message(sio: AsyncServer, sid: str, data: Dict) -> bool:
    """
    Kullanıcının mesaj güncellemesini işler
    """
    try:
        user = get_user_by_sid(sid)
        if not user:
            await sio.emit('error', {'message': 'Kullanıcı bulunamadı'}, to=sid)
            return False
            
        message_id = data.get('messageId')
        new_content = data.get('content')
        
        if not message_id or not new_content or message_id not in message_by_id:
            await sio.emit('error', {'message': 'Geçersiz mesaj ID veya içerik'}, to=sid)
            return False
        
        # Mesajı sözlükten al
        room_id, message = message_by_id[message_id]
        
        # Mesajı güncelleme yetkisi kontrolü
        if message.user_id != user.id:
            await sio.emit('error', {'message': 'Bu mesajı güncelleme yetkiniz yok'}, to=sid)
            return False
            
        update_user_activity(sid)
        
        # Mesaj içeriğini güncelle
        original_content = message.content
        message.content = new_content
        
        # Düzenleme bilgisi ekle
        message.edited = True
        message.edited_at = datetime.now()
        
        # Güncellenen mesajı odadaki tüm kullanıcılara bildir
        message_dict = message.to_dict()
        await sio.emit('message_updated', message_dict, room=room_id)
        
        log.info(f"Mesaj güncellendi: {user.username} - Oda: {room_id} - Mesaj ID: {message_id}")
        log.debug(f"Eski içerik: {original_content[:30]}... - Yeni içerik: {new_content[:30]}...")
        
        return True
    except Exception as e:
        log.error(f"Mesaj güncelleme hatası: {str(e)}")
        await sio.emit('error', {'message': 'Mesaj güncellenirken hata oluştu'}, to=sid)
        return False

async def handle_delete_message(sio: AsyncServer, sid: str, data: Dict) -> bool:
    """
    Kullanıcının mesaj silmesini işler
    """
    try:
        user = get_user_by_sid(sid)
        if not user:
            await sio.emit('error', {'message': 'Kullanıcı bulunamadı'}, to=sid)
            return False
            
        message_id = data.get('messageId')
        
        if not message_id or message_id not in message_by_id:
            await sio.emit('error', {'message': 'Geçersiz mesaj ID'}, to=sid)
            return False
        
        # Mesajı sözlükten al
        room_id, message = message_by_id[message_id]
        
        # Mesajı silme yetkisi kontrolü
        if message.user_id != user.id:
            await sio.emit('error', {'message': 'Bu mesajı silme yetkiniz yok'}, to=sid)
            return False
            
        update_user_activity(sid)
        
        # Mesajı oda geçmişinden bul ve işaretle
        message.deleted = True
        message.content = "[Bu mesaj silindi]"
        
        # Silinen mesaj bilgisini odadaki tüm kullanıcılara bildir
        await sio.emit('message_deleted', {
            'messageId': message_id,
            'roomId': room_id,
            'deletedBy': user.id,
            'deletedAt': datetime.now().isoformat()
        }, room=room_id)
        
        log.info(f"Mesaj silindi: {user.username} - Oda: {room_id} - Mesaj ID: {message_id}")
        
        return True
    except Exception as e:
        log.error(f"Mesaj silme hatası: {str(e)}")
        await sio.emit('error', {'message': 'Mesaj silinirken hata oluştu'}, to=sid)
        return False

async def handle_typing_status(sio: AsyncServer, sid: str, data: Dict) -> bool:
    """
    Kullanıcının yazma durumunu işler
    """
    try:
        user = get_user_by_sid(sid)
        if not user:
            return False
            
        room_id = data.get('room_id')
        is_typing = data.get('is_typing', False)
        
        if not room_id or not user.room_id or user.room_id != room_id:
            return False
            
        update_user_activity(sid)
        
        # Yazma durumu nesnesi oluştur
        typing_status = TypingStatus(
            user_id=user.id,
            room_id=room_id,
            username=user.username,
            is_typing=is_typing
        )
        
        # Odadaki diğer kullanıcılara durum bildirimi gönder
        await sio.emit('typing_status', typing_status.dict(), room=room_id, skip_sid=sid)
        
        return True
    except Exception as e:
        log.error(f"Yazma durumu bildirimi hatası: {str(e)}")
        return False

async def handle_broadcast_message(sio: AsyncServer, sid: str, data: Dict) -> bool:
    """
    İstemciden gelen mesajı tüm bağlı istemcilere broadcast eder
    """
    try:
        # Gerekli alanların kontrolü
        required_fields = ['username', 'deviceId', 'message', 'timestamp', 'source']
        for field in required_fields:
            if field not in data:
                await sio.emit('error', {'message': f'Eksik alan: {field}'}, to=sid)
                return False
        
        # Kullanıcı mesaj gönderme zamanını güncelle
        update_user_activity(sid)
        
        # Mesaj verisini olduğu gibi kullan
        message_data = {
            'username': data['username'],
            'deviceId': data['deviceId'],
            'message': data['message'],
            'timestamp': data['timestamp'],
            'source': data['source'],
            'server_received_at': datetime.now().isoformat()
        }
        
        # Mesajı tüm bağlı istemcilere gönder
        await sio.emit('broadcast_message', message_data)
        
        log.info(f"Broadcast mesaj gönderildi: {data['username']} - Mesaj: {data['message'][:30]}...")
        
        return True
    except Exception as e:
        log.error(f"Broadcast mesaj hatası: {str(e)}")
        await sio.emit('error', {'message': 'Mesaj broadcast edilirken hata oluştu'}, to=sid)
        return False

def register_message_events(sio: AsyncServer):
    """
    Socket.IO mesaj olaylarını kaydetme
    """
    @sio.event
    async def send_message(sid, data):
        """
        Oda içinde mesaj gönderme
        """
        return await handle_send_message(sio, sid, data)
    
    @sio.event
    async def broadcast_message(sid, data):
        """
        Tüm bağlı istemcilere mesaj yayınlama
        """
        return await handle_broadcast_message(sio, sid, data)
    
    @sio.event
    async def typing_status(sid, data):
        """
        Kullanıcı yazıyor durumunu yönetir
        """
        return await handle_typing_status(sio, sid, data)
    
    log.info("Socket.IO mesaj olayları kaydedildi")

def register_message_edit_events(sio: AsyncServer):
    """
    Socket.IO mesaj düzenleme olaylarını kaydetme
    """
    @sio.event
    async def update_message(sid, data):
        """
        Mevcut bir mesajı günceller
        
        Parametreler:
        - messageId: str - Güncellenecek mesajın ID'si
        - content: str - Yeni mesaj içeriği
        """
        return await handle_update_message(sio, sid, data)
    
    @sio.event
    async def delete_message(sid, data):
        """
        Mevcut bir mesajı siler
        
        Parametreler:
        - messageId: str - Silinecek mesajın ID'si
        """
        return await handle_delete_message(sio, sid, data)
    
    log.info("Socket.IO mesaj düzenleme olayları kaydedildi") 