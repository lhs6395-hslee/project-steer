#!/usr/bin/env python3
"""Verify Lab-9 (Extended Thinking) — Converse with reasoning_config."""
import boto3
import json

REGION = "us-west-2"
MODEL = "us.anthropic.claude-sonnet-4-6"

br = boto3.client("bedrock-runtime", region_name=REGION)

resp = br.converse(
    modelId=MODEL,
    system=[{"text": "You solve multi-step reasoning problems."}],
    messages=[{
        "role": "user",
        "content": [{
            "text": ("If a store sells 3 jackets at $80 each and 2 pants at $60 each, "
                     "and offers 15% discount on the total when buying 4+ items, "
                     "what's the final price?"),
        }],
    }],
    inferenceConfig={"temperature": 1.0, "maxTokens": 4000},
    additionalModelRequestFields={
        "thinking": {"type": "enabled", "budget_tokens": 2000},
    },
)

print("=== output content blocks ===")
text_parts = []
reasoning_parts = []
for block in resp["output"]["message"]["content"]:
    if "text" in block:
        text_parts.append(block["text"])
        print(f"[text] {block['text'][:200]}...")
    elif "reasoningContent" in block:
        rt = block["reasoningContent"].get("reasoningText", {})
        rt_text = rt.get("text", "") if isinstance(rt, dict) else ""
        reasoning_parts.append(rt_text)
        print(f"[reasoning] {rt_text[:200]}...")
    else:
        print(f"[other] keys={list(block.keys())}")

print("\n=== usage ===")
print(json.dumps(resp.get("usage", {}), indent=2, default=str))

print(f"\n=== summary ===")
print(f"text blocks: {len(text_parts)}")
print(f"reasoning blocks: {len(reasoning_parts)}")
print(f"reasoning empty? {all(not r for r in reasoning_parts)}")

# 검증 통과 조건
assert len(reasoning_parts) >= 1, "no reasoning content — thinking didn't activate"
assert len(text_parts) >= 1, "no text output"
print("\n[PASS] reasoning + text blocks both present")
