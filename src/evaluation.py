"""Evaluation utilities for running RAG QA over an evaluation dataset."""
import os
import csv
import time
from typing import List, Dict
from src.config import EVAL_DEFAULT_CSV, EVAL_RESULTS_DIR, DATA_DIR, REFUSAL_MESSAGE
from src.rag_chain import answer_question


def ensure_eval_dirs():
    os.makedirs(EVAL_RESULTS_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)


def load_evaluation_questions(path: str) -> List[Dict]:
    questions = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            questions.append(row)
    return questions


def run_evaluation(questions: List[Dict], retriever, save_path: str | None = None) -> Dict:
    """
    Run evaluation on a list of question dicts.

    Each question dict should have: question, expected_source, expected_page, question_type
    Returns dict with 'results' (list) and 'summary' (metrics).
    """
    ensure_eval_dirs()

    results = []
    total_latency = 0.0
    answerable_hits = 0
    answerable_total = 0
    unanswerable_correct = 0
    unanswerable_total = 0

    for q in questions:
        question_text = q.get('question', '')
        expected_source = q.get('expected_source', '')
        expected_page = q.get('expected_page', '')
        qtype = q.get('question_type', 'answerable')

        start = time.perf_counter()
        result = answer_question(question_text, retriever)
        latency = result.get('latency_seconds') or (time.perf_counter() - start)
        total_latency += latency

        retrieved = result.get('sources', [])
        retrieved_list = [f"{d.metadata.get('source','')}:page:{d.metadata.get('page','')}" for d in retrieved]

        source_hit = False
        correctly_refused = False

        if qtype == 'answerable':
            answerable_total += 1
            for d in retrieved:
                if d.metadata.get('source') == expected_source and str(d.metadata.get('page')) == str(expected_page):
                    source_hit = True
                    break
            if source_hit:
                answerable_hits += 1
        else:
            unanswerable_total += 1
            if result.get('answer','').strip() == REFUSAL_MESSAGE:
                correctly_refused = True
                unanswerable_correct += 1

        results.append({
            'question': question_text,
            'question_type': qtype,
            'expected_source': expected_source,
            'expected_page': expected_page,
            'answer': result.get('answer',''),
            'retrieved_sources': ';'.join(retrieved_list),
            'source_hit': source_hit,
            'correctly_refused': correctly_refused,
            'latency_seconds': latency,
        })

    avg_latency = total_latency / max(1, len(questions))
    summary = {
        'source_hit_rate': (answerable_hits / answerable_total) if answerable_total else None,
        'refusal_accuracy': (unanswerable_correct / unanswerable_total) if unanswerable_total else None,
        'average_latency': avg_latency,
    }

    # Optionally save
    if save_path:
        keys = list(results[0].keys()) if results else []
        with open(save_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for r in results:
                writer.writerow(r)

    return {'results': results, 'summary': summary}