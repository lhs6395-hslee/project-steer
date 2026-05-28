#!/usr/bin/env python3
"""Try every possible way to invoke Sonnet 4.6 / Haiku 4.5."""
import boto3

REGIONS = ["us-west-2", "us-east-1", "us-east-2", "ap-northeast-2"]
TARGETS = [
    # 직접 모델 ID
    "anthropic.claude-sonnet-4-6",
    "anthropic.claude-haiku-4-5-20251001-v1:0",
    # us. prefix
    "us.anthropic.claude-sonnet-4-6",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    # global. prefix (있을 수도)
    "global.anthropic.claude-sonnet-4-6",
    "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    # apac. prefix (ap-northeast-2 용)
    "apac.anthropic.claude-sonnet-4-6",
    "apac.anthropic.claude-haiku-4-5-20251001-v1:0",
]

for region in REGIONS:
    print(f"\n========= {region} =========")
    br = boto3.client("bedrock-runtime", region_name=region)
    bc = boto3.client("bedrock", region_name=region)

    # 1) 모든 inference profile 목록 (cross-region + application)
    print("--- ALL inference profiles (sonnet-4-6 / haiku-4-5 만) ---")
    try:
        for ptype in ["SYSTEM_DEFINED", "APPLICATION"]:
            try:
                resp = bc.list_inference_profiles(maxResults=200, typeEquals=ptype)
                for p in resp.get("inferenceProfileSummaries", []):
                    pid = p["inferenceProfileId"]
                    pname = p.get("inferenceProfileName", "")
                    if "sonnet-4-6" in pid.lower() or "haiku-4-5" in pid.lower() or \
                       "sonnet 4.6" in pname.lower() or "haiku 4.5" in pname.lower():
                        print(f"  [{ptype:11s}] {pid:55s} | {pname}")
            except Exception as e:
                if "ValidationException" in str(e):
                    # typeEquals 미지원이면 fallback
                    if ptype == "SYSTEM_DEFINED":
                        resp = bc.list_inference_profiles(maxResults=200)
                        for p in resp.get("inferenceProfileSummaries", []):
                            pid = p["inferenceProfileId"]
                            pname = p.get("inferenceProfileName", "")
                            if "sonnet-4-6" in pid.lower() or "haiku-4-5" in pid.lower() or \
                               "sonnet 4.6" in pname.lower() or "haiku 4.5" in pname.lower():
                                print(f"  [DEFAULT  ] {pid:55s} | {pname}")
                        break  # only run once
                else:
                    print(f"  list error ({ptype}): {e}")
    except Exception as e:
        print(f"  region error: {e}")

    # 2) 각 후보 ID 로 실제 invoke 시도
    print("--- Actual invoke attempts ---")
    for mid in TARGETS:
        try:
            resp = br.converse(
                modelId=mid,
                messages=[{"role": "user", "content": [{"text": "hi"}]}],
                inferenceConfig={"maxTokens": 5},
            )
            out = resp["output"]["message"]["content"][0]["text"][:30]
            print(f"  [OK]  {mid:55s} -> {out!r}")
        except Exception as e:
            msg = str(e)
            short = "?"
            for tag in ("on-demand throughput isn", "Legacy", "ResourceNotFoundException",
                        "AccessDenied", "ValidationException"):
                if tag in msg:
                    short = tag[:30]; break
            print(f"  [ERR] {mid:55s} -> {short}")
