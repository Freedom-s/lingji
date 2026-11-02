from flask import request
from types import SimpleNamespace


def test_load_user_retries_transient_database_error(monkeypatch):
    import api.apps as apps

    expected_user = SimpleNamespace(email="test@example.com")
    query_calls = 0
    close_calls = 0

    monkeypatch.setattr(apps.settings, "SECRET_KEY", "test-secret")

    def query_user(**_kwargs):
        nonlocal query_calls
        query_calls += 1
        if query_calls == 1:
            raise RuntimeError("stale database connection")
        return [expected_user]

    def close_database():
        nonlocal close_calls
        close_calls += 1

    monkeypatch.setattr(apps.UserService, "query", query_user)
    monkeypatch.setattr(apps.DB, "is_closed", lambda: False)
    monkeypatch.setattr(apps.DB, "close", close_database)
    signed_token = apps.Serializer(secret_key="test-secret").dumps("access-token")

    with apps.app.test_request_context(
        "/v1/user/info", headers={"Authorization": signed_token}
    ):
        assert apps.load_user(request) is expected_user

    assert query_calls == 2
    assert close_calls == 1
