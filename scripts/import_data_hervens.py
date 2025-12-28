"""
Script pour importer les données depuis data.json vers MongoDB Hervens
Database: Hervens
Collection: product
"""

import os
import json
from dotenv import load_dotenv
from pymongo import MongoClient
from tqdm import tqdm
import sys

# Ajouter le parent au path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from scripts.path_utils import get_data_path

load_dotenv()

MONGODB_URI = os.getenv('MONGODB_URI2')
DATABASE_NAME = 'Hervens'
COLLECTION_NAME = 'product'
DATA_FILE = get_data_path('data.json')

if not MONGODB_URI:
    raise ValueError("MONGODB_URI2 not set in environment variables")

if not os.path.exists(DATA_FILE):
    raise FileNotFoundError(f"Fichier {DATA_FILE} non trouvé")

print("="*70)
print("📦 IMPORTATION DES DONNÉES VERS MONGODB HERVENS")
print("="*70)
print()

# Charger les données depuis le fichier JSON
print(f"📂 Chargement du fichier {DATA_FILE}...")
with open(DATA_FILE, 'r', encoding='utf-8') as f:
    json_data = json.load(f)

# Extraction des produits
if isinstance(json_data, dict) and 'products' in json_data:
    data = json_data['products']
else:
    data = json_data

print(f"✅ {len(data)} documents chargés depuis le fichier")
print()

# Connexion à MongoDB
print(f"🔗 Connexion à MongoDB Hervens...")
client = MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]

print(f"📍 Database: {DATABASE_NAME}")
print(f"📍 Collection: {COLLECTION_NAME}")
print(f"📍 URI: {MONGODB_URI.split('@')[1] if '@' in MONGODB_URI else 'custom'}")
print()

# Vérifier si la collection contient déjà des données
existing_count = collection.count_documents({})
if existing_count > 0:
    print(f"⚠️  La collection contient déjà {existing_count} documents.")
    print("🗑️  Suppression automatique des données existantes...")
    collection.delete_many({})
    print(f"✅ {existing_count} documents supprimés")

print()

# Transformation des données
# Pour orca_unified.json, les attributes sont déjà au format object
# Pas besoin de transformation si c'est un object, sinon convertir en array
print("🔄 Validation et transformation des données...")
transformed_data = []
for i, product in enumerate(data):
    new_product = product.copy()
    
    # Vérifier et transformer les attributes si nécessaire
    if 'attributes' in new_product:
        if isinstance(new_product['attributes'], dict):
            # Format object - convertir en array (Attribute Pattern)
            new_attributes = []
            for key, value in new_product['attributes'].items():
                if isinstance(value, list):
                    for item in value:
                        new_attributes.append({"key": key, "value": str(item)})
                else:
                    new_attributes.append({"key": key, "value": str(value)})
            new_product['attributes'] = new_attributes
        elif isinstance(new_product['attributes'], list):
            # Déjà au format array - garder tel quel
            pass
    
    transformed_data.append(new_product)

data = transformed_data
print(f"✅ {len(data)} documents transformés")

# Importer les données
print(f"📥 Importation de {len(data)} documents...")
print()

try:
    batch_size = 1000
    total_inserted = 0
    
    for i in tqdm(range(0, len(data), batch_size), desc="Importing"):
        batch = data[i:i + batch_size]
        result = collection.insert_many(batch, ordered=False)
        total_inserted += len(result.inserted_ids)
    
    print()
    print("="*70)
    print("✅ IMPORTATION TERMINÉE")
    print("="*70)
    print(f"✅ {total_inserted} documents importés avec succès dans Hervens")
    print()
    
    # Statistiques
    products_count = collection.count_documents({"type": "product"})
    
    print("📊 Statistiques:")
    print(f"  - Produits: {products_count}")
    print(f"  - Total: {total_inserted}")
    print()
    
    print("🎯 Prochaines étapes:")
    print("  1. python scripts/hervens_scripts/generate_embeddings_hervens.py")
    print("  2. python scripts/hervens_scripts/create_filter_index_hervens.py")
    print("  3. python scripts/hervens_scripts/eval_answers_hervens.py")
    
except Exception as e:
    print()
    print(f"❌ Erreur lors de l'importation: {e}")
    
finally:
    client.close()
    print()
    print("✅ Connexion fermée.")
