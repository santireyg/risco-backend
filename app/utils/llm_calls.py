# app/utils/llm_calls.py

import base64
from PIL import Image
import io
import os
from typing import List
from app.models.docs_recognition import RecognizedInfo
from app.models.docs_report import AIReport
from app.utils.llm_clients import get_openai_client, get_anthropic_client

def get_base64_encoded_image(image_path: str) -> str:
    """Convierte una imagen a una cadena codificada en base64."""
    with open(image_path, "rb") as image_file:
        binary_data = image_file.read()
    return base64.b64encode(binary_data).decode('utf-8')

def get_base64_encoded_images_from_pages(pages: List[dict]) -> List[str]:
    """
    Recibe una lista de páginas (como diccionarios) y devuelve una lista de imágenes codificadas en base64.
    Si la imagen requiere rotación, se procesa previamente.
    """
    base64_strings = []
    for page in pages:
        image_path = page['image_path'].lstrip("/")
        with Image.open(image_path) as img:
            buffered = io.BytesIO()
            if page.get('rotation_degrees', 0) != 0:
                img = img.rotate(-page.get('rotation_degrees', 0), expand=True)
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            base64_strings.append(img_str)
            
            # Limpiar buffer explícitamente
            buffered.close()
            buffered = None
            
    return base64_strings

def openai_image(indications: str, image_path: str, model: str = "gpt-4o-mini"):
    """
    Envía una imagen y unas indicaciones al modelo de OpenAI y retorna el resultado
    formateado según el modelo RecognizedInfo.
    """
    client = get_openai_client()
    image_data = get_base64_encoded_image(image_path)
    response = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": indications},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
                ],
            }
        ],
        response_format=RecognizedInfo,
    )
    return response.choices[0].message.parsed

def anthropic_images(
    indications: str,
    pages: List[dict],
    model: str = "claude-3-5-haiku-20241022",
    temperature: float = 0.1,
    max_tokens: int = 7000,
    image_media_type: str = "image/png"
) -> str:
    """
    Toma una lista de páginas, codifica las imágenes en base64, arma el mensaje y lo envía
    al modelo de Anthropic para obtener un JSON con la extracción.
    """
    user_message_content = []
    base64_images = get_base64_encoded_images_from_pages(pages)
    for i, image in enumerate(base64_images):
        user_message_content.append({
            "type": "text",
            "text": f"Imagen {i+1}:"
        })
        user_message_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": image_media_type,
                "data": image,
            },
        })
    user_message_content.append({
        "type": "text",
        "text": indications
    })
    client = get_anthropic_client()
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {
                "role": "user",
                "content": user_message_content
            },
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "Aquí está el JSON solicitado:"
                    }
                ],
            },
        ],
    )
    return message.content[0].text

def openai_text(indications: str, data: str, model: str = "gpt-4o-mini") -> dict:
    """
    Envía texto e indicaciones al modelo de OpenAI y retorna el resultado formateado según AIReport.
    """
    client = get_openai_client()
    response = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": indications},
                    {"type": "text", "text": f"DATOS:\n{data}"},
                ]
            }
        ],
        response_format=AIReport,
        max_tokens=4000,
    )
    return response.choices[0].message.parsed
