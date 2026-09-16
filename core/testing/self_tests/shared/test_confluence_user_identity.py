import pytest

from core.confluence.gateway import ConfluenceGateway
from core.confluence.models import ConfluenceGatewayConfig


class Api:
    def __init__(self, outcomes=()):
        self.key_calls, self.outcomes = [], list(outcomes)
    def get_user_details_by_userkey(self, value):
        self.key_calls.append(value)
        assert value == "user-key-1"
        if self.outcomes:
            outcome = self.outcomes.pop(0)
            if isinstance(outcome, Exception): raise outcome
            return outcome
        return {"username": "alice", "displayName": "张三", "active": True}


def make_gateway(api):
    return ConfluenceGateway(ConfluenceGatewayConfig("https://confluence.example"), "coco", "secret", api=api)


def test_user_key_lookup_uses_user_endpoint_and_accepts_chinese_display_name():
    api = Api()
    gateway = make_gateway(api)

    assert gateway.resolve_user_keys(("user-key-1",)) == {
        "user-key-1": {"account": "alice", "display_name": "张三", "active": True},
    }
    assert api.key_calls == ["user-key-1"]


class HttpError(RuntimeError):
    def __init__(self, status):
        super().__init__(f"response body must not be logged: {status}")
        self.status_code = status


def test_user_key_lookup_retries_transient_failure_with_a_fixed_bound():
    api = Api((HttpError(503), HttpError(429),
               {"username": "alice", "displayName": "张三", "active": True}))
    assert make_gateway(api).resolve_user_keys(("user-key-1",))["user-key-1"]["account"] == "alice"
    assert api.key_calls == ["user-key-1"] * 3


def test_user_key_lookup_does_not_retry_non_429_4xx():
    api = Api((HttpError(403),))
    with pytest.raises(HttpError): make_gateway(api).resolve_user_keys(("user-key-1",))
    assert api.key_calls == ["user-key-1"]
