# Hervens Scripts - Configuration et Évaluation

Ce dossier contient les scripts pour importer, indexer et évaluer les données de `orca_unified.json` sur la base de données **Hervens** de MongoDB.

## 🏗️ Architecture Séparée

Ce dossier contient un **pipeline complètement indépendant** du code principal (`core/`) pour éviter de casser le système existant.

### Modules Locaux
| Fichier | Description |
|---------|-------------|
| `product_hervens.py` | Extraction de filtres LLM avec schéma anglais |
| `execute_query_hervens.py` | Exécution de requêtes sur base Hervens |

### Différences avec le code original

| Aspect | Original (`core/`) | Hervens (`hervens_scripts/`) |
|--------|-------------------|------------------------------|
| Base de données | `quali` | `Hervens` |
| Variable d'env | `MONGODB_URI` | `MONGODB_URI2` |
| Clés attributs | Français (`couleur`, `matériau`) | Anglais (`color`, `material`) |
| Index | `embedding_gemini_004_index` | `embedding_gemini_004_index_hervens` |
| Source données | `orca_product_complete.json` | `orca_unified.json` |

## Structure des Données

### Source: `orca_unified.json`
- **Database**: Hervens
- **Collection**: product
- **Schéma**: UNIFIED (voir `product_hervens.py`)
- **Caractéristiques**:
  - `attributes`: **Array** de {key, value} avec clés **anglaises** (color, material, shape)
  - `brand`: Présent (ex: "orca deco")
  - `keywords`: Pré-générés
  - `currency`: XOF (au lieu de CFA)

### Vs Données Originales (`orca_product_complete.json`)
- **Database**: quali
- **Collection**: product
- **Schéma**: ORIGINAL
- **Caractéristiques**:
  - `attributes`: **Array** d'objets {key, value} avec clés **françaises**
  - `brand`: Absent
  - `keywords`: Absent

## Scripts Disponibles

### 1. `import_data_hervens.py` - Import des données
```bash
python scripts/hervens_scripts/import_data_hervens.py
```

### 2. `generate_embeddings_hervens.py` - Génération des embeddings
```bash
python scripts/hervens_scripts/generate_embeddings_hervens.py
```

### 3. `create_filter_index_hervens.py` - Création de l'index
```bash
python scripts/hervens_scripts/create_filter_index_hervens.py
```

### 4. `execute_hervens.py` - Test manuel de queries
```bash
python scripts/hervens_scripts/execute_hervens.py "vase noir design"
python scripts/hervens_scripts/execute_hervens.py "je cherche un vase en verre" --limit 5
```

### 5. `eval_answers_hervens.py` - Évaluation complète
```bash
python scripts/hervens_scripts/eval_answers_hervens.py
```

## Ordre d'Exécution Recommandé

1. **Import** → 2. **Embeddings** → 3. **Index** → 4. **Test** → 5. **Évaluation**

### ⚠️ Test Manuel Important
Avant de lancer l'évaluation complète, testez quelques queries manuellement :

```bash
# Test basique
python scripts/hervens_scripts/execute_hervens.py "vase noir"

# Test avec limite
python scripts/hervens_scripts/execute_hervens.py "je cherche un vase en verre" --limit 5

# Test de filtres complexes
python scripts/hervens_scripts/execute_hervens.py "assiette ronde blanche"
```

**Vérifiez que :**
- ✅ Les filtres sont correctement extraits par le LLM (clés anglaises : `color`, `material`, etc.)
- ✅ Les résultats sont pertinents
- ✅ Les scores sont cohérents
- ✅ Aucun erreur de connexion

### Évaluation Complète
Une fois les tests validés :
```bash
python scripts/hervens_scripts/eval_answers_hervens.py
```

## Configuration Environment

Assurez-vous que `.env` contient:
```env
MONGODB_URI2 = "mongodb+srv://..." # Connexion Hervens (DIFFÉRENT de MONGODB_URI)
GEMINI_API_KEY = "..." # Pour les embeddings
OPENAI_API_KEY = "..." # Pour l'extraction de filtres (fallback)
```

## Modules Créés (Séparés du Core)

### `product_hervens.py` - Extraction de filtres LLM
- **`PRODUCT_SCHEMA_UNIFIED`** : Schéma avec clés anglaises
- **`PRODUCT_DATA_EXAMPLE_UNIFIED`** : Exemples de produits Hervens
- **`_construct_prompt_hervens()`** : Prompt avec attributs anglais (color, material, shape)
- **`extract_filters_agent_hervens(user_query)`** : Fonction principale d'extraction

### `execute_query_hervens.py` - Exécution de requêtes
- **`MONGODB_URI2`** : Connexion à la base Hervens
- **`_build_mongo_filter_hervens()`** : Construction de filtres avec Attribute Pattern (clés anglaises)
- **`_build_vector_search_pipeline_hervens()`** : Pipeline utilisant `embedding_gemini_004_index_hervens`
- **`execute_query_hervens(parsed_output, ...)`** : Fonction principale d'exécution

### Scripts Hervens
- `import_data_hervens.py`: Import depuis orca_unified.json
- `generate_embeddings_hervens.py`: Génération des embeddings
- `create_filter_index_hervens.py`: Création de l'index
- `execute_hervens.py`: Test manuel de queries
- `eval_answers_hervens.py`: Évaluation complète

## Comparaison des Résultats

Après exécution:

**Résultats Quali (Original)**
```
data/eval_pipeline_results.json
```

**Résultats Hervens (Unified)**
```
data/eval_pipeline_results_hervens.json
```

Comparer les métriques globales pour évaluer l'impact du nouveau schéma et de la nouvelle source de données.

## Notes Importantes

1. **Code Séparé**: Les modules `product_hervens.py` et `execute_query_hervens.py` sont **complètement indépendants** de `core/product.py` et `scripts/execute_query.py`
2. **Clés Anglaises**: Les filtres utilisent `attributes.color`, `attributes.material` (pas `couleur`, `matériau`)
3. **Attribute Pattern**: Les deux formats utilisent l'Attribute Pattern (array) pour MongoDB Vector Search
4. **Embeddings**: Même modèle (`text-embedding-004`) pour garantir la compatibilité
5. **Index Name**: `embedding_gemini_004_index_hervens` pour distinguer des indices quali

## Troubleshooting

### Index Creation Timeout
- Peut prendre 5+ minutes
- Vérifier le statut dans MongoDB Atlas → Indexes

### No Results in Search
- Vérifier que les embeddings ont été générés
- Vérifier que l'index est "queryable"
- Vérifier les filtres extraits par le LLM

### Filtres Incorrects (ex: `couleur` au lieu de `color`)
- Le LLM utilise les mauvais attributs
- Vérifier que vous utilisez `product_hervens.py` et non `core/product.py`
- Vérifier les exemples dans `PRODUCT_DATA_EXAMPLE_UNIFIED`

### Import Error "No module named..."
- Vérifier que vous exécutez depuis la racine du projet
- Ajouter `hervens_scripts/` au chemin si nécessaire

---

*Dernière mise à jour: Janvier 2025*
