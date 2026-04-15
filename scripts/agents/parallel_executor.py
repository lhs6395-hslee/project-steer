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
    Create input file for a specific step.
    Includes outputs of completed dependency steps (minimal context, not full contract).
    공식 근거: subagents.md — each subagent gets focused context for its task only.
    """
    step = next((s for s in contract['steps'] if s['id'] == step_id), None)
    if not step:
        return None

    input_path = os.path.join(run_dir, f"step_{step_id}_input.txt")

    with open(input_path, 'w', encoding='utf-8') as f:
        f.write(f"TASK: {contract['task']}\n")
        f.write(f"MODULE: {contract['module']}\n\n")
        f.write(f"STEP ID: {step_id}\n")
        f.write(f"ACTION: {step['action']}\n\n")
        f.write(f"ACCEPTANCE CRITERIA:\n")
        for criterion in step.get('acceptance_criteria', []):
            f.write(f"  - {criterion}\n")
        f.write(f"\nCONSTRAINTS:\n")
        for constraint in contract.get('constraints', []):
            f.write(f"  - {constraint}\n")

        # Include outputs from dependency steps (context for chained execution)
        deps = step.get('dependencies', [])
        if deps and completed_outputs:
            f.write(f"\nDEPENDENCY OUTPUTS (steps this step depends on):\n")
            for dep_id in deps:
                dep_out_path = os.path.join(run_dir, f"step_{dep_id}_output.json")
                if os.path.exists(dep_out_path):
                    try:
                        with open(dep_out_path, 'r', encoding='utf-8') as dep_f:
                            dep_data = json.load(dep_f)
                        f.write(f"Step {dep_id} output:\n{json.dumps(dep_data, ensure_ascii=False, indent=2)}\n\n")
                    except Exception:
                        f.write(f"Step {dep_id} output: (unreadable)\n")

        f.write(f"\nExecute this step and provide JSON output following schemas/executor_output.schema.json\n")

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
    all_constraint_compliance = []
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

            # Aggregate fields
            if 'constraint_compliance' in data:
                all_constraint_compliance.extend(data['constraint_compliance'])
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

    # Determine overall status
    overall_status = 'success' if len(failed_steps) == 0 else 'partial_success'

    # Write aggregated output
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'constraint_compliance': all_constraint_compliance,
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

def main():
    if len(sys.argv) != 4:
        print("Usage: parallel_executor.py <sprint_contract.json> <module> <run_dir>")
        sys.exit(1)

    contract_file = sys.argv[1]
    module = sys.argv[2]
    run_dir = sys.argv[3]
    script_dir = os.path.dirname(os.path.abspath(__file__))

    print("  [Parallel Executor] Analyzing dependency graph...")

    # Load contract
    contract = load_sprint_contract(contract_file)
    steps = contract.get('steps', [])

    # Validate DAG before execution (#17 audit fix: cycle detection)
    if not validate_dag(steps):
        print("  ERROR: Sprint_Contract contains circular dependencies — aborting", file=sys.stderr)
        sys.exit(1)

    # Analyze dependencies
    levels, step_deps = analyze_dependencies(steps)
    max_level = max(levels.keys()) if levels else 0

    print(f"  [Parallel Executor] Found {max_level + 1} dependency levels")

    # Track completed step IDs for dependency context
    completed_outputs = set()

    # Execute steps level by level
    for level in range(max_level + 1):
        level_steps = levels.get(level, [])
        if not level_steps:
            continue

        print(f"  [Parallel Executor] Level {level}: Starting parallel execution...")
        print(f"  [Parallel Executor] Level {level}: {len(level_steps)} steps to execute")

        # Create inputs for all steps at this level (include dependency outputs)
        inputs = {}
        for step_id in level_steps:
            input_path = create_step_input(contract, step_id, run_dir, completed_outputs)
            if input_path:
                inputs[step_id] = input_path

        # Execute all steps in parallel using subprocess
        # Adaptive max-turns based on step complexity (sprint_contract estimated_complexity)
        # MCP tool use + --json-schema 조합: tool turns + structured output 생성 turns 필요
        COMPLEXITY_TURNS = {"low": 40, "medium": 80, "high": 120}
        COMPLEXITY_TIMEOUT = {"low": 300, "medium": 600, "high": 900}

        processes = {}
        for step_id, input_path in inputs.items():
            output_path = os.path.join(run_dir, f"step_{step_id}_output.json")
            call_agent_path = os.path.join(script_dir, "call_agent.sh")

            # Get complexity from sprint contract step
            step = next((s for s in contract['steps'] if s['id'] == step_id), {})
            complexity = step.get('estimated_complexity', 'medium')
            max_turns = str(COMPLEXITY_TURNS.get(complexity, 20))
            timeout = str(COMPLEXITY_TIMEOUT.get(complexity, 600))

            env = os.environ.copy()
            env['EXECUTOR_MAX_TURNS'] = max_turns
            env['EXECUTOR_TIMEOUT'] = timeout

            proc = subprocess.Popen(
                ["bash", call_agent_path, "executor", input_path, output_path, module],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            processes[step_id] = proc
            print(f"  [Parallel Executor] Step {step_id} started (complexity={complexity}, max_turns={max_turns})")

        # Wait for all processes to complete, track completed for next level
        print(f"  [Parallel Executor] Level {level}: Waiting for {len(processes)} steps...")
        import time as _time
        start = _time.time()
        for step_id, proc in processes.items():
            # Use EXECUTOR_TIMEOUT env (same as call_agent.sh) + buffer (#10 audit fix)
            step_timeout = int(os.environ.get('EXECUTOR_TIMEOUT', '900')) + 60
            try:
                proc.wait(timeout=step_timeout)
                if proc.returncode == 0:
                    completed_outputs.add(step_id)
                    print(f"  [Parallel Executor] ✓ Step {step_id} done ({_time.time()-start:.0f}s)")
                else:
                    print(f"  WARNING: Step {step_id} failed (code {proc.returncode})")
            except subprocess.TimeoutExpired:
                print(f"  WARNING: Step {step_id} timed out after 720s")
                proc.kill()

        print(f"  [Parallel Executor] Level {level}: Completed {len(level_steps)} steps")

    # Aggregate results
    print("  [Parallel Executor] Aggregating results...")
    output_file = os.path.join(run_dir, "aggregated_output.json")
    aggregate_results(run_dir, contract_file, output_file)

    print(f"  [Parallel Executor] Done. Output: {output_file}")

if __name__ == '__main__':
    main()
