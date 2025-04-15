#!/usr/bin/env python3
"""
JSON formatında mesaj alışverişi yapabilen istemci test örneği.
Sunucuya bağlanıp otomatik olarak test mesajları gönderir.
"""

import json
import time
import sys
import os
import random
from typing import List, Dict, Any

# Proje kök dizinini Python modül yoluna ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Client modülünü import et
from client import ChatClient
from utils import json_helper


def main():
    """Test istemcisini çalıştırır."""
    print("===== JSON Mesaj Test İstemcisi =====")
    
    # Komut satırı parametrelerini kontrol et
    host = 'localhost'
    port = 12345
    
    if len(sys.argv) >= 2:
        host = sys.argv[1]
    if len(sys.argv) >= 3:
        try:
            port = int(sys.argv[2])
        except ValueError:
            print(f"Hatalı port numarası: {sys.argv[2]}")
            sys.exit(1)
    
    # Test kullanıcı adları
    test_usernames = [
        "Test_Kullanıcı",
        "JSON_Tester",
        "Ahmet_Test"
    ]
    
    # Test mesajları
    test_messages = [
        "Merhaba, bu bir test mesajıdır!",
        "JSON formatında mesajlaşma testi yapıyorum",
        "Uzun bir mesaj örneği: Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nullam nec dui nec ante facilisis fermentum.",
        "Özel karakterler: Türkçe (ğüşiöç), emojiler 🙂👍🎉",
        "Socket sunucusu JSON formatında çalışıyor!"
    ]
    
    # Rastgele bir kullanıcı adı seç
    username = random.choice(test_usernames)
    
    # İstemci nesnesi oluştur
    client = ChatClient(host, port)
    client.set_username(username)
    
    print(f"Test istemcisi '{username}' olarak başlatılıyor...")
    print(f"Hedef sunucu: {host}:{port}")
    
    # Sunucuya bağlan
    if not client.connect():
        print("Sunucuya bağlanılamadı!")
        sys.exit(1)
    
    print("Bağlantı başarılı.")
    print(f"5 saniye içinde {len(test_messages)} adet test mesajı gönderilecek...")
    time.sleep(5)
    
    # Test mesajlarını gönder
    for i, message in enumerate(test_messages, 1):
        print(f"\nTest mesajı #{i} gönderiliyor...")
        
        if not client.send_message(message):
            print("Mesaj gönderilemedi!")
            break
        
        # Her mesaj arasında 3 saniye bekle
        time.sleep(3)
    
    print("\nTüm test mesajları gönderildi.")
    print("İstemci 5 saniye daha aktif kalacak ve kapatılacak...")
    time.sleep(5)
    
    # İstemciyi kapat
    client.disconnect()
    print("Test tamamlandı.")


if __name__ == "__main__":
    main() 