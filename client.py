import socket
import threading
import sys
import json
import datetime
import uuid
import os
from typing import Optional, Dict, Any, List

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
        self.current_room = None  # Mevcut oda
        self.available_rooms = []  # Kullanılabilir odalar listesi
        
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
    
    def send_command(self, command: str, params: Dict[str, Any] = None):
        """Sunucuya komut gönderir.
        
        Args:
            command: Komut adı
            params: Komut parametreleri
            
        Returns:
            İşlem başarılıysa True, değilse False
        """
        if not self.socket or not self.running:
            print("Komut gönderilemiyor: Bağlantı yok")
            return False
            
        try:
            # JSON komut nesnesi oluştur
            command_obj = json_helper.build_message(
                username=self.username,
                message=f"/{command} komutu çalıştırılıyor",
                device_id=self.device_id,
                source="client",
                command=command,
                params=params or {}
            )
            
            # JSON string'ine çevir ve gönder
            json_str = json_helper.serialize_message(command_obj)
            self.socket.send(json_str.encode('utf-8'))
            
            return True
            
        except Exception as e:
            print(f"Komut gönderme hatası: {e}")
            self.running = False
            return False
                
    def send_message(self, message_text: str):
        """Sunucuya mesaj gönderir.
        
        Args:
            message_text: Gönderilecek mesaj metni
        """
        if not self.socket or not self.running:
            print("Mesaj gönderilemiyor: Bağlantı yok")
            return False
        
        # Komut mu kontrol et
        if message_text.startswith('/'):
            return self.process_command_text(message_text)
        
        try:
            # JSON mesaj nesnesi oluştur
            message = json_helper.build_message(
                username=self.username,
                message=message_text,
                device_id=self.device_id,
                source="client"
            )
            
            # Mevcut oda varsa ekle
            if self.current_room:
                message["roomName"] = self.current_room
            
            # JSON string'ine çevir ve gönder
            json_str = json_helper.serialize_message(message)
            self.socket.send(json_str.encode('utf-8'))
            
            # Gönderilen mesajı yerel olarak ekranda göster (↑ işareti ile)
            room_info = f" [{self.current_room}]" if self.current_room else ""
            print(f"[{self.username}]{room_info} {datetime.datetime.now().strftime('%H:%M:%S')} ↑ {message_text}")
            
            return True
            
        except Exception as e:
            print(f"Mesaj gönderme hatası: {e}")
            self.running = False
            return False
            
    def process_command_text(self, command_text: str) -> bool:
        """Komut metnini işler ve sunucuya gönderir.
        
        Args:
            command_text: Komut metni (örn. "/join OdaAdı")
            
        Returns:
            İşlem başarılıysa True, değilse False
        """
        # Komut adını ve parametreleri ayır
        parts = command_text[1:].strip().split(maxsplit=1)
        command = parts[0].lower()
        
        # Yerel komutları kontrol et (yardım vb.)
        if command == "help":
            self.display_help()
            return True
            
        elif command == "rooms":
            # Mevcut oda listesini görüntüle
            self.send_command("list_rooms")
            return True
            
        elif command == "join":
            # /join OdaAdı [şifre] şeklinde kullanılır
            if len(parts) < 2:
                print("Kullanım: /join <oda_adı> [şifre]")
                return False
                
            join_parts = parts[1].split(maxsplit=1)
            room_name = join_parts[0]
            password = join_parts[1] if len(join_parts) > 1 else None
            
            return self.send_command("join_room", {
                "roomName": room_name,
                "password": password
            })
            
        elif command == "leave":
            # Mevcut odadan ayrıl
            return self.send_command("leave_room")
            
        elif command == "create":
            # /create OdaAdı [public|private] [şifre] şeklinde kullanılır
            if len(parts) < 2:
                print("Kullanım: /create <oda_adı> [public|private] [şifre]")
                return False
                
            create_parts = parts[1].split(maxsplit=2)
            room_name = create_parts[0]
            
            # Oda tipi
            room_type = "public"
            password = None
            
            if len(create_parts) > 1:
                if create_parts[1].lower() in ["public", "private"]:
                    room_type = create_parts[1].lower()
                    # Şifre
                    if len(create_parts) > 2 and room_type == "private":
                        password = create_parts[2]
                else:
                    # İkinci parametre oda tipi değilse, şifre olarak kabul et
                    password = create_parts[1]
                    room_type = "private"  # Şifre varsa özel oda
            
            return self.send_command("create_room", {
                "roomName": room_name,
                "roomType": room_type,
                "password": password
            })
            
        elif command == "delete":
            # Oda silme komutu
            if len(parts) < 2:
                print("Kullanım: /delete <oda_adı>")
                return False
                
            return self.send_command("delete_room", {
                "roomName": parts[1]
            })
            
        elif command == "info":
            # Oda bilgisi komutu
            room_name = parts[1] if len(parts) > 1 else ""
            
            return self.send_command("room_info", {
                "roomName": room_name
            })
            
        else:
            # Bilinmeyen komut, sunucuya gönder
            print(f"Komut gönderiliyor: {command}")
            
            params = {}
            if len(parts) > 1:
                # Basit parametre çözümleme - daha karmaşık komutlar için geliştirilmeli
                params["text"] = parts[1]
            
            return self.send_command(command, params)
            
    def display_help(self):
        """Kullanılabilir komutları ekrana yazdırır."""
        help_text = """
Kullanılabilir Komutlar:
/help             - Bu yardım mesajını gösterir
/rooms            - Mevcut odaları listeler
/join <oda_adı> [şifre] - Belirtilen odaya katılır
/leave            - Mevcut odadan ayrılır
/create <oda_adı> [public|private] [şifre] - Yeni bir oda oluşturur
/delete <oda_adı>  - Bir odayı siler (sadece oda sahibi)
/info [oda_adı]   - Oda hakkında bilgi verir (parametre verilmezse mevcut oda)
"""
        print(help_text)
            
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
                    # Mesajı işle
                    message_obj = result
                    
                    # Komut yanıtlarını işle
                    if "command" in message_obj:
                        self.handle_command_response(message_obj)
                        continue
                    
                    # Oda bilgisini güncelle
                    if "roomName" in message_obj:
                        room_name = message_obj["roomName"]
                        # Eğer bir odadaysak, farklı odadan gelen mesajları gösterme
                        if self.current_room and self.current_room != room_name:
                            continue
                    
                    # Kendi mesajımızı tekrar alma (echo) durumunu kontrol et
                    is_own_message = (message_obj.get("source") == "client" and 
                                     message_obj.get("username") == self.username and
                                     message_obj.get("deviceId") == self.device_id)
                    
                    # Kendi mesajımız değilse veya sunucudan gelen bir mesajsa göster
                    if not is_own_message or message_obj.get("source") == "host":
                        # Biçimlendirilmiş mesajı konsola yazdır
                        room_info = ""
                        if "roomName" in message_obj and message_obj["roomName"] != self.current_room:
                            room_info = f" [{message_obj['roomName']}]"
                            
                        formatted = json_helper.format_message_for_console(message_obj)
                        if room_info:
                            # Oda bilgisini ekle
                            username_end = formatted.find("]") + 1
                            formatted = formatted[:username_end] + room_info + formatted[username_end:]
                        
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
                
    def handle_command_response(self, message_obj: Dict[str, Any]):
        """Sunucudan gelen komut yanıtlarını işler.
        
        Args:
            message_obj: Komut yanıtı nesne
        """
        command = message_obj.get("command", "")
        params = message_obj.get("params", {})
        
        # Komut tipine göre işle
        if command == "list_rooms_result":
            # Oda listesini güncelle
            self.available_rooms = params.get("rooms", [])
            
            # Konsola zaten mesaj yazdırılmış olacak
            # print(message_obj.get("message", ""))
            
        elif command == "join_room_result":
            # Odaya katılma sonucu
            success = params.get("success", False)
            room_name = params.get("roomName", "")
            
            if success:
                self.current_room = room_name
                print(f"Mevcut oda: {self.current_room}")
                
        elif command == "create_room_result":
            # Oda oluşturma sonucu
            success = params.get("success", False)
            room_name = params.get("roomName", "")
            
            if success:
                # Oluşturulan odaya otomatik katıl
                self.send_command("join_room", {
                    "roomName": room_name,
                    "password": params.get("password")  # Şifre varsa gönder
                })
                
        elif command == "leave_room_result":
            # Odadan ayrılma sonucu
            success = params.get("success", False)
            
            if success:
                old_room = self.current_room
                new_room = params.get("roomName", "Genel")
                
                # Genel odaya geçildi
                if old_room != "Genel" and new_room == "Genel":
                    self.current_room = "Genel"
                    print(f"Mevcut oda: {self.current_room}")
                
        elif command == "delete_room_result":
            # Oda silme sonucu
            success = params.get("success", False)
            
            if success:
                room_name = params.get("roomName", "")
                
                # Eğer silinmiş odadaysak, current_room'u temizle
                if self.current_room == room_name:
                    self.current_room = None
                    
        elif command == "room_info_result":
            # Oda bilgisi sonucu
            room_info = params.get("roomInfo", {})
            
            if room_info:
                # Zaten sunucu bilgileri gönderiyor, ek bir şey yapmaya gerek yok
                pass
                
        elif command == "error":
            # Hata durumu
            error_msg = message_obj.get("message", "Bilinmeyen hata")
            print(f"Sunucu hatası: {error_msg}")


def main():
    """Ana program fonksiyonu."""
    print("===== Socket Sohbet İstemcisi =====")
    print("(JSON mesaj formatını ve oda sistemini kullanıyor)")
    
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
    print("Komutlar için /help yazabilirsiniz.")
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