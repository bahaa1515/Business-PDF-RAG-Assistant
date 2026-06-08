"""Simple experiment runner to re-index documents with different RAG settings and evaluate."""
import os
import csv
import time
from itertools import product
from typing import List, Dict
from src.pdf_loader import load_pdf_pages
from src.text_splitter import split_pages_into_chunks
from src.vector_store import create_vector_store, get_retriever
from src.evaluation import run_evaluation, ensure_eval_dirs
from src.config import EVAL_RESULTS_DIR


def run_experiments(uploaded_files: List[Dict], questions: List[Dict], save_path: str | None = None) -> List[Dict]:
    """
    Run a grid of experiments over uploaded_files (list of {name, bytes}) and questions.

    Returns list of results for each configuration.
    """
    ensure_eval_dirs()

    chunk_sizes = [400, 800, 1200]
    chunk_overlaps = [50, 150, 250]
    top_ks = [3, 5]
    methods = ["similarity", "mmr"]

    results = []

    # Preload pages from uploaded files
    all_pages = []
    for uf in uploaded_files:
        pages = load_pdf_pages(uf)
        all_pages.extend(pages)

    for cs, co, tk, meth in product(chunk_sizes, chunk_overlaps, top_ks, methods):
        # Re-split pages
        chunks = split_pages_into_chunks(all_pages, chunk_size=cs, chunk_overlap=co)
        if not chunks:
            continue
        # Recreate vector store and retriever
        vector_store = create_vector_store(chunks)
        retriever = get_retriever(vector_store, k=tk, method=meth)

        # Run evaluation over these questions
        eval_res = run_evaluation(questions, retriever)
        summary = eval_res['summary']

        results.append({
            'chunk_size': cs,
            'chunk_overlap': co,
            'top_k': tk,
            'retrieval_method': meth,
            'source_hit_rate': summary.get('source_hit_rate'),
            'refusal_accuracy': summary.get('refusal_accuracy'),
            'average_latency': summary.get('average_latency'),
        })

    # Save if requested
    if save_path:
        keys = list(results[0].keys()) if results else []
        with open(save_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for r in results:
                writer.writerow(r)

    return results