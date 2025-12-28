from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import json
from datetime import datetime
import time

load_dotenv()

# Configuration de Gemini (sera reconfigurée dynamiquement)
# genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
genai_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

def save_to_json_file(data: list, filename: str = "extracted_foods.json"):
    """
    Sauvegarde les données extraites dans un fichier JSON unique.
    Ajoute les nouveaux résultats aux données existantes.

    Args:
        data (list): Liste des plats extraits
        filename (str): Nom du fichier JSON de destination
    """
    try:
        # Lire les données existantes si le fichier existe
        existing_data = []
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                try:
                    existing_data = json.load(f)
                    if not isinstance(existing_data, list):
                        existing_data = [existing_data]
                except json.JSONDecodeError:
                    print(f"⚠️ Fichier {filename} corrompu, création d'un nouveau fichier")
                    existing_data = []

        # Ajouter les nouvelles données avec timestamp
        timestamp = datetime.now().isoformat()
        new_entry = {
            "extraction_timestamp": timestamp,
            "image_path": getattr(save_to_json_file, '_current_image_path', 'unknown'),
            "extracted_foods": data
        }

        existing_data.append(new_entry)

        # Sauvegarder dans le fichier
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Données sauvegardées dans {filename} (total: {len(existing_data)} extractions)")

    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde: {e}")

def load_extracted_data(filename: str = "extracted_foods.json") -> list:
    """
    Charge et retourne toutes les données extraites sauvegardées.

    Args:
        filename (str): Nom du fichier JSON à lire

    Returns:
        list: Liste de toutes les extractions avec timestamps
    """
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else [data]
        else:
            print(f"📁 Fichier {filename} n'existe pas encore")
            return []
    except Exception as e:
        print(f"❌ Erreur lors de la lecture: {e}")
        return []

def display_saved_extractions(filename: str = "extracted_foods.json"):
    """
    Affiche un résumé de toutes les extractions sauvegardées.
    """
    data = load_extracted_data(filename)

    if not data:
        print("📭 Aucune extraction sauvegardée")
        return

    print(f"\n📊 RÉSUMÉ DES EXTRACTIONS ({len(data)} sessions)")
    print("="*60)

    total_foods = 0
    for i, extraction in enumerate(data, 1):
        timestamp = extraction.get('extraction_timestamp', 'N/A')
        image_path = extraction.get('image_path', 'N/A')
        extracted_data = extraction.get('extracted_foods', {})

        # Vérifier si c'est le nouveau format avec meta
        if isinstance(extracted_data, dict) and 'foods' in extracted_data:
            foods = extracted_data.get('foods', [])
            meta = extracted_data.get('meta', {})
            restaurant_name = meta.get('source', 'unknown')
        else:
            # Ancien format (liste directe)
            foods = extracted_data if isinstance(extracted_data, list) else []
            restaurant_name = 'unknown'

        print(f"\n🔸 Session {i} - {timestamp}")
        print(f"   📁 Image: {image_path}")
        print(f"   🏪 Restaurant: {restaurant_name}")
        print(f"   🍽️  Plats extraits: {len(foods)}")

        total_foods += len(foods)

        # Afficher les premiers plats
        for food in foods[:3]:  # Afficher max 3 plats par session
            name = food.get('name', 'N/A')
            price = food.get('price', {})
            amount = price.get('amount', 'N/A')
            currency = price.get('currency', '')
            print(f"      • {name} - {amount} {currency}")

        if len(foods) > 3:
            print(f"      ... et {len(foods) - 3} autres plats")

    print(f"\n📈 TOTAL: {total_foods} plats extraits de {len(data)} images")

def extract_food_info_from_image(image_path: str, save_to_file: bool = True) -> dict:
    """
    Envoie une image à Gemini et extrait les informations sur les mets offerts.

    Args:
        image_path (str): Chemin vers le fichier image local (capture d'écran du menu).
        save_to_file (bool): Si True, sauvegarde automatiquement les résultats dans extracted_foods.json

    Returns:
        dict: Dictionnaire/Liste JSON structuré contenant les informations extraites.
    """

    # Lecture de l'image
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # Prompt détaillé expliquant la tâche
    prompt = """
Tu es un assistant intelligent spécialisé dans l'extraction d'informations de menus de restaurants.

🎯 **TÂCHE** : Extrais TOUTES les informations visibles sur cette image de menu de restaurant.

📋 **CE QUE TU DOIS EXTRAIRE** :

**INFORMATIONS SUR LE RESTAURANT (META)** :
- Le NOM du restaurant (obligatoire - c'est la source)
- La NOTE/ÉVALUATION du restaurant (si visible)
- Le NOMBRE d'avis/commentaires (si visible)

**INFORMATIONS SUR LES PLATS** :
- Le NOM de chaque plat (obligatoire)
- Le PRIX de chaque plat (obligatoire)
- La DESCRIPTION (si visible)
- Les CATÉGORIES du plat (entrée, plat principal, dessert, boisson, etc.)
- Les INGRÉDIENTS mentionnés
- Toute autre information pertinente

⚠️ **RÈGLES IMPORTANTES** :
1. Extrais CHAQUE plat individuellement dans un tableau JSON
2. Si une information n'est pas visible, utilise "unknown" ou null
3. Pour les prix, extrais le montant ET la devise (FCFA, EUR, USD, etc.)
4. Génère un ID unique pour chaque plat (food-001, food-002, etc.)
5. Pour la meta, utilise "unknown" si l'info n'est pas visible
6. Ne rajoute AUCUN texte en dehors du JSON
7. Si plusieurs plats ont le même nom mais des variantes, créé des entrées séparées

📊 **FORMAT DE SORTIE REQUIS** (objet JSON):
{
  "foods": [
    {
      "id": "food-001",
      "type": "food",
      "name": "Nom exact du plat",
      "description": "Description si disponible sinon unknown",
      "categories": ["catégorie principale", "sous-catégorie"],
      "tags": ["mots-clés du plat"],
      "price": {
        "amount": 5500,
        "currency": "FCFA"
      },
      "availability": {
        "status": "available"
      },
      "attributes": {
        "spicy_level": "none",
        "ingredients": ["ingredient1", "ingredient2"]
      },
      "meta": {
        "source": "Nom du restaurant trouvé sur l'image",
        "rating": 4.8,
        "reviews_count": 320
      }
    },
    {
      "id": "food-002",
      "type": "food",
      "name": "Autre plat",
      "description": "Description du deuxième plat",
      "categories": ["catégorie"],
      "tags": ["tag1", "tag2"],
      "price": {
        "amount": 3500,
        "currency": "FCFA"
      },
      "availability": {
        "status": "available"
      },
      "attributes": {
        "spicy_level": "medium",
        "ingredients": ["ingredient1", "ingredient2"]
      },
      "meta": {
        "source": "Nom du restaurant trouvé sur l'image",
        "rating": 4.8,
        "reviews_count": 320
      }
    }
  ]
}

🔍 **CONSIGNES D'EXTRACTION** :
- Lis attentivement toute l'image pour trouver le nom du restaurant
- Cherche les informations de notation et nombre d'avis
- IMPORTANT: Ajoute les informations meta (source, rating, reviews_count) à CHAQUE plat individuellement
- Le champ "source" dans meta doit contenir le nom du restaurant pour TOUS les plats
- Si le restaurant a une note, ajoute-la dans "rating" de CHAQUE plat
- Si le restaurant a un nombre d'avis, ajoute-le dans "reviews_count" de CHAQUE plat
- N'oublie AUCUN plat visible
- Respecte l'orthographe exacte des noms
- Extrais TOUS les prix visibles
- Si un plat a plusieurs tailles/variantes, créé des entrées séparées avec les mêmes informations meta

Renvoie UNIQUEMENT l'objet JSON, sans texte additionnel."""

    # Envoi de la requête à Gemini
    # model = genai.GenerativeModel('gemini-2.0-flash-lite')

    # Créer le contenu avec l'image et le prompt
    response = genai_client.models.generate_content(
        model='gemini-2.0-flash-lite',
        contents=[
            prompt,
            types.Part.from_bytes(
                data=image_bytes,
                mime_type='image/jpeg'
            )
        ]
    )

    # Extraction du texte JSON renvoyé
    content = response.text.strip()

    # Nettoyer les marqueurs markdown si présents
    if content.startswith("```json"):
        content = content[7:]  # Retirer ```json
    if content.startswith("```"):
        content = content[3:]   # Retirer ``` simple
    if content.endswith("```"):
        content = content[:-3]  # Retirer ``` de fin

    content = content.strip()

    # Tentative de conversion en dictionnaire Python
    try:
        data = json.loads(content)
        if isinstance(data, dict) and 'foods' in data:
            foods = data.get('foods', [])
            meta = data.get('meta', {})
            print(f"✅ Extraction réussie : {len(foods)} plats trouvés")
            print(f"🏪 Restaurant: {meta.get('source', 'unknown')}")
            if meta.get('rating') != 'unknown' and meta.get('rating') is not None:
                print(f"⭐ Note: {meta.get('rating')}")
            if meta.get('reviews_count') != 'unknown' and meta.get('reviews_count') is not None:
                print(f"💬 Avis: {meta.get('reviews_count')}")

            # Sauvegarder automatiquement si demandé
            if save_to_file:
                save_to_json_file._current_image_path = image_path
                save_to_json_file(data)
        else:
            print(f"✅ Extraction réussie")
    except json.JSONDecodeError:
        print("⚠️ Le modèle n'a pas renvoyé un JSON valide. Réponse brute :")
        print(content)
        data = {"error": "Invalid JSON", "raw_response": content}

    return data


def process_all_images(images_folder: str = "image", output_file: str = "extracted_foods.json", images_per_key: int = 6):
    """
    Traite toutes les images d'un dossier avec rotation des clés API Google.
    
    Args:
        images_folder (str): Chemin du dossier contenant les images
        output_file (str): Fichier JSON de sortie unique
        images_per_key (int): Nombre d'images à traiter par clé API (défaut: 6)
    
    Returns:
        dict: Statistiques du traitement
    """
    # Récupérer toutes les clés API disponibles
    api_keys = []
    if os.getenv("GOOGLE_API_KEY"):
        api_keys.append(os.getenv("GOOGLE_API_KEY"))
    if os.getenv("GOOGLE_API_KEY2"):
        api_keys.append(os.getenv("GOOGLE_API_KEY2"))
    if os.getenv("GOOGLE_API_KEY3"):
        api_keys.append(os.getenv("GOOGLE_API_KEY3"))
    
    if not api_keys:
        print("❌ Aucune clé API Google trouvée dans le fichier .env")
        return {"error": "No API keys found"}
    
    print(f"🔑 {len(api_keys)} clés API disponibles")
    print(f"📋 Configuration: {images_per_key} images par clé\n")
    
    # Récupérer toutes les images (jpg, jpeg, png) - avec déduplication
    image_extensions = ['.jpg', '.jpeg', '.png', '.webp']
    all_images = []
    
    # Lister tous les fichiers du dossier
    if os.path.exists(images_folder):
        for filename in os.listdir(images_folder):
            file_path = os.path.join(images_folder, filename)
            # Vérifier si c'est un fichier et si l'extension est valide
            if os.path.isfile(file_path):
                ext = os.path.splitext(filename)[1].lower()
                if ext in image_extensions:
                    all_images.append(file_path)
    
    # Dédupliquer au cas où (set puis list)
    all_images = list(set(all_images))
    # Trier pour avoir un ordre cohérent
    all_images.sort()
    
    if not all_images:
        print(f"❌ Aucune image trouvée dans le dossier '{images_folder}'")
        return {"error": "No images found", "folder": images_folder}
    
    print(f"📁 {len(all_images)} images trouvées dans '{images_folder}'\n")
    print("="*60)
    print("🚀 DÉBUT DU TRAITEMENT")
    print("="*60 + "\n")
    
    # Statistiques
    stats = {
        "total_images": len(all_images),
        "processed": 0,
        "failed": 0,
        "total_foods": 0,
        "start_time": datetime.now().isoformat(),
        "errors": []
    }
    
    current_key_index = 0
    images_with_current_key = 0
    
    for idx, image_path in enumerate(all_images, 1):
        # Rotation des clés API si nécessaire
        if images_with_current_key >= images_per_key and current_key_index < len(api_keys) - 1:
            current_key_index += 1
            images_with_current_key = 0
            print(f"\n🔄 Changement de clé API → Clé #{current_key_index + 1}")
            global genai_client
            genai_client = genai.Client(api_key=api_keys[current_key_index])
            # Petite pause pour éviter les rate limits
            time.sleep(2)
        
        print(f"\n{'='*60}")
        print(f"📸 Image {idx}/{len(all_images)}: {os.path.basename(image_path)}")
        print(f"🔑 Clé API #{current_key_index + 1} (image {images_with_current_key + 1}/{images_per_key})")
        print(f"{'='*60}")
        
        try:
            # Extraire les informations
            result = extract_food_info_from_image(image_path, save_to_file=True)
            
            if isinstance(result, dict) and 'foods' in result:
                foods_count = len(result.get('foods', []))
                stats["total_foods"] += foods_count
                stats["processed"] += 1
                print(f"✅ Succès: {foods_count} plats extraits")
            elif 'error' in result:
                stats["failed"] += 1
                stats["errors"].append({
                    "image": os.path.basename(image_path),
                    "error": result.get('error', 'Unknown error')
                })
                print(f"⚠️ Erreur lors de l'extraction")
            else:
                stats["processed"] += 1
                print(f"✅ Extraction complétée")
            
            images_with_current_key += 1
            
            # Pause entre chaque image pour éviter les rate limits
            if idx < len(all_images):
                time.sleep(1)
                
        except Exception as e:
            stats["failed"] += 1
            stats["errors"].append({
                "image": os.path.basename(image_path),
                "error": str(e)
            })
            print(f"❌ Erreur: {e}")
            
            # Si erreur de ressources, essayer de changer de clé
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                if current_key_index < len(api_keys) - 1:
                    current_key_index += 1
                    images_with_current_key = 0
                    print(f"\n⚠️ Ressources épuisées → Changement de clé API → Clé #{current_key_index + 1}")
                    genai_client = genai.Client(api_key=api_keys[current_key_index])
                    time.sleep(5)
                else:
                    print("\n⚠️ Toutes les clés API sont épuisées, pause de 10 secondes...")
                    time.sleep(10)
    
    # Résumé final
    stats["end_time"] = datetime.now().isoformat()
    
    print("\n" + "="*60)
    print("✨ TRAITEMENT TERMINÉ")
    print("="*60)
    print(f"\n📊 STATISTIQUES:")
    print(f"   ✅ Images traitées avec succès: {stats['processed']}/{stats['total_images']}")
    print(f"   ❌ Images échouées: {stats['failed']}")
    print(f"   🍽️  Total de plats extraits: {stats['total_foods']}")
    print(f"   💾 Fichier de sortie: {output_file}")
    
    if stats['errors']:
        print(f"\n⚠️ ERREURS DÉTECTÉES ({len(stats['errors'])}):")
        for error in stats['errors'][:5]:  # Afficher max 5 erreurs
            print(f"   • {error['image']}: {error['error']}")
        if len(stats['errors']) > 5:
            print(f"   ... et {len(stats['errors']) - 5} autres erreurs")
    
    print(f"\n🔍 Utilisez 'python agent_gemini.py --view' pour voir toutes les extractions\n")
    
    return stats


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--view":
        # Afficher les extractions sauvegardées
        display_saved_extractions()
        sys.exit(0)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--batch":
        # Traiter toutes les images du dossier
        print("🚀 Mode batch: traitement de toutes les images\n")
        stats = process_all_images()
        sys.exit(0)

    # Mode par défaut : traiter toutes les images du dossier
    print("🚀 Traitement automatique de toutes les images du dossier 'image/'\n")
    stats = process_all_images()