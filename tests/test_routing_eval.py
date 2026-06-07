from app.evaluation.run_routing_eval import run


def test_routing_eval_cases_pass():
    assert run('eval/routing_eval_cases.json') == 0
