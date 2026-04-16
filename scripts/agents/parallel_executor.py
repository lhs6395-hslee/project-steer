#!/usr/bin/env python3
"""
Parallel Executor — Dependency-Aware Step Execution

Usage:
    python3 scripts/agents/parallel_executor.py <sprint_contract.json> <module> <run_dir>

Features:
- Analyzes dependency graph from Sprint_Contract
- Executes independent steps in parallel
- Waits for dependencies before starting dependent steps
- Aggregates results from all parallel executions
"""

import json
import sys
import os
import re
import subprocess
from collections import defaultdict


def step_label(step: dict) -> str:
    """Sprint Contract step에서 사용자 친화적 레이블 추출.
    예: '7p(L02) 흐름도 겹침 수정', '10p(L05) subtitle 잘림 수정'
    """
    action = step.get('action', '') or step.get('description', '')
    # 페이지/레이아웃 패턴 추출: Slide N, L0N, page N 등
    page_match = re.search(r'[Ss]lide\s*(\d+)', action)
    layout_match = re.search(r'(L0[1-9]|L[1-9][0-9])', action)
    # 작업 키워드 추출
    keyword = ''
    for kw, label in [
        ('recon', '전체 슬라이드 분석'),
        ('font', '폰트 수정'),
        ('subtitle', 'subtitle 수정'),
        ('icon', '아이콘 추가'),
        ('merge', '병합 및 저장'),
        ('save', '저장'),
        ('fix', '수정'),
        ('overlap', '겹침 수정'),
    ]:
        if kw in action.lower():
            keyword = label
            break
    if not keyword:
        keyword = action[:30].strip()

    parts = []
    if page_match:
        parts.append(f"{page_match.group(1)}p")
    if layout_match:
        parts.append(f"({layout_match.group(1)})")
    parts.append(keyword)
    return ' '.join(parts) if parts else f"Step {step.get('id', '?')}"
from pathlib import Path
import time

def load_sprint_contract(filepath):
    """Load Sprint_Contract JSON"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def validate_dag(steps):
    """Validate sprint_contract steps form a valid DAG (no cycles). (#17 audit fix)"""
    step_ids = {s['id'] for s in steps}
    adj = {s['id']: s.get('dependencies', []) for s in steps}

    visited = set()
    rec_stack = set()

    def has_cycle(node):
        visited.add(node)
        rec_stack.add(node)
        for dep in adj.get(node, []):
            if dep not in step_ids:
                print(f"  WARNING: Step {node} depends on unknown step {dep}", file=sys.stderr)
                continue
            if dep not in visited:
                if has_cycle(dep):
                    return True
            elif dep in rec_stack:
                print(f"  ERROR: Circular dependency detected: {node} → {dep}", file=sys.stderr)
                return True
        rec_stack.discard(node)
        return False

    for s in steps:
        if s['id'] not in visited:
            if has_cycle(s['id']):
                return False
    return True


def analyze_dependencies(steps):
    """Build dependency levels for parallel execution"""
    step_levels = {}
    step_deps = {}

    for step in steps:
        step_id = step['id']
        deps = step.get('dependencies', [])
        step_deps[step_id] = deps

        # Calculate level (max dependency level + 1)
        if not deps:
            step_levels[step_id] = 0
        else:
            max_dep_level = max(step_levels.get(dep, 0) for dep in deps)
            step_levels[step_id] = max_dep_level + 1

    # Group steps by level
    levels = defaultdict(list)
    for step_id, level in step_levels.items():
        levels[level].append(step_id)

    return levels, step_deps

def create_step_input(contract, step_id, run_dir, completed_outputs=None):
    """
    Create minimal input for a specific step.

    원칙: 각 Executor는 자기 step에 필요한 정보만 받는다.
    - 전체 Sprint_Contract 전달 금지 (context 낭비)
    - 전체 SKILL.md는 call_agent.sh가 system prompt로 주입 (여기선 제외)
    - 의존 step output은 핵심 요약만 전달 (전체 JSON 금지)
    """
    step = next((s for s in contract['steps'] if s['id'] == step_id), None)
    if not step:
        return None

    input_path = os.path.join(run_dir, f"step_{step_id}_input.txt")

    with open(input_path, 'w', encoding='utf-8') as f:
        # 태스크 컨텍스트 (최소)
        f.write(f"TASK: {contract['task']}\n")
        f.write(f"MODULE: {contract['module']}\n\n")

        # 이 step의 정보만
        f.write(f"STEP {step_id}: {step['action']}\n\n")

        if step.get('target_slide_index') is not None:
            f.write(f"TARGET SLIDE INDEX: {step['target_slide_index']} (0-based)\n\n")

        f.write("ACCEPTANCE CRITERIA:\n")
        for criterion in step.get('acceptance_criteria', []):
            f.write(f"  - {criterion}\n")

        # 이 step에 직접 관련된 constraints만 (step 레벨 > contract 레벨)
        step_constraints = step.get('constraints', [])
        if step_constraints:
            f.write("\nCONSTRAINTS (this step):\n")
            for c in step_constraints:
                f.write(f"  - {c}\n")

        # 의존 step output: 핵심 요약만 (전체 JSON 금지)
        deps = step.get('dependencies', [])
        if deps and completed_outputs:
            f.write("\nDEPENDENCY SUMMARY:\n")
            for dep_id in deps:
                dep_out_path = os.path.join(run_dir, f"step_{dep_id}_output.json")
                if os.path.exists(dep_out_path):
                    try:
                        with open(dep_out_path, 'r', encoding='utf-8') as dep_f:
                            dep_data = json.load(dep_f)
                        # 전체 JSON 대신 outputs 필드의 핵심 결과만 전달
                        outputs = dep_data.get('outputs', [])
                        status = dep_data.get('status', 'unknown')
                        artifacts = dep_data.get('artifacts', [])
                        issues = []
                        for out in outputs:
                            if out.get('status') == 'failed':
                                issues.append(out.get('action', ''))
                            # recon step: result 필드에 실측값 요약 있으면 포함
                            result = out.get('result', '')
                            if result and len(str(result)) < 1000:
                                issues.append(str(result))
                        f.write(f"  Step {dep_id}: status={status}")
                        if artifacts:
                            f.write(f", artifacts={artifacts}")
                        if issues:
                            f.write(f"\n  Key findings: {'; '.join(issues[:3])}")
                        f.write("\n")
                    except Exception:
                        f.write(f"  Step {dep_id}: (unreadable)\n")

        f.write("\nExecute this step. Output JSON matching schemas/executor_output.schema.json.\n")
        f.write("MCP tools (mcp__pptx__*) for new content. python-pptx utils only for text replace/delete/reorder.\n")
        f.write("prs.save() FORBIDDEN — use mcp__pptx__save_presentation.\n")

    return input_path

def execute_step(step_id, input_path, run_dir, module, script_dir):
    """Execute a single step using call_agent.sh"""
    output_path = os.path.join(run_dir, f"step_{step_id}_output.json")
    call_agent_path = os.path.join(script_dir, "call_agent.sh")

    cmd = ["bash", call_agent_path, "executor", input_path, output_path, module]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
        return {
            'step_id': step_id,
            'status': 'success' if result.returncode == 0 else 'failed',
            'returncode': result.returncode,
            'output_path': output_path
        }
    except subprocess.TimeoutExpired:
        return {
            'step_id': step_id,
            'status': 'timeout',
            'output_path': output_path
        }
    except Exception as e:
        return {
            'step_id': step_id,
            'status': 'error',
            'error': str(e),
            'output_path': output_path
        }

def aggregate_results(run_dir, contract_file, output_file):
    """Aggregate all step outputs into executor_output.schema.json format"""
    with open(contract_file, 'r', encoding='utf-8') as f:
        contract = json.load(f)

    step_results = []
    # constraint_compliance는 executor_output.schema.json 기준 object
    # {constraints_checked: [...], violations: [...]}
    # 여러 step의 결과를 하나의 object로 병합
    all_constraints_checked = []
    all_violations = []
    all_outputs = []
    all_artifacts = []
    failed_steps = []

    # Collect all step outputs — use regex to avoid IndexError (#4 audit fix)
    STEP_PATTERN = re.compile(r'^step_(\d+)_output\.json$')
    for file in sorted(os.listdir(run_dir)):
        m = STEP_PATTERN.match(file)
        if not m:
            continue
        step_id = int(m.group(1))
        filepath = os.path.join(run_dir, file)

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            step_results.append({
                'step_id': step_id,
                'status': 'success',
                'output': data
            })

            # Aggregate constraint_compliance — schema requires object, not list
            cc = data.get('constraint_compliance', {})
            if isinstance(cc, dict):
                all_constraints_checked.extend(cc.get('constraints_checked', []))
                all_violations.extend(cc.get('violations', []))
            elif isinstance(cc, list):
                # 하위 호환: 일부 executor가 list를 반환할 경우 checked로 처리
                all_constraints_checked.extend(cc)

            if 'outputs' in data:
                all_outputs.extend(data['outputs'])
            if 'artifacts' in data:
                all_artifacts.extend(data['artifacts'])

        except Exception as e:
            step_results.append({
                'step_id': step_id,
                'status': 'failed',
                'error': f'Invalid JSON: {str(e)}'
            })
            failed_steps.append(step_id)

    # Determine overall status — schema enum: "completed" | "partial" | "failed"
    if len(failed_steps) == 0:
        overall_status = 'completed'
    elif len(failed_steps) < len(step_results):
        overall_status = 'partial'
    else:
        overall_status = 'failed'

    # Write aggregated output — matches executor_output.schema.json
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'constraint_compliance': {
                'constraints_checked': all_constraints_checked,
                'violations': all_violations
            },
            'outputs': all_outputs,
            'status': overall_status,
            'artifacts': all_artifacts,
            'parallel_execution': {
                'total_steps': len(step_results),
                'successful_steps': len(step_results) - len(failed_steps),
                'failed_steps': failed_steps,
                'step_details': step_results
            }
        }, f, indent=2, ensure_ascii=False)

    print(f"Aggregated {len(step_results)} step results ({len(failed_steps)} failed)")

def load_approved_steps(run_dir: str, attempt: int) -> set:
    """이전 attempt에서 approved된 step ID 집합 반환 — 재실행 스킵 대상"""
    approved = set()
    if attempt <= 1:
        return approved
    # 직전 attempt의 per-step verdict 파일 읽기
    prev_attempt = attempt - 1
    import glob as _glob
    pattern = os.path.join(run_dir, f"review_{prev_attempt}_step_*_verdict.json")
    for verdict_file in _glob.glob(pattern):
        try:
            with open(verdict_file) as f:
                data = json.load(f)
            verdict = data.get('verdict', 'needs_revision')
            score = float(data.get('score', 0))
            if verdict in ('approved', 'pass') and score >= 0.85:
                # step ID 추출: review_N_step_X_verdict.json
                basename = os.path.basename(verdict_file)
                parts = basename.split('_')
                # parts: ['review', N, 'step', X, 'verdict.json']
                step_id_str = parts[3] if len(parts) > 3 else None
                if step_id_str and step_id_str.isdigit():
                    approved.add(int(step_id_str))
        except Exception:
            pass
    if approved:
        print(f"  [Parallel Executor] Skipping approved steps from attempt {prev_attempt}: {sorted(approved)}", flush=True)
    return approved


def main():
    if len(sys.argv) < 4:
        print("Usage: parallel_executor.py <sprint_contract.json> <module> <run_dir> [attempt]")
        sys.exit(1)

    contract_file = sys.argv[1]
    module = sys.argv[2]
    run_dir = sys.argv[3]
    attempt = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    script_dir = os.path.dirname(os.path.abspath(__file__))

    print("  [Parallel Executor] Analyzing dependency graph...")

    # Load contract
    contract = load_sprint_contract(contract_file)
    steps = contract.get('steps', [])

    # Validate DAG before execution (#17 audit fix: cycle detection)
    if not validate_dag(steps):
        print("  ERROR: Sprint_Contract contains circular dependencies — aborting", file=sys.stderr)
        sys.exit(1)

    # Load approved steps from previous attempt — skip re-execution
    approved_steps = load_approved_steps(run_dir, attempt)

    # Analyze dependencies
    levels, step_deps = analyze_dependencies(steps)
    max_level = max(levels.keys()) if levels else 0

    print(f"  [Parallel Executor] Found {max_level + 1} dependency levels")

    # Track completed step IDs for dependency context
    # Pre-populate with approved steps — their outputs already exist
    completed_outputs = set(approved_steps)

    # Execute steps level by level
    for level in range(max_level + 1):
        level_steps = levels.get(level, [])
        if not level_steps:
            continue

        # Skip approved steps — reuse previous output
        skip = [s for s in level_steps if s in approved_steps]
        run = [s for s in level_steps if s not in approved_steps]
        for s in skip:
            print(f"  [Parallel Executor] ↩ Step {s} skipped (approved in previous attempt)", flush=True)

        if not run:
            print(f"  [Parallel Executor] Level {level}: all steps already approved, skipping", flush=True)
            continue

        print(f"  [Parallel Executor] Level {level}: {len(run)} step(s) to execute ({len(skip)} skipped)", flush=True)

        # Create inputs for all steps at this level (include dependency outputs)
        inputs = {}
        for step_id in run:
            input_path = create_step_input(contract, step_id, run_dir, completed_outputs)
            if input_path:
                inputs[step_id] = input_path

        # Execute all steps in parallel using subprocess
        # Adaptive max-turns based on step complexity (sprint_contract estimated_complexity)
        # MCP tool use + --json-schema 조합: tool turns + structured output 생성 turns 필요
        COMPLEXITY_TURNS = {"low": 40, "medium": 80, "high": 120}
        COMPLEXITY_TIMEOUT = {"low": 300, "medium": 600, "high": 900}

        # Write pipeline status file — 각 step 시작/완료를 파일로 기록
        status_file = os.path.join(run_dir, "pipeline_status.json")

        def write_status(step_id, status, elapsed=None):
            try:
                import json as _json
                existing = {}
                if os.path.exists(status_file):
                    with open(status_file) as f:
                        existing = _json.load(f)
                existing[str(step_id)] = {"status": status, "elapsed": elapsed}
                with open(status_file + ".tmp", "w") as f:
                    _json.dump(existing, f, indent=2)
                os.replace(status_file + ".tmp", status_file)
            except Exception:
                pass

        def run_one_step(step_id, input_path):
            output_path = os.path.join(run_dir, f"step_{step_id}_output.json")
            call_agent_path = os.path.join(script_dir, "call_agent.sh")
            step = next((s for s in contract['steps'] if s['id'] == step_id), {})
            complexity = step.get('estimated_complexity', 'medium')
            max_turns = str(COMPLEXITY_TURNS.get(complexity, 80))
            timeout_sec = COMPLEXITY_TIMEOUT.get(complexity, 600)

            env = os.environ.copy()
            env['EXECUTOR_MAX_TURNS'] = max_turns
            env['EXECUTOR_TIMEOUT'] = str(timeout_sec)

            label = step_label(step)
            write_status(step_id, "running")
            print(f"  [Executor 시작] {label} ...", flush=True)
            t0 = _time.time()
            try:
                proc = subprocess.Popen(
                    ["bash", call_agent_path, "executor", input_path, output_path, module],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                )
                stdout, stderr = proc.communicate(timeout=timeout_sec + 60)
                elapsed = round(_time.time() - t0)
                if proc.returncode == 0:
                    write_status(step_id, "done", elapsed)
                    print(f"  ✅ [Executor 완료] {label} ({elapsed}s)", flush=True)
                    return step_id, True, stderr
                else:
                    write_status(step_id, "failed", elapsed)
                    print(f"  ❌ [Executor 실패] {label} (exit={proc.returncode}, {elapsed}s)", flush=True)
                    if stderr:
                        print(f"    오류: {stderr.decode(errors='replace')[-200:]}", flush=True)
                    return step_id, False, stderr
            except subprocess.TimeoutExpired:
                proc.kill()
                elapsed = round(_time.time() - t0)
                write_status(step_id, "timeout", elapsed)
                print(f"  ❌ [Executor 시간초과] {label} ({timeout_sec}s 초과 — 강제종료)", flush=True)
                return step_id, False, b""

        from concurrent.futures import ThreadPoolExecutor as _TPE, as_completed as _ac
        import time as _time

        print(f"  [Parallel Executor] Level {level}: Launching {len(inputs)} steps in parallel...", flush=True)
        start = _time.time()
        with _TPE(max_workers=len(inputs)) as pool:
            futures = {pool.submit(run_one_step, sid, ipath): sid for sid, ipath in inputs.items()}
            for future in _ac(futures):
                step_id, success, _ = future.result()
                if success:
                    completed_outputs.add(step_id)

        print(f"  [Parallel Executor] Level {level}: All steps done ({round(_time.time()-start)}s)", flush=True)

    # Aggregate results
    print("  [Parallel Executor] Aggregating results...")
    output_file = os.path.join(run_dir, "aggregated_output.json")
    aggregate_results(run_dir, contract_file, output_file)

    print(f"  [Parallel Executor] Done. Output: {output_file}")

if __name__ == '__main__':
    main()
