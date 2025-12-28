import os
from pymongo import MongoClient
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()


def get_field_type(value: Any) -> str:
    """Détermine le type d'un champ à partir d'une valeur."""
    if isinstance(value, str):
        return "string"
    elif isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "integer"
    elif isinstance(value, float):
        return "number"
    elif isinstance(value, list):
        return "array"
    elif isinstance(value, dict):
        return "object"
    elif value is None:
        return "null"
    else:
        return "unknown"


def flatten_document(doc: Dict[str, Any], parent_key="", result=None):
    """Aplati les documents MongoDB avec champs imbriqués : price.amount, attributes.brand, etc."""
    if result is None:
        result = {}

    for key, value in doc.items():
        full_key = f"{parent_key}.{key}" if parent_key else key

        if isinstance(value, dict):
            flatten_document(value, full_key, result)
        else:
            result[full_key] = value

    return result


def infer_schema_from_mongodb(collection_name: str = "products", sample_size: int = 100):
    """
    Infère automatiquement le schéma de la collection MongoDB.
    Gère les champs simples, les champs imbriqués et les arrays.
    """
    mongodb_uri = os.getenv("MONGODB_URI")
    if not mongodb_uri:
        raise ValueError("MONGODB_URI not found in environment variables")

    # Connexion MongoDB
    client = MongoClient(mongodb_uri)
    db_name = mongodb_uri.split("/")[-1].split("?")[0]
    db = client[db_name]
    collection = db[collection_name]

    # Échantillon
    docs = list(collection.aggregate([{"$sample": {"size": sample_size}}]))

    if not docs:
        raise ValueError(f"No documents found in collection '{collection_name}'")

    field_types = {}

    # Aplatir tous les documents
    for doc in docs:
        if "_id" in doc:
            del doc["_id"]

        flat_doc = flatten_document(doc)

        for field, value in flat_doc.items():
            t = get_field_type(value)
            field_types.setdefault(field, set()).add(t)

    # Construction du schéma final
    final_schema = {}

    for field, types in field_types.items():
        if len(types) == 1:
            field_type = list(types)[0]
        else:
            field_type = "mixed"

        final_schema[field] = {
            "type": field_type,
            "description": generate_field_description(field, field_type)
        }

    return final_schema


def generate_field_description(field_name: str, field_type: str) -> str:
    """Descriptions automatiques basées sur le nom."""
    base = field_name.lower()

    if "price.amount" in base:
        return "Montant du prix en FCFA."
    if "price.currency" in base:
        return "Devise du prix."
    if "availability.status" in base:
        return "Statut de disponibilité du produit."
    if "attributes.brand" in base:
        return "Marque du produit."
    if "attributes.color" in base:
        return "Couleur du produit."

    return f"Champ '{field_name}' de type {field_type}."


def get_sample_document(collection_name: str = "products"):
    """Récupère un document exemple."""
    mongodb_uri = os.getenv("MONGODB_URI")
    if not mongodb_uri:
        raise ValueError("MONGODB_URI not found in environment variables")

    client = MongoClient(mongodb_uri)
    db_name = mongodb_uri.split("/")[-1].split("?")[0]
    db = client[db_name]
    collection = db[collection_name]

    sample = list(collection.aggregate([{"$sample": {"size": 1}}]))
    if not sample:
        raise ValueError("No sample document found.")

    doc = sample[0]
    if "_id" in doc:
        del doc["_id"]

    return doc
