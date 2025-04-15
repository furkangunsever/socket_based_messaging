import socket
import threading
import sys
import json
import datetime
import uuid
import os
from typing import Optional

# JSON yardımcı modülünü import et
try:
    from utils import json_helper
except ImportError:
    # Doğrudan bu dosyadan çalıştırılınca import yolu düzeltme
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils import json_helper


class ChatClient:
    def __init__(self, host: str = 'localhost', port: int = 12345):
        """İstemci bağlantısını başlatmak için gerekli ayarları yapar.
        
        Args:
            host: Sunucu IP adresi
            port: Sunucu portu
        """
        self.host = host
        self.port = port
        self.socket = None
        self.running = False
        self.username = "Anonim"
        self.device_id = str(uuid.uuid4())[:8]  # Benzersiz cihaz kimliği
        
    def set_username(self, username: str):
        """Kullanıcı adını ayarlar.
        
        Args:
            username: Kullanıcı adı
        """
        self.username = username if username and username.strip() else "Anonim"

    def connect(self, username: Optional[str] = None):
        """Sunucuya bağlanır ve mesaj alma thread'ini başlatır.
        
        Args:
            username: Kullanıcının seçtiği isim
        """
        if username:
            self.set_username(username)
            
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.running = True
            
            # Mesaj alma thread'ini başlat
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()
            
            print(f"Sunucuya bağlandı: {self.host}:{self.port}")
            
            # Bağlantı bilgilerini içeren ilk mesaj
            self.send_message(f"Merhaba, ben {self.username}!")
            
            return True
            
        except Exception as e:
            print(f"Bağlantı hatası: {e}")
            return False
            
    def disconnect(self):
        """Sunucudan bağlantıyı keser."""
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
                
    def send_message(self, message_text: str):
        """Sunucuya mesaj gönderir.
        
        Args:
            message_text: Gönderilecek mesaj metni
        """
        if not self.socket or not self.running:
            print("Mesaj gönderilemiyor: Bağlantı yok")
            return False
        
        try:
            # JSON mesaj nesnesi oluştur
            message = json_helper.build_message(
                username=self.username,
                message=message_text,
                device_id=self.device_id,
                source="client"
            )
            
            # JSON string'ine çevir ve gönder
            json_str = json_helper.serialize_message(message)
            self.socket.send(json_str.encode('utf-8'))
            
            # Gönderilen mesajı yerel olarak ekranda göster (↑ işareti ile)
            print(f"[{self.username}] {datetime.datetime.now().strftime('%H:%M:%S')} ↑ {message_text}")
            
            return True
            
        except Exception as e:
            print(f"Mesaj gönderme hatası: {e}")
            self.running = False
            return False
            
    def receive_messages(self):
        """Sunucudan gelen mesajları dinler ve ekrana yazdırır."""
        while self.running:
            try:
                # JSON mesajını al
                data = self.socket.recv(4096).decode('utf-8')
                if not data:
                    print("Sunucu bağlantısı kapandı.")
                    self.running = False
                    break
                
                # JSON mesajını ayrıştır
                success, result = json_helper.parse_message(data)
                
                if success:
                    # Mesajı görüntüle
                    message_obj = result
                    
                    # Kendi mesajımızı tekrar alma (echo) durumunu kontrol et
                    is_own_message = (message_obj.get("source") == "client" and 
                                    message_obj.get("username") == self.username and
                                    message_obj.get("deviceId") == self.device_id)
                    
                    # Kendi mesajımız değilse veya sunucudan gelen bir mesajsa göster
                    if not is_own_message or message_obj.get("source") == "host":
                        # Biçimlendirilmiş mesajı konsola yazdır
                        formatted = json_helper.format_message_for_console(message_obj)
                        print(formatted)
                else:
                    # JSON ayrıştırma hatası
                    print(f"Mesaj ayrıştırma hatası: {result}")
                
            except ConnectionResetError:
                print("Sunucu bağlantısı kesildi.")
                self.running = False
                break
            except json.JSONDecodeError:
                print("Geçersiz JSON mesajı alındı.")
                continue
            except Exception as e:
                print(f"Mesaj alma hatası: {e}")
                self.running = False
                break


def main():
    """Ana program fonksiyonu."""
    print("===== Socket Sohbet İstemcisi =====")
    print("(JSON mesaj formatını kullanıyor)")
    
    # Varsayılan bağlantı bilgileri
    host = 'localhost'
    port = 12345
    
    # Komut satırı parametrelerini kontrol et
    if len(sys.argv) >= 2:
        host = sys.argv[1]
    if len(sys.argv) >= 3:
        try:
            port = int(sys.argv[2])
        except ValueError:
            print(f"Hatalı port numarası: {sys.argv[2]}")
            sys.exit(1)
    
    # Kullanıcı adı iste
    username = input("Kullanıcı adınızı girin: ")
    
    # İstemci nesnesini oluştur ve kullanıcı adını ayarla
    client = ChatClient(host, port)
    client.set_username(username)
    
    # Sunucuya bağlan
    if not client.connect():
        sys.exit(1)
    
    print(f"Cihaz kimliğiniz: {client.device_id}")
    print("Mesaj göndermek için yazın, çıkmak için 'exit' yazın")
    
    try:
        while client.running:
            message = input()
            
            if message.lower() == 'exit':
                break
                
            if not client.send_message(message):
                break
                
    except KeyboardInterrupt:
        print("\nİstemci kapatılıyor...")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main() 