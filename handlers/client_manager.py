"""
İstemci bağlantılarını yöneten sınıf.
Bu modül, bağlı istemcilerin durumlarını yönetir ve mesaj iletişimini sağlar.
"""

import socket
import threading
import datetime
from typing import Dict, List, Tuple, Optional, Callable

class ClientManager:
    def __init__(self, broadcast_callback: Optional[Callable] = None):
        """İstemci yöneticisini başlatır.
        
        Args:
            broadcast_callback: Mesaj yayınlama için kullanılacak fonksiyon
        """
        # {client_socket: (address, username, join_time)}
        self.clients: Dict[socket.socket, Tuple[str, str, datetime.datetime]] = {}
        self.lock = threading.Lock()  # Thread güvenliği için kilit
        self.broadcast_callback = broadcast_callback
        
    def add_client(self, client_socket: socket.socket, address: str, username: str = None) -> str:
        """Yeni bir istemciyi listeye ekler.
        
        Args:
            client_socket: İstemcinin socket bağlantısı
            address: İstemcinin IP:port adresi
            username: İstemcinin kullanıcı adı (belirtilmezse otomatik oluşturulur)
            
        Returns:
            Atanan kullanıcı adı
        """
        if username is None or username.strip() == "":
            username = f"Kullanıcı-{len(self.clients)+1}"
            
        join_time = datetime.datetime.now()
        
        with self.lock:
            self.clients[client_socket] = (address, username, join_time)
            
        return username
    
    def remove_client(self, client_socket: socket.socket) -> Optional[Tuple[str, str]]:
        """İstemciyi listeden çıkarır.
        
        Args:
            client_socket: Çıkarılacak istemcinin socket bağlantısı
            
        Returns:
            (address, username) eğer istemci bulunursa, bulunamazsa None
        """
        with self.lock:
            if client_socket in self.clients:
                client_info = self.clients[client_socket]
                del self.clients[client_socket]
                return client_info[0], client_info[1]  # address, username
        
        return None
    
    def get_client_info(self, client_socket: socket.socket) -> Optional[Tuple[str, str]]:
        """İstemci bilgilerini getirir.
        
        Args:
            client_socket: Bilgileri istenen istemcinin socket bağlantısı
            
        Returns:
            (address, username) eğer istemci bulunursa, bulunamazsa None
        """
        with self.lock:
            if client_socket in self.clients:
                info = self.clients[client_socket]
                return info[0], info[1]  # address, username
        
        return None
    
    def get_client_count(self) -> int:
        """Bağlı istemci sayısını döndürür."""
        with self.lock:
            return len(self.clients)
    
    def get_client_list(self) -> List[str]:
        """Bağlı istemcilerin kullanıcı adlarını döndürür."""
        with self.lock:
            return [info[1] for info in self.clients.values()]
            
    def broadcast(self, message: str, sender_socket: socket.socket = None, system_message: bool = False) -> List[socket.socket]:
        """Mesajı tüm bağlı istemcilere iletir.
        
        Args:
            message: İletilecek mesaj
            sender_socket: Mesajı gönderen istemcinin socket'i (kendisine mesaj gönderilmeyecek)
            system_message: Sistem mesajı ise True, normal mesaj ise False
            
        Returns:
            Bağlantısı kopan istemcilerin listesi
        """
        if self.broadcast_callback:
            return self.broadcast_callback(message, sender_socket, system_message)
            
        disconnected_clients = []
        
        with self.lock:
            for client in list(self.clients.keys()):
                # Mesajı gönderen hariç tüm istemcilere gönder
                # System mesajları herkese gider (sender_socket=None durumunda)
                if client != sender_socket or system_message:
                    try:
                        client.send(message.encode('utf-8'))
                    except:
                        disconnected_clients.append(client)
                        
        return disconnected_clients
    
    def close_all(self):
        """Tüm istemci bağlantılarını kapatır."""
        with self.lock:
            for client in list(self.clients.keys()):
                try:
                    client.close()
                except:
                    pass
            
            self.clients.clear() 