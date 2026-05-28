"""Lab-8 AgentCore Memory real-call verification.

Steps
-----
1. Create a tiny IAM role for memoryExecutionRoleArn (allows Bedrock InvokeModel).
2. Create a Memory resource with a single semanticMemoryStrategy via
   bedrock-agentcore-control.
3. Wait until status=ACTIVE.
4. Insert two memory records via data plane batch_create_memory_records.
5. List records via list_memory_records to confirm persistence.
6. Cleanup — delete memory + IAM role.

References (boto3 1.43.15)
- bedrock-agentcore-control.create_memory / get_memory / delete_memory
- bedrock-agentcore.create_event / list_events
  (data plane records are exposed as Events, not Records, in 0.5.x SDK)

Run:
    python3 verify_lab8_memory.py
"""
from __future__ import annotations

import json
import sys
import time
import uuid

import boto3
from botocore.exceptions import ClientError

REGION = "us-west-2"
MEMORY_NAME = "anycompany_memory_verify"
ROLE_NAME = "anycompany-memory-verify-role"


def ensure_role(iam, region: str) -> str:
    assume = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }],
    }
    try:
        resp = iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(assume),
            Description="ephemeral verify role",
        )
        arn = resp["Role"]["Arn"]
        print(f"role created: {arn}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "EntityAlreadyExists":
            raise
        arn = iam.get_role(RoleName=ROLE_NAME)["Role"]["Arn"]
        print(f"role exists : {arn}")

    inline = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": ["bedrock:InvokeModel"],
            "Resource": "*",
        }],
    }
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="bedrock-invoke",
        PolicyDocument=json.dumps(inline),
    )
    # IAM eventual consistency
    time.sleep(10)
    return arn


def find_memory(c, name):
    """list_memories doesn't return name in summary — must get_memory each."""
    paginator = c.get_paginator("list_memories")
    for page in paginator.paginate():
        for m in page.get("memories", []):
            try:
                full = c.get_memory(memoryId=m["id"])["memory"]
                if full.get("name") == name:
                    return full
            except ClientError:
                continue
    return None


def wait_active(c, mid, timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        m = c.get_memory(memoryId=mid)["memory"]
        status = m["status"]
        print(f"  status={status} elapsed={int(time.time() - t0)}s")
        if status == "ACTIVE":
            return m
        if status in ("FAILED", "DELETING"):
            raise RuntimeError(f"memory entered terminal state {status}: {m}")
        time.sleep(10)
    raise TimeoutError(f"memory did not become ACTIVE within {timeout}s")


def main() -> int:
    iam = boto3.client("iam")
    role_arn = ensure_role(iam, REGION)

    cp = boto3.client("bedrock-agentcore-control", region_name=REGION)
    dp = boto3.client("bedrock-agentcore", region_name=REGION)

    existing = find_memory(cp, MEMORY_NAME)
    if existing:
        mid = existing.get("id") or existing.get("memoryId")
        print(f"reusing existing memory: {mid}")
    else:
        print("creating memory...")
        resp = cp.create_memory(
            name=MEMORY_NAME,
            description="ephemeral verify",
            memoryExecutionRoleArn=role_arn,
            eventExpiryDuration=7,  # days (range 3..365)
            memoryStrategies=[{
                "semanticMemoryStrategy": {
                    "name": "verify_semantic",
                    "namespaces": ["sessions/{actorId}"],
                }
            }],
        )
        mem = resp["memory"]
        mid = mem.get("id") or mem.get("memoryId")
        print(f"memory id: {mid}")

    print("waiting for ACTIVE...")
    m = wait_active(cp, mid)
    print(f"  ARN: {m.get('arn')}")
    print()

    actor_id = "u-verify"
    session_id = "s-" + uuid.uuid4().hex[:8]
    import datetime as _dt
    now = _dt.datetime.now(_dt.UTC)

    print(f"==> create_event x 2 (actor={actor_id}, session={session_id})")
    try:
        e1 = dp.create_event(
            memoryId=mid,
            actorId=actor_id,
            sessionId=session_id,
            eventTimestamp=now,
            payload=[{"conversational": {"role": "USER", "content": {"text": "I prefer midi dresses"}}}],
        )
        e2 = dp.create_event(
            memoryId=mid,
            actorId=actor_id,
            sessionId=session_id,
            eventTimestamp=now + _dt.timedelta(seconds=1),
            payload=[{"conversational": {"role": "ASSISTANT", "content": {"text": "Noted — midi dress preference saved"}}}],
        )
        print(f"  event1: {e1.get('event', {}).get('eventId', e1)}")
        print(f"  event2: {e2.get('event', {}).get('eventId', e2)}")
    except ClientError as e:
        print(f"FAIL — create_event: {e}")
        return 1

    print()
    print("==> list_events")
    try:
        listed = dp.list_events(
            memoryId=mid,
            actorId=actor_id,
            sessionId=session_id,
            includePayloads=True,
            maxResults=10,
        )
        events = listed.get("events", [])
        print(f"  count: {len(events)}")
        for ev in events:
            payload = ev.get("payload", [])
            if payload and "conversational" in payload[0]:
                role = payload[0]["conversational"].get("role")
                txt = payload[0]["conversational"].get("content", {}).get("text", "")[:60]
                print(f"  - {role}: {txt}")
            else:
                print(f"  - {json.dumps(ev, default=str)[:120]}")
    except ClientError as e:
        print(f"FAIL — list_events: {e}")
        return 1

    print()
    print("==> Cleanup")
    try:
        cp.delete_memory(memoryId=mid)
        print(f"  delete_memory: {mid} requested")
    except ClientError as e:
        print(f"  delete_memory failed: {e}")

    try:
        iam.delete_role_policy(RoleName=ROLE_NAME, PolicyName="bedrock-invoke")
        iam.delete_role(RoleName=ROLE_NAME)
        print(f"  IAM role deleted")
    except ClientError as e:
        print(f"  IAM cleanup: {e}")

    print()
    print("PASS — Memory create_event + list_events work")
    return 0


if __name__ == "__main__":
    sys.exit(main())
