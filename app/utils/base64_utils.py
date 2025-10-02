# app/utils/base64_utils.py

import base64
from pathlib import Path
from urllib.parse import urlparse

# Importamos el cliente S3 y la configuración
from app.core.s3_client import s3_client
from app.core.config import S3_BUCKET_NAME

def get_base64_encoded_image(image_path: str) -> str:
    """
    Devuelve la imagen codificada en base64.
    Si image_path es una URL (almacenada en S3), descarga el archivo desde S3.
    Si no, lo lee desde el sistema de archivos local.
    """
    if image_path.startswith("https://"):
        # Se asume que la URL es de la forma: https://{bucket}.s3.amazonaws.com/{key}
        parsed = urlparse(image_path)
        key = parsed.path.lstrip("/")
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=key)
        file_content = response['Body'].read()
    else:
        file_content = Path(image_path).read_bytes()
    
    # Codificar a base64
    encoded_image = base64.b64encode(file_content).decode('utf-8')
    
    # Liberar file_content inmediatamente
    del file_content
    
    return encoded_image
