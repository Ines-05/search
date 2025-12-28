import os
import json
from typing import Dict, Any, Optional
import google.generativeai as genai
from openai import OpenAI
try:
    from dotenv import load_dotenv
except ImportError:
    # If python-dotenv is not installed, provide a no-op fallback so the module still runs.
    # You can install python-dotenv with: pip install python-dotenv
    def load_dotenv(*args, **kwargs):
        print("Warning: python-dotenv not installed; skipping .env loading.")
        return False

# Importer les fonctions pour récupérer le schéma depuis MongoDB
try:
    from core.db_schema import infer_schema_from_mongodb, get_sample_document
except ImportError:
    try:
        from db_schema import infer_schema_from_mongodb, get_sample_document
    except ImportError:
        # Fallback si le module n'est pas disponible
        def infer_schema_from_mongodb(*args, **kwargs):
            raise ImportError("db_schema module not available")
        def get_sample_document(*args, **kwargs):
            raise ImportError("db_schema module not available")

load_dotenv()

# --- Configuration des API Keys ---
# Assurez-vous que cette variable d'environnement est définie
# os.environ["GEMINI_API_KEY"] = "YOUR_GEMINI_API_KEY"

# Initialiser le client Gemini
gemini_client = None
if "GEMINI_API_KEY" in os.environ:
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    gemini_client = genai
else:
    print("Warning: GEMINI_API_KEY environment variable not set. Gemini client will not be available.")

# Initialiser le client OpenAI
openai_client = None
if "OPENAI_API_KEY" in os.environ:
    openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
else:
    print("Warning: OPENAI_API_KEY environment variable not set. OpenAI client will not be available.")

# --- Récupération du schéma ---
# Nous utilisons un schéma fixe et robuste pour gérer la nature dynamique des attributs
PRODUCT_SCHEMA = {
    "id": {"type": "string", "description": "Identifiant unique du produit (slug)."},
    "type": {"type": "string", "description": "Type d'entité (product)."},
    "name": {"type": "string", "description": "Nom du produit."},
    "description": {"type": "string", "description": "Description enrichie et détaillée du produit."},
    "categories": {"type": "array", "description": "Liste des catégories (ex: ['Vase', 'Article de décoration'])."},
    "keywords": {"type": "array", "description": "Mots-clés extraits pour la recherche."},
    "price": {"type": "object", "description": "Information prix."},
    "price.amount": {"type": "number", "description": "Prix en FCFA (entier)."},
    "stock": {"type": "object", "description": "Information stock."},
    "stock.status": {"type": "string", "description": "Status (ex: 'in_stock')."},
    "attributes": {
        "type": "array", 
        "description": "Liste dynamique d'attributs clé-valeur. Peut contenir n'importe quelle caractéristique (couleur, materiau, forme, dimensions, etc.).",
        "items": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Nom de l'attribut (ex: 'couleur', 'materiau')"},
                "value": {"type": "string", "description": "Valeur de l'attribut (ex: 'Rouge', 'Verre')"}
            }
        }
    }
}

PRODUCT_DATA_EXAMPLE = {
    "id": "photophore-en-verre-cylindrique-transparent-dore-12-5x28cm",
    "type": "product",
    "name": "PHOTOPHORE EN VERRE-CYLINDRIQUE TRANSPARENT-DORE-12.5X28CM",
    "categories": ["Vase"],
    "price": {
        "amount": 10750,
        "currency": "CFA"
    },
    "price_promo": None,
    "stock": {
        "status": "in_stock",
        "quantity": 10
    },
    "sku": "*308959*",
    "image": "https://orca.ci/wp-content/uploads/2024/01/71SJg6gQMML._AC_SX569_.jpg",
    "images": [
        "https://orca.ci/wp-content/uploads/2024/01/71SJg6gQMML._AC_SX569_.jpg",
        "https://orca.ci/wp-content/uploads/2024/01/71LPX822-TL._AC_SL1024_-600x600.jpg"
    ],
    "meta": {
        "source": "Orca.ci",
        "url": "https://orca.ci/produit/photophore-en-verre-cylindrique-transparent-dore-12-5x28cm/",
        "scraped_at": "2025-12-04T12:06:11.841311"
    },
    "description_originale": "PHOTOPHORE EN VERRE-CYLINDRIQUE TRANSPARENT-DORE-12.5X28CM La bouche du vase est polie et lisse...",
    "description": "Sublimez votre intérieur avec ce photophore cylindrique en verre transparent, rehaussé d'une base dorée étincelante...",
    "attributes": [
        {"key": "materiau", "value": "verre"},
        {"key": "forme", "value": "cylindrique"},
        {"key": "couleur", "value": "Doré"},
        {"key": "dimensions", "value": "12.5X28cm"},
        {"key": "caracteristiques", "value": "bouche polie et lisse"},
        {"key": "caracteristiques", "value": "fond épaissi pour le rendre stable, robuste et non fragile"}
    ],
    "keywords": ["Doré", "Vase", "verre", "cylindrique"]
}

def _construct_prompt(user_query: str) -> str:
    """
    Construit le prompt pour le LLM en incluant le schéma de la base de données,
    des exemples et des instructions pour la sortie JSON.
    """
    schema_description = json.dumps(PRODUCT_SCHEMA, indent=2)
    product_example_str = json.dumps(PRODUCT_DATA_EXAMPLE, indent=2)

    prompt = f"""
    You are an intelligent assistant designed to extract search filters and a semantic query
    from a user's natural language request. You need to identify both mandatory and optional filters
    based on the provided database schema.

    Here is the database schema for products you'll be querying. This schema describes
    the available fields and their types.
    PRODUCT_SCHEMA:
    {schema_description}

    Here is an example of a product document structure in the database:
    PRODUCT_DATA_EXAMPLE:
    {product_example_str}

    The user's query is: "{user_query}"

    Please extract the following information and return it as a JSON object.
    
    - 'semantic_query': A refined version of the user's query, optimized for semantic search.
      CRITICAL: Include ALL descriptive information here, including:
        * Colors and appearance: "black", "noir", "white", "red", "doré", "blanc"
        * Materials: "céramique", "verre", "métal", "bois", "porcelaine"
        * Shapes and styles: "cylindrique", "amphore", "moderne", "rustique"
        * Technical specs and features
        * Any attribute that describes the product
      
      The semantic search with embeddings is VERY powerful and handles variations in spelling and case.
      Example: User says "vase céramique noir" → semantic_query = "vase céramique noir décoration intérieur"
      Example: User says "rideau bleu" → semantic_query = "rideau bleu voilage fenêtre"
      
    - 'filters': Use for EXACT matches on database fields.
        - 'mandatory': Strict filters that MUST match (categories, price)
        - 'optional': Preferred filters for attributes (colors, materials, etc.)
        
        AVAILABLE FILTER FIELDS:
        1. 'categories': EXACT category match (e.g., "Vase", "Literie", "Vaisselle", "Rideau & Voilage & Store")
           → Put in MANDATORY
        2. 'price.amount': Price range in FCFA (e.g., {{"lt": 15000}})
           → Put in MANDATORY
        3. 'stock.status': Stock availability (e.g., "in_stock")
           → Put in MANDATORY
        4. 'attributes.couleur': Color filter (e.g., "noir", "blanc", "doré", "bleu")
           → Put in OPTIONAL (will be used as post-filter)
        5. 'attributes.materiau': Material filter (e.g., "verre", "céramique", "métal", "bois")
           → Put in OPTIONAL (will be used as post-filter)
        6. 'attributes.forme': Shape filter (e.g., "cylindrique", "jarre", "bouteille")
           → Put in OPTIONAL (will be used as post-filter)
        
        IMPORTANT: Always use LOWERCASE for attribute values (noir, blanc, verre, céramique)
        The system will handle case-insensitive matching.

    The output JSON structure MUST strictly follow this format:
    {{
        "semantic_query": "<string>",
        "filters": {{
            "mandatory": {{
                "field_name_1": {{ "operator": "<operator>", "value": "<value>" }},
                "field_name_2": {{ "operator": "<operator>", "value": "<value>" }}
            }},
            "optional": {{
                "field_name_3": {{ "operator": "<operator>", "value": "<value>" }}
            }}
        }},
        "confidence": <float_between_0_and_1>
    }}

    If no specific filters are identified, the 'mandatory' and 'optional' objects should be empty.
    If you are unsure about a filter or its value, set the confidence lower.

    Example for user query "vase en céramique noir":
    {{
        "semantic_query": "vase céramique noir design moderne décoration",
        "filters": {{
            "mandatory": {{
                "categories": {{ "operator": "term", "value": "Vase" }}
            }},
            "optional": {{
                "attributes.couleur": {{ "operator": "term", "value": "noir" }},
                "attributes.materiau": {{ "operator": "term", "value": "céramique" }}
            }}
        }},
        "confidence": 0.95
    }}

    Example for user query "photophore en verre pas cher moins de 15000 FCFA":
    {{
        "semantic_query": "photophore verre transparent élégant décoration",
        "filters": {{
            "mandatory": {{
                "price.amount": {{ "operator": "range", "value": {{ "lt": 15000 }} }}
            }},
            "optional": {{
                "attributes.materiau": {{ "operator": "term", "value": "verre" }}
            }}
        }},
        "confidence": 0.92
    }}
    
    Example for user query "décoration dorée pour salon":
    {{
        "semantic_query": "objet décoratif doré élégant salon intérieur luxe",
        "filters": {{
            "mandatory": {{}},
            "optional": {{
                "attributes.couleur": {{ "operator": "term", "value": "doré" }}
            }}
        }},
        "confidence": 0.85
    }}
    
    Example for user query "vase":
    {{
        "semantic_query": "vase décoration fleurs intérieur",
        "filters": {{
            "mandatory": {{
                "categories": {{ "operator": "term", "value": "Vase" }}
            }},
            "optional": {{}}
        }},
        "confidence": 0.95
    }}
    
    Example for user query "rideau bleu":
    {{
        "semantic_query": "rideau bleu voilage store fenêtre décoration",
        "filters": {{
            "mandatory": {{
                "categories": {{ "operator": "term", "value": "Rideau & Voilage & Store" }}
            }},
            "optional": {{
                "attributes.couleur": {{ "operator": "term", "value": "bleu" }}
            }}
        }},
        "confidence": 0.95
    }}
    
    CRITICAL RULES - READ CAREFULLY:
    1. Put descriptive terms (colors, materials, shapes) in BOTH semantic_query AND optional filters
    2. Use attributes.couleur, attributes.materiau, attributes.forme as OPTIONAL filters (lowercase values)
    3. Use categories, price.amount, stock.status as MANDATORY filters
    4. NEVER use 'text' operator - it's incompatible with Vector Search
    5. ONLY use 'term' (exact match) or 'range' (numeric) operators
    6. price.amount is in FCFA (1 EUR ≈ 655 FCFA)
    7. Attribute values must be LOWERCASE: "noir", "blanc", "verre", "céramique"
    """
    return prompt

def _call_gemini_llm(prompt: str, model_name: str = "gemini-2.5-flash-lite") -> Optional[str]:
    """
    Effectue l'appel au LLM Gemini et gère les exceptions de base.
    """
    if not gemini_client:
        print("Error: Gemini client is not configured. Please set GEMINI_API_KEY.")
        return None
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error calling Gemini LLM ({model_name}): {e}")
        return None

def _call_openai_llm(prompt: str, model_name: str = "gpt-4o") -> Optional[str]:
    """
    Effectue l'appel au LLM OpenAI et gère les exceptions de base.
    """
    if not openai_client:
        print("Error: OpenAI client is not configured. Please set OPENAI_API_KEY.")
        return None
    try:
        response = openai_client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that outputs JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling OpenAI LLM ({model_name}): {e}")
        return None

def _validate_output_structure(llm_output: Dict[str, Any]) -> bool:
    """
    Valide que la structure de la sortie du LLM correspond au format attendu.
    """
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

def extract_filters_agent(
    user_query: str
) -> Dict[str, Any]:
    """
    Composant 1 : Agent Extractor (LLM-powered function)

    Cette fonction extrait des filtres et une requête sémantique à partir d'une
    requête utilisateur en langage naturel, en utilisant un modèle de langage large (LLM).

    Input:
    - user_query: La requête de l'utilisateur (str).

    Output:
    - Un dictionnaire avec la structure suivante:
      {
        "semantic_query": str,
        "filters": {
            "mandatory": {...},
            "optional": {...}
        },
        "confidence": float
      }
      En cas d'échec du LLM, une structure vide avec une faible confiance est retournée.

    Error Handling:
    - Si l'appel LLM échoue ou que la réponse JSON est invalide après les réessais,
      une structure de résultat vide avec une confiance de 0.0 est retournée.
    - Si la confiance retournée par le LLM est inférieure à 0.5, une suggestion de clarification
      peut être nécessaire par le composant appelant.
    """
    prompt = _construct_prompt(user_query)
    llm_output_str = None
    parsed_output = None

    # Tentative d'appel LLM avec fallback: Gemini d'abord, puis GPT si échec
    models_to_try = [
        ("gemini", "gemini-2.5-flash-lite"),
        ("openai", "gpt-4o")
    ]
    
    for model_type, model_name in models_to_try:
        print(f"Trying {model_type.upper()} model ({model_name})...")
        for attempt in range(2):
            if model_type == "gemini":
                llm_output_str = _call_gemini_llm(prompt, model_name)
            elif model_type == "openai":
                llm_output_str = _call_openai_llm(prompt, model_name)

            if llm_output_str:
                try:
                    # Nettoyer la sortie (Gemini peut ajouter des backticks)
                    cleaned_output = llm_output_str.strip()
                    if cleaned_output.startswith("```json"):
                        cleaned_output = cleaned_output[len("```json"):].strip()
                    if cleaned_output.endswith("```"):
                        cleaned_output = cleaned_output[:-len("```")].strip()

                    parsed_output = json.loads(cleaned_output)
                    if _validate_output_structure(parsed_output):
                        print(f"Success with {model_type.upper()} on attempt {attempt+1}")
                        break  # Succès, sortir de la boucle des tentatives
                    else:
                        print(f"Warning: {model_type.upper()} response structure invalid on attempt {attempt+1}. Retrying...")
                except json.JSONDecodeError:
                    print(f"Warning: {model_type.upper()} response not valid JSON on attempt {attempt+1}. Retrying...")
            else:
                print(f"Warning: {model_type.upper()} LLM call failed on attempt {attempt+1}.")
        
        if parsed_output and _validate_output_structure(parsed_output):
            break  # Succès avec ce modèle, sortir de la boucle des modèles

    # Si aucune sortie LLM valide n'a été obtenue après les réessais sur les deux modèles
    if not parsed_output or not _validate_output_structure(parsed_output):
        print("Error: Failed to get valid LLM output after retries on both Gemini and GPT. Returning empty filters.")
        return {
            "semantic_query": user_query,
            "filters": {
                "mandatory": {},
                "optional": {}
            },
            "confidence": 0.0
        }

    # Gérer la confiance
    if parsed_output.get("confidence", 0.0) < 0.5:
        print(f"Low confidence ({parsed_output.get('confidence', 0.0)}). Clarification might be needed.")

    return parsed_output

"""# --- Exemples d'utilisation ---
if __name__ == "__main__":
    # Assurez-vous d'avoir configuré votre API Key pour Gemini (ex: GEMINI_API_KEY)

    print("--- Test 1 : Recherche de téléphone ---")
    user_query_1 = "Je cherche un iPhone 15 Pro noir avec un prix inférieur à 1000 euros."
    result_1 = extract_filters_agent(user_query_1)
    print(json.dumps(result_1, indent=2))
    print("\n" + "="*50 + "\n")

    print("--- Test 2 : Recherche d'ordinateur portable ---")
    user_query_2 = "Montre moi des ordinateurs portables HP EliteBook avec 16GB RAM et SSD 512GB."
    result_2 = extract_filters_agent(user_query_2)
    print(json.dumps(result_2, indent=2))
    print("\n" + "="*50 + "\n")

    print("--- Test 3 : Recherche d'accessoire ---")
    user_query_3 = "Je veux un chargeur rapide USB-C pour iPhone moins de 10 euros."
    result_3 = extract_filters_agent(user_query_3)
    print(json.dumps(result_3, indent=2))
    print("\n" + "="*50 + "\n")

    print("--- Test 4 : Recherche de produit beauté ---")
    user_query_4 = "Des produits de maquillage pour enfants roses moins de 15 euros."
    result_4 = extract_filters_agent(user_query_4)
    print(json.dumps(result_4, indent=2))
    print("\n" + "="*50 + "\n")

    print("--- Test 5 : Recherche de fauteuil de massage ---")
    user_query_5 = "Fauteuil de massage Discovery avec fonction chauffante et Bluetooth."
    result_5 = extract_filters_agent(user_query_5)
    print(json.dumps(result_5, indent=2))
    print("\n" + "="*50 + "\n")

    print("--- Test 6 : Requête difficile (faible confiance) ---")
    user_query_6 = "un article introuvable pour moi"
    result_6 = extract_filters_agent(user_query_6)
    print(json.dumps(result_6, indent=2))
    print("\n" + "="*50 + "\n")

    print("--- Test 7 : Simulation d'échec du LLM ---")
    # Pour simuler un échec complet du LLM, nous allons temporairement désactiver le client Gemini.
    temp_gemini_client = gemini_client
    gemini_client = None
    user_query_7 = "un téléphone moins de 100 euros de marque Apple"
    result_7 = extract_filters_agent(user_query_7)
    print(json.dumps(result_7, indent=2))
    gemini_client = temp_gemini_client # Restaurer le client
    print("\n" + "="*50 + "\n")
"""