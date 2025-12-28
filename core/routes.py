"""
Routes pour l'API FastAPI de recherche hybride de produits.
Utilise la recherche vectorielle avec extraction de filtres LLM.
"""

import sys
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

# Add parent directory to path to import from scripts
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the search function from scripts
from scripts.execute_hervens import search_products as execute_search
from scripts.product_hervens import extract_filters_agent_hervens as extract_filters_agent
from scripts.execute_query_hervens import execute_query_hervens as execute_query

# Initialiser le router
router = APIRouter(tags=["Search"])

# Modèles Pydantic
class SearchRequest(BaseModel):
    """Modèle pour les requêtes de recherche"""
    query: str
    use_vector_search: bool = True
    limit: int = 10
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "un smartphone Samsung moins de 300 euros",
                "use_vector_search": True,
                "limit": 10
            }
        }

class ProductResponse(BaseModel):
    """Modèle pour un produit dans la réponse"""
    id: Optional[str] = None
    type: Optional[str] = None
    name: str
    description: Optional[str] = None
    categories: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    price: Optional[dict] = None  # {amount, currency, display}
    image: Optional[str] = None  # Pour produits (single URL)
    images: Optional[List[str]] = None  # Pour accommodations (array)
    location: Optional[dict] = None  # {city, country, coordinates}
    capacity: Optional[dict] = None  # {guests, bedrooms, beds, bathrooms}
    availability: Optional[dict] = None  # {status}
    attributes: Optional[dict] = None  # {brand, color, roomType, etc.}
    meta: Optional[dict] = None  # {source, rating, reviews_count}
    rating: Optional[dict] = None  # {score, reviewsCount}
    similarity_score: Optional[float] = None

class SearchResponse(BaseModel):
    """Modèle pour la réponse de recherche"""
    success: bool
    message: str
    query: str
    results_count: int
    results: List[ProductResponse]
    filters_extracted: Optional[dict] = None

# Routes
@router.post("/search", response_model=SearchResponse)
def search_products_api(request: SearchRequest):
    """
    Recherche hybride de produits avec extraction de filtres LLM et recherche vectorielle.
    
    Le système:
    1. Extrait les filtres et la requête sémantique avec un LLM (Gemini 2.5 Flash Lite)
    2. Génère des embeddings pour la recherche sémantique (text-embedding-004)
    3. Effectue une recherche vectorielle dans MongoDB Atlas
    4. Applique les filtres structurés (brand, price, etc.)
    5. Retourne les résultats classés par pertinence
    
    **Paramètres:**
    - `query`: La requête de l'utilisateur (toutes langues supportées)
    - `use_vector_search`: Utiliser la recherche vectorielle (True par défaut)
    - `limit`: Nombre maximum de résultats (10 par défaut)
    
    **Exemple:**
    ```json
    {
        "query": "smartphone Samsung pas cher",
        "use_vector_search": true,
        "limit": 10
    }
    ```
    
    **Réponse:**
    - Liste de produits avec scores de similarité
    - Filtres extraits par le LLM
    - Nombre de résultats trouvés
    """
    try:
        # Effectuer la recherche avec la fonction simple
        results = execute_search(
            user_query=request.query,
            use_vector_search=request.use_vector_search,
            limit=request.limit,
            verbose=False  # Silent mode for API
        )
        
        # Formater les résultats
        formatted_results = [
            ProductResponse(
                id=product.get('id'),
                type=product.get('type'),
                name=product.get('name', 'Sans nom'),
                description=product.get('description'),
                categories=product.get('categories', []),
                tags=product.get('tags', []),
                price=product.get('price'),
                image=product.get('image'),
                images=product.get('images'),
                location=product.get('location'),
                capacity=product.get('capacity'),
                availability=product.get('availability'),
                attributes=product.get('attributes'),
                meta=product.get('meta'),
                rating=product.get('rating'),
                similarity_score=product.get('similarity_score')
            )
            for product in results
        ]
        
        # Message selon le résultat
        success = len(formatted_results) > 0
        if success:
            message = f"Recherche réussie. {len(formatted_results)} produit(s) trouvé(s)."
        else:
            message = "Aucun produit trouvé. Essayez une recherche différente."
        
        return SearchResponse(
            success=success,
            message=message,
            query=request.query,
            results_count=len(formatted_results),
            results=formatted_results,
            filters_extracted=None  # Could add parsed filters here if needed
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur: {str(e)}"
        )
