#!/usr/bin/env python3
"""
Gather detailed slide information using MCP tools output
"""
import json
import subprocess

slides_data = []

# Get info for each slide (0-10 based on presentation info showing 11 slides)
for i in range(11):
    print(f"[INFO] Gathering slide {i}...")
    result = subprocess.run(
        ['python3', '-c', f'''
import sys
sys.path.insert(0, ".")
from mcp_pptx import get_slide_info
result = get_slide_info(slide_index={i}, presentation_id="review_target")
print(result)
'''],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        slides_data.append({
            'index': i,
            'raw_output': result.stdout
        })
    else:
        print(f"[ERROR] Failed to get slide {i}: {result.stderr}")

# Save raw data
with open('results/slides_raw_data.json', 'w') as f:
    json.dump(slides_data, f, indent=2)

print(f"[COMPLETE] Gathered {len(slides_data)} slides")

