#!/usr/bin/env python3
"""
QR Code Generator для VPN конфигов
Генерирует QR коды для быстрого сканирования на мобильных устройствах
"""

import logging
from typing import Optional
from io import BytesIO

logger = logging.getLogger(__name__)

try:
    import qrcode
    from PIL import Image
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False
    logger.warning("qrcode not installed. Install: pip install qrcode[pil]")


def generate_qr_code(
    data: str,
    size: int = 10,
    border: int = 4,
    error_correction: str = "M"
) -> Optional[BytesIO]:
    """
    Generate QR code image from data
    
    Args:
        data: Data to encode (VLESS link)
        size: Box size (default: 10)
        border: Border size (default: 4)
        error_correction: Error correction level (L/M/Q/H, default: M)
    
    Returns:
        BytesIO object with PNG image, or None if qrcode not available
    """
    if not QR_AVAILABLE:
        logger.warning("QR code generation not available")
        return None
    
    # Map error correction
    error_map = {
        'L': qrcode.constants.ERROR_CORRECT_L,
        'M': qrcode.constants.ERROR_CORRECT_M,
        'Q': qrcode.constants.ERROR_CORRECT_Q,
        'H': qrcode.constants.ERROR_CORRECT_H
    }
    error_level = error_map.get(error_correction, qrcode.constants.ERROR_CORRECT_M)
    
    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=error_level,
        box_size=size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    # Create image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to BytesIO
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return img_bytes


def generate_qr_code_for_vless(vless_link: str) -> Optional[BytesIO]:
    """
    Generate QR code for VLESS link
    
    Args:
        vless_link: VLESS connection string
    
    Returns:
        BytesIO object with PNG image, or None if qrcode not available
    """
    return generate_qr_code(vless_link, size=10, border=4)


# Example usage
if __name__ == "__main__":
    test_link = "vless://f56fb669-32ec-4142-b2fe-8b65c4321102@89.125.1.107:39829?type=tcp&encryption=none&security=reality&pbk=xMwVfOuehQZwVHPodTvo3TJEGUYUbxmGTeAxMUBWpww&fp=chrome&sni=google.com&sid=6b&spx=%2Fwatch%3Fv%3DdQw4w9WgXcQ&flow=xtls-rprx-vision#x0tta6bl4_VPN"
    
    qr_image = generate_qr_code_for_vless(test_link)
    if qr_image:
        with open("test_qr.png", "wb") as f:
            f.write(qr_image.read())
        print("QR code saved to test_qr.png")
    else:
        print("QR code generation not available. Install: pip install qrcode[pil]")

