"""
Oda yönetimi için gerekli sınıflar ve fonksiyonlar.
Bu modül, sohbet odalarının oluşturulması, yönetilmesi ve mesaj dağıtımı işlevlerini içerir.
"""

import socket
import threading
import json
import datetime
from typing import Dict, List, Set, Optional, Any, Tuple, Callable

from utils import json_helper


class Room:
    """Sohbet odası sınıfı."""
    
    def __init__(self, 
                 room_name: str, 
                 room_type: str = "public", 
                 password: Optional[str] = None, 
                 created_by: str = "SERVER"):
        """Yeni bir sohbet odası oluşturur.
        
        Args:
            room_name: Oda adı
            room_type: Oda tipi ("public" veya "private")
            password: Özel odalar için şifre
            created_by: Odayı oluşturan kullanıcı adı
        """
        self.room_name = room_name
        self.room_type = room_type
        self.password = password
        self.created_by = created_by
        self.created_at = datetime.datetime.now()
        self.clients: Set[socket.socket] = set()
        self.client_usernames: Dict[socket.socket, str] = {}
        
    def add_client(self, client_socket: socket.socket, username: str) -> bool:
        """Odaya bir istemci ekler.
        
        Args:
            client_socket: İstemci socket nesnesi
            username: İstemcinin kullanıcı adı
            
        Returns:
            İşlem başarılıysa True, değilse False
        """
        if client_socket in self.clients:
            return False
            
        self.clients.add(client_socket)
        self.client_usernames[client_socket] = username
        return True
        
    def remove_client(self, client_socket: socket.socket) -> Tuple[bool, Optional[str]]:
        """Odadan bir istemciyi çıkarır.
        
        Args:
            client_socket: İstemci socket nesnesi
            
        Returns:
            (başarı, kullanıcı_adı) tuple:
                - başarı: İşlem başarılıysa True, istemci bulunamazsa False
                - kullanıcı_adı: Çıkarılan istemcinin kullanıcı adı, bulunamazsa None
        """
        if client_socket not in self.clients:
            return False, None
            
        username = self.client_usernames.get(client_socket)
        self.clients.remove(client_socket)
        
        if client_socket in self.client_usernames:
            del self.client_usernames[client_socket]
            
        return True, username
        
    def check_password(self, password: Optional[str]) -> bool:
        """Verilen şifrenin oda şifresiyle eşleşip eşleşmediğini kontrol eder.
        
        Args:
            password: Kontrol edilecek şifre
            
        Returns:
            Şifre doğruysa veya oda herkese açıksa True, değilse False
        """
        # Public odalar şifre gerektirmez
        if self.room_type == "public":
            return True
            
        # Private odalar şifre gerektirir
        if not self.password:
            return False
            
        return self.password == password
        
    def broadcast(self, message: str, sender_socket: Optional[socket.socket] = None,
                 broadcast_callback: Optional[Callable] = None) -> List[socket.socket]:
        """Odadaki tüm istemcilere mesaj gönderir.
        
        Args:
            message: Gönderilecek mesaj (JSON string)
            sender_socket: Mesajı gönderen istemci (varsa bu istemciye gönderilmez)
            broadcast_callback: Her istemciye mesaj göndermek için kullanılacak callback
            
        Returns:
            Bağlantısı kopan istemcilerin listesi
        """
        disconnected_clients = []
        
        # Callback tanımlıysa callback ile gönder
        if broadcast_callback:
            for client in self.clients:
                if client != sender_socket:
                    if not broadcast_callback(client, message):
                        disconnected_clients.append(client)
            return disconnected_clients
        
        # Callback tanımlı değilse varsayılan gönderim yöntemi
        for client in self.clients:
            if client != sender_socket:
                try:
                    client.send(message.encode('utf-8'))
                except:
                    disconnected_clients.append(client)
                    
        return disconnected_clients
        
    def get_client_count(self) -> int:
        """Odadaki istemci sayısını döndürür."""
        return len(self.clients)
        
    def get_info(self) -> Dict[str, Any]:
        """Oda bilgilerini içeren bir sözlük döndürür."""
        return {
            "roomName": self.room_name,
            "roomType": self.room_type,
            "hasPassword": bool(self.password),
            "createdBy": self.created_by,
            "createdAt": self.created_at.isoformat(),
            "clientCount": self.get_client_count(),
            "clients": list(self.client_usernames.values())
        }


class RoomManager:
    """Sohbet odalarını yöneten sınıf."""
    
    def __init__(self, broadcast_callback: Optional[Callable] = None):
        """Oda yöneticisini başlatır.
        
        Args:
            broadcast_callback: İstemcilere mesaj göndermek için kullanılacak fonksiyon
                Callback şu imzaya sahip olmalı: func(client_socket, message) -> bool
        """
        self.rooms: Dict[str, Room] = {}
        self.client_rooms: Dict[socket.socket, str] = {}
        self.lock = threading.Lock()
        self.broadcast_callback = broadcast_callback
        
        # Varsayılan olarak 'Genel' odası oluştur
        self.create_room("Genel", "public", None, "SERVER")
        
    def create_room(self, room_name: str, room_type: str = "public", 
                   password: Optional[str] = None, created_by: str = "SERVER") -> Tuple[bool, str]:
        """Yeni bir sohbet odası oluşturur.
        
        Args:
            room_name: Oda adı
            room_type: Oda tipi ("public" veya "private")
            password: Özel odalar için şifre
            created_by: Odayı oluşturan kullanıcı adı
            
        Returns:
            (başarı, mesaj) tuple:
                - başarı: Oda oluşturulduysa True, oluşturulmadıysa False
                - mesaj: İşlem sonucu hakkında bilgi
        """
        with self.lock:
            # Oda adı daha önce kullanılmış mı kontrol et
            if room_name in self.rooms:
                return False, f"'{room_name}' adında bir oda zaten var"
                
            # Oda tipini doğrula
            if room_type not in ["public", "private"]:
                return False, "Oda tipi 'public' veya 'private' olmalıdır"
                
            # Private oda için şifre kontrolü
            if room_type == "private" and not password:
                return False, "Özel odalar için şifre gereklidir"
                
            # Yeni oda oluştur
            self.rooms[room_name] = Room(room_name, room_type, password, created_by)
            return True, f"'{room_name}' odası başarıyla oluşturuldu"
    
    def delete_room(self, room_name: str) -> Tuple[bool, str, List[socket.socket]]:
        """Bir sohbet odasını siler.
        
        Args:
            room_name: Silinecek oda adı
            
        Returns:
            (başarı, mesaj, etkilenen_istemciler) tuple:
                - başarı: Oda silindiyse True, silinmediyse False
                - mesaj: İşlem sonucu hakkında bilgi
                - etkilenen_istemciler: Odada bulunan istemcilerin listesi
        """
        with self.lock:
            # 'Genel' odası silinemez
            if room_name == "Genel":
                return False, "'Genel' odası silinemez", []
                
            # Oda var mı kontrol et
            if room_name not in self.rooms:
                return False, f"'{room_name}' adında bir oda bulunamadı", []
                
            # Odadaki istemcilerin listesini al
            affected_clients = list(self.rooms[room_name].clients)
            
            # İstemcilerin oda bilgisini güncelle
            for client in affected_clients:
                if client in self.client_rooms and self.client_rooms[client] == room_name:
                    del self.client_rooms[client]
            
            # Odayı sil
            del self.rooms[room_name]
            return True, f"'{room_name}' odası başarıyla silindi", affected_clients
    
    def join_room(self, client_socket: socket.socket, room_name: str, 
                 username: str, password: Optional[str] = None) -> Tuple[bool, str]:
        """Bir istemciyi belirtilen odaya ekler.
        
        Args:
            client_socket: İstemci socket nesnesi
            room_name: Katılınacak oda adı
            username: İstemcinin kullanıcı adı
            password: Özel odalar için şifre
            
        Returns:
            (başarı, mesaj) tuple:
                - başarı: İşlem başarılıysa True, değilse False
                - mesaj: İşlem sonucu hakkında bilgi
        """
        with self.lock:
            # Oda var mı kontrol et
            if room_name not in self.rooms:
                return False, f"'{room_name}' adında bir oda bulunamadı"
                
            room = self.rooms[room_name]
            
            # Şifre kontrolü
            if not room.check_password(password):
                return False, "Hatalı şifre veya şifre gerekiyor"
            
            # İstemci zaten bir odada mı?
            current_room_name = self.client_rooms.get(client_socket)
            if current_room_name:
                # Aynı odaya tekrar katılmaya çalışıyor
                if current_room_name == room_name:
                    return False, f"Zaten '{room_name}' odasındasınız"
                    
                # Önceki odadan çıkar
                current_room = self.rooms.get(current_room_name)
                if current_room:
                    current_room.remove_client(client_socket)
            
            # Yeni odaya ekle
            success = room.add_client(client_socket, username)
            if success:
                self.client_rooms[client_socket] = room_name
                return True, f"'{room_name}' odasına başarıyla katıldınız"
            else:
                return False, "Odaya katılırken bir hata oluştu"
    
    def leave_room(self, client_socket: socket.socket) -> Tuple[bool, str, Optional[str]]:
        """Bir istemciyi bulunduğu odadan çıkarır.
        
        Args:
            client_socket: İstemci socket nesnesi
            
        Returns:
            (başarı, mesaj, oda_adı) tuple:
                - başarı: İşlem başarılıysa True, değilse False
                - mesaj: İşlem sonucu hakkında bilgi
                - oda_adı: İstemcinin çıktığı oda adı (odada değilse None)
        """
        with self.lock:
            # İstemci bir odada mı?
            room_name = self.client_rooms.get(client_socket)
            if not room_name:
                return False, "Herhangi bir odada değilsiniz", None
                
            # Odayı bul
            room = self.rooms.get(room_name)
            if not room:
                # Kayıtlı oda bulunamadı, istemci kaydını temizle
                if client_socket in self.client_rooms:
                    del self.client_rooms[client_socket]
                return False, f"'{room_name}' odası bulunamadı", room_name
            
            # Odadan çıkar
            success, username = room.remove_client(client_socket)
            
            # İstemci kaydını güncelle
            if client_socket in self.client_rooms:
                del self.client_rooms[client_socket]
                
            if success:
                return True, f"'{room_name}' odasından ayrıldınız", room_name
            else:
                return False, f"'{room_name}' odasından ayrılırken bir hata oluştu", room_name
    
    def remove_client(self, client_socket: socket.socket) -> Tuple[bool, Optional[str], Optional[str]]:
        """Bir istemciyi tüm odalardan çıkarır (bağlantı koptuğunda).
        
        Args:
            client_socket: İstemci socket nesnesi
            
        Returns:
            (başarı, oda_adı, kullanıcı_adı) tuple:
                - başarı: İşlem başarılıysa True, değilse False
                - oda_adı: İstemcinin bulunduğu oda adı (odada değilse None)
                - kullanıcı_adı: İstemcinin kullanıcı adı (bulunamazsa None)
        """
        with self.lock:
            # İstemci bir odada mı?
            room_name = self.client_rooms.get(client_socket)
            if not room_name or room_name not in self.rooms:
                # İstemci kaydını temizle
                if client_socket in self.client_rooms:
                    del self.client_rooms[client_socket]
                return False, None, None
            
            # Odadan çıkar
            room = self.rooms[room_name]
            success, username = room.remove_client(client_socket)
            
            # İstemci kaydını güncelle
            if client_socket in self.client_rooms:
                del self.client_rooms[client_socket]
                
            return success, room_name, username
    
    def broadcast_to_room(self, room_name: str, message: str, 
                         sender_socket: Optional[socket.socket] = None) -> Tuple[bool, List[socket.socket]]:
        """Belirtilen odadaki tüm istemcilere mesaj gönderir.
        
        Args:
            room_name: Mesajın gönderileceği oda adı
            message: Gönderilecek mesaj (JSON string)
            sender_socket: Mesajı gönderen istemci (varsa bu istemciye gönderilmez)
            
        Returns:
            (başarı, bağlantısı_kopan_istemciler) tuple:
                - başarı: İşlem başarılıysa True, değilse False
                - bağlantısı_kopan_istemciler: Bağlantısı kopan istemcilerin listesi
        """
        with self.lock:
            # Oda var mı kontrol et
            if room_name not in self.rooms:
                return False, []
                
            room = self.rooms[room_name]
            
            # İstemci bir mesaj gönderdiyse, odada olup olmadığını kontrol et
            if sender_socket:
                client_room = self.client_rooms.get(sender_socket)
                if not client_room or client_room != room_name:
                    return False, []  # İstemci bu odada değil
            
            # Mesajı odaya yayınla
            disconnected = room.broadcast(message, sender_socket, self.broadcast_callback)
            return True, disconnected
    
    def broadcast_to_client_room(self, client_socket: socket.socket, message: str) -> Tuple[bool, str, List[socket.socket]]:
        """Bir istemcinin bulunduğu odadaki tüm istemcilere mesaj gönderir.
        
        Args:
            client_socket: İstemci socket nesnesi
            message: Gönderilecek mesaj (JSON string)
            
        Returns:
            (başarı, oda_adı, bağlantısı_kopan_istemciler) tuple:
                - başarı: İşlem başarılıysa True, değilse False
                - oda_adı: İstemcinin bulunduğu oda adı
                - bağlantısı_kopan_istemciler: Bağlantısı kopan istemcilerin listesi
        """
        with self.lock:
            # İstemci bir odada mı?
            room_name = self.client_rooms.get(client_socket)
            if not room_name or room_name not in self.rooms:
                return False, "", []
            
            # Mesajı odaya yayınla
            success, disconnected = self.broadcast_to_room(room_name, message, client_socket)
            return success, room_name, disconnected
    
    def get_client_room(self, client_socket: socket.socket) -> Optional[str]:
        """Bir istemcinin bulunduğu odanın adını döndürür.
        
        Args:
            client_socket: İstemci socket nesnesi
            
        Returns:
            İstemcinin bulunduğu oda adı, odada değilse None
        """
        return self.client_rooms.get(client_socket)
    
    def get_room_info(self, room_name: str) -> Optional[Dict[str, Any]]:
        """Belirtilen odanın bilgilerini döndürür.
        
        Args:
            room_name: Bilgileri istenen oda adı
            
        Returns:
            Oda bilgilerini içeren sözlük, oda bulunamazsa None
        """
        with self.lock:
            room = self.rooms.get(room_name)
            if not room:
                return None
            return room.get_info()
    
    def list_public_rooms(self) -> List[Dict[str, Any]]:
        """Herkese açık odaların listesini döndürür.
        
        Returns:
            Herkese açık odaların bilgilerini içeren liste
        """
        with self.lock:
            public_rooms = []
            for room_name, room in self.rooms.items():
                if room.room_type == "public":
                    public_rooms.append(room.get_info())
            return public_rooms
    
    def list_all_rooms(self) -> List[Dict[str, Any]]:
        """Tüm odaların listesini döndürür (private odaların şifreleri gizlenir).
        
        Returns:
            Tüm odaların bilgilerini içeren liste
        """
        with self.lock:
            return [room.get_info() for room in self.rooms.values()]
    
    def get_room_clients(self, room_name: str) -> List[socket.socket]:
        """Belirtilen odadaki istemcilerin listesini döndürür.
        
        Args:
            room_name: İstemcileri istenen oda adı
            
        Returns:
            Odadaki istemcilerin listesi, oda bulunamazsa boş liste
        """
        with self.lock:
            room = self.rooms.get(room_name)
            if not room:
                return []
            return list(room.clients)
    
    def get_room_client_usernames(self, room_name: str) -> List[str]:
        """Belirtilen odadaki kullanıcı adlarının listesini döndürür.
        
        Args:
            room_name: Kullanıcı adları istenen oda adı
            
        Returns:
            Odadaki kullanıcı adlarının listesi, oda bulunamazsa boş liste
        """
        with self.lock:
            room = self.rooms.get(room_name)
            if not room:
                return []
            return list(room.client_usernames.values())

    def get_stats(self) -> Dict[str, Any]:
        """Oda yöneticisinin istatistiklerini döndürür.
        
        Returns:
            İstatistik bilgilerini içeren sözlük
        """
        with self.lock:
            total_clients = sum(room.get_client_count() for room in self.rooms.values())
            
            stats = {
                "totalRooms": len(self.rooms),
                "publicRooms": sum(1 for room in self.rooms.values() if room.room_type == "public"),
                "privateRooms": sum(1 for room in self.rooms.values() if room.room_type == "private"),
                "totalClients": total_clients,
                "roomStats": {name: room.get_client_count() for name, room in self.rooms.items()}
            }
            return stats 