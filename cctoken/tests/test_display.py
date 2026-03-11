from cctoken.display import _sum_tokens, _sum_cost
from cctoken.parser import TokenRecord
from cctoken.pricing import UNKNOWN_COST
from datetime import datetime, timezone


def make_record(input_t, cache_create, cache_read, output_t, model="claude-sonnet-4-6"):
    return TokenRecord(
        timestamp=datetime.now(timezone.utc),
        session_id="s",
        cwd="/foo",
        model=model,
        input_tokens=input_t,
        cache_creation_tokens=cache_create,
        cache_read_tokens=cache_read,
        output_tokens=output_t,
    )


def test_sum_tokens_spec_acceptance():
    r = make_record(100, 500, 200, 50)
    display, cache = _sum_tokens([r])
    assert display == 150   # input + output
    assert cache == 700     # cache_create + cache_read


def test_sum_tokens_zero():
    r = make_record(0, 0, 0, 0)
    display, cache = _sum_tokens([r])
    assert display == 0
    assert cache == 0


def test_sum_cost_spec_acceptance():
    r = make_record(100, 500, 200, 50)
    cost, has_unknown = _sum_cost([r])
    assert not has_unknown
    assert abs(cost - 0.002985) < 1e-9


def test_sum_cost_unknown_model():
    r = make_record(100, 0, 0, 50, model="claude-future-99")
    cost, has_unknown = _sum_cost([r])
    assert has_unknown
    assert cost == 0.0
