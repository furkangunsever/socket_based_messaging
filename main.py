import socket
import threading
import datetime
import json
from typing import List, Dict, Tuple, Optional, Any

# Yeni eklenen JSON yardımcı modülünü import et
from utils import json_helper

class ChatServer:
    def __init__(self, host: str = 'localhost', port: int = 12345):
        """Socket sunucusunu başlatmak için gerekli ayarları yapar.
        
        Args:
            host: Sunucu IP adresi
            port: Sunucu portu
        """
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # SO_REUSEADDR: Sunucu yeniden başlatıldığında port kullanımıyla ilgili sorunları önler
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Aktif istemci bağlantılarını saklar: {client_socket: (address, username, device_id)}
        self.clients: Dict[socket.socket, Tuple[str, str, Optional[str]]] = {}
        # İstemcilerin ek bilgilerini saklar: {username: device_id}
        self.client_info: Dict[str, str] = {}
        # Sunucunun çalışıp çalışmadığını kontrol eden bayrak
        self.running = False
        
    def start(self):
        """Sunucuyu başlatır ve gelen bağlantıları dinler."""
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)  # En fazla 5 bekleyen bağlantı kuyruğu
            self.running = True
            
            self.log(f"Sunucu başlatıldı - {self.host}:{self.port}")
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    client_address = f"{address[0]}:{address[1]}"
                    self.log(f"Yeni bağlantı: {client_address}")
                    
                    # Geçici kullanıcı adı ve cihaz kimliği ata
                    # Gerçek bilgiler ilk mesajla gelecek
                    temp_username = f"Misafir-{len(self.clients)+1}"
                    self.clients[client_socket] = (client_address, temp_username, None)
                    
                    # Karşılama mesajı gönder (JSON formatında)
                    welcome_msg = json_helper.build_message(
                        username="SERVER",
                        message=f"Hoş geldiniz! Sunucuya bağlandınız. Mevcut aktif kullanıcı sayısı: {len(self.clients)}",
                        source="host"
                    )
                    client_socket.send(json_helper.serialize_message(welcome_msg).encode('utf-8'))
                    
                    # Her istemci için ayrı bir thread başlat
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket,)
                    )
                    client_thread.daemon = True  # Ana program sonlandığında thread de sonlanacak
                    client_thread.start()
                    
                except Exception as e:
                    self.log(f"Bağlantı kabul hatası: {e}")
                    
        except Exception as e:
            self.log(f"Sunucu başlatma hatası: {e}")
        finally:
            self.stop()
            
    def stop(self):
        """Sunucuyu durdurur ve tüm bağlantıları kapatır."""
        self.running = False
        
        # Tüm istemci bağlantılarını kapat
        for client in list(self.clients.keys()):
            try:
                client.close()
            except:
                pass
        
        # Sunucu soketini kapat
        try:
            self.server_socket.close()
        except:
            pass
            
        self.log("Sunucu durduruldu.")
            
    def handle_client(self, client_socket: socket.socket):
        """İstemciden gelen mesajları işler.
        
        Args:
            client_socket: İstemcinin socket bağlantısı
        """
        try:
            while self.running:
                # 4096 byte boyutuna kadar mesaj kabul et
                data = client_socket.recv(4096).decode('utf-8')
                
                if not data:
                    break
                
                # JSON mesajı ayrıştır
                success, result = json_helper.parse_message(data)
                
                if not success:
                    # Ayrıştırma hatası
                    error_msg = json_helper.build_message(
                        username="SERVER",
                        message=f"Mesaj işleme hatası: {result}",
                        source="host"
                    )
                    client_socket.send(json_helper.serialize_message(error_msg).encode('utf-8'))
                    continue
                
                # Ayrıştırma başarılı, mesaj nesnesini al
                message_obj = result
                
                # İlk mesajda kullanıcı adını ve cihaz kimliğini güncelle
                client_address, current_username, _ = self.clients.get(client_socket, ("", "", None))
                if current_username.startswith("Misafir-"):
                    new_username = message_obj["username"]
                    device_id = message_obj.get("deviceId")
                    
                    # Kullanıcı adı benzersiz olmalı
                    if new_username in [info[1] for info in self.clients.values()]:
                        new_username = f"{new_username}_{len(self.clients)}"
                    
                    # İstemci bilgilerini güncelle
                    self.clients[client_socket] = (client_address, new_username, device_id)
                    self.client_info[new_username] = device_id
                    
                    # Yeni kullanıcının katıldığını herkese bildir
                    join_msg = json_helper.build_message(
                        username="SERVER",
                        message=f"{new_username} sohbete katıldı!",
                        source="host"
                    )
                    self.broadcast(json_helper.serialize_message(join_msg), client_socket, system_message=True)
                    self.log(f"Kullanıcı tanımlandı: {client_address} -> {new_username} (Cihaz: {device_id})")
                
                # Güncel kullanıcı bilgisini al
                _, username, device_id = self.clients.get(client_socket, (client_address, "Bilinmeyen", None))
                
                # Gelen mesajı logla
                self.log(json_helper.format_message_for_console(message_obj))
                
                # Mesajı diğer istemcilere ilet
                # Mesaj nesnesini doğrudan kullan, source alanı değişmeden kalsın
                self.broadcast(json_helper.serialize_message(message_obj), client_socket)
                
        except json.JSONDecodeError as e:
            self.log(f"JSON ayrıştırma hatası ({self.get_client_name(client_socket)}): {e}")
        except ConnectionResetError:
            self.log(f"Bağlantı sıfırlandı: {self.get_client_name(client_socket)}")
        except Exception as e:
            self.log(f"İstemci işleme hatası ({self.get_client_name(client_socket)}): {e}")
        finally:
            # İstemci bağlantısını kapat ve listeden çıkar
            try:
                if client_socket in self.clients:
                    client_address, username, _ = self.clients[client_socket]
                    self.log(f"Bağlantı kapatıldı: {client_address} ({username})")
                    
                    # Kullanıcının ayrıldığını herkese bildir
                    leave_msg = json_helper.build_message(
                        username="SERVER", 
                        message=f"{username} sohbetten ayrıldı.",
                        source="host"
                    )
                    self.broadcast(json_helper.serialize_message(leave_msg), None, system_message=True)
                    
                    # İstemciyi listeden çıkar
                    del self.clients[client_socket]
                    if username in self.client_info:
                        del self.client_info[username]
                    
                client_socket.close()
            except:
                pass
            
    def broadcast(self, message: str, sender_socket: socket.socket = None, system_message: bool = False):
        """Mesajı tüm bağlı istemcilere iletir.
        
        Args:
            message: İletilecek JSON formatındaki mesaj
            sender_socket: Mesajı gönderen istemcinin socket'i (kendisine mesaj gönderilmeyecek)
            system_message: Sistem mesajı ise True, normal mesaj ise False
        """
        # Sistem mesajlarını konsola yazdır
        if system_message and json_helper.is_valid_json(message):
            message_obj = json.loads(message)
            self.log(json_helper.format_message_for_console(message_obj))
            
        disconnected_clients = []
        
        for client in self.clients:
            # Mesajı gönderen hariç tüm istemcilere gönder
            # System mesajları herkese gider (sender_socket=None durumunda)
            if client != sender_socket or system_message:
                try:
                    client.send(message.encode('utf-8'))
                except:
                    # Gönderim başarısız olursa istemciyi işaretleyelim
                    disconnected_clients.append(client)
        
        # Bağlantısı kopan istemcileri listeden çıkar
        for client in disconnected_clients:
            if client in self.clients:
                client_address, username, _ = self.clients[client]
                self.log(f"Bağlantı koptu: {client_address} ({username})")
                del self.clients[client]
                if username in self.client_info:
                    del self.client_info[username]
                try:
                    client.close()
                except:
                    pass
    
    def log(self, message: str):
        """Konsola zaman damgalı log mesajı yazdırır.
        
        Args:
            message: Yazdırılacak log mesajı
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {message}")
        
    def get_client_count(self) -> int:
        """Bağlı istemci sayısını döndürür."""
        return len(self.clients)
        
    def get_client_list(self) -> List[str]:
        """Bağlı istemcilerin listesini döndürür."""
        return [username for _, username, _ in self.clients.values()]
    
    def get_client_name(self, client_socket: socket.socket) -> str:
        """Socket nesnesinden istemci adını döndürür.
        
        Args:
            client_socket: İstemci socket nesnesi
            
        Returns:
            İstemcinin adı (adres ve kullanıcı adı)
        """
        if client_socket in self.clients:
            addr, name, _ = self.clients[client_socket]
            return f"{addr} ({name})"
        return "Bilinmeyen istemci"


def main():
    """Ana program fonksiyonu."""
    print("Socket tabanlı çok kullanıcılı sohbet sunucusu başlatılıyor...")
    print("JSON mesaj formatı kullanılıyor.")
    
    # Örnek mesaj formatını ekrana yazdır
    print("\nÖrnek JSON mesaj formatı:")
    print(json.dumps(json_helper.EXAMPLE_MESSAGE, indent=2))
    print("\nSunucu başlatılıyor...\n")
    
    # Sunucu örneğini oluştur ve başlat
    server = ChatServer()
    
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nSunucu kullanıcı tarafından durduruldu.")
    finally:
        server.stop()


if __name__ == "__main__":
    main() 