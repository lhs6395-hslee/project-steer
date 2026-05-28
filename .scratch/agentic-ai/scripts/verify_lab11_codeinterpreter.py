"""Lab-11 AgentCore Code Interpreter real-call verification.

Steps
-----
1. Create a SANDBOX-mode CodeInterpreter resource.
2. Wait until status=READY.
3. Start a session.
4. Invoke executeCode with simple Python (numpy mean) and parse streaming output.
5. Stop session + delete CodeInterpreter.

Reference (boto3 1.43.15)
- bedrock-agentcore-control: CreateCodeInterpreter / GetCodeInterpreter / DeleteCodeInterpreter
- bedrock-agentcore: StartCodeInterpreterSession / InvokeCodeInterpreter / StopCodeInterpreterSession
- InvokeCodeInterpreter.name enum: executeCode / executeCommand / readFiles / listFiles /
  removeFiles / writeFiles / startCommandExecution / getTask / stopTask
- arguments.language enum: python / javascript / typescript

Run:
    python3 verify_lab11_codeinterpreter.py
"""
from __future__ import annotations

import json
import sys
import time

import boto3
from botocore.exceptions import ClientError

REGION = "us-west-2"
NAME = "anycompany_codeinterp_verify"


def wait_status(c, cid: str, target: str, timeout: int = 300):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        resp = c.get_code_interpreter(codeInterpreterId=cid)
        status = resp.get("status")
        if status != last:
            print(f"  status={status} elapsed={int(time.time() - t0)}s")
            last = status
        if status == target:
            return resp
        if status in ("CREATE_FAILED", "DELETING", "DELETED"):
            raise RuntimeError(f"terminal state {status}: {resp}")
        time.sleep(8)
    raise TimeoutError(f"did not reach {target} within {timeout}s")


def consume_stream(stream_iter) -> str:
    """InvokeCodeInterpreter returns an event stream — collect text payloads."""
    parts = []
    for event in stream_iter:
        # Each event has one of: result, error, etc.
        if "result" in event:
            r = event["result"]
            content = r.get("content") or []
            for c in content:
                if "text" in c:
                    parts.append(c["text"])
                elif "json" in c:
                    parts.append(json.dumps(c["json"]))
        elif "error" in event:
            parts.append(f"[error] {event['error']}")
    return "\n".join(parts)


def main() -> int:
    cp = boto3.client("bedrock-agentcore-control", region_name=REGION)
    dp = boto3.client("bedrock-agentcore", region_name=REGION)

    print("==> create code interpreter (SANDBOX)")
    try:
        resp = cp.create_code_interpreter(
            name=NAME,
            description="ephemeral verify",
            networkConfiguration={"networkMode": "SANDBOX"},
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConflictException":
            # already exists — find via list
            print("  already exists, locating...")
            for page in cp.get_paginator("list_code_interpreters").paginate():
                for ci in page.get("codeInterpreterSummaries", []) + page.get("items", []):
                    if ci.get("name") == NAME:
                        resp = {"codeInterpreterId": ci.get("codeInterpreterId") or ci.get("id")}
                        break
                else:
                    continue
                break
            else:
                raise
        else:
            raise
    cid = resp["codeInterpreterId"]
    print(f"  id: {cid}")

    print("==> wait READY")
    wait_status(cp, cid, "READY", timeout=300)

    print()
    print("==> start session")
    s = dp.start_code_interpreter_session(
        codeInterpreterIdentifier=cid,
        sessionTimeoutSeconds=300,
    )
    session_id = s["sessionId"]
    print(f"  sessionId: {session_id}")

    print()
    print("==> invoke executeCode (numpy mean)")
    code = (
        "import numpy as np\n"
        "data = [10, 20, 30, 40, 50]\n"
        "print('mean:', np.mean(data))\n"
        "print('std :', round(float(np.std(data)), 4))\n"
    )
    inv = dp.invoke_code_interpreter(
        codeInterpreterIdentifier=cid,
        sessionId=session_id,
        name="executeCode",
        arguments={"code": code, "language": "python"},
    )
    output = consume_stream(inv.get("stream", []))
    print("--- output ---")
    print(output or "(empty)")
    print("--- end ---")

    success = "mean: 30.0" in output and "std :" in output

    print()
    print("==> stop session + delete code interpreter")
    try:
        dp.stop_code_interpreter_session(
            codeInterpreterIdentifier=cid,
            sessionId=session_id,
        )
        print(f"  session stopped")
    except ClientError as e:
        print(f"  stop_session: {e}")
    try:
        cp.delete_code_interpreter(codeInterpreterId=cid)
        print(f"  delete requested")
    except ClientError as e:
        print(f"  delete: {e}")

    print()
    if success:
        print("PASS — Code Interpreter sandbox executes Python with numpy")
        return 0
    print("FAIL — expected output not found")
    return 1


if __name__ == "__main__":
    sys.exit(main())
