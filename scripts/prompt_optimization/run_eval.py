#!/usr/bin/env python3
"""
Run the Writer assistant on the dataset (no optimization).
Shows per-example: task_id, expected/reject checks, correctness, tokens, score, and doc snippet.

Usage:
  export OPENROUTER_API_KEY="your-key"   # or OPENAI_API_KEY
  cd scripts/prompt_optimization
  python run_eval.py                    # run all examples
  python run_eval.py --example table_from_mess   # run one task_id
  python run_eval.py -n 2               # run first 2 examples only
  python run_eval.py -v                 # verbose: print every tool call
  python run_eval.py --compare-with optimized_writer_prompt.json   # run both prompts, report diff
  python run_eval.py --no-bust-cache   # disable cache-busting (default: enabled)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import dspy

from dataset import ALL_EXAMPLES, to_dspy_examples
from program import build_program
from metric import writer_assistant_metric, TOKEN_PENALTY_LAMBDA
import tools_mock

DEFAULT_API_BASE = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "nvidia/llama-3.3-nemotron-super-49b-v1.5"


def _load_prompt_from_json(path: Path) -> str:
    """Load instruction from a DSPy saved program JSON (optimized_writer_prompt.json)."""
    data = json.loads(path.read_text())
    # react.react.signature.instructions is the main ReAct predictor's system prompt
    try:
        return data["react.react"]["signature"]["instructions"]
    except KeyError:
        raise ValueError(f"Could not find react.react.signature.instructions in {path}")


def _get_tokens_from_pred(pred, debug_usage: bool = False) -> int:
    """Extract total tokens from DSPy prediction. Handles OpenRouter/LiteLLM formats."""
    try:
        usage = pred.get_lm_usage()
        if not usage or not isinstance(usage, dict):
            if debug_usage:
                print(f"  [debug] get_lm_usage() = {usage!r}", flush=True)
            return 0
        for model_data in usage.values():
            if not isinstance(model_data, dict):
                continue
            if "total_tokens" in model_data:
                return int(model_data["total_tokens"])
            p = int(model_data.get("prompt_tokens", 0) or model_data.get("input_tokens", 0))
            c = int(model_data.get("completion_tokens", 0) or model_data.get("output_tokens", 0))
            if p or c:
                return p + c
        if debug_usage:
            print(f"  [debug] get_lm_usage() = {usage!r} (no token keys found)", flush=True)
    except Exception as e:
        if debug_usage:
            print(f"  [debug] get_lm_usage error: {e}", flush=True)
    return 0


def _run_eval(program, examples, verbose: bool, debug_usage: bool = False, bust_cache: bool = False) -> tuple[list[float], list[int]]:
    """Run program on examples and return (scores, token_counts).
    If bust_cache=True, append a unique suffix to the instruction per example to avoid OpenRouter prompt cache."""
    scores = []
    token_counts = []
    n = len(examples)
    base_instruction = getattr(program, "instruction", None) or ""
    with dspy.settings.context(track_usage=True, cache=False):
        for i, ex in enumerate(examples):
            task_id = getattr(ex, "task_id", "") or f"example_{i}"
            doc = getattr(ex, "document_content", "")
            question = getattr(ex, "user_question", "")
            print(f"--- [{i+1}/{n}] {task_id} ---")
            print(f"  Q: {question[:80]}{'...' if len(question) > 80 else ''}")
            print("  Calling model (may take 15–60s)...", flush=True)
            try:
                if bust_cache and base_instruction:
                    prog = build_program(instruction=base_instruction + f"\n\n[Eval: {uuid.uuid4().hex[:8]}]", tool_names=None)
                else:
                    prog = program
                pred = prog(document_content=doc, user_question=question)
                final = getattr(pred, "final_document", "") or ""
                correct, missing, found_reject = _correctness_breakdown(ex, final)
                tokens = _get_tokens_from_pred(pred, debug_usage=debug_usage)
                penalty = TOKEN_PENALTY_LAMBDA * (tokens / 1000.0)
                score = max(0.0, correct - penalty)
                scores.append(score)
                token_counts.append(tokens)
                if missing:
                    print(f"  expected_contains MISSING: {missing}")
                else:
                    print(f"  expected_contains: ok")
                if found_reject:
                    print(f"  reject_contains FOUND (bad): {found_reject}")
                else:
                    print(f"  reject_contains: ok")
                print(f"  correctness={correct:.2f}  tokens={tokens}  score={score:.3f}")
                snippet = (final[:300] + "...") if len(final) > 300 else final
                print(f"  doc snippet: {snippet!r}")
            except Exception as e:
                print(f"  ERROR: {e}")
                scores.append(0.0)
                token_counts.append(0)
            print()
    return scores, token_counts


def _correctness_breakdown(example, final_document: str) -> tuple[float, list[str], list[str]]:
    """Return (score, list of missing expected, list of bad reject found)."""
    expected = getattr(example, "expected_contains", []) or []
    reject = getattr(example, "reject_contains", []) or []
    score = 1.0
    missing = []
    for s in expected:
        if s not in (final_document or ""):
            score -= 0.2
            missing.append(s)
    found_reject = []
    for s in reject:
        if s in (final_document or ""):
            score -= 0.3
            found_reject.append(s)
    return max(0.0, min(1.0, score)), missing, found_reject


def main():
    p = argparse.ArgumentParser(description="Eval Writer assistant on dataset (no MIPROv2).")
    p.add_argument("--model", "-m", default=os.environ.get("OPENAI_MODEL", DEFAULT_MODEL))
    p.add_argument("--api-base", default=os.environ.get("OPENAI_API_BASE", DEFAULT_API_BASE))
    p.add_argument("--api-key", "-k", default=os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY", ""))
    p.add_argument("--example", "-e", metavar="TASK_ID", help="Run only this task_id (e.g. table_from_mess).")
    p.add_argument("-n", type=int, default=None, help="Run only first N examples.")
    p.add_argument("--verbose", "-v", action="store_true", help="Print every tool call as it runs.")
    p.add_argument("--compare-with", metavar="JSON", help="Compare: run with current prompt, then with prompt from JSON file, report both scores.")
    p.add_argument("--debug-usage", action="store_true", help="Print raw get_lm_usage() when tokens=0 to debug token extraction.")
    p.add_argument("--no-bust-cache", action="store_true", help="Disable cache-busting (default: enabled for accurate token counts with OpenRouter).")
    args = p.parse_args()

    api_key = args.api_key
    api_base = args.api_base
    model = args.model
    if "openrouter" in api_base.lower() and not model.startswith("openrouter/"):
        model = "openrouter/" + model

    if not api_key and "openrouter" in api_base.lower():
        print("Warning: OPENROUTER_API_KEY (or OPENAI_API_KEY) not set.", file=sys.stderr)

    print(f"Model: {model} @ {api_base}\n")
    lm = dspy.LM(model=model, api_key=api_key, api_base=api_base, model_type="chat")
    dspy.configure(lm=lm)

    examples = to_dspy_examples(ALL_EXAMPLES, with_inputs=True)
    if args.example:
        examples = [ex for ex in examples if getattr(ex, "task_id", "") == args.example]
        if not examples:
            print(f"No example with task_id={args.example!r}. Valid: {[getattr(e, 'task_id', '') for e in to_dspy_examples(ALL_EXAMPLES)]}")
            return 1
    if args.n is not None:
        examples = examples[: args.n]

    tools_mock.VERBOSE = args.verbose
    n = len(examples)
    print(f"Running {n} example(s). Each can take 15–60+ seconds (multiple API calls). Total often 2–10 min.\n")
    sys.stdout.flush()

    if args.compare_with:
        # Compare mode: run both prompts and report
        compare_path = Path(args.compare_with)
        if not compare_path.is_absolute():
            compare_path = SCRIPT_DIR / compare_path
        if not compare_path.exists():
            print(f"Error: --compare-with file not found: {compare_path}", file=sys.stderr)
            return 1
        try:
            alt_instruction = _load_prompt_from_json(compare_path)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        print("=" * 60)
        print("PROMPT A: Current (from core/constants.py)")
        print("=" * 60)
        program_a = build_program(instruction=None, tool_names=None)
        scores_a, tokens_a = _run_eval(program_a, examples, args.verbose, args.debug_usage, bust_cache=not args.no_bust_cache)
        avg_a = sum(scores_a) / len(scores_a) if scores_a else 0
        total_tokens_a = sum(tokens_a)

        print("=" * 60)
        print(f"PROMPT B: From {compare_path.name}")
        print("=" * 60)
        program_b = build_program(instruction=alt_instruction, tool_names=None)
        scores_b, tokens_b = _run_eval(program_b, examples, args.verbose, args.debug_usage, bust_cache=not args.no_bust_cache)
        avg_b = sum(scores_b) / len(scores_b) if scores_b else 0
        total_tokens_b = sum(tokens_b)

        print("=" * 60)
        print("COMPARISON")
        print("=" * 60)
        print(f"  Current (git):  avg score = {avg_a:.3f}  total tokens = {total_tokens_a}")
        print(f"  Optimized:      avg score = {avg_b:.3f}  total tokens = {total_tokens_b}")
        diff = avg_b - avg_a
        if diff > 0:
            print(f"  -> Optimized is {diff:.3f} better (higher score)")
        elif diff < 0:
            print(f"  -> Current is {-diff:.3f} better (higher score)")
        else:
            print("  -> Tie")
        return 0

    program = build_program(instruction=None, tool_names=None)
    scores, _ = _run_eval(program, examples, args.verbose, args.debug_usage, bust_cache=not args.no_bust_cache)
    if scores:
        print(f"Average score: {sum(scores)/len(scores):.3f} ({len(scores)} examples)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
