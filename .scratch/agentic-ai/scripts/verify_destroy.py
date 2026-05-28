#!/usr/bin/env python3
"""Verify no anycompany-related resources remain after terraform destroy."""
import boto3

REGION = "us-west-2"

print("AOSS collections:")
aoss = boto3.client("opensearchserverless", region_name=REGION)
cols = aoss.list_collections().get("collectionSummaries", [])
if not cols:
    print("  (none)")
for c in cols:
    print(f"  - {c['name']} ({c['status']})")

print("\nAOSS data access policies:")
pols = aoss.list_access_policies(type="data").get("accessPolicySummaries", [])
if not pols:
    print("  (none)")
for p in pols:
    print(f"  - {p['name']}")

print("\nBedrock KBs:")
ba = boto3.client("bedrock-agent", region_name=REGION)
kbs = ba.list_knowledge_bases().get("knowledgeBaseSummaries", [])
if not kbs:
    print("  (none)")
for kb in kbs:
    print(f"  - {kb['name']} {kb['knowledgeBaseId']} {kb['status']}")

print("\nS3 anycompany buckets:")
hits = [b["Name"] for b in boto3.client("s3").list_buckets()["Buckets"]
        if "anycompany" in b["Name"]]
if not hits:
    print("  (none)")
for n in hits:
    print(f"  - {n}")

print("\nDDB tables (anycompany):")
ddb = boto3.client("dynamodb", region_name=REGION)
hits = [t for t in ddb.list_tables()["TableNames"] if "anycompany" in t.lower()]
if not hits:
    print("  (none)")
for n in hits:
    print(f"  - {n}")

print("\nLambdas (anycompany):")
lam = boto3.client("lambda", region_name=REGION)
hits = [f["FunctionName"] for f in lam.list_functions()["Functions"]
        if "anycompany" in f["FunctionName"].lower()]
if not hits:
    print("  (none)")
for n in hits:
    print(f"  - {n}")

print("\nCognito user pools (anycompany):")
cog = boto3.client("cognito-idp", region_name=REGION)
hits = [(p["Name"], p["Id"]) for p in cog.list_user_pools(MaxResults=60)["UserPools"]
        if "anycompany" in p["Name"].lower()]
if not hits:
    print("  (none)")
for name, pid in hits:
    print(f"  - {name} {pid}")

print("\nSecrets Manager (anycompany):")
sm = boto3.client("secretsmanager", region_name=REGION)
hits = [s["Name"] for s in sm.list_secrets()["SecretList"]
        if "anycompany" in s["Name"].lower()]
if not hits:
    print("  (none)")
for n in hits:
    print(f"  - {n}")

print("\nSSM Parameters (anycompany-related):")
ssm = boto3.client("ssm", region_name=REGION)
names = ["coordinator_model_id", "agent_model_id", "faq_kb_id",
         "product_search_kb_id", "agentcore_gateway_role_name",
         "cognito_discovery_url", "cognito_token_endpoint",
         "cognito_client_id", "anycomp_prod_reviews_mcp_server_url"]
remaining = []
for n in names:
    try:
        ssm.get_parameter(Name=n)
        remaining.append(n)
    except ssm.exceptions.ParameterNotFound:
        pass
if not remaining:
    print("  (none)")
for n in remaining:
    print(f"  EXISTS: {n}")
