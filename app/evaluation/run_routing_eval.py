from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.routing.router import route_query_sync


def _check_case(case: dict) -> tuple[bool, list[str]]:
    history = case.get('history') or {}
    state = history if isinstance(history, dict) else {}
    decision = route_query_sync(case['query'], conversation_state=state)
    problems: list[str] = []

    if case.get('expected_intent') and decision.intent != case['expected_intent']:
        problems.append(f"intent expected={case['expected_intent']} actual={decision.intent}")

    if case.get('expected_route') and decision.selected_route != case['expected_route']:
        problems.append(f"route expected={case['expected_route']} actual={decision.selected_route}")

    for tool in case.get('must_call_tools', []):
        if tool not in decision.tools_to_call:
            problems.append(f"missing tool: {tool}")

    for tool in case.get('must_not_call_tools', []):
        if tool in decision.tools_to_call:
            problems.append(f"forbidden tool present: {tool}")

    if case.get('expected_intent') == 'ambiguous_question' and not decision.needs_clarification:
        problems.append('expected needs_clarification=True')

    if not decision.reason:
        problems.append('empty reason')

    if decision.confidence <= 0:
        problems.append('invalid confidence')

    return not problems, problems


def run(path: str) -> int:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    cases = data.get('cases', [])
    passed = 0
    failed_rows: list[dict] = []

    for case in cases:
        ok, problems = _check_case(case)
        if ok:
            passed += 1
            print(f"[PASS] {case['id']}: {case['query']}")
        else:
            decision = route_query_sync(case['query'], conversation_state=case.get('history') or {})
            print(f"[FAIL] {case['id']}: {case['query']}")
            for p in problems:
                print(f"    - {p}")
            print(f"    actual: intent={decision.intent} route={decision.selected_route} tools={decision.tools_to_call} reason={decision.reason}")
            failed_rows.append({'id': case['id'], 'problems': problems, 'expected_behavior': case.get('expected_behavior')})

    total = len(cases)
    accuracy = (passed / total * 100) if total else 0.0
    print(f"\nTotal: {total} | Passed: {passed} | Failed: {total - passed} | Accuracy: {accuracy:.1f}%")
    if failed_rows:
        print('Failed cases:')
        for row in failed_rows:
            print(f"  - {row['id']}: {row['problems']}")
    return 0 if passed == total else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', default='eval/routing_eval_cases.json')
    args = parser.parse_args()
    raise SystemExit(run(args.path))
