"""
Script d'évaluation du pipeline de recherche complet pour DB Hervens.
Évalue : extract_filters_agent_hervens (LLM) -> execute_query_hervens (Vector Search + Filtres)

Database: Hervens
Collection: product
Dataset: orca_unified.json
Schema: unified (clés anglaises: color, material)

Usage:
    python scripts/hervens_scripts/eval_answers_hervens.py
"""

import os
import sys
import json
import time
from typing import List, Dict, Any
from datetime import datetime
from dotenv import load_dotenv
import statistics
from dataclasses import dataclass

# Ajouter le dossier hervens_scripts au path
sys.path.insert(0, os.path.dirname(__file__))

# Importer les modules Hervens locaux
from product_hervens import extract_filters_agent_hervens
from execute_query_hervens import execute_query_hervens

load_dotenv()

# Configuration Hervens
DATABASE_NAME = 'Hervens'
COLLECTION_NAME = 'product'

if not os.getenv('MONGODB_URI2'):
    print("⚠️ MONGODB_URI2 manquante dans les variables d'environnement")

@dataclass
class QueryResult:
    query: str
    query_type: str
    parsed_output: Dict[str, Any]
    retrieved_products: List[Dict[str, Any]]
    relevant_ids: List[str]
    relevant_names: List[str]
    metrics: Dict[str, float]

class PipelineEvaluatorHervens:
    """Évaluateur du pipeline complet de recherche pour DB Hervens."""
    
    def __init__(self):
        # Vérification des clés API (OpenAI ou Gemini)
        if not os.getenv('OPENAI_API_KEY') and not os.getenv('GEMINI_API_KEY'):
            print("⚠️ Aucune clé API (OPENAI_API_KEY ou GEMINI_API_KEY) trouvée dans les variables d'environnement")
    
    # --- Fonctions de Calcul de Métriques ---

    def calculate_precision_at_k(self, retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
        if not retrieved_ids or k == 0: 
            return 0.0
        retrieved_k = retrieved_ids[:k]
        relevant_set = set(relevant_ids)
        relevant_retrieved = sum(1 for doc_id in retrieved_k if doc_id in relevant_set)
        return relevant_retrieved / k

    def calculate_recall_at_k(self, retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
        if not relevant_ids: 
            return 0.0
        retrieved_k = retrieved_ids[:k]
        relevant_set = set(relevant_ids)
        relevant_retrieved = sum(1 for doc_id in retrieved_k if doc_id in relevant_set)
        return relevant_retrieved / len(relevant_ids)

    def calculate_f1_at_k(self, retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
        precision = self.calculate_precision_at_k(retrieved_ids, relevant_ids, k)
        recall = self.calculate_recall_at_k(retrieved_ids, relevant_ids, k)
        return 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    def calculate_mrr(self, retrieved_ids: List[str], relevant_ids: List[str]) -> float:
        relevant_set = set(relevant_ids)
        for i, doc_id in enumerate(retrieved_ids, 1):
            if doc_id in relevant_set:
                return 1.0 / i
        return 0.0

    def calculate_ndcg_at_k(self, retrieved_ids: List[str], relevant_ids: List[str], k: int) -> float:
        # DCG
        retrieved_k = retrieved_ids[:k]
        relevant_set = set(relevant_ids)
        dcg = 0.0
        for i, doc_id in enumerate(retrieved_k, 1):
            relevance = 1.0 if doc_id in relevant_set else 0.0
            dcg += relevance / (i ** 0.5) if i > 1 else relevance 
        
        # IDCG (Ideal DCG)
        ideal_count = min(len(relevant_ids), k)
        idcg = 0.0
        for i in range(1, ideal_count + 1):
            idcg += 1.0 / (i ** 0.5) if i > 1 else 1.0
            
        return dcg / idcg if idcg > 0 else 0.0

    def evaluate_query(self, query_data: Dict[str, Any], k_values: List[int] = [5, 10]) -> QueryResult:
        """
        Évalue une requête à travers le pipeline complet.
        
        1. extract_filters_agent() - Extraction des filtres par LLM (schema_version='unified')
        2. execute_query() - Recherche vectorielle + filtres sur DB Hervens
        3. Calcul des métriques
        """
        query = query_data['query']
        query_type = query_data.get('query_type', 'unknown')
        relevant_ids = query_data['relevant_ids']
        relevant_names = query_data.get('relevant_names', [])
        
        # 1. Extraction des filtres par LLM (module Hervens avec clés anglaises)
        print(f"   🤖 Extraction des filtres (LLM Hervens - clés anglaises)...")
        parsed_output = extract_filters_agent_hervens(query)
        
        if parsed_output.get('confidence', 0) < 0.3:
            print(f"   ⚠️ Confiance faible: {parsed_output.get('confidence', 0):.2f}")
        
        # 2. Exécution de la requête (Vector Search + Filtres) sur Hervens
        print(f"   🔍 Exécution de la recherche (DB: {DATABASE_NAME})...")
        retrieved_docs = execute_query_hervens(
            parsed_output,
            limit=max(k_values)
        )
        
        # Extraire les IDs des résultats
        retrieved_ids = [str(doc.get('id', doc.get('_id', ''))) for doc in retrieved_docs]
        
        # 3. Calcul des métriques
        metrics = {}
        for k in k_values:
            metrics[f'precision@{k}'] = self.calculate_precision_at_k(retrieved_ids, relevant_ids, k)
            metrics[f'recall@{k}'] = self.calculate_recall_at_k(retrieved_ids, relevant_ids, k)
            metrics[f'f1@{k}'] = self.calculate_f1_at_k(retrieved_ids, relevant_ids, k)
            metrics[f'ndcg@{k}'] = self.calculate_ndcg_at_k(retrieved_ids, relevant_ids, k)
        
        metrics['mrr'] = self.calculate_mrr(retrieved_ids, relevant_ids)
        metrics['confidence'] = parsed_output.get('confidence', 0.0)
        
        return QueryResult(
            query=query,
            query_type=query_type,
            parsed_output=parsed_output,
            retrieved_products=retrieved_docs,
            relevant_ids=relevant_ids,
            relevant_names=relevant_names,
            metrics=metrics
        )


def main():
    print("="*70)
    print("🚀 ÉVALUATION DU PIPELINE COMPLET - DB HERVENS")
    print("   (extract_filters_agent → execute_query)")
    print("="*70)

    import argparse
    parser = argparse.ArgumentParser(description="Évaluer le pipeline de recherche (Hervens).")
    parser.add_argument("--file", type=str, default=None, help="Chemin vers le fichier de dataset de test (JSON).")
    args = parser.parse_args()

    if args.file:
        TEST_FILE = args.file
    else:
        # Par défaut
        TEST_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'eval_answers_hervens_new.json')
    
    if not os.path.exists(TEST_FILE):
        print(f"⚠️ Fichier de test '{TEST_FILE}' non trouvé.")
        print("Veuillez créer ce fichier avec vos requêtes de test.")
        return
        
    print(f"📂 Utilisation du dataset: {TEST_FILE}")
    print(f"📍 Database: {DATABASE_NAME}")
    print(f"📍 Collection: {COLLECTION_NAME}")

    with open(TEST_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    queries = data.get('test_queries', [])
    print(f"\n📋 Chargement de {len(queries)} requêtes de test.\n")

    evaluator = PipelineEvaluatorHervens()

    detailed_results = []
    
    for i, q in enumerate(queries, 1):
        print(f"\n[{i}/{len(queries)}] 📝 '{q['query']}' (Type: {q.get('query_type', 'N/A')})")
        print("-" * 50)
        
        try:
            res = evaluator.evaluate_query(q)
            
            if res:
                detailed_results.append(res)
                
                # Affichage des résultats
                print(f"\n   📊 Métriques:")
                print(f"      P@5: {res.metrics['precision@5']:.2f} | R@5: {res.metrics['recall@5']:.2f} | MRR: {res.metrics['mrr']:.2f}")
                print(f"      Confiance LLM: {res.metrics['confidence']:.2f}")
                
                # Filtres extraits
                filters = res.parsed_output.get('filters', {})
                mandatory = filters.get('mandatory', {})
                optional = filters.get('optional', {})
                print(f"   🎯 Filtres: mandatory={list(mandatory.keys())}, optional={list(optional.keys())}")
                print(f"   🔎 Semantic Query: {res.parsed_output.get('semantic_query', 'N/A')}")
                
                # Top match vs expected
                top_match_name = res.retrieved_products[0].get('name', 'Aucun') if res.retrieved_products else "Aucun résultat"
                print(f"   ► Trouvé #1: {top_match_name[:60]}...")
                
                if res.relevant_names:
                    expected_str = res.relevant_names[0][:50] + "..." if len(res.relevant_names[0]) > 50 else res.relevant_names[0]
                    print(f"   ► Attendu #1: {expected_str}")
                
        except Exception as e:
            print(f"   ❌ Erreur: {e}")
            import traceback
            traceback.print_exc()
        
        time.sleep(1)  # Rate limiting

    # --- RÉSULTATS PAR TYPE ---
    results_by_type = {}
    for res in detailed_results:
        q_type = res.query_type
        if q_type not in results_by_type:
            results_by_type[q_type] = []
        results_by_type[q_type].append(res)
    
    metrics_by_type = {}
    
    print("\n" + "="*70)
    print("📊 RÉSULTATS PAR TYPE DE REQUÊTE (Hervens)")
    print("="*70)
    
    for q_type, results in results_by_type.items():
        if not results: continue
        
        type_metrics = {}
        metric_keys = results[0].metrics.keys()
        for key in metric_keys:
             values = [r.metrics[key] for r in results]
             type_metrics[key] = statistics.mean(values)
        
        metrics_by_type[q_type] = type_metrics
        
        print(f"\n🔹 Type: {q_type.upper()} ({len(results)} requêtes)")
        print(f"   MRR: {type_metrics['mrr']:.4f}")
        print(f"   Précision@5: {type_metrics['precision@5']:.4f}")
        print(f"   Rappel@5:    {type_metrics['recall@5']:.4f}")
        print(f"   NDCG@5:      {type_metrics['ndcg@5']:.4f}")
        print(f"   Confiance:   {type_metrics['confidence']:.2f}")

    # --- RÉSULTATS GLOBAUX ---
    if detailed_results:
        avg_metrics = {}
        metric_keys = detailed_results[0].metrics.keys()
        
        for key in metric_keys:
            values = [r.metrics[key] for r in detailed_results]
            avg_metrics[key] = statistics.mean(values)

        print("\n" + "="*70)
        print("📊 RÉSULTATS GLOBAUX - Pipeline Complet (HERVENS)")
        print("="*70)
        print(f"MRR Moyen:           {avg_metrics['mrr']:.4f}")
        print(f"Précision@5 Moyenne: {avg_metrics['precision@5']:.4f}")
        print(f"Rappel@5 Moyen:      {avg_metrics['recall@5']:.4f}")
        print(f"F1 Score@5 Moyen:    {avg_metrics['f1@5']:.4f}")
        print(f"NDCG@5 Moyen:        {avg_metrics['ndcg@5']:.4f}")
        print(f"Confiance LLM Moy:   {avg_metrics['confidence']:.4f}")
        print("-" * 30)
        
        # Sauvegarder les résultats détaillés
        output_file = 'eval_pipeline_results_hervens.json'
        output_data = {
            "timestamp": datetime.now().isoformat(),
            "database": DATABASE_NAME,
            "collection": COLLECTION_NAME,
            "schema_version": "unified (clés anglaises: color, material)",
            "pipeline": "extract_filters_agent_hervens -> execute_query_hervens",
            "global_metrics": avg_metrics,
            "metrics_by_type": metrics_by_type,
            "details": [
                {
                    "query": r.query,
                    "query_type": r.query_type,
                    "semantic_query": r.parsed_output.get('semantic_query', ''),
                    "filters": r.parsed_output.get('filters', {}),
                    "confidence": r.parsed_output.get('confidence', 0),
                    "metrics": r.metrics,
                    "retrieved": [p.get('name') for p in r.retrieved_products[:5]],
                    "expected_ids": r.relevant_ids,
                    "expected_names": r.relevant_names
                }
                for r in detailed_results
            ]
        }
        
        output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', output_file)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"💾 Résultats détaillés sauvegardés dans '{output_path}'")


if __name__ == "__main__":
    main()
