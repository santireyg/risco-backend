# app/core/database.py

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.server_api import ServerApi
from app.core.config import MONGO_URI, MONGO_DB

# Cliente asíncrono para MongoDB
client = AsyncIOMotorClient(MONGO_URI, server_api=ServerApi('1'))
db = client[MONGO_DB]

# Colecciones de la base de datos
users_collection = db["users"]
docs_collection = db["documents"]