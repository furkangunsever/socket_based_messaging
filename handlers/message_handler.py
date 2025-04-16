"""
Mesaj işleme modülü.
Bu modül, socket sunucusuna gelen mesajları, mesaj güncellemelerini 
ve mesaj silme isteklerini işler.
"""

import socket
import uuid
import datetime
import logging
from typing import Dict, List, Any, Optional, Tuple, Set

from utils import json_helper
from handlers.room_manager import RoomManager

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MessageHandler:
    """Mesajların işlenmesini yöneten sınıf."""
    
    def __init__(self, room_manager: RoomManager):
        """Mesaj işleyici sınıfını başlatır.
        
        Args:
            room_manager: Oda yönetimi için RoomManager nesnesi
        """
        self.room_manager = room_manager
        # Oda adına göre mesajları saklar: {oda_adı: [mesaj1, mesaj2, ...]}
        self.room_messages: Dict[str, List[Dict[str, Any]]] = {}
        # Mesaj kimliklerine göre mesajları saklar: {mesaj_kimliği: (oda_adı, mesaj)}
        self.message_lookup: Dict[str, Tuple[str, Dict[str, Any]]] = {}
        # Silinen mesajların kimliklerini tutar
        self.deleted_messages: Set[str] = set()
        # Güncellenmiş mesajların geçmişini tutar: {mesaj_kimliği: [eski_mesaj1, eski_mesaj2, ...]}
        self.message_history: Dict[str, List[Dict[str, Any]]] = {}
        
    def handle_message(self, client_socket: socket.socket, 
                      message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Gelen mesajı işler ve uygun odaya yayınlar.
        
        Args:
            client_socket: Mesajı gönderen istemcinin socket bağlantısı
            message_data: İşlenecek mesaj verisi
            
        Returns:
            İşlenmiş mesaj nesnesi veya hata durumunda None
        """
        # Mesaj türünü kontrol et
        message_type = message_data.get("type", "message")
        
        # Mesaj türüne göre işle
        if message_type == "message":
            return self._handle_new_message(client_socket, message_data)
        elif message_type == "update":
            return self._handle_update_message(client_socket, message_data)
        elif message_type == "delete":
            return self._handle_delete_message(client_socket, message_data)
        else:
            logger.warning(f"Bilinmeyen mesaj türü: {message_type}")
            return None
            
    def _handle_new_message(self, client_socket: socket.socket, 
                           message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Yeni bir mesajı işler.
        
        Args:
            client_socket: Mesajı gönderen istemcinin socket bağlantısı
            message_data: İşlenecek mesaj verisi
            
        Returns:
            İşlenmiş mesaj nesnesi veya hata durumunda None
        """
        # İstemcinin hangi odada olduğunu kontrol et
        room_name = self.room_manager.get_client_room(client_socket)
        if not room_name:
            logger.warning(f"İstemci herhangi bir odada değil")
            return None
            
        # messageId kontrolü - yoksa oluştur
        if "messageId" not in message_data or not message_data["messageId"]:
            message_data["messageId"] = str(uuid.uuid4())
            
        # Zaman damgası kontrolü
        if "timestamp" not in message_data or not message_data["timestamp"]:
            message_data["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
            
        # Mesajı odaya ekle
        message_id = message_data["messageId"]
        
        # Oda için mesaj listesi yoksa oluştur
        if room_name not in self.room_messages:
            self.room_messages[room_name] = []
            
        # Mesajı sakla
        self.room_messages[room_name].append(message_data)
        self.message_lookup[message_id] = (room_name, message_data)
        
        # Başarıyla işlenen mesajı döndür
        return message_data
        
    def _handle_update_message(self, client_socket: socket.socket, 
                              update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Mesaj güncelleme isteğini işler.
        
        Args:
            client_socket: İsteği gönderen istemcinin socket bağlantısı
            update_data: Güncelleme verisi
            
        Returns:
            Güncellenmiş mesaj nesnesi veya hata durumunda None
        """
        # Gerekli alanların kontrolü
        if not all(key in update_data for key in ["messageId", "newContent", "username"]):
            logger.warning("Mesaj güncelleme için gerekli alanlar eksik")
            return None
            
        message_id = update_data["messageId"]
        username = update_data["username"]
        new_content = update_data["newContent"]
        
        # Mesajı bul
        if message_id not in self.message_lookup:
            logger.warning(f"Güncellenecek mesaj bulunamadı: {message_id}")
            return None
            
        # Silinen mesajlar güncellenemez
        if message_id in self.deleted_messages:
            logger.warning(f"Silinen mesaj güncellenemez: {message_id}")
            return None
            
        room_name, message = self.message_lookup[message_id]
        
        # Mesaj sahibi kontrolü
        if message.get("username") != username:
            logger.warning(f"Yetkisiz mesaj güncelleme girişimi: {username} kullanıcısı {message.get('username')} kullanıcısının mesajını güncellemeye çalışıyor")
            return None
            
        # Mevcut mesajın kopyasını geçmişe ekle
        if message_id not in self.message_history:
            self.message_history[message_id] = []
        self.message_history[message_id].append(message.copy())
        
        # Mesajı güncelle
        message["message"] = new_content
        message["updatedAt"] = datetime.datetime.utcnow().isoformat() + "Z"
        message["edited"] = True
        
        # Güncelleme bildirimini hazırla
        update_notification = {
            "type": "update_notification",
            "messageId": message_id,
            "username": username,
            "originalTimestamp": message.get("timestamp"),
            "updatedAt": message["updatedAt"],
            "oldContent": self.message_history[message_id][-1]["message"],
            "newContent": new_content
        }
        
        return update_notification
        
    def _handle_delete_message(self, client_socket: socket.socket, 
                              delete_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Mesaj silme isteğini işler.
        
        Args:
            client_socket: İsteği gönderen istemcinin socket bağlantısı
            delete_data: Silme verisi
            
        Returns:
            Silme bildirim nesnesi veya hata durumunda None
        """
        # Gerekli alanların kontrolü
        if not all(key in delete_data for key in ["messageId", "username"]):
            logger.warning("Mesaj silme için gerekli alanlar eksik")
            return None
            
        message_id = delete_data["messageId"]
        username = delete_data["username"]
        
        # Mesajı bul
        if message_id not in self.message_lookup:
            logger.warning(f"Silinecek mesaj bulunamadı: {message_id}")
            return None
            
        # Zaten silinmiş mi kontrol et
        if message_id in self.deleted_messages:
            logger.warning(f"Mesaj zaten silinmiş: {message_id}")
            return None
            
        room_name, message = self.message_lookup[message_id]
        
        # Mesaj sahibi kontrolü
        if message.get("username") != username:
            logger.warning(f"Yetkisiz mesaj silme girişimi: {username} kullanıcısı {message.get('username')} kullanıcısının mesajını silmeye çalışıyor")
            return None
            
        # Silme işlemi için mesajı işaretle
        self.deleted_messages.add(message_id)
        
        # Mesajın kopyasını geçmişe ekle (silme öncesi durum)
        if message_id not in self.message_history:
            self.message_history[message_id] = []
        self.message_history[message_id].append(message.copy())
        
        # Odadaki mesaj listesinden kaldır
        if room_name in self.room_messages:
            self.room_messages[room_name] = [
                msg for msg in self.room_messages[room_name] 
                if msg.get("messageId") != message_id
            ]
        
        # Silme bildirimini hazırla
        delete_notification = {
            "type": "delete_notification",
            "messageId": message_id,
            "username": username,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "originalTimestamp": message.get("timestamp"),
            "deletedContent": message.get("message", "")
        }
        
        return delete_notification
    
    def broadcast_message_to_room(self, room_name: str, message_data: Dict[str, Any], 
                                sender_socket: Optional[socket.socket] = None) -> bool:
        """Mesajı belirtilen odadaki tüm istemcilere yayınlar.
        
        Args:
            room_name: Mesajın yayınlanacağı oda adı
            message_data: Yayınlanacak mesaj verisi
            sender_socket: Mesajı gönderen istemcinin socket bağlantısı (varsa)
            
        Returns:
            İşlem başarılıysa True, değilse False
        """
        # Mesajı JSON formatına dönüştür
        json_message = json_helper.serialize_message(message_data)
        
        # Odaya yayınla
        success, _ = self.room_manager.broadcast_to_room(room_name, json_message, sender_socket)
        return success
    
    def get_room_messages(self, room_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Belirtilen odadaki mesajları döndürür.
        
        Args:
            room_name: Mesajları istenen oda adı
            limit: Döndürülecek maksimum mesaj sayısı
            
        Returns:
            Oda mesajlarının listesi (en yeniden en eskiye doğru)
        """
        if room_name not in self.room_messages:
            return []
            
        # Silinmiş mesajları filtrele ve en yeni limit kadar mesajı döndür
        messages = [
            msg for msg in self.room_messages[room_name]
            if msg.get("messageId") not in self.deleted_messages
        ]
        
        # Zamanlamaya göre sırala (en yeniden en eskiye)
        messages.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return messages[:limit]
        
    def get_message_by_id(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Mesaj kimliğine göre mesajı döndürür.
        
        Args:
            message_id: İstenen mesajın kimliği
            
        Returns:
            Mesaj nesnesi, bulunamazsa veya silinmişse None
        """
        if message_id in self.deleted_messages:
            return None
            
        if message_id not in self.message_lookup:
            return None
            
        _, message = self.message_lookup[message_id]
        return message
        
    def get_message_history(self, message_id: str) -> List[Dict[str, Any]]:
        """Bir mesajın geçmiş sürümlerini döndürür.
        
        Args:
            message_id: Geçmişi istenen mesajın kimliği
            
        Returns:
            Mesajın geçmiş sürümlerinin listesi (en eskiden en yeniye)
        """
        if message_id not in self.message_history:
            return []
            
        return self.message_history[message_id] 