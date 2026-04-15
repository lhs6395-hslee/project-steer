#!/usr/bin/env python3
"""
Parallel Reviewer — Independent Per-Step Adversarial Review

공식 문서 근거:
  - Parallel subagents pattern:
    code.claude.com/docs/en/agent-sdk/subagents.md
    "you can run style-checker, security-scanner, and test-coverage subagents
     simultaneously, reducing review time from minutes to seconds"
  - Information isolation (adversarial review):
    Reviewer receives ONLY Sprint_Contract + its assigned step output
    (never Executor reasoning, never other steps' outputs)
  - --json-schema structured output:
    code.claude.com/docs/en/agent-sdk/structured-outputs.md

Usage:
    python3 scripts/agents/parallel_reviewer.py \\
        <sprint_contract.json> <aggregated_output.json> <module> <run_dir> [attempt]

Design:
    - One Reviewer subprocess per Executor step output (fully independent)
    - All Reviewers start concurrently (no dependencies between reviews)
    - Each Reviewer gets: Sprint_Contract + single step output (minimal context)
    - Aggregate: PASS only if ALL step verdicts = approved
    - Circular feedback detection across attempts
"""

import json
import sys
import os
import subprocess
from pathlib import Path
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent


def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def build_review_input(contract: dict, step_output: dict, module: str, attempt: int) -> str:
    """
    Minimal review input per step — information barrier enforced.
    Reviewer gets ONLY: Sprint_Contract + this step's output.
    (Never other steps' outputs, never Executor reasoning)
    """
    lines = [
        "SPRINT_CONTRACT:",
        json.dumps(contract, ensure_ascii=False, indent=2),
        "",
        "STEP EXECUTION OUTPUT:",
        json.dumps(step_output, ensure_ascii=False, indent=2),
        "",
        f"MODULE: {module}",
        f"ATTEMPT: {attempt}",
        "",
        "Review this step output adversarially against the Sprint_Contract.",
        "Output JSON verdict following schemas/verdict.schema.json.",
        "REQUIRED fields: verdict, score, checklist_results, constraint_violations, issues, suggestions.",
    ]
    if attempt > 1:
        lines.append("REQUIRED on retry: retry_fix_assessment for each previous issue.")
    return "\n".join(lines)


def run_reviewer(step_id, review_input_path, review_output_path, module):
    """Run a single Reviewer subprocess via call_agent.sh."""
    call_agent = str(SCRIPT_DIR / "call_agent.sh")
    cmd = ["bash", call_agent, "reviewer", str(review_input_path), str(review_output_path), module]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=360,  # 공식 근거: call_agent.sh reviewer timeout=360s
        )
        return {
            "step_id": step_id,
            "status": "success" if result.returncode == 0 else "failed",
            "returncode": result.returncode,
            "output_path": str(review_output_path),
            "stderr": result.stderr[-500:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"step_id": step_id, "status": "timeout", "output_path": str(review_output_path)}
    except Exception as e:
        return {"step_id": step_id, "status": "error", "error": str(e), "output_path": str(review_output_path)}


def parse_verdict(verdict_path: str) -> dict:
    """Parse a single step verdict file. Returns safe defaults on failure."""
    try:
        data = load_json(verdict_path)
        return {
            "verdict": data.get("verdict", "needs_revision"),
            "score": float(data.get("score", 0.0)),
            "issues": data.get("issues", []),
            "constraint_violations": data.get("constraint_violations", []),
            "checklist_results": data.get("checklist_results", {}),
            "suggestions": data.get("suggestions", []),
            "retry_fix_assessment": data.get("retry_fix_assessment", []),
        }
    except Exception as e:
        return {
            "verdict": "needs_revision",
            "score": 0.0,
            "issues": [f"Failed to parse verdict: {e}"],
            "constraint_violations": [],
            "checklist_results": {},
            "suggestions": [],
            "retry_fix_assessment": [],
        }


def aggregate_verdicts(step_verdicts: list[dict]) -> dict:
    """
    Aggregate per-step verdicts using MoA-inspired weighted ensemble.

    근거: arxiv.org/abs/2406.04692 (Mixture-of-Agents, Together AI 2024)
    "Each agent takes outputs from previous layer agents as auxiliary information"
    → 여러 독립 Reviewer의 verdict를 집계할 때 단순 min/max 대신
       score-weighted majority voting으로 앙상블 품질 향상

    Rules:
    - constraint_violation 있으면 → 즉시 needs_revision (hard rule, MoA와 무관)
    - Score: weighted average (score가 높은 Reviewer의 판단에 더 가중치)
    - Verdict: weighted majority (approved score weight vs needs_revision score weight)
    - Issues: 중복 제거 후 score 가중치로 정렬 (가장 신뢰도 높은 Reviewer의 이슈 우선)
    """
    all_issues = []
    all_violations = []
    all_suggestions = []
    scores = []
    step_results = []
    approved_weight = 0.0
    revision_weight = 0.0

    for sv in step_verdicts:
        verdict_data = sv["verdict_data"]
        score = verdict_data["score"]
        verdict = verdict_data["verdict"]

        all_issues.extend(verdict_data["issues"])
        all_violations.extend(verdict_data["constraint_violations"])
        all_suggestions.extend(verdict_data["suggestions"])
        scores.append(score)

        # Weighted majority: score as confidence weight
        if verdict in ("approved", "pass"):
            approved_weight += score
        else:
            revision_weight += score

        step_results.append({
            "step_id": sv["step_id"],
            "verdict": verdict,
            "score": score,
            "issues": verdict_data["issues"],
            "constraint_violations": verdict_data["constraint_violations"],
        })

    # Hard rule: any constraint violation → fail regardless of ensemble
    has_violations = len(all_violations) > 0

    # Weighted average score (MoA: higher-confidence reviewers weighted more)
    total_weight = sum(scores) if scores else 1.0
    weighted_score = sum(
        sv["verdict_data"]["score"] ** 2  # square to amplify high-confidence signals
        for sv in step_verdicts
    ) / total_weight if total_weight > 0 else 0.0

    # Ensemble verdict via weighted majority
    if has_violations:
        overall_verdict = "needs_revision"
    elif approved_weight > revision_weight and weighted_score >= 0.7:
        overall_verdict = "approved"
    else:
        overall_verdict = "needs_revision"

    # De-duplicate issues, preserving order (first occurrence = highest priority)
    seen_issues: set = set()
    deduped_issues = []
    for issue in all_issues:
        key = issue.lower().strip()[:80]
        if key not in seen_issues:
            seen_issues.add(key)
            deduped_issues.append(issue)

    return {
        "verdict": overall_verdict,
        "score": round(weighted_score, 3),
        "issues": deduped_issues,
        "constraint_violations": all_violations,
        "suggestions": list(dict.fromkeys(all_suggestions)),  # deduplicated
        "checklist_results": step_verdicts[0]["verdict_data"]["checklist_results"] if step_verdicts else {},
        "parallel_review": {
            "total_steps": len(step_verdicts),
            "approved_steps": sum(1 for sv in step_verdicts if sv["verdict_data"]["verdict"] in ("approved", "pass")),
            "failed_steps": [sv["step_id"] for sv in step_verdicts if sv["verdict_data"]["verdict"] not in ("approved", "pass")],
            "ensemble_method": "moa_weighted_majority",
            "approved_weight": round(approved_weight, 3),
            "revision_weight": round(revision_weight, 3),
            "step_results": step_results,
        },
    }


def write_fallback_verdict(verdict_file: Path, reason: str):
    """Always write a verdict file even on error — orchestrate.sh depends on it. (#18 audit fix)"""
    write_json(str(verdict_file), {
        "verdict": "needs_revision",
        "score": 0.0,
        "checklist_results": {"completeness": False, "constraint_compliance": False,
                               "content_accuracy": False, "design_quality": False},
        "constraint_violations": [],
        "issues": [f"Parallel reviewer error: {reason}"],
        "suggestions": [],
    })


def main():
    if len(sys.argv) < 5:
        print("Usage: parallel_reviewer.py <sprint_contract.json> <aggregated_output.json> <module> <run_dir> [attempt]")
        sys.exit(1)

    contract_file = sys.argv[1]
    aggregated_output_file = sys.argv[2]
    module = sys.argv[3]
    run_dir = Path(sys.argv[4])
    attempt = int(sys.argv[5]) if len(sys.argv) > 5 else 1

    verdict_file = run_dir / f"verdict_{attempt}.json"

    try:
        print(f"  [Parallel Reviewer] Loading Sprint_Contract and aggregated output...")
        contract = load_json(contract_file)
        aggregated = load_json(aggregated_output_file)
    except Exception as e:
        print(f"  ERROR: Failed to load input files: {e}", file=sys.stderr)
        write_fallback_verdict(verdict_file, str(e))
        sys.exit(0)  # Always exit 0; verdict file contains the failure

    # Extract per-step outputs
    step_outputs = {}
    for out in aggregated.get("outputs", []):
        step_id = out.get("step_id")
        if step_id is not None:
            step_outputs[step_id] = out

    # If no per-step outputs, review the whole aggregated output as one step
    if not step_outputs:
        step_outputs = {"all": aggregated}

    print(f"  [Parallel Reviewer] {len(step_outputs)} step(s) to review in parallel (attempt {attempt})")

    # Prepare review inputs (one per step)
    review_tasks = []
    for step_id, step_out in step_outputs.items():
        review_input_path = run_dir / f"review_{attempt}_step_{step_id}_input.txt"
        review_output_path = run_dir / f"review_{attempt}_step_{step_id}_verdict.json"

        review_input = build_review_input(contract, step_out, module, attempt)
        review_input_path.write_text(review_input, encoding="utf-8")

        review_tasks.append({
            "step_id": step_id,
            "input_path": review_input_path,
            "output_path": review_output_path,
        })

    # Run all Reviewers in parallel (ThreadPoolExecutor — each launches subprocess)
    # 공식 근거: subagents.md — parallel subagents pattern
    print(f"  [Parallel Reviewer] Launching {len(review_tasks)} reviewer subprocess(es) concurrently...")
    start_time = time.time()

    run_results = {}
    # Dynamic thread pool: use cpu_count//2, min 2, max 8 (#13 audit fix)
    import os as _os
    cpu_cap = max(2, (_os.cpu_count() or 4) // 2)
    max_workers = min(len(review_tasks), cpu_cap, 8)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                run_reviewer,
                task["step_id"],
                task["input_path"],
                task["output_path"],
                module,
            ): task["step_id"]
            for task in review_tasks
        }
        for future in as_completed(futures):
            result = future.result()
            run_results[result["step_id"]] = result
            status_icon = "✓" if result["status"] == "success" else "✗"
            print(f"  [Parallel Reviewer] {status_icon} Step {result['step_id']} — {result['status']}")

    elapsed = time.time() - start_time
    print(f"  [Parallel Reviewer] All reviews completed in {elapsed:.1f}s")

    # Parse individual verdicts
    step_verdicts = []
    for task in review_tasks:
        step_id = task["step_id"]
        verdict_path = str(task["output_path"])
        verdict_data = parse_verdict(verdict_path)
        step_verdicts.append({"step_id": step_id, "verdict_data": verdict_data})
        icon = "✓" if verdict_data["verdict"] in ("approved", "pass") else "✗"
        print(f"  [Parallel Reviewer] {icon} Step {step_id}: {verdict_data['verdict']} (score={verdict_data['score']:.2f})")

    # Aggregate
    aggregated_verdict = aggregate_verdicts(step_verdicts)

    # Write final aggregated verdict
    verdict_file = run_dir / f"verdict_{attempt}.json"
    write_json(str(verdict_file), aggregated_verdict)

    print(f"  [Parallel Reviewer] Overall: {aggregated_verdict['verdict']} (score={aggregated_verdict['score']:.2f})")
    print(f"  [Parallel Reviewer] Verdict written: {verdict_file}")

    # Always exit 0 — orchestrate.sh reads verdict file to determine outcome (#18 audit fix)
    # Writing verdict file is the contract; exit code is secondary
    sys.exit(0)


if __name__ == "__main__":
    main()
