"""
Point d'entrée pour Google Cloud Run avec CORS et gestion des erreurs.
"""

import sys
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add parent directory to path to support both module and direct execution
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try relative import first (when run as module), fallback to absolute import
try:
    from .routes import router
    from .config import settings
except ImportError:
    from routes import router
    from config import settings

# Configuration des logs
logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Initialiser FastAPI
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION
)

# Ajouter middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_CREDENTIALS,
    allow_methods=settings.CORS_METHODS,
    allow_headers=settings.CORS_HEADERS,
)

# Inclure les routes
app.include_router(router)

# Routes de base
@app.get("/", tags=["Info"])
def read_root():
    """Route d'accueil - Informations sur l'API"""
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "description": settings.API_DESCRIPTION,
        "endpoints": {
            "search": "/search",
            "docs": "/docs",
            "health": "/health"
        }
    }

@app.get("/health", tags=["Health"])
def health_check():
    """Vérifier l'état de l'API"""
    return {
        "status": "healthy",
        "message": "L'API est en ligne",
        "version": settings.API_VERSION
    }

# Gestion des erreurs 404
@app.get("/{full_path:path}", include_in_schema=False)
def catch_all(full_path: str):
    """Gérer les routes non trouvées"""
    return {
        "status": "error",
        "message": f"Route '{full_path}' non trouvée",
        "available_routes": ["/search", "/health", "/docs"]
    }

# Pour développement local
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
