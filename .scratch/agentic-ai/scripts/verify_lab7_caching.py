"""Lab-7 prompt caching real-call verification.

Purpose
-------
Validate the wiki claim that Anthropic models on Bedrock honor `cachePoint`
markers and return `cacheReadInputTokens` / `cacheWriteInputTokens` on second
identical call within TTL.

References (boto3 1.43.15 service model)
- bedrock-runtime.Converse.input.system[].cachePoint
- response.usage.{inputTokens, cacheReadInputTokens, cacheWriteInputTokens, outputTokens}

Anthropic minimum prefix length for caching is 1024 tokens — we pad the system
prompt to comfortably exceed that.

Usage:
    python3 verify_lab7_caching.py
"""
from __future__ import annotations

import json
import sys
import time

import boto3

REGION = "us-west-2"
MODEL_ID = "us.anthropic.claude-sonnet-4-6"

# ~1500 token system prompt — synthetic but stable
LONG_PROMPT = (
    "You are AnyCompany's customer assistant. "
    "Follow these rules strictly:\n"
    + "\n".join(f"Rule {i}: respond concisely with rule context {i}." for i in range(1, 80))
    + "\n\nWhen answering, prefer factual replies. Never invent SKUs."
)


def converse(client: "boto3.client", question: str) -> dict:
    return client.converse(
        modelId=MODEL_ID,
        system=[
            {"text": LONG_PROMPT},
            {"cachePoint": {"type": "default"}},  # ttl defaults to 5m
        ],
        messages=[{"role": "user", "content": [{"text": question}]}],
        inferenceConfig={"temperature": 0.2, "maxTokens": 200},
    )


def main() -> int:
    client = boto3.client("bedrock-runtime", region_name=REGION)

    print(f"Region : {REGION}")
    print(f"Model  : {MODEL_ID}")
    print(f"System prompt length (chars): {len(LONG_PROMPT)}")
    print()

    # First call — cache write expected
    print("==> Call 1 (cache write expected)")
    t0 = time.time()
    r1 = converse(client, "What is your purpose in one sentence?")
    dt1 = time.time() - t0
    u1 = r1["usage"]
    print(json.dumps(u1, indent=2))
    print(f"latency: {dt1:.2f}s")
    print()

    # Second call — same prefix, different question — cache read expected
    print("==> Call 2 (same prefix, cache read expected)")
    t0 = time.time()
    r2 = converse(client, "What is your purpose in two sentences?")
    dt2 = time.time() - t0
    u2 = r2["usage"]
    print(json.dumps(u2, indent=2))
    print(f"latency: {dt2:.2f}s")
    print()

    cache_write = u1.get("cacheWriteInputTokens", 0)
    cache_read = u2.get("cacheReadInputTokens", 0)
    print("=== Verdict ===")
    print(f"Call 1 cacheWriteInputTokens: {cache_write}")
    print(f"Call 2 cacheReadInputTokens : {cache_read}")
    print(f"Latency delta (call2 vs call1): {(dt2 - dt1):+.2f}s")

    if cache_write > 0 and cache_read > 0:
        print("PASS — caching active")
        return 0
    print("FAIL — usage fields not populated. Possible reasons:")
    print(" - Prefix below minimum token threshold")
    print(" - Model variant does not support caching in this region")
    print(" - cachePoint marker malformed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
