#!/usr/bin/env python3
"""
Extract structured output or result field from claude --print JSON response.

Usage:
    python3 extract_result.py <input_json_file> <output_file>

With --json-schema flag: extracts "structured_output" field (schema-validated JSON)
Without --json-schema: extracts "result" field (text content)

Reference: code.claude.com/docs/en/headless.md
"""

import json
import sys
import re


def strip_markdown_wrapper(text):
    """Remove markdown code fences if present."""
    # Remove ```json ... ``` or ``` ... ``` wrappers
    text = text.strip()
    if text.startswith('```'):
        lines = text.split('\n')
        # Remove first line (```json or ```)
        if lines[0].strip().startswith('```'):
            lines = lines[1:]
        # Remove last line if it's ```
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        text = '\n'.join(lines).strip()
    return text


def extract_json_from_text(text):
    """Try to extract JSON object from text."""
    text = strip_markdown_wrapper(text)

    # Try to parse as-is first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in text
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def main():
    if len(sys.argv) != 3:
        print("Usage: extract_result.py <input_json> <output_file>", file=sys.stderr)
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            response = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse input JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"ERROR: Input file not found: {input_file}", file=sys.stderr)
        sys.exit(1)

    # Priority 1: structured_output (when --json-schema is used)
    if 'structured_output' in response:
        output_data = response['structured_output']
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        sys.exit(0)

    # Priority 2: result field (text output)
    if 'result' in response:
        result_text = response['result']

        # Try to extract JSON from result text
        extracted_json = extract_json_from_text(result_text)
        if extracted_json:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(extracted_json, f, indent=2, ensure_ascii=False)
            sys.exit(0)

        # If not JSON, write as plain text
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result_text)
        sys.exit(0)

    # Error: no recognized output field
    print(f"ERROR: Response contains neither 'structured_output' nor 'result' field", file=sys.stderr)
    print(f"Available fields: {list(response.keys())}", file=sys.stderr)
    sys.exit(1)


if __name__ == '__main__':
    main()
