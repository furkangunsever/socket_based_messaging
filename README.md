# Socket.IO Tabanlı Çok Kullanıcılı Sohbet Uygulaması

Bu proje, mobil cihazlar arasında Socket.IO kullanarak gerçek zamanlı mesajlaşmayı mümkün kılan bir sohbet uygulamasının backend kısmını içerir.

## Özellikler

- FastAPI ve python-socketio ile gerçek zamanlı iletişim
- Çoklu kullanıcı desteği
- Sohbet odaları (genel ve şifre korumalı özel odalar)
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

### Mesaj İşlemleri

- `send_message`: Odaya mesaj gönderme
- `update_message`: Mesaj düzenleme
- `delete_message`: Mesaj silme
- `typing_status`: Kullanıcı yazıyor bildirimi

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
