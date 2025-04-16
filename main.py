import socket
import threading
import datetime
import json
import time
from typing import List, Dict, Tuple, Optional, Any, Callable

# Yardımcı modülleri import et
from utils import json_helper
from handlers.room_manager import RoomManager
from handlers.message_handler import MessageHandler

class ChatServer:
    def __init__(self, host: str = 'localhost', port: int = 12345, inactivity_timeout: int = 300):
        """Socket sunucusunu başlatmak için gerekli ayarları yapar.
        
        Args:
            host: Sunucu IP adresi
            port: Sunucu portu
            inactivity_timeout: Pasif bağlantılar için zamanaşımı süresi (saniye)
        """
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # SO_REUSEADDR: Sunucu yeniden başlatıldığında port kullanımıyla ilgili sorunları önler
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Aktif istemci bağlantılarını saklar: {client_socket: (address, username, device_id)}
        self.clients: Dict[socket.socket, Tuple[str, str, Optional[str]]] = {}
        # İstemcilerin ek bilgilerini saklar
        self.active_clients: Dict[socket.socket, Dict[str, Any]] = {}
        # Cihaz kimliğine göre kullanıcı bilgilerini saklar (istemci cihaz bazlı tanınması için)
        self.device_clients: Dict[str, Dict[str, Any]] = {}
        # Bağlantısı kopan istemcilerin bilgilerini saklar: {device_id: {username, last_seen, room}}
        self.disconnected_clients: Dict[str, Dict[str, Any]] = {}
        # İstemcilerin ek bilgilerini saklar: {username: device_id}
        self.client_info: Dict[str, str] = {}
        # İnaktivite zamanaşımı süresi (saniye)
        self.inactivity_timeout = inactivity_timeout
        # İnaktivite kontrolü için thread
        self.timeout_thread = None
        # Oda yöneticisini başlat
        self.room_manager = RoomManager(broadcast_callback=self.send_to_client)
        # Mesaj işleyiciyi başlat
        self.message_handler = MessageHandler(self.room_manager)
        # Sunucunun çalışıp çalışmadığını kontrol eden bayrak
        self.running = False
        
    def start(self):
        """Sunucuyu başlatır ve gelen bağlantıları dinler."""
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)  # En fazla 5 bekleyen bağlantı kuyruğu
            self.running = True
            
            self.log(f"Sunucu başlatıldı - {self.host}:{self.port}")
            self.log(f"Varsayılan 'Genel' odası oluşturuldu.")
            
            # İnaktivite kontrolü için thread'i başlat
            if self.inactivity_timeout > 0:
                self.timeout_thread = threading.Thread(target=self.check_client_timeouts)
                self.timeout_thread.daemon = True
                self.timeout_thread.start()
                self.log(f"İnaktivite zamanaşımı kontrolü başlatıldı: {self.inactivity_timeout} saniye")
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    client_address = f"{address[0]}:{address[1]}"
                    self.log(f"Yeni bağlantı: {client_address}")
                    
                    # Geçici kullanıcı adı ve cihaz kimliği ata
                    # Gerçek bilgiler ilk mesajla gelecek
                    temp_username = f"Misafir-{len(self.clients)+1}"
                    self.clients[client_socket] = (client_address, temp_username, None)
                    
                    # Aktif istemci olarak kaydet
                    self.active_clients[client_socket] = {
                        "username": temp_username,
                        "address": client_address,
                        "deviceId": None,
                        "last_active": datetime.datetime.now(),
                        "room": None
                    }
                    
                    # Karşılama mesajı gönder (JSON formatında)
                    welcome_msg = json_helper.build_message(
                        username="SERVER",
                        message=f"Hoş geldiniz! Sunucuya bağlandınız. Mevcut aktif kullanıcı sayısı: {len(self.clients)}",
                        source="host"
                    )
                    client_socket.send(json_helper.serialize_message(welcome_msg).encode('utf-8'))
                    
                    # Oda bilgilerini gönder
                    self.send_room_info(client_socket)
                    
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
    
    def check_client_timeouts(self):
        """Belirli aralıklarla tüm istemcilerin aktivite durumunu kontrol eder
        ve inaktif olanları bağlantısını sonlandırır."""
        check_interval = min(60, self.inactivity_timeout // 4)  # En fazla 60 saniye, en az timeout/4
        
        while self.running:
            time.sleep(check_interval)
            
            now = datetime.datetime.now()
            inactive_clients = []
            
            # İnaktif istemcileri tespit et
            for client_socket, client_data in list(self.active_clients.items()):
                last_active = client_data["last_active"]
                inactive_seconds = (now - last_active).total_seconds()
                
                if inactive_seconds > self.inactivity_timeout:
                    inactive_clients.append(client_socket)
                    self.log(f"İnaktivite tespit edildi: {client_data['username']} "
                             f"({inactive_seconds:.1f} saniye)")
            
            # İnaktif istemcilerin bağlantılarını kapat
            for client_socket in inactive_clients:
                try:
                    # Bağlantıyı kapat, handle_client'ın finally bloğu ilgili temizleme işlemlerini yapacak
                    client_socket.close()
                except:
                    # Bağlantı zaten kapalıysa da temizleme yap
                    self.handle_disconnection(client_socket, reason="timeout")
            
    def update_client_activity(self, client_socket: socket.socket):
        """İstemcinin son aktivite zamanını günceller.
        
        Args:
            client_socket: İstemci socket nesnesi
        """
        if client_socket in self.active_clients:
            self.active_clients[client_socket]["last_active"] = datetime.datetime.now()
            
    def handle_disconnection(self, client_socket: socket.socket, reason: str = "unknown"):
        """İstemci bağlantısı koptuğunda gerekli işlemleri yapar.
        
        Args:
            client_socket: Bağlantısı kopan istemci
            reason: Bağlantının kopma nedeni ("timeout", "client_closed", "error" vb.)
        """
        try:
            if client_socket in self.clients:
                client_address, username, device_id = self.clients[client_socket]
                
                self.log(f"Bağlantı koptu ({reason}): {client_address} ({username})")
                
                # İstemciyi odadan çıkar
                success, room_name, _ = self.room_manager.remove_client(client_socket)
                
                # Bağlantı bilgilerini saklama
                if device_id and username != f"Misafir-{len(self.clients)}":
                    self.disconnected_clients[device_id] = {
                        "username": username,
                        "last_seen": datetime.datetime.now(),
                        "room": room_name,
                        "address": client_address
                    }
                
                if success and room_name:
                    # Kullanıcının bağlantısının koptuğunu odadaki diğer kullanıcılara bildir
                    disconnect_msg = json_helper.build_message(
                        username="SERVER", 
                        message=f"{username} kullanıcısının bağlantısı koptu.",
                        source="host",
                        command="user_disconnect",
                        params={"username": username, "reason": reason}
                    )
                    
                    # Odadaki tüm kullanıcılara bildirim gönder
                    self.room_manager.broadcast_to_room(
                        room_name,
                        json_helper.serialize_message(disconnect_msg),
                        None
                    )
                
                # İstemciyi listeden çıkar
                del self.clients[client_socket]
                if client_socket in self.active_clients:
                    del self.active_clients[client_socket]
                
                if device_id and device_id in self.device_clients:
                    del self.device_clients[device_id]
                    
                if username in self.client_info:
                    del self.client_info[username]
                
                # Soket bağlantısını kapat
                if client_socket:
                    try:
                        client_socket.close()
                    except:
                        pass
        except Exception as e:
            self.log(f"Bağlantı kopma işleme hatası: {e}")
            
    def handle_client(self, client_socket: socket.socket):
        """İstemciden gelen mesajları işler.
        
        Args:
            client_socket: İstemcinin socket bağlantısı
        """
        try:
            while self.running:
                try:
                    # 4096 byte boyutuna kadar mesaj kabul et
                    data = client_socket.recv(4096).decode('utf-8')
                    
                    # Veri gelmezse bağlantı kopmuş demektir
                    if not data:
                        self.log(f"Veri alınamadı: {self.get_client_name(client_socket)}")
                        break
                    
                    # İstemci aktivitesini güncelle
                    self.update_client_activity(client_socket)
                    
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
                        
                        # Yeniden bağlanma kontrolü yap (aynı cihaz kimliği varsa)
                        if device_id and device_id in self.disconnected_clients:
                            reconnect_data = self.disconnected_clients[device_id]
                            self.log(f"Kullanıcı yeniden bağlanıyor: {new_username} (Cihaz: {device_id})")
                            
                            # Eski odasına otomatik katılma isteği gönder
                            if reconnect_data["room"]:
                                self.log(f"Kullanıcı '{reconnect_data['room']}' odasına tekrar katılıyor.")
                                
                                # Yeniden bağlanma mesajı
                                reconnect_msg = json_helper.build_message(
                                    username="SERVER",
                                    message=f"{new_username} yeniden bağlandı!",
                                    source="host"
                                )
                                
                                # Özel odalarla ilgili şifre gerektiği için burada doğrudan katılamayız,
                                # İstemcinin kendi odasına yeniden katılması için bilgi mesajı
                                info_msg = json_helper.build_message(
                                    username="SERVER",
                                    message=f"Bağlantınız yeniden kuruldu. Önceki odanız: '{reconnect_data['room']}'",
                                    source="host",
                                    command="reconnect_info",
                                    params={"previousRoom": reconnect_data["room"]}
                                )
                                client_socket.send(json_helper.serialize_message(info_msg).encode('utf-8'))
                            
                            # Yeniden bağlanma kaydını sil
                            del self.disconnected_clients[device_id]
                        
                        # Kullanıcı adı benzersiz olmalı
                        if new_username in [info[1] for info in self.clients.values()]:
                            new_username = f"{new_username}_{len(self.clients)}"
                        
                        # İstemci bilgilerini güncelle
                        self.clients[client_socket] = (client_address, new_username, device_id)
                        self.client_info[new_username] = device_id
                        
                        # Aktif istemci bilgilerini güncelle
                        if client_socket in self.active_clients:
                            self.active_clients[client_socket].update({
                                "username": new_username,
                                "deviceId": device_id,
                                "last_active": datetime.datetime.now()
                            })
                        
                        # Cihaz kimliği varsa, cihaz tabanlı istemci listesine ekle
                        if device_id:
                            self.device_clients[device_id] = {
                                "socket": client_socket,
                                "username": new_username,
                                "connected_at": datetime.datetime.now()
                            }
                        
                        # Varsayılan odaya ekle ('Genel')
                        success, msg = self.room_manager.join_room(client_socket, "Genel", new_username)
                        
                        # İstemcinin oda bilgisini güncelle
                        if client_socket in self.active_clients:
                            self.active_clients[client_socket]["room"] = "Genel"
                        
                        # Yeni kullanıcının katıldığını herkese bildir
                        join_msg = json_helper.build_message(
                            username="SERVER",
                            message=f"{new_username} sohbete katıldı!",
                            source="host"
                        )
                        # Sadece Genel odadaki kullanıcılara bildirim gönder
                        self.room_manager.broadcast_to_room("Genel", json_helper.serialize_message(join_msg), client_socket)
                        self.log(f"Kullanıcı tanımlandı: {client_address} -> {new_username} (Cihaz: {device_id})")
                        
                        # Doğrudan devam et, kullanıcı kaydı tamamlandı
                        continue
                    
                    # Güncel kullanıcı bilgisini al
                    _, username, device_id = self.clients.get(client_socket, (client_address, "Bilinmeyen", None))
                    
                    # Özel komutları kontrol et (odalarla ilgili)
                    if "command" in message_obj:
                        self.handle_command(client_socket, message_obj)
                        continue
                    
                    # Mesaj işleme - Türüne göre normal mesaj, güncelleme veya silme işlemi yap
                    if "type" in message_obj and message_obj["type"] in ["update", "delete"]:
                        # Mesaj silme veya güncelleme işlemi
                        processed_message = self.message_handler.handle_message(client_socket, message_obj)
                        
                        if processed_message:
                            # İşlenmiş mesajı (bildirim) odaya yayınla
                            room_name = self.room_manager.get_client_room(client_socket)
                            if room_name:
                                # Odadaki herkese mesaj güncelleme/silme bildirimi gönder
                                self.message_handler.broadcast_message_to_room(room_name, processed_message, None)
                        continue
                    
                    # Normal mesaj - önce mesajı logla
                    self.log(json_helper.format_message_for_console(message_obj))
                    
                    # Mesajı işle ve saklama işlemini yap
                    processed_message = self.message_handler.handle_message(client_socket, message_obj)
                    
                    if not processed_message:
                        # Mesaj işleme başarısız oldu
                        error_msg = json_helper.build_message(
                            username="SERVER",
                            message="Mesaj işlenemedi.",
                            source="host"
                        )
                        client_socket.send(json_helper.serialize_message(error_msg).encode('utf-8'))
                        continue
                    
                    # Mesajı sadece kullanıcının bulunduğu odaya ilet
                    room_name = self.room_manager.get_client_room(client_socket)
                    if room_name:
                        # Mesaja oda bilgisini ekle
                        processed_message["roomName"] = room_name
                        # Mesajı odaya yayınla
                        self.room_manager.broadcast_to_room(
                            room_name, 
                            json_helper.serialize_message(processed_message), 
                            client_socket
                        )
                    else:
                        # Kullanıcı henüz bir odada değil, hata mesajı gönder
                        error_msg = json_helper.build_message(
                            username="SERVER",
                            message="Henüz bir odaya katılmadınız. Lütfen önce bir odaya katılın.",
                            source="host"
                        )
                        client_socket.send(json_helper.serialize_message(error_msg).encode('utf-8'))
                
                except json.JSONDecodeError as e:
                    self.log(f"JSON ayrıştırma hatası ({self.get_client_name(client_socket)}): {e}")
                except ConnectionResetError:
                    self.log(f"Bağlantı sıfırlandı: {self.get_client_name(client_socket)}")
                    break
                except Exception as e:
                    self.log(f"İstemci işleme hatası ({self.get_client_name(client_socket)}): {e}")
                    break
                    
        finally:
            # Bağlantı koptuğunda temizleme işlemleri
            self.handle_disconnection(client_socket, reason="client_closed")
    
    def handle_command(self, client_socket: socket.socket, message_obj: Dict[str, Any]):
        """Özel komutları işler (oda komutları vb.).
        
        Args:
            client_socket: İstemci socket nesnesi
            message_obj: Mesaj nesnesi
        """
        command = message_obj.get("command", "").lower()
        params = message_obj.get("params", {})
        _, username, _ = self.clients.get(client_socket, ("", "Bilinmeyen", ""))
        
        # Komutu logla
        self.log(f"Komut alındı ({username}): {command} {params}")
        
        response_msg = None
        
        # Komut tipine göre işle
        if command == "create_room":
            # Oda oluşturma komutu
            room_name = params.get("roomName", "")
            room_type = params.get("roomType", "public")
            password = params.get("password", None)
            
            if not room_name:
                response_msg = json_helper.build_message(
                    username="SERVER",
                    message="Oda adı belirtilmedi.",
                    source="host",
                    command="error"
                )
            else:
                success, msg = self.room_manager.create_room(room_name, room_type, password, username)
                response_msg = json_helper.build_message(
                    username="SERVER",
                    message=msg,
                    source="host",
                    command="create_room_result",
                    params={"success": success, "roomName": room_name}
                )
                
                # Oda oluşturuldu bilgisini tüm kullanıcılara bildir
                if success:
                    room_created_msg = json_helper.build_message(
                        username="SERVER",
                        message=f"'{username}' tarafından yeni bir oda oluşturuldu: '{room_name}' ({room_type})",
                        source="host"
                    )
                    # Tüm kullanıcılara yeni oda bilgisini ilet (tüm odalara)
                    for r_name in self.room_manager.rooms:
                        self.room_manager.broadcast_to_room(r_name, json_helper.serialize_message(room_created_msg))
        
        elif command == "join_room":
            # Odaya katılma komutu
            room_name = params.get("roomName", "")
            password = params.get("password", None)
            
            if not room_name:
                response_msg = json_helper.build_message(
                    username="SERVER",
                    message="Oda adı belirtilmedi.",
                    source="host",
                    command="error"
                )
            else:
                # Önceki oda bilgisini al
                old_room = self.room_manager.get_client_room(client_socket)
                
                # Yeni odaya katıl
                success, msg = self.room_manager.join_room(client_socket, room_name, username, password)
                
                response_msg = json_helper.build_message(
                    username="SERVER",
                    message=msg,
                    source="host",
                    command="join_room_result",
                    params={"success": success, "roomName": room_name}
                )
                
                # Başarılıysa, eski ve yeni odada bilgi mesajları gönder
                if success:
                    # Eski odadan ayrıldı bilgisi
                    if old_room:
                        leave_old_msg = json_helper.build_message(
                            username="SERVER",
                            message=f"{username} '{old_room}' odasından ayrıldı.",
                            source="host"
                        )
                        self.room_manager.broadcast_to_room(old_room, json_helper.serialize_message(leave_old_msg))
                    
                    # Yeni odaya katıldı bilgisi
                    join_new_msg = json_helper.build_message(
                        username="SERVER",
                        message=f"{username} '{room_name}' odasına katıldı.",
                        source="host"
                    )
                    self.room_manager.broadcast_to_room(room_name, json_helper.serialize_message(join_new_msg), client_socket)
                    
                    # Odaya katılan kullanıcıya oda bilgilerini gönder
                    self.send_room_info(client_socket, room_name)
        
        elif command == "leave_room":
            success, msg, room_name = self.room_manager.leave_room(client_socket)
            
            # Genel odaya geri yönlendir
            if success:
                # Ayrılma bilgisini odadaki diğer kullanıcılara bildir
                leave_msg = json_helper.build_message(
                    username="SERVER",
                    message=f"{username} '{room_name}' odasından ayrıldı.",
                    source="host"
                )
                self.room_manager.broadcast_to_room(room_name, json_helper.serialize_message(leave_msg))
                
                # Genel odaya katıl
                success, join_msg = self.room_manager.join_room(client_socket, "Genel", username)
                msg += f" {join_msg}"
            
            response_msg = json_helper.build_message(
                username="SERVER",
                message=msg,
                source="host",
                command="leave_room_result",
                params={"success": success, "roomName": room_name}
            )
        
        elif command == "list_rooms":
            # Odaları listeleme komutu
            rooms = self.room_manager.list_public_rooms()
            
            room_list_text = "Mevcut Odalar:\n"
            for room_info in rooms:
                room_list_text += f"- {room_info['roomName']} ({room_info['clientCount']} kullanıcı)\n"
            
            response_msg = json_helper.build_message(
                username="SERVER",
                message=room_list_text,
                source="host",
                command="list_rooms_result",
                params={"rooms": rooms}
            )
        
        elif command == "room_info":
            # Oda bilgisi komutu
            room_name = params.get("roomName", "")
            
            # Belirtilen oda yoksa, mevcut odayı kullan
            if not room_name:
                room_name = self.room_manager.get_client_room(client_socket)
            
            if not room_name:
                response_msg = json_helper.build_message(
                    username="SERVER",
                    message="Henüz bir odaya katılmadınız.",
                    source="host",
                    command="error"
                )
            else:
                room_info = self.room_manager.get_room_info(room_name)
                
                if room_info:
                    client_count = room_info["clientCount"]
                    client_list = ", ".join(room_info["clients"])
                    
                    room_type = "Herkese Açık" if room_info["roomType"] == "public" else "Özel"
                    room_info_text = f"Oda: {room_name} ({room_type})\n"
                    room_info_text += f"Oluşturan: {room_info['createdBy']}\n"
                    room_info_text += f"Kullanıcılar ({client_count}): {client_list}"
                    
                    response_msg = json_helper.build_message(
                        username="SERVER",
                        message=room_info_text,
                        source="host",
                        command="room_info_result",
                        params={"roomInfo": room_info}
                    )
                else:
                    response_msg = json_helper.build_message(
                        username="SERVER",
                        message=f"'{room_name}' adında bir oda bulunamadı.",
                        source="host",
                        command="error"
                    )
                    
        elif command == "delete_room":
            # Oda silme komutu (sadece oda sahibi veya SERVER)
            room_name = params.get("roomName", "")
            
            if not room_name:
                response_msg = json_helper.build_message(
                    username="SERVER",
                    message="Oda adı belirtilmedi.",
                    source="host",
                    command="error"
                )
            else:
                # Odayı ve sahibini kontrol et
                room_info = self.room_manager.get_room_info(room_name)
                
                if not room_info:
                    response_msg = json_helper.build_message(
                        username="SERVER",
                        message=f"'{room_name}' adında bir oda bulunamadı.",
                        source="host",
                        command="error"
                    )
                elif room_info["createdBy"] != username and username != "SERVER":
                    response_msg = json_helper.build_message(
                        username="SERVER",
                        message=f"'{room_name}' odasını silme yetkiniz yok.",
                        source="host",
                        command="error"
                    )
                else:
                    success, msg, affected_clients = self.room_manager.delete_room(room_name)
                    
                    response_msg = json_helper.build_message(
                        username="SERVER",
                        message=msg,
                        source="host",
                        command="delete_room_result",
                        params={"success": success, "roomName": room_name}
                    )
                    
                    # Başarılıysa etkilenen kullanıcıları Genel odaya yönlendir
                    if success:
                        # Tüm kullanıcılara oda kapandı bilgisini gönder
                        room_closed_msg = json_helper.build_message(
                            username="SERVER",
                            message=f"'{room_name}' odası kapatıldı.",
                            source="host"
                        )
                        
                        # Tüm odalara bildir
                        for r_name in self.room_manager.rooms:
                            self.room_manager.broadcast_to_room(r_name, json_helper.serialize_message(room_closed_msg))
                        
                        # Etkilenen kullanıcıları Genel odaya yönlendir
                        for client in affected_clients:
                            if client in self.clients:
                                _, c_username, _ = self.clients[client]
                                self.room_manager.join_room(client, "Genel", c_username)
                                
                                # Kullanıcıya bildirim gönder
                                notify_msg = json_helper.build_message(
                                    username="SERVER",
                                    message=f"'{room_name}' odası kapandı. 'Genel' odasına yönlendirildiniz.",
                                    source="host"
                                )
                                client.send(json_helper.serialize_message(notify_msg).encode('utf-8'))
        
        else:
            # Bilinmeyen komut
            response_msg = json_helper.build_message(
                username="SERVER",
                message=f"Bilinmeyen komut: {command}",
                source="host",
                command="error"
            )
        
        # Cevap mesajını gönder (varsa)
        if response_msg:
            client_socket.send(json_helper.serialize_message(response_msg).encode('utf-8'))
    
    def send_room_info(self, client_socket: socket.socket, room_name: str = None):
        """İstemciye oda bilgilerini gönderir.
        
        Args:
            client_socket: İstemci socket nesnesi
            room_name: Belirli bir oda adı (belirtilmezse tüm odalar)
        """
        if room_name:
            # Belirli bir oda hakkında bilgi
            room_info = self.room_manager.get_room_info(room_name)
            
            if room_info:
                # İstemciye oda bilgisini gönder
                room_info_msg = json_helper.build_message(
                    username="SERVER",
                    message=f"Oda bilgisi: {room_name}",
                    source="host",
                    command="room_info_result",
                    params={"roomInfo": room_info}
                )
                client_socket.send(json_helper.serialize_message(room_info_msg).encode('utf-8'))
        else:
            # Tüm odaların listesi
            rooms = self.room_manager.list_public_rooms()
            
            # İstemciye oda listesini gönder
            room_list_msg = json_helper.build_message(
                username="SERVER",
                message="Kullanılabilir odalar",
                source="host",
                command="list_rooms_result",
                params={"rooms": rooms}
            )
            client_socket.send(json_helper.serialize_message(room_list_msg).encode('utf-8'))
    
    def send_to_client(self, client_socket: socket.socket, message: str) -> bool:
        """Belirli bir istemciye mesaj gönderir. RoomManager için callback olarak kullanılır.
        
        Args:
            client_socket: İstemci socket nesnesi
            message: Gönderilecek mesaj (JSON string)
            
        Returns:
            İşlem başarılıysa True, değilse False
        """
        try:
            client_socket.send(message.encode('utf-8'))
            return True
        except:
            return False
            
    def broadcast(self, message: str, sender_socket: socket.socket = None, system_message: bool = False):
        """Mesajı tüm bağlı istemcilere iletir. (Bu fonksiyon artık sadece sistem mesajları için kullanılır)
        
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
                
                # İstemciyi odadan çıkar
                self.room_manager.remove_client(client)
                
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
    print("JSON mesaj formatı ve oda sistemi kullanılıyor.")
    
    # Örnek mesaj formatını ekrana yazdır
    print("\nÖrnek JSON mesaj formatı:")
    print(json.dumps(json_helper.EXAMPLE_MESSAGE, indent=2))
    
    # Oda komutlarını göster
    print("\nKullanılabilir Oda Komutları:")
    print("- create_room: Yeni bir oda oluşturur")
    print("- join_room: Bir odaya katılır")
    print("- leave_room: Mevcut odadan ayrılır")
    print("- list_rooms: Mevcut odaları listeler")
    print("- room_info: Oda hakkında bilgi verir")
    print("- delete_room: Bir odayı siler (sadece oda sahibi)")
    
    print("\nBağlantı Yönetimi:")
    print("- Zamanaşımı kontrolü: 300 saniye (5 dakika) inaktif bağlantılar otomatik sonlandırılır")
    print("- Bağlantı kopunca otomatik odadan çıkarma ve bildirim gönderme")
    print("- Aynı cihaz kimliği ile yeniden bağlanma desteği")
    
    print("\nSunucu başlatılıyor...\n")
    
    # Sunucu örneğini oluştur ve başlat (5 dakika zamanaşımı süresi)
    server = ChatServer(inactivity_timeout=300)
    
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nSunucu kullanıcı tarafından durduruldu.")
    finally:
        server.stop()


if __name__ == "__main__":
    main() 