#!/usr/bin/env python3
# Parallel Executor — Dependency-Aware Step Execution
#
# Usage:
#   python3 scripts/agents/parallel_executor.sh <sprint_contract.json> <module> <run_dir>
#
# Features:
# - Analyzes dependency graph from Sprint_Contract
# - Executes independent steps in parallel
# - Waits for dependencies before starting dependent steps
# - Aggregates results from all parallel executions

import json
import sys
import os
import subprocess
from collections import defaultdict
from pathlib import Path

SPRINT_CONTRACT="${1:?Usage: parallel_executor.sh <sprint_contract.json> <module> <run_dir>}"
MODULE="${2:?}"
RUN_DIR="${3:?}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "  [Parallel Executor] Analyzing dependency graph..."

# Extract steps from Sprint_Contract
STEPS=$(python3 - "$SPRINT_CONTRACT" <<'PYTHON'
import json
import sys

with open(sys.argv[1], 'r') as f:
    contract = json.load(f)

steps = contract.get('steps', [])
for step in steps:
    step_id = step['id']
    deps = step.get('dependencies', [])
    print(f"{step_id}:{','.join(map(str, deps))}")
PYTHON
)

# Build dependency levels
declare -A STEP_LEVEL
declare -A STEP_DEPS
MAX_LEVEL=0

while IFS=: read -r step_id deps; do
    STEP_DEPS[$step_id]="$deps"

    # Calculate level (max dependency level + 1)
    level=0
    if [ -n "$deps" ]; then
        IFS=',' read -ra dep_array <<< "$deps"
        for dep in "${dep_array[@]}"; do
            dep_level=${STEP_LEVEL[$dep]:-0}
            if [ $dep_level -ge $level ]; then
                level=$((dep_level + 1))
            fi
        done
    fi

    STEP_LEVEL[$step_id]=$level
    if [ $level -gt $MAX_LEVEL ]; then
        MAX_LEVEL=$level
    fi
done <<< "$STEPS"

echo "  [Parallel Executor] Found $((MAX_LEVEL + 1)) dependency levels"

# Execute steps level by level
for level in $(seq 0 $MAX_LEVEL); do
    echo "  [Parallel Executor] Level $level: Starting parallel execution..."

    pids=()
    step_ids=()

    # Find all steps at this level
    for step_id in "${!STEP_LEVEL[@]}"; do
        if [ "${STEP_LEVEL[$step_id]}" -eq "$level" ]; then
            step_ids+=("$step_id")

            # Create step input
            STEP_INPUT="$RUN_DIR/step_${step_id}_input.txt"
            python3 - "$SPRINT_CONTRACT" "$step_id" "$RUN_DIR" > "$STEP_INPUT" <<'PYTHON'
import json
import sys

with open(sys.argv[1], 'r') as f:
    contract = json.load(f)

step_id = int(sys.argv[2])
run_dir = sys.argv[3]

# Find step
step = next((s for s in contract['steps'] if s['id'] == step_id), None)
if not step:
    sys.exit(1)

# Build input
print("TASK:", contract['task'])
print("MODULE:", contract['module'])
print("")
print("STEP ID:", step_id)
print("ACTION:", step['action'])
print("")
print("ACCEPTANCE CRITERIA:")
for criterion in step.get('acceptance_criteria', []):
    print(f"  - {criterion}")
print("")
print("CONSTRAINTS:")
for constraint in contract.get('constraints', []):
    print(f"  - {constraint}")
print("")
print("Execute this step and provide JSON output following schemas/executor_output.schema.json")
PYTHON

            # Execute step in background
            STEP_OUTPUT="$RUN_DIR/step_${step_id}_output.json"
            bash "$SCRIPT_DIR/call_agent.sh" executor "$STEP_INPUT" "$STEP_OUTPUT" "$MODULE" &
            pids+=($!)
        fi
    done

    # Wait for all steps at this level to complete
    echo "  [Parallel Executor] Level $level: Waiting for ${#pids[@]} steps..."
    for pid in "${pids[@]}"; do
        wait "$pid" || echo "  WARNING: Step failed with pid $pid"
    done

    echo "  [Parallel Executor] Level $level: Completed ${#step_ids[@]} steps"
done

# Aggregate results into executor_output.schema.json format
echo "  [Parallel Executor] Aggregating results..."
AGGREGATED_OUTPUT="$RUN_DIR/aggregated_output.json"

python3 - "$RUN_DIR" "$AGGREGATED_OUTPUT" "$SPRINT_CONTRACT" <<'PYTHON'
import json
import sys
import os

run_dir = sys.argv[1]
output_file = sys.argv[2]
contract_file = sys.argv[3]

# Load Sprint_Contract
with open(contract_file, 'r') as f:
    contract = json.load(f)

# Collect all step outputs
step_results = []
all_constraint_compliance = []
all_outputs = []
all_artifacts = []
failed_steps = []

for file in sorted(os.listdir(run_dir)):
    if file.startswith('step_') and file.endswith('_output.json'):
        step_id = int(file.split('_')[1])
        filepath = os.path.join(run_dir, file)
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                step_results.append({
                    'step_id': step_id,
                    'status': 'success',
                    'output': data
                })

                # Aggregate constraint_compliance
                if 'constraint_compliance' in data:
                    all_constraint_compliance.extend(data['constraint_compliance'])

                # Aggregate outputs
                if 'outputs' in data:
                    all_outputs.extend(data['outputs'])

                # Aggregate artifacts
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

# Write aggregated output in executor_output.schema.json format
with open(output_file, 'w') as f:
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
PYTHON

echo "  [Parallel Executor] Done. Output: $AGGREGATED_OUTPUT"
