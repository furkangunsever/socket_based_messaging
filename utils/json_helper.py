"""
JSON tabanlı mesajlar için yardımcı fonksiyonlar.
Bu modül, mesajların JSON formatında işlenmesi için gerekli fonksiyonları içerir.
"""

import json
import uuid
import datetime
from typing import Dict, Any, Optional, Union, Tuple


def parse_message(json_str: str) -> Tuple[bool, Union[Dict[str, Any], str]]:
    """Gelen JSON mesajını ayrıştırır ve gerekli alanları kontrol eder.
    
    Args:
        json_str: JSON formatındaki mesaj verisi
        
    Returns:
        (başarı, veri) tuple:
            - başarı: Ayrıştırma başarılıysa True, değilse False
            - veri: Başarılıysa mesaj dict'i, başarısızsa hata mesajı
    """
    try:
        # JSON verisi ayrıştırılıyor
        data = json.loads(json_str)
        
        # Zorunlu alanların kontrolü
        required_fields = ["username", "message"]
        for field in required_fields:
            if field not in data:
                return False, f"Eksik alan: {field}"
        
        # Timestamp alanı yoksa ekleyelim
        if "timestamp" not in data:
            data["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
            
        # Kaynak belirtilmemişse istemci kabul et
        if "source" not in data:
            data["source"] = "client"
            
        # Cihaz kimliği yoksa None ata
        if "deviceId" not in data:
            data["deviceId"] = None
            
        # Mesaj kimliği yoksa UUID ata
        if "messageId" not in data:
            data["messageId"] = str(uuid.uuid4())
            
        return True, data
        
    except json.JSONDecodeError as e:
        return False, f"JSON ayrıştırma hatası: {str(e)}"
    except Exception as e:
        return False, f"Beklenmeyen hata: {str(e)}"


def build_message(username: str,
                 message: str,
                 source: str = "host", 
                 device_id: Optional[str] = None,
                 message_id: Optional[str] = None,
                 timestamp: Optional[str] = None) -> Dict[str, Any]:
    """Belirli alanlardan yeni bir mesaj nesnesi oluşturur.
    
    Args:
        username: Kullanıcı adı
        message: Mesaj içeriği
        source: Mesaj kaynağı ("host" veya "client")
        device_id: Cihaz kimliği (opsiyonel)
        message_id: Mesaj kimliği (opsiyonel, belirtilmezse UUID atanır)
        timestamp: Zaman damgası (opsiyonel, belirtilmezse şimdiki zaman atanır)
        
    Returns:
        Oluşturulan mesaj nesnesi
    """
    # Temel mesaj yapısı
    msg = {
        "username": username,
        "message": message,
        "source": source,
        "deviceId": device_id,
        "messageId": message_id or str(uuid.uuid4()),
        "timestamp": timestamp or datetime.datetime.utcnow().isoformat() + "Z"
    }
    
    return msg


def serialize_message(message: Dict[str, Any]) -> str:
    """Mesaj nesnesini JSON string'e dönüştürür.
    
    Args:
        message: Mesaj nesnesi
        
    Returns:
        JSON formatındaki mesaj string'i
    """
    return json.dumps(message)


def format_message_for_console(message: Dict[str, Any]) -> str:
    """Mesaj nesnesini konsolda görüntülemek için formatlar.
    
    Args:
        message: Mesaj nesnesi
        
    Returns:
        Formatlanmış mesaj string'i
    """
    # ISO formatındaki timestamp'i datetime nesnesine çevir
    try:
        timestamp = datetime.datetime.fromisoformat(message["timestamp"].replace("Z", "+00:00"))
        time_str = timestamp.strftime("%H:%M:%S")
    except:
        time_str = "??:??"
    
    # Kaynak bilgisi
    source_icon = "↪" if message["source"] == "client" else "↩"
    
    # Formatlanmış mesaj
    return f"[{message['username']}] {time_str} {source_icon} {message['message']}"


def is_valid_json(json_str: str) -> bool:
    """Bir string'in geçerli JSON olup olmadığını kontrol eder.
    
    Args:
        json_str: Kontrol edilecek string
        
    Returns:
        Geçerli JSON ise True, değilse False
    """
    try:
        json.loads(json_str)
        return True
    except:
        return False


# Örnek mesaj formatı (referans için)
EXAMPLE_MESSAGE = {
    "username": "ahmet",
    "deviceId": "123456",
    "message": "Merhaba!",
    "timestamp": "2023-04-15T12:34:56Z",
    "source": "client",
    "messageId": "550e8400-e29b-41d4-a716-446655440000"
} 