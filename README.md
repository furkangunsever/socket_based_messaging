# Socket Tabanlı Çok Kullanıcılı Sohbet Sunucusu

Bu proje, gerçek zamanlı mesajlaşmayı sağlayan çok kullanıcılı bir socket sunucusu uygulamasıdır.

## Özellikler

- Çoklu istemci desteği
- Gerçek zamanlı mesajlaşma
- Modüler ve genişletilebilir yapı
- Thread tabanlı bağlantı yönetimi

## Kurulum

1. Python 3.x sürümünün yüklü olduğundan emin olun
2. Gerekli kütüphaneleri yükleyin:
   ```bash
   pip install -r requirements.txt
   ```
3. Sunucuyu başlatın:
   ```bash
   python main.py
   ```

## Proje Yapısı

- `main.py`: Ana sunucu uygulaması
- `handlers/`: Bağlantı yönetimi ve mesaj işleme modülleri
- `utils/`: Yardımcı fonksiyonlar ve araçlar
