#!/usr/bin/env python3
"""Try invoking each Anthropic profile to find which is actually callable."""
import boto3

REGION = "us-west-2"
br = boto3.client("bedrock-runtime", region_name=REGION)
bc = boto3.client("bedrock", region_name=REGION)

# 모든 us. prefix Anthropic 프로파일
profiles = [p["inferenceProfileId"]
            for p in bc.list_inference_profiles(maxResults=200).get("inferenceProfileSummaries", [])
            if p["inferenceProfileId"].startswith("us.anthropic.")]

print(f"Testing {len(profiles)} profiles...\n")

for pid in profiles:
    try:
        resp = br.converse(
            modelId=pid,
            messages=[{"role": "user", "content": [{"text": "say hi"}]}],
            inferenceConfig={"maxTokens": 10},
        )
        out = resp["output"]["message"]["content"][0]["text"][:30]
        print(f"  [OK]  {pid:55s} -> {out!r}")
    except Exception as e:
        msg = str(e)
        # 짧게
        if "Legacy" in msg:
            short = "LEGACY"
        elif "ResourceNotFoundException" in msg:
            short = "NOT_FOUND"
        elif "ValidationException" in msg:
            short = "VALIDATION"
        elif "AccessDenied" in msg:
            short = "ACCESS_DENIED"
        else:
            short = msg[:60]
        print(f"  [ERR] {pid:55s} -> {short}")
