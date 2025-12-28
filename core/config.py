"""
Configuration de l'application FastAPI pour GCP.
"""

import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

class Settings:
    """Configuration générale de l'application"""
    
    # API
    API_TITLE = "Product Search API"
    API_VERSION = "1.0.0"
    API_DESCRIPTION = "API de recherche hybride avec filtres LLM et recherche vectorielle"
    
    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8080))
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    
    # MongoDB
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGO_DB = os.getenv("MONGO_DB", "Qualiwo")
    MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "products")
    
    # LLM / Gemini
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-pro")
    
    # Recherche
    VECTOR_SEARCH_ENABLED = os.getenv("VECTOR_SEARCH_ENABLED", "True").lower() == "true"
    DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", 10))
    MAX_LIMIT = int(os.getenv("MAX_LIMIT", 100))
    
    # CORS
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
    CORS_CREDENTIALS = True
    CORS_METHODS = ["*"]
    CORS_HEADERS = ["*"]
    
    # Logs
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()
