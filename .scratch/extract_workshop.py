#!/usr/bin/env python3
"""Extract Bedrock KB, Cognito, AgentCore, SSM, IAM resources from the workshop AWS account.

Reads credentials from environment (AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY/AWS_SESSION_TOKEN/AWS_DEFAULT_REGION).
Writes JSON files into the agenticai/workshop-extract directory tree.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

OUT_BASE = Path("/Users/toule/Documents/Works/2026/교육용자료/agenticai/workshop-extract")


def write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    print(f"  -> {path.relative_to(OUT_BASE)} ({path.stat().st_size:,} bytes)")


def safe_call(label: str, fn, *args, **kwargs) -> Any:
    try:
        return fn(*args, **kwargs)
    except ClientError as e:
        print(f"  ! {label}: {e.response['Error']['Code']} - {e.response['Error']['Message']}")
        return {"error": str(e), "code": e.response["Error"]["Code"]}
    except Exception as e:  # noqa: BLE001
        print(f"  ! {label}: {type(e).__name__}: {e}")
        return {"error": str(e)}


def extract_bedrock_kb() -> None:
    print("\n=== Bedrock Knowledge Bases ===")
    out = OUT_BASE / "kb"
    bra = boto3.client("bedrock-agent")
    kb_list = safe_call("list_knowledge_bases", bra.list_knowledge_bases, maxResults=20)
    write(out / "list-knowledge-bases.json", kb_list)
    for kb in kb_list.get("knowledgeBaseSummaries", []) or []:
        kb_id = kb["knowledgeBaseId"]
        name = kb.get("name", kb_id)
        print(f"  KB: {name} ({kb_id})")
        write(out / f"{name}.describe.json", safe_call(f"get_kb {kb_id}", bra.get_knowledge_base, knowledgeBaseId=kb_id))
        ds_list = safe_call(f"list_data_sources {kb_id}", bra.list_data_sources, knowledgeBaseId=kb_id, maxResults=10)
        write(out / f"{name}.data-sources.json", ds_list)
        for ds in ds_list.get("dataSourceSummaries", []) or []:
            ds_id = ds["dataSourceId"]
            write(
                out / f"{name}.{ds_id}.describe.json",
                safe_call(f"get_data_source {ds_id}", bra.get_data_source, knowledgeBaseId=kb_id, dataSourceId=ds_id),
            )


def extract_cognito() -> None:
    print("\n=== Cognito ===")
    out = OUT_BASE / "cognito"
    cip = boto3.client("cognito-idp")
    pools = safe_call("list_user_pools", cip.list_user_pools, MaxResults=20)
    write(out / "list-user-pools.json", pools)
    for pool in pools.get("UserPools", []) or []:
        pid = pool["Id"]
        name = pool["Name"]
        print(f"  Pool: {name} ({pid})")
        write(out / f"{name}.describe.json", safe_call(f"describe_user_pool {pid}", cip.describe_user_pool, UserPoolId=pid))
        clients = safe_call(f"list_user_pool_clients {pid}", cip.list_user_pool_clients, UserPoolId=pid, MaxResults=20)
        write(out / f"{name}.clients.json", clients)
        for c in clients.get("UserPoolClients", []) or []:
            cid = c["ClientId"]
            write(
                out / f"{name}.{cid}.describe.json",
                safe_call(
                    f"describe_user_pool_client {cid}",
                    cip.describe_user_pool_client,
                    UserPoolId=pid,
                    ClientId=cid,
                ),
            )
        domain = safe_call(f"describe_user_pool_domain {pid}", cip.describe_user_pool_domain, Domain=pool.get("Name", ""))
        write(out / f"{name}.domain.json", domain)
        rs_list = safe_call(f"list_resource_servers {pid}", cip.list_resource_servers, UserPoolId=pid, MaxResults=20)
        write(out / f"{name}.resource-servers.json", rs_list)


def extract_agentcore() -> None:
    print("\n=== Bedrock AgentCore (Gateways, Runtimes) ===")
    out = OUT_BASE / "agentcore"
    try:
        ac = boto3.client("bedrock-agentcore-control")
    except Exception as e:  # noqa: BLE001
        print(f"  ! cannot create bedrock-agentcore-control client: {e}")
        # fallback: try alternate names
        try:
            ac = boto3.client("bedrock-agentcore")
        except Exception as e2:
            print(f"  ! cannot create bedrock-agentcore client: {e2}")
            return

    # gateways
    gw = safe_call("list_gateways", ac.list_gateways, maxResults=50)
    write(out / "list-gateways.json", gw)
    for g in gw.get("items", []) or []:
        gid = g.get("gatewayId") or g.get("id")
        if not gid:
            continue
        name = g.get("name", gid)
        print(f"  Gateway: {name} ({gid})")
        write(out / f"gw.{name}.describe.json", safe_call(f"get_gateway {gid}", ac.get_gateway, gatewayIdentifier=gid))
        targets = safe_call(f"list_gateway_targets {gid}", ac.list_gateway_targets, gatewayIdentifier=gid, maxResults=50)
        write(out / f"gw.{name}.targets.json", targets)
        for t in targets.get("items", []) or []:
            tid = t.get("targetId") or t.get("id")
            if not tid:
                continue
            tname = t.get("name", tid)
            write(
                out / f"gw.{name}.target.{tname}.describe.json",
                safe_call(
                    f"get_gateway_target {tid}",
                    ac.get_gateway_target,
                    gatewayIdentifier=gid,
                    targetId=tid,
                ),
            )

    # runtimes
    rt = safe_call("list_agent_runtimes", ac.list_agent_runtimes, maxResults=50)
    write(out / "list-agent-runtimes.json", rt)
    for r in rt.get("items", []) or []:
        rid = r.get("agentRuntimeId") or r.get("id")
        if not rid:
            continue
        name = r.get("name", rid)
        print(f"  Runtime: {name} ({rid})")
        write(
            out / f"runtime.{name}.describe.json",
            safe_call(f"get_agent_runtime {rid}", ac.get_agent_runtime, agentRuntimeId=rid),
        )


def extract_ssm() -> None:
    print("\n=== SSM Parameters ===")
    out = OUT_BASE / "ssm"
    ssm = boto3.client("ssm")
    paginator = ssm.get_paginator("describe_parameters")
    all_params: list[dict] = []
    for page in paginator.paginate(MaxResults=50):
        all_params.extend(page.get("Parameters", []))
    write(out / "describe-parameters.json", all_params)
    print(f"  {len(all_params)} parameters")

    if not all_params:
        return
    # batch get values (max 10 per call)
    values: dict[str, dict] = {}
    for i in range(0, len(all_params), 10):
        names = [p["Name"] for p in all_params[i : i + 10]]
        resp = safe_call(
            f"get_parameters batch {i}", ssm.get_parameters, Names=names, WithDecryption=True
        )
        for p in resp.get("Parameters", []) or []:
            values[p["Name"]] = p
    write(out / "parameter-values.json", values)


def extract_iam() -> None:
    print("\n=== IAM (workshop roles only) ===")
    out = OUT_BASE / "iam"
    iam = boto3.client("iam")
    roles = []
    paginator = iam.get_paginator("list_roles")
    for page in paginator.paginate():
        roles.extend(page.get("Roles", []))
    # only workshop-related roles
    keywords = ("cfn-", "Bedrock", "VSCode", "AnyCompany", "WSP", "Cognito", "agentcore", "Workshop", "workshop")
    workshop_roles = [r for r in roles if any(k.lower() in r["RoleName"].lower() for k in keywords)]
    print(f"  {len(workshop_roles)} relevant roles (out of {len(roles)} total)")
    write(out / "roles-summary.json", workshop_roles)

    for r in workshop_roles:
        name = r["RoleName"]
        try:
            detail = iam.get_role(RoleName=name)
        except ClientError as e:
            print(f"  ! get_role {name}: {e}")
            continue
        attached = safe_call(f"list_attached_role_policies {name}", iam.list_attached_role_policies, RoleName=name)
        inline_names = safe_call(f"list_role_policies {name}", iam.list_role_policies, RoleName=name)
        inline_docs = {}
        for pn in inline_names.get("PolicyNames", []) or []:
            doc = safe_call(f"get_role_policy {name}/{pn}", iam.get_role_policy, RoleName=name, PolicyName=pn)
            inline_docs[pn] = doc
        write(
            out / f"role.{name}.json",
            {
                "role": detail.get("Role"),
                "attached_managed": attached.get("AttachedPolicies", []),
                "inline_policies": inline_docs,
            },
        )


def main() -> int:
    if not OUT_BASE.exists():
        print(f"OUT_BASE missing: {OUT_BASE}", file=sys.stderr)
        return 2
    extract_bedrock_kb()
    extract_cognito()
    extract_agentcore()
    extract_ssm()
    extract_iam()
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
