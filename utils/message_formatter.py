"""
Mesaj formatlamak için yardımcı fonksiyonlar.
Bu modül, mesajları işlemek ve formatlamak için gerekli araçları içerir.
"""

import json
import datetime
from typing import Dict, Any, Optional

def format_system_message(content: str) -> str:
    """Sistem mesajını formatlar.
    
    Args:
        content: Mesaj içeriği
        
    Returns:
        Formatlanmış sistem mesajı
    """
    return f"[SERVER] {content}"

def format_user_message(username: str, content: str) -> str:
    """Kullanıcı mesajını formatlar.
    
    Args:
        username: Kullanıcı adı
        content: Mesaj içeriği
        
    Returns:
        Formatlanmış kullanıcı mesajı
    """
    return f"[{username}] {content}"

def create_message_object(message_type: str, sender: str, content: str, 
                         recipient: Optional[str] = None) -> Dict[str, Any]:
    """JSON formatında mesaj nesnesi oluşturur.
    
    Bu yapı, ileride mesaj formatını JSON'a geçirmek istenirse kullanılabilir.
    
    Args:
        message_type: Mesaj tipi ('chat', 'system', 'private', vb.)
        sender: Gönderen kullanıcı
        content: Mesaj içeriği
        recipient: Alıcı kullanıcı (özel mesaj için)
        
    Returns:
        Mesaj nesnesi
    """
    timestamp = datetime.datetime.now().isoformat()
    
    message = {
        "type": message_type,
        "sender": sender,
        "content": content,
        "timestamp": timestamp
    }
    
    if recipient:
        message["recipient"] = recipient
        
    return message

def serialize_message(message: Dict[str, Any]) -> str:
    """Mesaj nesnesini JSON formatına dönüştürür.
    
    Args:
        message: Mesaj nesnesi
        
    Returns:
        JSON formatında mesaj
    """
    return json.dumps(message)

def deserialize_message(json_data: str) -> Dict[str, Any]:
    """JSON formatındaki mesajı nesneye dönüştürür.
    
    Args:
        json_data: JSON formatında mesaj
        
    Returns:
        Mesaj nesnesi
    """
    try:
        return json.loads(json_data)
    except json.JSONDecodeError:
        # Eğer geçerli JSON değilse, düz metin olarak ele al
        return {
            "type": "chat",
            "sender": "unknown",
            "content": json_data,
            "timestamp": datetime.datetime.now().isoformat()
        }

def parse_command(message: str) -> tuple:
    """Mesajın komut olup olmadığını kontrol eder.
    
    Örnek: /pm username mesaj içeriği
           /list
           /help
    
    Args:
        message: Mesaj içeriği
        
    Returns:
        (komut, parametre) tuple'ı veya komut değilse (None, None)
    """
    if not message.startswith('/'):
        return None, None
        
    parts = message.strip().split(' ', 2)
    command = parts[0][1:]  # Baştaki / işaretini kaldır
    
    if len(parts) > 1:
        param = parts[1]
        
        # Özel durum: /pm username message
        if command == 'pm' and len(parts) > 2:
            return command, (param, parts[2])  # (username, message)
            
        return command, param
        
    return command, None 