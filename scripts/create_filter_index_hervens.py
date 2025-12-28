"""
Créer/mettre à jour l'index vectoriel avec support des filtres pour DB Hervens
Database: Hervens
Collection: product
"""
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel
import json
import time

load_dotenv()

MONGODB_URI = os.getenv('MONGODB_URI2')
DATABASE_NAME = 'Hervens'
COLLECTION_NAME = 'product'

if not MONGODB_URI:
    raise ValueError("MONGODB_URI2 not set in environment variables")

client = MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]

print("="*80)
print("🔧 CRÉATION D'INDEX VECTORIEL HERVENS AVEC FILTRES")
print("="*80)
print(f"📍 Database: {DATABASE_NAME}")
print(f"📍 Collection: {COLLECTION_NAME}")
print()

# Définition du nouvel index pour orca_unified.json
# Champs adaptés à la nouvelle structure
index_definition = {
    "fields": [
        {
            "type": "vector",
            "path": "embedding_gemini_004",
            "numDimensions": 768,
            "similarity": "cosine"
        },
        # Filtres principaux
        { "type": "filter", "path": "price.amount" },
        { "type": "filter", "path": "categories" },
        { "type": "filter", "path": "stock.status" },
        { "type": "filter", "path": "tags" },
        { "type": "filter", "path": "keywords" },  # NOUVEAU - présent dans orca_unified
        { "type": "filter", "path": "brand" },     # NOUVEAU - présent dans orca_unified
        { "type": "filter", "path": "type" },
        
        # Filtres Attributs (Attribute Pattern)
        # Permet de filtrer sur n'importe quel attribut sans l'ajouter explicitement à l'index
        { "type": "filter", "path": "attributes.key" },
        { "type": "filter", "path": "attributes.value" }
    ]
}

print("📋 Configuration de l'index:")
print(json.dumps(index_definition, indent=2))
print()

# Supprimer l'ancien index s'il existe
print("1️⃣ Tentative de suppression de l'ancien index...")
try:
    collection.search_indexes.delete_one("embedding_gemini_004_index_hervens")
    print(f"   ✅ Ancien index supprimé")
    time.sleep(3)
except:
    print(f"   ℹ️ Index non trouvé ou déjà supprimé")

# Créer le nouvel index
print("\n2️⃣ Création du nouvel index avec filtres...")
try:
    search_index_model = SearchIndexModel(
        definition=index_definition,
        name="embedding_gemini_004_index_hervens",
        type="vectorSearch"
    )
    
    try:
        result = collection.create_search_index(model=search_index_model)
        print(f"   ✅ Index créé: {result}")
    except Exception as e:
        if "already defined" in str(e):
            print(f"   ℹ️ Index existe déjà, mise à jour...")
            collection.search_indexes.update_one(
                "embedding_gemini_004_index_hervens",
                {
                    "$set": {"definition": index_definition}
                }
            )
            print(f"   ✅ Index mis à jour")
        else:
            raise
    
    # Attendre que l'index soit prêt
    print("\n3️⃣ Attente que l'index devienne queryable...")
    timeout = 300  # 5 minutes
    start_time = time.time()
    
    while True:
        indexes = list(collection.list_search_indexes(result))
        
        if len(indexes) and indexes[0].get("queryable") is True:
            print(f"\n   ✅ Index 'embedding_gemini_004_index_hervens' est READY!")
            print(f"   Status: {indexes[0].get('status')}")
            print(f"   Queryable: {indexes[0].get('queryable')}")
            break
        
        elapsed = time.time() - start_time
        if elapsed > timeout:
            print(f"\n   ⚠️ Timeout ({int(elapsed)}s)")
            break
        
        status = indexes[0].get('status') if indexes else 'Creating...'
        print(f"   ⏳ Status: {status}... ({int(elapsed)}s)", end='\r')
        time.sleep(5)
        
except Exception as e:
    print(f"   ❌ Erreur: {e}")

client.close()
print("\n" + "="*80)
