"""
Générer les embeddings pour les produits dans la base de données Hervens
Database: Hervens
Collection: product
Modèle d'embedding: Google text-embedding-004

Usage:
    python scripts/hervens_scripts/generate_embeddings_hervens.py
"""

import os
import sys
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from tqdm import tqdm
import time

# Ajouter le parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    import google.generativeai as genai
except ImportError:
    print("⚠️  google-generativeai not installed. Install with: pip install google-generativeai")
    sys.exit(1)

load_dotenv()

# Configuration
MONGODB_URI = os.getenv('MONGODB_URI2')
DATABASE_NAME = 'Hervens'
COLLECTION_NAME = 'product'
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
EMBEDDING_MODEL = 'text-embedding-004'
EMBEDDING_FIELD = 'embedding_gemini_004'

if not MONGODB_URI:
    raise ValueError("MONGODB_URI2 not set in environment variables")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not set in environment variables")

genai.configure(api_key=GEMINI_API_KEY)

print("="*80)
print("🔧 GÉNÉRATION DES EMBEDDINGS - DB HERVENS")
print("="*80)
print(f"📍 Database: {DATABASE_NAME}")
print(f"📍 Collection: {COLLECTION_NAME}")
print(f"📍 Modèle: {EMBEDDING_MODEL}")
print()

# Connexion à MongoDB
print(f"🔗 Connexion à MongoDB Hervens...")
client = MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]

print(f"✅ Connecté à {DATABASE_NAME}.{COLLECTION_NAME}")
print()

def create_product_text(product: dict) -> str:
    """
    Crée un texte riche pour l'embedding en combinant les champs importants.
    Format étendu incluant nom, description, prix, catégories, mots-clés et attributs.
    """
    parts = []
    
    # Nom du produit
    if product.get('name'):
        parts.append(product['name'])
    
    # Description du produit
    if product.get('description'):
        parts.append(product['description'])

    # Prix
    if product.get('price'):
        price = product['price']
        if isinstance(price, dict) and 'amount' in price and 'currency' in price:
            parts.append(f"{price['amount']} {price['currency']}")
        else:
            parts.append(str(price))
            
    # Catégories
    if product.get('categories') and isinstance(product['categories'], list):
        parts.append(f"Catégories: {', '.join(product['categories'])}")

    # Mots-clés
    if product.get('keywords') and isinstance(product['keywords'], list):
        parts.append(f"Mots-clés: {', '.join(product['keywords'])}")

    # Attributs (Générique - inclut tout)
    if 'attributes' in product:
        attrs = product['attributes']
        if isinstance(attrs, dict):
            for key, value in attrs.items():
                if isinstance(value, list):
                    parts.append(f"{key}: {', '.join(str(v) for v in value)}")
                else:
                    parts.append(f"{key}: {str(value)}")
        elif isinstance(attrs, list):
            # Support du format Attribute Pattern (liste de {key, value})
            for attr in attrs:
                if isinstance(attr, dict) and 'key' in attr and 'value' in attr:
                    parts.append(f"{attr['key']}: {str(attr['value'])}")

    # Marque
    if product.get('brand'):
        parts.append(f"Marque: {product['brand']}")
    
    return ". ".join(parts)

# Compter les documents avec et sans embeddings
total_docs = collection.count_documents({})
docs_with_embedding = collection.count_documents({EMBEDDING_FIELD: {"$exists": True}})

print(f"📊 Statistiques:")
print(f"  - Documents totaux: {total_docs}")
print(f"  - Documents avec embedding: {docs_with_embedding}")
print(f"  - Documents à traiter: {total_docs - docs_with_embedding}")
print()

if docs_with_embedding == total_docs:
    print("✅ Tous les documents ont déjà des embeddings!")
    print("Si vous voulez régénérer, supprimez d'abord le champ 'embedding_gemini_004'")
    client.close()
    sys.exit(0)

# Générer les embeddings par batch
print(f"🚀 Génération des embeddings...")
batch_size = 50
processed = 0
errors = 0

try:
    # Récupérer les documents sans embedding
    docs_to_process = collection.find({EMBEDDING_FIELD: {"$exists": False}})
    
    updates = []
    for doc in tqdm(docs_to_process, total=total_docs - docs_with_embedding):
        try:
            # Créer le texte riche
            product_text = create_product_text(doc)
            
            # Générer l'embedding
            embedding_result = genai.embed_content(
                model=f"models/{EMBEDDING_MODEL}",
                content=product_text
            )
            
            embedding_vector = embedding_result['embedding']
            
            # Préparer la mise à jour
            updates.append(UpdateOne(
                {'_id': doc['_id']},
                {'$set': {
                    EMBEDDING_FIELD: embedding_vector,
                    'embedding_text': product_text
                }}
            ))
            
            processed += 1
            
            # Exécuter les mises à jour par batch
            if len(updates) >= batch_size:
                collection.bulk_write(updates)
                updates = []
                time.sleep(0.5)  # Rate limiting
        
        except Exception as e:
            print(f"\n⚠️  Erreur pour le doc {doc.get('id', doc.get('_id'))}: {e}")
            errors += 1
    
    # Exécuter les mises à jour restantes
    if updates:
        collection.bulk_write(updates)
    
    print()
    print("="*80)
    print("✅ GÉNÉRATION TERMINÉE")
    print("="*80)
    print(f"✅ {processed} embeddings générés avec succès")
    if errors > 0:
        print(f"⚠️  {errors} erreurs rencontrées")
    print()

except Exception as e:
    print(f"\n❌ Erreur: {e}")

finally:
    client.close()
    print("✅ Connexion fermée.")
