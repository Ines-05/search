"""
Module execute_query_hervens.py - Exécution de requêtes sur la base Hervens

Ce module est dédié à la base de données Hervens avec le schéma UNIFIED.
Les attributs utilisent des clés ANGLAISES (color, material).

Database: Hervens
Collection: product
Index: embedding_gemini_004_index_hervens

Usage:
    from scripts.hervens_scripts.execute_query_hervens import execute_query_hervens
    results = execute_query_hervens(parsed_output, limit=10)
"""

import os
import json
import re
import unicodedata
from typing import Dict, Any, List
from pymongo import MongoClient
from google import genai
from google.genai import types
from pymongo.errors import OperationFailure

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

load_dotenv()

# Configuration Hervens
MONGODB_URI = os.getenv("MONGODB_URI2")
DATABASE_NAME = "Hervens"
COLLECTION_NAME = "product"
VECTOR_INDEX_NAME = "embedding_gemini_004_index_hervens"

if not MONGODB_URI:
    print("⚠️ Warning: MONGODB_URI2 not set. Hervens database will not be available.")

# Configuration Gemini pour les embeddings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai_client = None
if GEMINI_API_KEY:
    genai_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    print("⚠️ Warning: GEMINI_API_KEY not set. Semantic search will be disabled.")


def _normalize_text_for_regex(text: str) -> str:
    """
    Normalise un texte pour créer un regex flexible qui matche avec ou sans accents.
    """
    accent_map = {
        'a': '[aàâäã]',
        'e': '[eéèêë]',
        'i': '[iîïí]',
        'o': '[oôöõó]',
        'u': '[uùûüú]',
        'c': '[cç]',
        'n': '[nñ]',
    }
    
    normalized = unicodedata.normalize('NFD', text.lower())
    base_text = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    
    pattern = ""
    for char in base_text:
        if char in accent_map:
            pattern += accent_map[char]
        elif char == ' ':
            pattern += r'\s+'
        elif char in '.+*?^${}[]|()\\':
            pattern += '\\' + char
        else:
            pattern += char
    
    return pattern


def _generate_embeddings(text: str) -> List[float]:
    """
    Génère un vecteur d'embeddings pour un texte donné en utilisant Gemini.
    """
    if not GEMINI_API_KEY:
        print("⚠️ Impossible de générer des embeddings sans GEMINI_API_KEY")
        return []
    
    try:
        result = genai_client.models.embed_content(
            model="text-embedding-004",
            contents=text,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY")
        )
        return result.embeddings[0].values
    except Exception as e:
        print(f"❌ Erreur lors de la génération des embeddings: {e}")
        return []


def _build_mongo_filter(filters: Dict[str, Any], for_vector_search: bool = False) -> Dict[str, Any]:
    """
    Construit un filtre MongoDB à partir des filtres extraits par le LLM.
    Gère la conversion vers le "Attribute Pattern" (key/value) pour les attributs.
    """
    # Champs supportés par Vector Search pre-filter
    SAFE_VECTOR_FIELDS = ['categories', 'stock.status', 'type', 'brand', 'keywords']
    
    and_clauses = []
    
    # Combiner mandatory et optional pour le traitement
    all_filters = {**filters.get("mandatory", {}), **filters.get("optional", {})}
    
    for field, filter_spec in all_filters.items():
        operator = filter_spec.get("operator")
        value = filter_spec.get("value")
        
        # --- GESTION DES ATTRIBUTS (Attribute Pattern) ---
        if field.startswith("attributes."):
            # ex: attributes.color -> key="color"
            attr_key = field.split(".", 1)[1]
            
            # Pour Vector Search (Pre-filter)
            if for_vector_search:
                # Le filtrage précis sur Attribute Pattern est complexe en pre-filter
                # On l'évite généralement pour ne pas casser la recherche vectorielle
                # Sauf si on indexe "attributes.key" et "attributes.value" séparément
                if field not in SAFE_VECTOR_FIELDS:
                    continue

            # Pour MongoDB (Post-filter / Match)
            # On utilise $elemMatch pour matcher la paire clef/valeur dans le tableau
            
            val_filter = {}
            if operator == "term":
                 # Recherche insensible à la casse
                val_pattern = _normalize_text_for_regex(str(value))
                val_filter = {"$regex": f"^{val_pattern}$", "$options": "i"}
            elif operator == "range":
                pass # Range non supporté simplement sur string value dans ce pattern
            else:
                val_filter = value # Fallback exact match

            if val_filter:
                and_clauses.append({
                    "attributes": {
                        "$elemMatch": {
                            "key": attr_key,
                            "value": val_filter
                        }
                    }
                })
            continue
        
        # --- GESTION DES CHAMPS STANDARDS ---
        if for_vector_search and field not in SAFE_VECTOR_FIELDS:
            continue

        if operator == "term":
            if isinstance(value, list):
                and_clauses.append({field: {"$in": value}})
            elif field == "categories":
                and_clauses.append({field: {"$in": [value]}})
            else:
                and_clauses.append({field: {"$eq": value}})
                
        elif operator == "range":
            if isinstance(value, dict):
                range_filter = {}
                if "lt" in value: range_filter["$lt"] = value["lt"]
                if "lte" in value: range_filter["$lte"] = value["lte"]
                if "gt" in value: range_filter["$gt"] = value["gt"]
                if "gte" in value: range_filter["$gte"] = value["gte"]
                if range_filter:
                    and_clauses.append({field: range_filter})
    
    if not and_clauses:
        return {}
    elif len(and_clauses) == 1:
        return and_clauses[0]
    else:
        return {"$and": and_clauses}


def _build_vector_search_pipeline(
    semantic_query: str,
    filters: Dict[str, Any],
    sort: Dict[str, str] = None,
    limit: int = 50,
    num_candidates: int = 150
) -> List[Dict[str, Any]]:
    """
    Construit le pipeline MongoDB pour Vector Search sur Hervens.
    """
    query_vector = _generate_embeddings(semantic_query)
    
    if not query_vector:
        print("⚠️ Pas d'embeddings générés, recherche vectorielle désactivée")
        return None
    
    print(f"   ✅ Embedding généré: {len(query_vector)} dimensions")
    
    # Pre-filtre pour Vector Search (uniquement champs safe)
    pre_filter = _build_mongo_filter(filters, for_vector_search=True)
    
    # Post-filtre complet (incluant attributes.*)
    post_filter = _build_mongo_filter(filters, for_vector_search=False)

    pipeline = []
    
    # Recherche vectorielle élargie
    # Si on a un tri strict, on veut s'assurer d'avoir assez de candidats pour trier
    # Sinon le tri se fait uniquement sur les résultats sémantiques (sub-optimal pour "le plus cher")
    search_limit = limit * 10 if sort else limit * 4
    search_num_candidates = max(num_candidates, search_limit * 2)

    vector_search_stage = {
        "$vectorSearch": {
            "index": VECTOR_INDEX_NAME,
            "path": "embedding_gemini_004",
            "queryVector": query_vector,
            "numCandidates": search_num_candidates,
            "limit": search_limit
        }
    }
    
    if pre_filter:
        vector_search_stage["$vectorSearch"]["filter"] = pre_filter
        print(f"   🛡️ Pre-Filtre Vector: {pre_filter}")
    else:
        print(f"   🛡️ Vector Search sans pre-filtre")
    
    pipeline.append(vector_search_stage)

    # Post-filtrage avec $match
    if post_filter:
        print(f"   🧹 Post-Filtre MongoDB: {post_filter}")
        pipeline.append({"$match": post_filter})
        
    # Score de similarité
    pipeline.append({
        "$addFields": {
            "score": {"$meta": "vectorSearchScore"}
        }
    })
    
    # Si pas de tri explicite, on filtre les résultats peu pertinents
    if not sort:
        pipeline.append({
            "$match": {"score": {"$gte": 0.5}}
        })
    else:
        print(f"   🔽 Tri activé (ignore seuil de score): {sort}")
    
    # Tri
    if sort and 'field' in sort:
        sort_order = -1 if sort.get('order') == 'desc' else 1
        pipeline.append({"$sort": {sort['field']: sort_order}})
        print(f"   🔄 Application du tri: {sort['field']} ({'DESC' if sort_order == -1 else 'ASC'})")
    else:
        # Tri par score par défaut
        pipeline.append({"$sort": {"score": -1}})
    
    # Limite finale
    pipeline.append({"$limit": limit})
    
    # Projection (exclure embeddings volumineux)
    pipeline.append({
        "$project": {
            "_id": 0,
            "embedding_gemini_004": 0
        }
    })
    
    return pipeline


def execute_query_hervens(
    parsed_output: Dict[str, Any], 
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Exécute une requête sur la base Hervens.
    
    Args:
        parsed_output: Sortie du LLM avec semantic_query, filters, confidence
        limit: Nombre maximum de résultats
        
    Returns:
        Liste de documents produits
    """
    confidence = parsed_output.get("confidence", 0.0)
    if confidence < 0.3:
        print(f"⚠️ Confiance très faible ({confidence:.2f}). Aucune requête exécutée.")
        return []
    
    filters = parsed_output.get("filters", {"mandatory": {}, "optional": {}})
    semantic_query = parsed_output.get("semantic_query", "")
    sort = parsed_output.get("sort", None)
    
    if not semantic_query:
        # Si on a juste un tri "plus cher" sans requête sémantique, on met un terme générique
        semantic_query = "produit"
        print(f"⚠️ Pas de semantic_query, utilisation de la requête par défaut")
    
    print(f"\n{'='*60}")
    print(f"🔍 EXÉCUTION REQUÊTE HERVENS")
    print(f"{'='*60}")
    print(f"📊 Confiance: {confidence:.2f}")
    print(f"🔎 Requête sémantique: '{semantic_query}'")
    print(f"🎯 Filtres mandatory: {list(filters.get('mandatory', {}).keys())}")
    print(f"💡 Filtres optional: {list(filters.get('optional', {}).keys())}")
    if sort:
        print(f"🔄 Tri demandé: {sort}")
    
    if not MONGODB_URI:
        print("❌ MONGODB_URI2 non défini")
        return []
    
    client = None
    try:
        client = MongoClient(MONGODB_URI)
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]
        
        total_docs = collection.count_documents({})
        docs_with_embedding = collection.count_documents({'embedding_gemini_004': {'$exists': True}})
        print(f"\n📊 [DATABASE INFO]")
        print(f"   Database: {DATABASE_NAME}")
        print(f"   Collection: {COLLECTION_NAME}")
        print(f"   Total documents: {total_docs}")
        print(f"   Documents avec embedding: {docs_with_embedding}")
        
        results = []
        
        # Détection du mode de recherche
        semantic_query_clean = semantic_query.lower().strip()
        is_generic_query = not semantic_query_clean or semantic_query_clean in ["produit", "produits", "article", "articles", "objet", "objets", "tout", "tous"]
        has_filters = bool(filters.get("mandatory")) or bool(filters.get("optional"))
        has_sort = bool(sort)
        
        # Si c'est une requête de filtre pur (ex: "le plus cher", "entre X et Y" sans mots clés sémantiques)
        # On utilise une recherche MongoDB standard pour être 100% précis
        if is_generic_query and (has_filters or has_sort):
            print(f"\n🚀 MODE: Recherche MongoDB Standard (Filtres/Tri purs)")
            print(f"{'='*60}")
            mongo_filter = _build_mongo_filter(filters, for_vector_search=False)
            
            cursor = collection.find(mongo_filter)
            if sort and 'field' in sort:
                sort_order = -1 if sort.get('order') == 'desc' else 1
                cursor = cursor.sort(sort['field'], sort_order)
                print(f"   🔄 Application du tri: {sort['field']} ({'DESC' if sort_order == -1 else 'ASC'})")
            
            results = list(cursor.limit(limit))
            for doc in results:
                doc['score'] = 1.0 # Score maximal pour les filtres exacts
                if '_id' in doc: doc['_id'] = str(doc['_id'])
                
        elif GEMINI_API_KEY:
            print(f"\n🚀 MODE: Recherche Vectorielle Hybride")
            print(f"{'='*60}")
            
            pipeline = _build_vector_search_pipeline(
                semantic_query=semantic_query,
                filters=filters,
                sort=sort,
                limit=limit,
                num_candidates=limit * 10 if sort else limit * 4
            )
            
            if pipeline:
                try:
                    cursor = collection.aggregate(pipeline)
                    for doc in cursor:
                        if '_id' in doc: doc['_id'] = str(doc['_id'])
                        results.append(doc)
                    print(f"\n✅ {len(results)} résultat(s) trouvé(s)")
                    
                except OperationFailure as e:
                    if "needs to be indexed as filter" in str(e):
                        print(f"\n⚠️ Erreur d'indexation, basculement vers post-filtrage")
                        pipeline_fallback = _build_vector_search_pipeline(semantic_query, {}, sort, limit*3, limit*6)
                        mongo_filter = _build_mongo_filter(filters, for_vector_search=False)
                        if mongo_filter:
                            pipeline_fallback.insert(1, {"$match": mongo_filter})
                        
                        cursor = collection.aggregate(pipeline_fallback)
                        results = []
                        for doc in cursor:
                            if '_id' in doc: doc['_id'] = str(doc['_id'])
                            results.append(doc)
                    else:
                        raise e
        else:
            print("⚠️ GEMINI_API_KEY absent, recherche vectorielle désactivée")
            return []
        
        print(f"\n📊 {len(results)} résultats trouvés")
        return results
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if client:
            client.close()


# --- Test ---
if __name__ == "__main__":
    print("="*60)
    print("TEST: execute_query_hervens")
    print("="*60)
    
    # Test avec un parsed_output simulé (avec tri)
    test_output = {
        "semantic_query": "produit orca deco",
        "filters": {
            "mandatory": {
                "brand": {"operator": "term", "value": "orca deco"}
            }
        },
        "sort": {"field": "price.amount", "order": "desc"},
        "confidence": 0.95
    }
    
    results = execute_query_hervens(test_output, limit=5)
    
    print("\n" + "="*60)
    print("RÉSULTATS:")
    print("="*60)
    for i, r in enumerate(results, 1):
        print(f"{i}. {r.get('name', 'N/A')}")
