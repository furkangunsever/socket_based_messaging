# Socket.IO Tabanlı Çok Kullanıcılı Sohbet Uygulaması

Bu proje, mobil cihazlar arasında Socket.IO kullanarak gerçek zamanlı mesajlaşmayı mümkün kılan bir sohbet uygulamasının backend kısmını içerir.

## Özellikler

- FastAPI ve python-socketio ile gerçek zamanlı iletişim
- Çoklu kullanıcı desteği
- Sohbet odaları (genel ve şifre korumalı özel odalar)
- Otomatik oda listesi güncellemesi
- Mesaj gönderme, düzenleme ve silme
- Mesaj geçmişi
- Kullanıcı durumu izleme

## Kurulum

### Yerel Geliştirme

1. Bağımlılıkları yükleyin:

   ```bash
   pip install -r requirements.txt
   ```

2. `.env` dosyasını gerektiğinde düzenleyin.

3. Uygulamayı başlatın:
   ```bash
   uvicorn app.main:socket_app --reload
   ```

### Render.com Deployment

Bu proje, Render.com üzerinde doğrudan deploy edilebilir.

1. Ana dosya olarak `app/main.py` kullanılır
2. Socket.IO entegrasyonu için `socket_app` ASGI uygulaması kullanılır
3. Deploy komutu: `uvicorn app.main:socket_app --host 0.0.0.0 --port $PORT`

Otomatik deployment için repo kökünde `render.yaml` dosyası bulunmaktadır.

## API Endpoints

- **GET /**: Ana sayfa (Socket.IO kullanım örnekleri)
- **GET /docs**: API dokümantasyonu (FastAPI tarafından otomatik oluşturulur)
- **GET /health**: Servis sağlık kontrolü

## Socket.IO Olayları

### Bağlantı İşlemleri

- `connect`: Kullanıcı bağlantısı
- `authenticate`: Kullanıcı kimlik doğrulama
- `disconnect`: Kullanıcı bağlantı kesimi

### Oda İşlemleri

- `create_room`: Yeni sohbet odası oluşturma (public/private)
- `join_room`: Bir odaya katılma
- `leave_room`: Bir odadan ayrılma
- `get_rooms`: Aktif odaları listeleme

### Otomatik Bildirimler

- `rooms_list`: Oda listesi güncellendiğinde tüm istemcilere otomatik olarak gönderilir
  - Oda oluşturulduğunda
  - Boş oda silindiğinde (son kullanıcı ayrıldığında)
- `room_created`: Oda oluşturulduğunda olusturana bildirilir
- `user_joined_room`: Bir kullanıcı odaya katıldığında odadaki herkese bildirilir
- `user_left_room`: Bir kullanıcı odadan ayrıldığında odadaki herkese bildirilir

### Mesaj İşlemleri

- `send_message`: Odaya mesaj gönderme
- `update_message`: Mesaj düzenleme
- `delete_message`: Mesaj silme
- `typing_status`: Kullanıcı yazıyor bildirimi
- `broadcast_message`: Tüm bağlı kullanıcılara yayın mesajı gönderme

## Proje Yapısı

```
app/
  ├── main.py                # Uygulamanın giriş noktası
  ├── sockets/               # Socket.IO olaylarını yöneten modüller
  │   ├── connection.py      # Bağlantı yönetimi
  │   ├── message.py         # Mesaj işlemleri
  │   └── room.py            # Oda işlemleri
  ├── models/                # Pydantic modelleri
  │   ├── message.py         # Mesaj modeli
  │   └── user.py            # Kullanıcı modeli
  └── core/                  # Ortak yardımcılar, yapılandırmalar
      ├── config.py          # Uygulama yapılandırması
      └── logger.py          # Loglama yapılandırması
```
<p align="center">
  <img src="https://github.com/user-attachments/assets/7d664b64-f489-4c67-8f40-50a8e444dc2e" width="250"/>
  <img src="https://github.com/user-attachments/assets/ca58a290-1a8e-44af-8d92-79a1a016d7b4" width="250"/>
  <img src="https://github.com/user-attachments/assets/ab93c963-9728-493d-8cbd-a47f5884529b" width="250"/>
</p>

<p align="center">
  <img src="https://github.com/user-attachments/assets/81347582-4d48-4b21-81c6-82badfceb009" width="250"/>
  <img src="https://github.com/user-attachments/assets/06cc8af0-1e39-4bf5-a20d-1e7a837eed78" width="250"/>
  <img src="https://github.com/user-attachments/assets/a662a9f9-deda-4f7d-ac59-eaf140f7ddd1" width="250"/>
</p>

<p align="center">
  <img src="https://github.com/user-attachments/assets/cb9d0f88-f3d3-4208-8a8a-2d0894ae16cb" width="250"/>
  <img src="https://github.com/user-attachments/assets/569c680a-9372-43db-9914-fb5ddb92aa19" width="250"/>
</p>







