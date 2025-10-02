# app/utils/llm_clients.py

import os
from openai import OpenAI
import anthropic
from dotenv import load_dotenv

load_dotenv()

def get_openai_client() -> OpenAI:
    """Retorna una instancia del cliente de OpenAI."""
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_anthropic_client() -> anthropic.Anthropic:
    """Retorna una instancia del cliente de Anthropic."""
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
