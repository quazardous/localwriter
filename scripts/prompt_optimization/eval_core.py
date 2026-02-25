from __future__ import annotations

"""
Shared evaluation helpers for the Writer DSPy program.

This centralizes correctness / token accounting so both run_eval.py and
multi-model scripts can reuse the same logic.
"""

from dataclasses import dataclass
from typing import Any, Iterable, List, Tuple

import dspy

from dataset import to_dspy_examples
from metric import TOKEN_PENALTY_LAMBDA
from program import build_program


@dataclass
class ExampleEval:
    """Per-example evaluation result."""

    task_id: str
    correctness: float
    missing_expected: list[str]
    found_reject: list[str]
    metric_score: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    final_document: str
    error: str | None = None


def _correctness_breakdown(example: Any, final_document: str) -> Tuple[float, list[str], list[str]]:
    """Return (score, list of missing expected, list of bad reject found)."""
    expected = getattr(example, "expected_contains", []) or []
    reject = getattr(example, "reject_contains", []) or []
    score = 1.0
    missing: list[str] = []
    for s in expected:
        if s not in (final_document or ""):
            score -= 0.2
            missing.append(s)
    found_reject: list[str] = []
    for s in reject:
        if s in (final_document or ""):
            score -= 0.3
            found_reject.append(s)
    # Clamp to [0, 1]
    score = max(0.0, min(1.0, score))
    return score, missing, found_reject


def _get_tokens_from_pred(pred: Any, debug_usage: bool = False) -> Tuple[int, int, int]:
    """
    Extract (prompt_tokens, completion_tokens, total_tokens) from a DSPy prediction.

    Handles OpenRouter / LiteLLM-style get_lm_usage() payloads.
    """
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    try:
        usage = pred.get_lm_usage()
        if not usage or not isinstance(usage, dict):
            if debug_usage:
                print(f"  [debug] get_lm_usage() = {usage!r}", flush=True)
            return 0, 0, 0
        # Usage is a dict keyed by model; take the first entry with token info.
        for model_data in usage.values():
            if not isinstance(model_data, dict):
                continue
            if "total_tokens" in model_data:
                total_tokens = int(model_data["total_tokens"])
                # Best-effort split if available.
                prompt_tokens = int(
                    model_data.get("prompt_tokens")
                    or model_data.get("input_tokens")
                    or 0
                )
                completion_tokens = int(
                    model_data.get("completion_tokens")
                    or model_data.get("output_tokens")
                    or 0
                )
                return prompt_tokens, completion_tokens, total_tokens
            prompt_tokens = int(
                model_data.get("prompt_tokens")
                or model_data.get("input_tokens")
                or 0
            )
            completion_tokens = int(
                model_data.get("completion_tokens")
                or model_data.get("output_tokens")
                or 0
            )
            if prompt_tokens or completion_tokens:
                total_tokens = prompt_tokens + completion_tokens
                return prompt_tokens, completion_tokens, total_tokens
        if debug_usage:
            print(f"  [debug] get_lm_usage() = {usage!r} (no token keys found)", flush=True)
    except Exception as e:  # pragma: no cover - defensive
        if debug_usage:
            print(f"  [debug] get_lm_usage error: {e}", flush=True)
    return 0, 0, 0


def run_eval_on_examples(
    program: Any,
    examples: Iterable[Any],
    *,
    verbose: bool = False,
    debug_usage: bool = False,
    bust_cache: bool = True,
    quiet: bool = False,
) -> List[ExampleEval]:
    """
    Run the Writer program on a sequence of examples and return per-example results.

    - program: WriterAssistant instance built via build_program().
    - examples: iterable of dspy.Example with fields document_content, user_question.
    - bust_cache: when True, appends a unique suffix to the instruction per example
      (via build_program) to avoid OpenRouter's prompt cache interfering with token
      accounting.
    - quiet: when True, no per-example prints (e.g. when running multiple models in parallel).
    """
    results: list[ExampleEval] = []
    examples = list(examples)
    n = len(examples)
    base_instruction = getattr(program, "instruction", None) or ""

    with dspy.settings.context(track_usage=True, cache=False):
        for i, ex in enumerate(examples):
            task_id = getattr(ex, "task_id", "") or f"example_{i}"
            doc = getattr(ex, "document_content", "")
            question = getattr(ex, "user_question", "")
            if not quiet:
                print(f"--- [{i+1}/{n}] {task_id} ---")
                print(f"  Q: {question[:80]}{'...' if len(question) > 80 else ''}")
                print("  Calling model (may take 15–60s)...", flush=True)
            pred = None
            error: str | None = None
            try:
                if bust_cache and base_instruction:
                    # Defer import to avoid circulars when eval_core is imported elsewhere.
                    import uuid

                    cached_suffix = f"\n\n[Eval: {uuid.uuid4().hex[:8]}]"
                    prog = build_program(
                        instruction=base_instruction + cached_suffix,
                        tool_names=None,
                    )
                else:
                    prog = program
                pred = prog(document_content=doc, user_question=question)
                final = getattr(pred, "final_document", "") or ""
                correctness, missing, found_reject = _correctness_breakdown(ex, final)
                prompt_tok, completion_tok, total_tok = _get_tokens_from_pred(
                    pred, debug_usage=debug_usage
                )
                penalty = TOKEN_PENALTY_LAMBDA * (total_tok / 1000.0)
                metric_score = max(0.0, correctness - penalty)
                snippet = (final[:300] + "...") if len(final) > 300 else final
                if not quiet:
                    if missing:
                        print(f"  expected_contains MISSING: {missing}")
                    else:
                        print("  expected_contains: ok")
                    if found_reject:
                        print(f"  reject_contains FOUND (bad): {found_reject}")
                    else:
                        print("  reject_contains: ok")
                    print(
                        f"  correctness={correctness:.2f}  tokens={total_tok}  score={metric_score:.3f}"
                    )
                    print(f"  doc snippet: {snippet!r}")
                results.append(
                    ExampleEval(
                        task_id=task_id,
                        correctness=correctness,
                        missing_expected=missing,
                        found_reject=found_reject,
                        metric_score=metric_score,
                        prompt_tokens=prompt_tok,
                        completion_tokens=completion_tok,
                        total_tokens=total_tok,
                        final_document=final,
                        error=None,
                    )
                )
            except Exception as e:  # pragma: no cover - keep eval robust
                error = str(e)
                if not quiet:
                    print(f"  ERROR: {error}")
                results.append(
                    ExampleEval(
                        task_id=task_id,
                        correctness=0.0,
                        missing_expected=[],
                        found_reject=[],
                        metric_score=0.0,
                        prompt_tokens=0,
                        completion_tokens=0,
                        total_tokens=0,
                        final_document="",
                        error=error,
                    )
                )
            if not quiet:
                print()
    return results


def summarize_results(results: Iterable[ExampleEval]) -> dict:
    """Compute simple aggregates over a list of ExampleEval objects."""
    results = list(results)
    if not results:
        return {
            "avg_correctness": 0.0,
            "avg_metric_score": 0.0,
            "total_tokens": 0,
        }
    n = len(results)
    avg_correctness = sum(r.correctness for r in results) / n
    avg_metric = sum(r.metric_score for r in results) / n
    total_tokens = sum(r.total_tokens for r in results)
    return {
        "avg_correctness": avg_correctness,
        "avg_metric_score": avg_metric,
        "total_tokens": total_tokens,
    }

