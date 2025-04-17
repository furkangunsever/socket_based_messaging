# Socket.IO Tabanlı Çok Kullanıcılı Sohbet Uygulaması

Bu proje, mobil cihazlar arasında Socket.IO kullanarak gerçek zamanlı mesajlaşmayı mümkün kılan bir sohbet uygulamasının backend kısmını içerir.

## Özellikler

- FastAPI ve python-socketio ile gerçek zamanlı iletişim
- Çoklu kullanıcı desteği
- Sohbet odaları
- Mesaj geçmişi
- Kullanıcı durumu izleme

## Kurulum

1. Bağımlılıkları yükleyin:

   ```bash
   pip install -r requirements.txt
   ```

2. `.env` dosyasını gerektiğinde düzenleyin.

3. Uygulamayı başlatın:
   ```bash
   uvicorn app.main:socket_app --reload
   ```

## API Endpoints

- **GET /**: Ana sayfa
- **GET /docs**: API dokümantasyonu (FastAPI tarafından otomatik oluşturulur)

## Socket.IO Olayları

- `connect`: Kullanıcı bağlantısı
- `disconnect`: Kullanıcı bağlantı kesimi
- `join_room`: Bir odaya katılma
- `leave_room`: Bir odadan ayrılma
- `send_message`: Mesaj gönderme
- `user_typing`: Kullanıcı yazıyor bildirimi

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
