#!/usr/bin/env python3
"""KB / Guardrail / Evaluation 관련 실제 API 입력 스키마 점검."""
from __future__ import annotations

import json
import re

import boto3


def show_op(client, op_pascal: str, max_depth=4) -> dict:
    sm = client.meta.service_model
    try:
        op = sm.operation_model(op_pascal)
    except Exception as e:
        return {"_error": str(e)}

    def shape_to_dict(shape, depth=0):
        if shape is None:
            return None
        if depth >= max_depth:
            return f"<{shape.type_name}>"
        if shape.type_name == "structure":
            members = {}
            for name, m in shape.members.items():
                req = name in (shape.required_members or [])
                members[name + ("*" if req else "")] = shape_to_dict(m, depth + 1)
            return members
        if shape.type_name == "list":
            return [shape_to_dict(shape.member, depth + 1)]
        if shape.type_name == "map":
            return {"<key>": shape_to_dict(shape.value, depth + 1)}
        enum = getattr(shape, "enum", None)
        if enum:
            return f"<{shape.type_name}: {enum}>"
        return f"<{shape.type_name}>"

    return shape_to_dict(op.input_shape)


def main():
    out = {}

    # 1. KB CreateKnowledgeBase 실제 storage_configuration 옵션
    ba = boto3.client("bedrock-agent", region_name="us-west-2")
    out["bedrock-agent.CreateKnowledgeBase.input"] = show_op(
        ba, "CreateKnowledgeBase", max_depth=6
    )

    # 2. Guardrail
    br = boto3.client("bedrock", region_name="us-west-2")
    out["bedrock.CreateGuardrail.input"] = show_op(br, "CreateGuardrail", max_depth=5)

    # 3. bedrock 의 모든 op — eval 패턴 다시 더 넓게 확인
    out["bedrock.all_ops"] = list(br.meta.service_model.operation_names)
    out["bedrock-agent.all_ops"] = list(ba.meta.service_model.operation_names)

    # 4. AgentCore data plane (control 외에 별도 client 존재 여부)
    try:
        adp = boto3.client("bedrock-agentcore", region_name="us-west-2")
        out["bedrock-agentcore.exists"] = True
        out["bedrock-agentcore.all_ops"] = list(
            adp.meta.service_model.operation_names
        )
    except Exception as e:
        out["bedrock-agentcore.exists"] = False
        out["bedrock-agentcore.error"] = str(e)

    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
