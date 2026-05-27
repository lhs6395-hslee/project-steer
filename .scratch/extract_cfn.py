#!/usr/bin/env python3
"""Extract the CFN template body from a JSON-wrapped string back to YAML."""
import json
import sys
from pathlib import Path

src = Path("/Users/toule/Documents/Works/2026/교육용자료/agenticai/workshop-extract/cfn/cfn-template.json")
yaml_dst = src.with_name("cfn-template.yaml")
json_dst = src

raw = src.read_text(encoding="utf-8")
data = json.loads(raw)
if isinstance(data, str):
    yaml_text = data
    yaml_dst.write_text(yaml_text, encoding="utf-8")
    try:
        import yaml  # type: ignore
        parsed = yaml.safe_load(yaml_text)
        json_dst.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Saved YAML: {yaml_dst} ({len(yaml_text)} chars)")
        print(f"Saved JSON: {json_dst} parsed structure")
    except ImportError:
        print(f"Saved YAML: {yaml_dst} ({len(yaml_text)} chars)")
        print("PyYAML not installed - skipping JSON parse")
elif isinstance(data, dict):
    json_dst.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Already JSON dict, saved: {json_dst}")
else:
    print(f"Unexpected type: {type(data)}", file=sys.stderr)
    sys.exit(1)
