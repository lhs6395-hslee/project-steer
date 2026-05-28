#!/usr/bin/env python3
"""List actually-invokable Anthropic models in us-west-2 (and a few other regions)."""
import boto3

REGIONS = ["us-west-2", "us-east-1", "us-east-2"]

for region in REGIONS:
    print(f"\n========= {region} =========")
    br = boto3.client("bedrock", region_name=region)

    print("--- inference profiles (Anthropic) ---")
    try:
        profs = br.list_inference_profiles(maxResults=200).get("inferenceProfileSummaries", [])
    except Exception as e:
        print(f"  error: {e}"); continue
    for p in profs:
        if "anthropic" in p["inferenceProfileId"].lower():
            print(f"  {p['inferenceProfileId']:65s} | {p.get('inferenceProfileName','')}")

    print("--- foundation models (Anthropic, ACTIVE) ---")
    try:
        fms = br.list_foundation_models(byProvider="anthropic").get("modelSummaries", [])
    except Exception as e:
        print(f"  error: {e}"); continue
    for m in fms:
        if m.get("modelLifecycle", {}).get("status") != "ACTIVE":
            continue
        flags = []
        types = m.get("inferenceTypesSupported", [])
        if "ON_DEMAND" in types: flags.append("ON_DEMAND")
        if "INFERENCE_PROFILE" in types: flags.append("PROFILE")
        if "PROVISIONED" in types: flags.append("PROVISIONED")
        mid = m["modelId"]
        print(f"  {mid:65s} {flags}")
