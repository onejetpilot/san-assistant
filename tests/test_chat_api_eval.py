from app.evaluation.run_chat_api_eval import _problems_for_response


def test_problems_for_response_passes_expected_answer():
    case = {
        'query': 'Кто производитель?',
        'expects': {'must_contain_all': ['Производитель', 'Sabie S.r.l.']},
    }
    response = {
        'answer': 'Производитель: Sabie S.r.l., Italy.',
        'answer_mode': 'technical_answer',
    }

    assert _problems_for_response(case, response) == []


def test_problems_for_response_flags_unexpected_clarify():
    case = {
        'query': 'Кто производитель?',
        'expects': {'must_contain_all': ['Производитель']},
    }
    response = {
        'answer': 'Уточните товар.',
        'answer_mode': 'clarify',
    }

    problems = _problems_for_response(case, response)

    assert 'unexpected clarification' in problems
