from cctoken.pricing import calculate_cost, UNKNOWN_COST, format_cost


def test_calculate_cost_sonnet():
    # input=100, cache_create=500, cache_read=200, output=50
    # 100×3 + 500×3.75 + 200×0.30 + 50×15 = 300+1875+60+750 = 2985 → $0.002985
    # (spec had a typo: $0.002685)
    cost = calculate_cost(
        model="claude-sonnet-4-6",
        input_tokens=100,
        cache_creation_tokens=500,
        cache_read_tokens=200,
        output_tokens=50,
    )
    assert abs(cost - 0.002985) < 1e-9


def test_calculate_cost_zero():
    cost = calculate_cost("claude-sonnet-4-6", 0, 0, 0, 0)
    assert cost == 0.0


def test_calculate_cost_unknown_model():
    cost = calculate_cost("claude-future-99", 100, 0, 0, 50)
    assert cost is UNKNOWN_COST


def test_format_cost_known():
    assert format_cost(0.002685) == "$0.0027"


def test_format_cost_unknown():
    assert format_cost(UNKNOWN_COST) == "~$?.??"
