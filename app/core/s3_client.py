# app/core/s3_client.py

import boto3
from botocore.config import Config
from urllib.parse import urlparse
from app.core.config import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION, S3_BUCKET_NAME

# Configuración del pool de conexiones para evitar warnings de pool lleno
boto_config = Config(
    # Configuración del pool de conexiones
    max_pool_connections=50,  # Aumentar el tamaño del pool (default es 10)
    
    # Configuración de S3
    s3={
        'addressing_style': 'virtual'
    },
    signature_version='s3v4',
    
    # Configuración de reintentos
    retries={
        'max_attempts': 3,
        'mode': 'adaptive'  # Se adapta automáticamente a las condiciones de la red
    },
    
    # Timeouts para evitar conexiones colgadas
    connect_timeout=5,
    read_timeout=30
)

# Crea el cliente de S3 con configuración específica para evitar redirects
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_DEFAULT_REGION,
    config=boto_config
)

def generate_presigned_url(key: str, expiration: int = 3600) -> str:
    """
    Genera una URL prefirmada para acceder a un objeto en S3.
    :param key: La clave del objeto en el bucket.
    :param expiration: Tiempo en segundos de validez de la URL.
    :return: URL prefirmada.
    """
    try:
        # Generar URL con endpoint específico de la región
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': S3_BUCKET_NAME, 
                'Key': key
            },
            ExpiresIn=expiration,
            HttpMethod='GET'
        )
        
        # Forzar el uso del endpoint regional si no lo está usando
        if f".s3.{AWS_DEFAULT_REGION}.amazonaws.com" not in url:
            url = url.replace(
                f"{S3_BUCKET_NAME}.s3.amazonaws.com",
                f"{S3_BUCKET_NAME}.s3.{AWS_DEFAULT_REGION}.amazonaws.com"
            )
        
        return url
        
    except Exception as e:
        raise e

def get_presigned_url_from_image_path(image_url: str, expiration: int = 3600) -> str:
    """
    Dado el valor almacenado en la base de datos (la URL completa), extrae la clave del objeto y
    devuelve una URL prefirmada.
    :param image_url: URL original almacenada (por ejemplo: 
                      "https://integrity-caucion-bucket.s3.amazonaws.com/test/documents/xxx/images/page_001.png")
    :param expiration: Tiempo en segundos de validez de la URL.
    :return: URL prefirmada para acceder al objeto.
    """
    try:
        parsed = urlparse(image_url)
        # Se asume que la clave es la parte del path sin la barra inicial
        key = parsed.path.lstrip("/")
        
        # Verificar si el objeto existe en S3 antes de generar la URL
        try:
            s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=key)
        except Exception as head_error:
            raise Exception(f"Object not found in S3: {key}")
        
        return generate_presigned_url(key, expiration)
        
    except Exception as e:
        raise e
