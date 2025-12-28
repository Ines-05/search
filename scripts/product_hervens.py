"""
Module product_hervens.py - Extraction de filtres pour la base Hervens (orca_unified.json)

Ce module est dédié au schéma UNIFIED utilisé dans la base de données Hervens.
Les attributs utilisent des clés ANGLAISES (color, material, etc.) et sont stockés
en Attribute Pattern (array de {key, value}).

Database: Hervens
Source: orca_unified.json
Schema: unified

Usage:
    from scripts.hervens_scripts.product_hervens import extract_filters_agent_hervens
    result = extract_filters_agent_hervens("vase noir en verre")
"""

import os
import json
import time
from typing import Dict, Any, Optional, List
import google.generativeai as genai
from openai import OpenAI

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

load_dotenv()

# --- Configuration des API Keys ---
gemini_client = None
if "GEMINI_API_KEY" in os.environ:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    gemini_client = genai

openai_client = None
if "OPENAI_API_KEY" in os.environ:
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# --- SCHÉMA HERVENS (data.json) ---
# Les données sont importées avec une structure unifiée où attributes est un objet plat
# et categories est un tableau.

PRODUCT_SCHEMA_HERVENS = {
    "id": {"type": "string", "description": "Identifiant unique du produit (slug)."},
    "type": {"type": "string", "description": "Type d'entité (product)."},
    "name": {"type": "string", "description": "Nom du produit."},
    "description": {"type": "string", "description": "Description enrichie et détaillée du produit."},
    "brand": {"type": "string", "description": "Marque du produit (ex: 'orca deco', 'Hervens')."},
    "categories": {"type": "array", "description": "Liste des catégories (ex: ['Vase', 'Article de décoration'])."},
    "keywords": {"type": "array", "description": "Mots-clés pré-générés pour la recherche."},
    "price": {"type": "object", "description": "Information prix."},
    "price.amount": {"type": "number", "description": "Prix en XOF."},
    "stock": {"type": "object", "description": "Information stock."},
    "stock.status": {"type": "string", "description": "Status (ex: 'in_stock')."},
    "attributes": {
        "type": "object", 
        "description": "Objet plat contenant les attributs. Clés en ANGLAIS: color, material, forme, dimensions, etc.",
        "properties": {
            "color": {"type": "array", "description": "Couleurs (ex: ['Noir', 'Doré'])"},
            "material": {"type": "array", "description": "Matériaux (ex: ['Verre', 'Céramique'])"},
            "forme": {"type": "string", "description": "Forme (ex: 'Cylindrique')"},
            "dimensions": {"type": "string", "description": "Dimensions (ex: '12.5 x 28 cm')"}
        }
    }
}

PRODUCT_DATA_EXAMPLE_HERVENS = {
    "id": "vase-en-ceramique-13x22cm-noir",
    "type": "product",
    "name": "VASE EN CERAMIQUE-13X22CM-NOIR",
    "brand": "orca deco",
    "categories": ["Vase"],
    "price": {
        "amount": 12500,
        "currency": "XOF"
    },
    "stock": {
        "status": "in_stock",
        "quantity": 36
    },
    "keywords": ["Céramique", "Noir", "Mat", "Moderne", "Vase"],
    "description": "Vase en céramique noir mat 13 x 22 cm, au corps bombé...",
    "attributes": {
        "color": ["Noir"],
        "material": ["Céramique"],
        "dimensions": "13x22cm",
        "forme": "Amphore",
        "style": "Rétro, abstrait"
    }
}

# Liste des catégories disponibles dans la base de données
AVAILABLE_CATEGORIES = [
    'Accessoires', 'Applique', 'Article de cuisine', 'Article de décoration', 'Article de maison', 
    'Balade & Sommeil', 'Baskets', 'Berceuse & Veilleuse', 'Blouses', 'Blousons', 'Bombers', 
    'Bottes', 'Bottes Hautes', 'Business', 'Bébé & Enfant', 'Cabas', 'Cardigans', 'Chaussures', 
    'Chaussures Confort', 'Chaussures Plates', 'Chaussures d\'été', 'Chemises', 'Chemises Décontractées', 
    'Chemises Imprimées', 'Chemises en Lin', 'Chemisiers', 'Confort de maison', 'Costumes', 'Divers', 
    'Drap housse', 'Electroménager', 'Ensembles', 'Entretien de linge', 'Eveil bébé', 'Femmes', 
    'Fer à repasser', 'Foulards', 'Gilets', 'Hauts', 'Hommes', 'Jeans', 'Jeans Droits', 'Jeans Larges', 
    'Jeans Relax', 'Jeu d\'imitation & Déguisement', 'Jeu multi-média', 'Jeux & Jouets', 'Jupes', 
    'Jupes Midi', 'Lampe', 'Linge de maison', 'Literie', 'Luminaire', 'Lustre & Suspension', 'Mailles', 
    'Manteaux', 'Manteaux en Laine', 'Mini Sacs', 'Miroir', 'Miroir mural', 'Mocassins', 'Mules', 
    'Nu-pieds', 'Objets lumineux', 'Outdoor', 'Pantalons', 'Pantalons Larges', 'Pantalons de Costume', 
    'Pantalons en Cuir', 'Pantalons en Velours', 'Parure de lit', 'Plaid & Couverture', 'Pochettes', 
    'Polos', 'Poussette', 'Préparation culinaire', 'Pulls', 'Ramadan', 'Rideau & Voilage & Store', 
    'Robes', 'Robes Chemise', 'Robes Décontractées', 'Robes Longues', 'Robes Pull', 'Robes d\'été', 
    'Robes de Soirée', 'Robot de cuisine', 'Running', 'Sacoches', 'Sacs', 'Sacs à Bandoulière', 
    'Sacs à Dos', 'Sacs à Main', 'Saladier & Plat & Moule', 'Sandales', 'Sneakers Blanches', 
    'Sneakers en Daim', 'Soirée', 'Surchemises', 'T-Shirts', 'T-Shirts Manches Longues', 
    'Tableau & Cadre photo', 'Tableau & Toile', 'Tabliers', 'Tailleur', 'Talons', 'Tenues Casual', 
    'Tenues Décontractées', 'Tenues d\'été', 'Tenues de Cérémonie', 'Tenues de Sortie', 'Tops', 
    'Tops Lingerie', 'Tops de Soirée', 'Tuniques', 'Unisexe', 'Vaisselle', 'Vase', 'Ventilateur', 
    'Verre & Carafe', 'Veste Légère', 'Vestes', 'Vestes Courtes', 'Vestes en Cuir', 'Vêtements', 
    'Workwear', 'Écharpes'
]

def _construct_prompt_hervens(user_query: str) -> str:
    """
    Construit le prompt pour le LLM avec le schéma Hervens.
    Les attributs utilisent des clés ANGLAISES (color, material).
    """
    schema_description = json.dumps(PRODUCT_SCHEMA_HERVENS, indent=2)
    product_example_str = json.dumps(PRODUCT_DATA_EXAMPLE_HERVENS, indent=2)
    categories_str = ", ".join(AVAILABLE_CATEGORIES)

    prompt = f"""
    You are an intelligent assistant designed to extract search filters and a semantic query
    from a user's natural language request for a product database.

    IMPORTANT - DATABASE SCHEMA (HERVENS/UNIFIED):
    - 'brand' field: Brand name (ex: 'orca deco', 'Hervens')
    - 'keywords' field: Pre-generated keywords for better semantic search
    - 'attributes' is a FLAT OBJECT with ENGLISH keys:
      * attributes.color (NOT couleur) - Array or String (e.g., ["Noir"], "Blanc")
      * attributes.material (NOT materiau) - Array or String (e.g., ["Verre"], "Céramique")
      * attributes.forme - String (e.g., "Cylindrique")
      * attributes.dimensions - String

    DATABASE SCHEMA:
    {schema_description}

    EXAMPLE PRODUCT DOCUMENT:
    {product_example_str}

    AVAILABLE CATEGORIES (Use these EXACT names for 'categories' filter):
    {categories_str}

    USER QUERY: "{user_query}"

    INSTRUCTIONS:
    1. Extract a 'semantic_query' - enriched version of the query for vector search.
       If the query is purely about price or brand (e.g., "the most expensive product"), 
       use generic terms like "produit" or the brand name.
       
    2. Extract 'filters' with:
       - 'mandatory': Strict filters (categories, price ranges - ONLY numbers in value)
       - 'optional': Attribute filters (colors, materials, shapes)

    PRICING LOGIC:
    - "le plus cher", "haut de gamme", "luxe" -> sort: {{"field": "price.amount", "order": "desc"}}
    - "pas cher", "moins cher", "abordable", "petit prix" -> sort: {{"field": "price.amount", "order": "asc"}}
    - "entre X et Y" -> price.amount: {{"operator": "range", "value": {{"gte": X, "lte": Y}}}}
    - "ne dépasse pas X", "moins de X", "maximum X" -> price.amount: {{"operator": "range", "value": {{"lte": X}}}}
    - "au moins X", "à partir de X", "plus de X" -> price.amount: {{"operator": "range", "value": {{"gte": X}}}}
    - "prix exact X", "coûte X" -> price.amount: {{"operator": "term", "value": X}}

    AVAILABLE FILTER FIELDS:
    - 'categories': Category match (Must be one of the AVAILABLE CATEGORIES) → MANDATORY
    - 'price.amount': Price range in XOF (e.g., {{"lte": 15000}}) → MANDATORY  
    - 'brand': Brand filter (e.g., "orca deco") → MANDATORY
    - 'stock.status': Stock availability (e.g., "in_stock") → MANDATORY
    - 'attributes.color': Color filter with ENGLISH key (e.g., "Noir") → OPTIONAL
    - 'attributes.material': Material filter with ENGLISH key (e.g., "Verre") → OPTIONAL

    OUTPUT FORMAT (JSON only, no markdown):
    {{
        "semantic_query": "<enriched search query>",
        "filters": {{
            "mandatory": {{
                "field_name": {{ "operator": "term|range", "value": <value_as_json> }}
            }},
            "optional": {{
                "field_name": {{ "operator": "term", "value": "<value>" }}
            }}
        }},
        "sort": {{ "field": "<field_name>", "order": "asc|desc" }},
        "confidence": <float 0-1>
    }}

    EXAMPLES:

    Query: "je cherche le produt le plus chère de orca deco"
    {{
        "semantic_query": "produit orca deco",
        "filters": {{
            "mandatory": {{
                "brand": {{ "operator": "term", "value": "orca deco" }}
            }}
        }},
        "sort": {{ "field": "price.amount", "order": "desc" }},
        "confidence": 0.95
    }}

    Query: "vase pas trop chère entre 5000 et 10000"
    {{
        "semantic_query": "vase décoration",
        "filters": {{
            "mandatory": {{
                "categories": {{ "operator": "term", "value": "Vase" }},
                "price.amount": {{ "operator": "range", "value": {{ "gte": 5000, "lte": 10000 }} }}
            }}
        }},
        "sort": {{ "field": "price.amount", "order": "asc" }},
        "confidence": 0.95
    }}

    Query: "produit qui ne dépasse pas 15000"
    {{
        "semantic_query": "produit",
        "filters": {{
            "mandatory": {{
                "price.amount": {{ "operator": "range", "value": {{ "lte": 15000 }} }}
            }}
        }},
        "confidence": 0.90
    }}

    CRITICAL RULES:
    1. Use ENGLISH keys for attributes: color, material (NOT couleur, materiau)
    2. price.amount value MUST be a number or a range object with numbers. NO strings like "15000 FCFA".
    3. Detect SORT intent implicitly ("pas trop cher" -> price asc, "le plus cher" -> price desc)
    4. Return ONLY valid JSON, no markdown formatting
    5. ALWAYS try to map the user query to one of the AVAILABLE CATEGORIES if possible.

    Now extract filters for the user query: "{user_query}"
    """
    return prompt


def _call_gemini_llm(prompt: str, model_name: str = "gemini-2.5-flash-lite", api_key: str = None) -> Optional[str]:
    """Appel au LLM Gemini."""
    if not api_key:
        print("Gemini API key not provided")
        return None
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error calling Gemini LLM ({model_name}): {e}")
        return None


def _call_openai_llm(prompt: str, model_name: str = "gpt-4o") -> Optional[str]:
    """Appel au LLM OpenAI."""
    if not openai_client:
        print("OpenAI client not available")
        return None
    try:
        response = openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that extracts search filters from natural language queries. Return ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling OpenAI LLM ({model_name}): {e}")
        return None


def _parse_llm_response(response: str) -> Optional[Dict[str, Any]]:
    """Parse la réponse JSON du LLM."""
    if not response:
        return None
    
    # Nettoyer la réponse (enlever les balises markdown si présentes)
    cleaned = response.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        return None


def _validate_output_structure(llm_output: Dict[str, Any]) -> bool:
    """Valide la structure de la sortie du LLM."""
    if not isinstance(llm_output, dict):
        return False
    if "semantic_query" not in llm_output or not isinstance(llm_output["semantic_query"], str):
        return False
    if "filters" not in llm_output or not isinstance(llm_output["filters"], dict):
        return False
    if "mandatory" not in llm_output["filters"] or not isinstance(llm_output["filters"]["mandatory"], dict):
        return False
    if "optional" not in llm_output["filters"] or not isinstance(llm_output["filters"]["optional"], dict):
        return False
    if "confidence" not in llm_output or not isinstance(llm_output["confidence"], (int, float)):
        return False
    return True


def extract_filters_agent_hervens(user_query: str) -> Dict[str, Any]:
    """
    Agent d'extraction de filtres pour la base Hervens.
    
    Utilise le schéma UNIFIED avec des clés d'attributs en ANGLAIS
    (color, material au lieu de couleur, materiau).
    
    Args:
        user_query: Requête utilisateur en langage naturel
        
    Returns:
        Dictionnaire avec semantic_query, filters, et confidence
    """
    prompt = _construct_prompt_hervens(user_query)
    parsed_output = None

    # Liste des clés Gemini à essayer
    gemini_keys = []
    if os.getenv("GEMINI_API_KEY"): gemini_keys.append(os.getenv("GEMINI_API_KEY"))
    if os.getenv("GOOGLE_API_KEY2"): gemini_keys.append(os.getenv("GOOGLE_API_KEY2"))
    if os.getenv("GOOGLE_API_KEY3"): gemini_keys.append(os.getenv("GOOGLE_API_KEY3"))

    # 1. Essayer Gemini avec rotation de clés
    model_name = "gemini-2.5-flash"
    
    for i, api_key in enumerate(gemini_keys):
        print(f"Trying Gemini model ({model_name}) with Key #{i+1}...")
        
        response = _call_gemini_llm(prompt, model_name, api_key)
        if response:
            parsed_output = _parse_llm_response(response)
            if parsed_output and _validate_output_structure(parsed_output):
                print(f"Success with Gemini Key #{i+1}")
                return parsed_output
        
        print(f"Warning: Gemini LLM call failed with Key #{i+1}.")
        if i < len(gemini_keys) - 1:
            print("Waiting 5s before next key...")
            time.sleep(5)

    # 2. Fallback sur OpenAI si toutes les clés Gemini échouent
    print("All Gemini keys failed. Falling back to OpenAI...")
    if os.getenv("OPENAI_API_KEY"):
        print(f"Trying OpenAI model (gpt-4o)...")
        response = _call_openai_llm(prompt, "gpt-4o")
        if response:
            parsed_output = _parse_llm_response(response)
            if parsed_output and _validate_output_structure(parsed_output):
                print(f"Success with OpenAI")
                return parsed_output
    
    # Échec complet - retourner une structure vide
    print("All LLM calls failed. Returning empty structure.")
    return {
        "semantic_query": user_query,
        "filters": {
            "mandatory": {},
            "optional": {}
        },
        "confidence": 0.0
    }


# --- Test ---
if __name__ == "__main__":
    print("="*60)
    print("TEST: extract_filters_agent_hervens")
    print("="*60)
    
    test_queries = [
        "vase noir en céramique",
        "le produit le plus cher de orca deco",
        "un produit pas trop cher entre 5000 et 15000",
        "quelque chose qui ne dépasse pas 10000 FCFA",
        "assiette à partir de 2000"
    ]
    
    for query in test_queries:
        print(f"\n📝 Query: '{query}'")
        print("-" * 40)
        result = extract_filters_agent_hervens(query)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print()
