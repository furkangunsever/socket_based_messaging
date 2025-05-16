"""
Firebase entegrasyonu için yardımcı fonksiyonlar
"""
from typing import Dict, Any, Optional
import os
import json
import aiohttp
from app.core.logger import log

# Firebase URL ve API anahtarınızı burada tanımlayın
# Bu bilgileri .env dosyasından alabilirsiniz
FIREBASE_URL = "https://messagingapp-36171-default-rtdb.europe-west1.firebasedatabase.app"
FIREBASE_API_KEY = "AIzaSyCkxjbPvwuEXwspk-aVJPtPAsruQC5FwXU"

async def get_firebase_rooms() -> Dict[str, Dict[str, Any]]:
    """
    Firebase'den tüm odaları alır
    
    Returns:
        Dict[str, Dict[str, Any]]: Oda ID'lerine göre oda bilgilerini içeren sözlük
    """
    if not FIREBASE_URL:
        log.warning("Firebase URL tanımlanmamış")
        return {}
        
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{FIREBASE_URL}/chat_rooms.json") as response:
                if response.status == 200:
                    data = await response.json()
                    return data or {}
                else:
                    log.error(f"Firebase odaları alınamadı. Durum kodu: {response.status}")
                    return {}
    except Exception as e:
        log.error(f"Firebase odaları alınırken hata: {str(e)}")
        return {}

async def get_firebase_room_by_id(room_id: str) -> Optional[Dict[str, Any]]:
    """
    Firebase'den belirli bir odayı ID'ye göre alır
    
    Args:
        room_id (str): Oda ID'si
        
    Returns:
        Optional[Dict[str, Any]]: Oda bilgileri veya None
    """
    if not FIREBASE_URL:
        log.warning("Firebase URL tanımlanmamış")
        return None
        
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{FIREBASE_URL}/chat_rooms/{room_id}.json") as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    log.error(f"Firebase oda alınamadı. Durum kodu: {response.status}")
                    return None
    except Exception as e:
        log.error(f"Firebase oda alınırken hata: {str(e)}")
        return None

async def save_room_to_firebase(room_id: str, room_data: Dict[str, Any]) -> bool:
    """
    Odayı Firebase'e kaydeder
    
    Args:
        room_id (str): Oda ID'si
        room_data (Dict[str, Any]): Oda verileri
        
    Returns:
        bool: İşlem başarılı ise True, değilse False
    """
    if not FIREBASE_URL:
        log.warning("Firebase URL tanımlanmamış")
        return False
        
    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(f"{FIREBASE_URL}/chat_rooms/{room_id}.json", json=room_data) as response:
                if response.status in (200, 201):
                    return True
                else:
                    log.error(f"Firebase oda kaydedilemedi. Durum kodu: {response.status}")
                    return False
    except Exception as e:
        log.error(f"Firebase oda kaydedilirken hata: {str(e)}")
        return False

async def delete_room_from_firebase(room_id: str) -> bool:
    """
    Odayı Firebase'den siler
    
    Args:
        room_id (str): Oda ID'si
        
    Returns:
        bool: İşlem başarılı ise True, değilse False
    """
    if not FIREBASE_URL:
        log.warning("Firebase URL tanımlanmamış")
        return False
        
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(f"{FIREBASE_URL}/chat_rooms/{room_id}.json") as response:
                if response.status in (200, 204):
                    return True
                else:
                    log.error(f"Firebase oda silinemedi. Durum kodu: {response.status}")
                    return False
    except Exception as e:
        log.error(f"Firebase oda silinirken hata: {str(e)}")
        return False 