"""
Automatic evaluation of the NHS Inform RAG agent:
- In-scope questions: expect answer (and optionally check for hallucination).
- Out-of-scope / vague: expect refusal.
"""

import json
from pathlib import Path

from agent import answer, REFUSAL_STRATEGIES

EVAL_QUESTIONS_PATH = Path(__file__).parent / "eval_questions.json"
RESULTS_PATH = Path(__file__).parent / "eval_results.json"


def load_eval_set() -> dict:
    with open(EVAL_QUESTIONS_PATH, encoding="utf-8") as f:
        return json.load(f)


def run_evaluation(refusal_strategy: str = "explain", save: bool = True) -> dict:
    """Run agent on all eval questions; return results and simple metrics."""
    eval_set = load_eval_set()
    results = {"strategy": refusal_strategy, "by_category": {}, "summary": {}}
    total_refuse_expected = 0
    total_answer_expected = 0
    correct_refuse = 0
    correct_answer = 0

    for category, items in eval_set.items():
        if category.startswith("_"):
            continue
        results["by_category"][category] = []
        for item in items:
            q = item.get("question", "")
            expected = item.get("expected", "answer")
            out = answer(q, refusal_strategy=refusal_strategy)
            refused = out["refused"]
            correct = (expected == "refuse" and refused) or (expected == "answer" and not refused)
            results["by_category"][category].append({
                "id": item.get("id"),
                "question": q,
                "expected": expected,
                "refused": refused,
                "correct": correct,
                "answer_preview": (out["answer"] or "")[:200],
            })
            if expected == "refuse":
                total_refuse_expected += 1
                if refused:
                    correct_refuse += 1
            else:
                total_answer_expected += 1
                if not refused:
                    correct_answer += 1

    results["summary"] = {
        "total_refuse_expected": total_refuse_expected,
        "correct_refusals": correct_refuse,
        "total_answer_expected": total_answer_expected,
        "correct_answers": correct_answer,
        "refusal_accuracy": correct_refuse / total_refuse_expected if total_refuse_expected else 0,
        "answer_accuracy": correct_answer / total_answer_expected if total_answer_expected else 0,
    }
    if save:
        RESULTS_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Results saved to {RESULTS_PATH}")
    return results


def main():
    import argparse
    p = argparse.ArgumentParser(description="Evaluate NHS Inform agent (refusal vs answer).")
    p.add_argument("--strategy", choices=list(REFUSAL_STRATEGIES), default="explain")
    p.add_argument("--no-save", action="store_true", help="Do not write eval_results.json")
    args = p.parse_args()
    res = run_evaluation(refusal_strategy=args.strategy, save=not args.no_save)
    print("\nSummary:")
    print(json.dumps(res["summary"], indent=2))
    print("\nPer-category: correct / total per row in eval_questions.json.")


if __name__ == "__main__":
    main()
