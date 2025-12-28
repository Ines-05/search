"""
Script pour tester manuellement des queries sur la base de données Hervens.
Permet de valider le pipeline avant l'évaluation complète.

Database: Hervens
Collection: product
Schema: unified (clés anglaises: color, material)

Usage:
    python scripts/hervens_scripts/execute_hervens.py "vase noir design"
"""

import os
import sys
import json
from dotenv import load_dotenv

# Ajouter le dossier hervens_scripts au path
sys.path.insert(0, os.path.dirname(__file__))

# Importer les modules Hervens locaux
from product_hervens import extract_filters_agent_hervens
from execute_query_hervens import execute_query_hervens

load_dotenv()

# Configuration Hervens
DATABASE_NAME = 'Hervens'
COLLECTION_NAME = 'product'

def test_query(query: str, limit: int = 10):
    """
    Teste une query complète sur Hervens :
    1. Extraction des filtres par LLM (clés anglaises: color, material)
    2. Recherche vectorielle + filtres
    """
    print("="*80)
    print(f"🔍 TEST QUERY HERVENS: '{query}'")
    print("="*80)
    print(f"📍 Database: {DATABASE_NAME}")
    print(f"📍 Collection: {COLLECTION_NAME}")
    print(f"📍 Schema: unified (clés anglaises)")
    print()

    try:
        # 1. Extraction des filtres par LLM (module Hervens)
        print("🤖 Étape 1: Extraction des filtres (LLM avec fallback)...")
        parsed_output = extract_filters_agent_hervens(query)

        print("📋 Résultat de l'extraction:")
        print(f"   Confiance: {parsed_output.get('confidence', 0):.2f}")
        print(f"   Query sémantique: {parsed_output.get('semantic_query', 'N/A')}")

        filters = parsed_output.get('filters', {})
        if 'mandatory' in filters and filters['mandatory']:
            print(f"   Filtres obligatoires: {filters['mandatory']}")
        if 'optional' in filters and filters['optional']:
            print(f"   Filtres optionnels: {filters['optional']}")

        print()

        # 2. Recherche vectorielle + filtres (module Hervens)
        print("🔎 Étape 2: Recherche vectorielle + filtres...")
        results = execute_query_hervens(parsed_output, limit=limit)

        print(f"📊 {len(results)} résultats trouvés")
        print()

        # 3. Affichage des résultats
        if results:
            print("🎯 RÉSULTATS (Top 10):")
            print("-" * 80)

            for i, product in enumerate(results[:10], 1):
                name = product.get('name', 'N/A')
                category = product.get('categories', ['N/A'])[0] if product.get('categories') else 'N/A'
                price = product.get('price', {}).get('amount', 'N/A')
                currency = product.get('price', {}).get('currency', '')
                brand = product.get('brand', 'N/A')
                score = product.get('score', 'N/A')

                print(f"{i:2d}. 📦 {name}")
                print(f"      📂 Catégorie: {category}")
                print(f"      💰 Prix: {price} {currency}")
                print(f"      🏷️  Marque: {brand}")
                print(f"      🎯 Score: {score}")
                print()

        else:
            print("❌ Aucun résultat trouvé")

        # 4. Debug: Afficher les détails complets du premier résultat
        if results:
            print("🔧 DEBUG - Premier résultat complet:")
            print(json.dumps(results[0], indent=2, ensure_ascii=False, default=str))
            print()

    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

def execute_query_api(query: str, limit: int = 10):
    """
    API version of test_query: returns data instead of printing.
    """
    try:
        parsed_output = extract_filters_agent_hervens(query)
        results = execute_query_hervens(parsed_output, limit=limit)
        return {
            "success": True,
            "parsed_output": parsed_output,
            "results": results
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def search_products(user_query: str, use_vector_search: bool = True, limit: int = 10, verbose: bool = False):
    """
    Wrapper to match the interface expected by core/routes.py.
    """
    parsed_output = extract_filters_agent_hervens(user_query)
    # Note: use_vector_search and verbose are currently ignored or handled inside execute_query_hervens
    return execute_query_hervens(parsed_output, limit=limit)

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Tester une query sur Hervens')
    parser.add_argument('query', nargs='?', help='La query à tester (optionnel)')
    parser.add_argument('--limit', type=int, default=5, help='Nombre maximum de résultats (défaut: 5)')

    args = parser.parse_args()

    if not os.getenv('MONGODB_URI2'):
        print("❌ MONGODB_URI2 non défini dans .env")
        return

    if not os.getenv('OPENAI_API_KEY') and not os.getenv('GEMINI_API_KEY'):
        print("❌ Aucune clé API LLM définie dans .env (OPENAI_API_KEY ou GEMINI_API_KEY)")
        return

    # Liste de requêtes de test variées (Scénarios clients réels)
    test_queries = [
        # 1. Fourchette de prix (Nouveau scénario)
        "produits entre 5000 et 25000 FCFA",
        
        # 2. Le plus cher (Tri DESC)
        "le produit le plus cher de orca deco",
        
        # 3. Moins cher (Tri ASC)
        "quelque chose de pas trop cher pour le salon",
        
        # 4. Limite supérieure
        "produit qui ne dépasse pas 10000",
        
        # 5. Attributs + Prix
        "vase noir en céramique moins de 15000",
        
        # 6. Spécifique (Exactement)
        "un miroir qui coûte exactement 25000"
    ]

    if args.query:
        # Exécuter une seule requête si fournie
        test_query(args.query, args.limit)
    else:
        # Sinon exécuter la suite de tests
        print("🚀 Lancement de la suite de tests automatique...")
        for i, query in enumerate(test_queries, 1):
            print(f"\n[{i}/{len(test_queries)}] Test de la requête : '{query}'")
            test_query(query, args.limit)
            # Petite pause entre les requêtes pour la clarté
            import time
            time.sleep(1)

if __name__ == "__main__":
    main()