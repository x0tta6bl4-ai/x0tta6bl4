"""Unit tests for canonical MaaS auth EventBus evidence."""

import asyncio
import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import src.api.maas_auth as auth_mod
from src.api.maas_auth_models import UserLoginRequest, UserRegisterRequest
from src.coordination.events import EventBus, EventType


def _request(bus: EventBus):
    return SimpleNamespace(state=SimpleNamespace(event_bus=bus))


class _JsonRequest:
    def __init__(self, bus: EventBus, *, headers=None, body=None):
        self.state = SimpleNamespace(event_bus=bus)
        self.headers = headers or {}
        self._body = body or {}

    async def json(self):
        return dict(self._body)


class _OidcRequest:
    def __init__(self, bus: EventBus, *, redirect_uri=None):
        self.state = SimpleNamespace(event_bus=bus)
        self.redirect_uri = redirect_uri or "https://app.example.test/auth/callback"

    def url_for(self, route_name):
        assert route_name == "auth_callback"
        return self.redirect_uri


class _Query:
    def __init__(self, result):
        self._result = result

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._result


class _Db:
    def __init__(self, query_result=None):
        self.query_result = query_result
        self.commit_count = 0

    def query(self, *_args, **_kwargs):
        return _Query(self.query_result)

    def commit(self):
        self.commit_count += 1


class _SequenceQuery:
    def __init__(self, db):
        self._db = db

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        if not self._db.query_results:
            return None
        return self._db.query_results.pop(0)


class _SequenceDb:
    def __init__(self, query_results):
        self.query_results = list(query_results)
        self.added = []
        self.commit_count = 0
        self.refresh_count = 0

    def query(self, *_args, **_kwargs):
        return _SequenceQuery(self)

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.commit_count += 1

    def refresh(self, _item):
        self.refresh_count += 1


class _FakeOidcClient:
    def __init__(self, *, redirect_response=None, token=None):
        self.redirect_response = redirect_response
        self.token = token or {}
        self.redirect_uri = None

    async def authorize_redirect(self, _request, redirect_uri):
        self.redirect_uri = redirect_uri
        return self.redirect_response or SimpleNamespace(status_code=307)

    async def authorize_access_token(self, _request):
        return dict(self.token)


class _FakeOAuth:
    def __init__(self, *, redirect_response=None, token=None):
        self.oidc = _FakeOidcClient(
            redirect_response=redirect_response,
            token=token,
        )


def _payloads(bus: EventBus, source_agent: str):
    return [
        event.data
        for event in bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent=source_agent,
            limit=10,
        )
    ]


def test_register_publishes_redacted_registration_evidence(monkeypatch, tmp_path):
    email = "maas-auth-register-secret@example.test"
    password = "private-register-password"
    full_name = "Private Register Name"
    company = "Private Register Company"
    user_id = "maas-auth-register-user-secret"
    api_key = "x0t_register_secret_api_key"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    req = UserRegisterRequest(
        email=email,
        password=password,
        full_name=full_name,
        company=company,
    )
    user = SimpleNamespace(id=user_id, role="user", plan="starter")

    monkeypatch.setattr(auth_mod.auth_service, "register", lambda db, req: user)
    monkeypatch.setattr(auth_mod.auth_service, "issued_api_key", lambda user: api_key)

    result = asyncio.run(auth_mod.register(req, db=SimpleNamespace(), request=request))

    assert result["access_token"] == api_key
    payloads = _payloads(bus, "maas-auth-register")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "maas_auth_register"
    assert payload["service_name"] == "maas-auth-register"
    assert payload["source_alias"] == "maas-auth-register"
    assert payload["layer"] == "api_auth_registration_intent"
    assert payload["stage"] == "register_created"
    assert payload["status"] == "success"
    assert payload["request_summary"]["email_hash"] == auth_mod._redacted_sha256_prefix(
        email.lower()
    )
    assert payload["request_summary"]["email_present"] is True
    assert payload["request_summary"]["password_present"] is True
    assert payload["request_summary"]["full_name_present"] is True
    assert payload["request_summary"]["company_present"] is True
    assert payload["user_id_hash"] == auth_mod._redacted_sha256_prefix(user_id)
    assert payload["token_issued"] is True
    assert payload["local_db_write"] is True
    assert payload["http_status_code"] == 200
    assert payload["control_action"] is True
    assert payload["raw_identifiers_redacted"] is True
    assert payload["raw_credentials_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (email, password, full_name, company, user_id, api_key):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_register_failure_publishes_redacted_error_evidence(monkeypatch, tmp_path):
    email = "maas-auth-register-failed-secret@example.test"
    password = "private-register-password"
    private_detail = "private duplicate email detail"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    req = UserRegisterRequest(email=email, password=password)

    def _register(db, req):
        raise HTTPException(status_code=400, detail=private_detail)

    monkeypatch.setattr(auth_mod.auth_service, "register", _register)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth_mod.register(req, db=SimpleNamespace(), request=request))

    assert exc.value.status_code == 400
    payloads = _payloads(bus, "maas-auth-register")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["stage"] == "register_failed"
    assert payload["status"] == "failed"
    assert payload["http_status_code"] == 400
    assert payload["reason"] == "http_400"
    assert payload["local_db_write"] is False

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (email, password, private_detail):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_login_publishes_redacted_login_evidence(monkeypatch, tmp_path):
    email = "maas-auth-login-secret@example.test"
    password = "private-login-password"
    api_key = "x0t_login_secret_api_key"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    req = UserLoginRequest(email=email, password=password)

    monkeypatch.setattr(auth_mod.auth_service, "login", lambda db, req: api_key)

    result = asyncio.run(auth_mod.login(req, db=SimpleNamespace(), request=request))

    assert result["access_token"] == api_key
    payloads = _payloads(bus, "maas-auth-login")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "maas_auth_login"
    assert payload["service_name"] == "maas-auth-login"
    assert payload["source_alias"] == "maas-auth-login"
    assert payload["layer"] == "api_auth_login_intent"
    assert payload["stage"] == "login_succeeded"
    assert payload["status"] == "success"
    assert payload["request_summary"]["email_hash"] == auth_mod._redacted_sha256_prefix(
        email.lower()
    )
    assert payload["request_summary"]["password_present"] is True
    assert payload["token_issued"] is True
    assert payload["local_db_write"] is True
    assert payload["http_status_code"] == 200
    assert payload["raw_credentials_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (email, password, api_key):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_login_failure_publishes_redacted_error_evidence(monkeypatch, tmp_path):
    email = "maas-auth-login-failed-secret@example.test"
    password = "private-login-password"
    private_detail = "private invalid login detail"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    req = UserLoginRequest(email=email, password=password)

    def _login(db, req):
        raise HTTPException(status_code=401, detail=private_detail)

    monkeypatch.setattr(auth_mod.auth_service, "login", _login)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth_mod.login(req, db=SimpleNamespace(), request=request))

    assert exc.value.status_code == 401
    payloads = _payloads(bus, "maas-auth-login")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["stage"] == "login_failed"
    assert payload["status"] == "failed"
    assert payload["http_status_code"] == 401
    assert payload["reason"] == "http_401"
    assert payload["token_issued"] is False

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (email, password, private_detail):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_rotate_api_key_publishes_redacted_rotation_evidence(monkeypatch, tmp_path):
    user_id = "maas-auth-rotate-user-secret"
    old_api_key_hash = "old-api-key-hash-secret"
    new_api_key = "x0t_rotate_secret_api_key"
    rotated_at = datetime(2026, 5, 30, 12, 0, 0)
    audit_calls = []
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    current_user = SimpleNamespace(
        id=user_id,
        role="user",
        plan="starter",
        api_key_hash=old_api_key_hash,
    )

    monkeypatch.setattr(
        auth_mod.auth_service,
        "rotate_api_key",
        lambda db, user: (new_api_key, rotated_at),
    )
    monkeypatch.setattr(auth_mod, "record_audit_log", lambda *args, **kwargs: audit_calls.append((args, kwargs)))

    result = asyncio.run(
        auth_mod.rotate_api_key(request, current_user=current_user, db=SimpleNamespace())
    )

    assert result == {"api_key": new_api_key, "created_at": rotated_at}
    assert len(audit_calls) == 1
    payloads = _payloads(bus, "maas-auth-api-key-rotation")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "maas_auth_api_key_rotation"
    assert payload["service_name"] == "maas-auth-api-key-rotation"
    assert payload["source_alias"] == "maas-auth-api-key-rotation"
    assert payload["layer"] == "api_auth_credential_rotation"
    assert payload["stage"] == "api_key_rotated"
    assert payload["status"] == "success"
    assert payload["actor_user_id_hash"] == auth_mod._redacted_sha256_prefix(user_id)
    assert payload["previous_api_key_hash_present"] is True
    assert payload["new_api_key_issued"] is True
    assert payload["local_db_write"] is True
    assert payload["audit_recorded"] is True
    assert payload["rotated_at_present"] is True
    assert payload["http_status_code"] == 200
    assert payload["raw_credentials_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (user_id, old_api_key_hash, new_api_key):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_rotate_api_key_failure_publishes_redacted_error_evidence(
    monkeypatch,
    tmp_path,
):
    user_id = "maas-auth-rotate-failed-user-secret"
    old_api_key_hash = "old-api-key-hash-failed-secret"
    private_detail = "private rotate failure detail"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    current_user = SimpleNamespace(
        id=user_id,
        role="user",
        plan="starter",
        api_key_hash=old_api_key_hash,
    )

    def _rotate_api_key(db, user):
        raise RuntimeError(private_detail)

    monkeypatch.setattr(auth_mod.auth_service, "rotate_api_key", _rotate_api_key)

    with pytest.raises(RuntimeError):
        asyncio.run(
            auth_mod.rotate_api_key(
                request,
                current_user=current_user,
                db=SimpleNamespace(),
            )
        )

    payloads = _payloads(bus, "maas-auth-api-key-rotation")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["stage"] == "api_key_rotation_failed"
    assert payload["status"] == "failed"
    assert payload["previous_api_key_hash_present"] is True
    assert payload["new_api_key_issued"] is False
    assert payload["local_db_write"] is False
    assert payload["audit_recorded"] is False
    assert payload["http_status_code"] == 500
    assert payload["reason"] == "RuntimeError"

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (user_id, old_api_key_hash, private_detail):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_admin_promotion_publishes_redacted_privilege_evidence(
    monkeypatch,
    tmp_path,
):
    target_email = "target-admin-secret@example.test"
    admin_id = "admin-actor-secret"
    target_id = "target-user-secret"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    admin_user = SimpleNamespace(id=admin_id, role="admin", plan="enterprise")
    target_user = SimpleNamespace(id=target_id, role="user")
    db = _Db(query_result=target_user)
    audit_calls = []

    monkeypatch.setattr(
        auth_mod,
        "record_audit_log",
        lambda *args, **kwargs: audit_calls.append((args, kwargs)),
    )

    result = asyncio.run(
        auth_mod.make_admin(
            target_email,
            request,
            db=db,
            _admin=admin_user,
        )
    )

    assert result == {"message": f"User {target_email} is now an ADMIN"}
    assert target_user.role == "admin"
    assert db.commit_count == 1
    assert len(audit_calls) == 1
    payloads = _payloads(bus, "maas-auth-admin-promotion")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "maas_auth_admin_promotion"
    assert payload["service_name"] == "maas-auth-admin-promotion"
    assert payload["source_alias"] == "maas-auth-admin-promotion"
    assert payload["layer"] == "api_auth_admin_privilege_control"
    assert payload["stage"] == "admin_promoted"
    assert payload["status"] == "success"
    assert payload["request_summary"]["target_email_hash"] == (
        auth_mod._redacted_sha256_prefix(target_email.lower())
    )
    assert payload["actor_user_id_hash"] == auth_mod._redacted_sha256_prefix(admin_id)
    assert payload["target_user_id_hash"] == auth_mod._redacted_sha256_prefix(target_id)
    assert payload["previous_role"] == "user"
    assert payload["new_role"] == "admin"
    assert payload["local_db_write"] is True
    assert payload["audit_recorded"] is True
    assert payload["privilege_control"] is True
    assert payload["raw_identifiers_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (target_email, admin_id, target_id):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_admin_promotion_missing_target_publishes_redacted_denial(tmp_path):
    target_email = "missing-admin-secret@example.test"
    admin_id = "admin-actor-missing-secret"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    admin_user = SimpleNamespace(id=admin_id, role="admin", plan="enterprise")
    db = _Db(query_result=None)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            auth_mod.make_admin(
                target_email,
                request,
                db=db,
                _admin=admin_user,
            )
        )

    assert exc.value.status_code == 404
    payloads = _payloads(bus, "maas-auth-admin-promotion")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["stage"] == "target_not_found"
    assert payload["status"] == "denied"
    assert payload["http_status_code"] == 404
    assert payload["local_db_write"] is False
    assert payload["audit_recorded"] is False

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (target_email, admin_id):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_bootstrap_admin_success_publishes_redacted_privilege_evidence(
    monkeypatch,
    tmp_path,
):
    bootstrap_token = "bootstrap-token-secret"
    email = "bootstrap-admin-secret@example.test"
    password = "private-bootstrap-password"
    api_key = "x0t_bootstrap_secret_api_key"
    user_id = "bootstrap-admin-user-secret"
    bus = EventBus(str(tmp_path))
    request = _JsonRequest(
        bus,
        headers={"X-Bootstrap-Token": bootstrap_token},
        body={"email": email, "password": password},
    )
    db = _Db(query_result=None)
    user = SimpleNamespace(id=user_id, role="user")
    audit_calls = []

    monkeypatch.setenv("BOOTSTRAP_TOKEN", bootstrap_token)
    monkeypatch.setattr(auth_mod.auth_service, "register", lambda db, req: user)
    monkeypatch.setattr(auth_mod.auth_service, "issued_api_key", lambda user: api_key)
    monkeypatch.setattr(
        auth_mod,
        "record_audit_log",
        lambda *args, **kwargs: audit_calls.append((args, kwargs)),
    )

    result = asyncio.run(auth_mod.bootstrap_admin(request, db=db))

    assert result == {
        "message": f"Bootstrap admin {email} created",
        "api_key": api_key,
    }
    assert user.role == "admin"
    assert db.commit_count == 1
    assert len(audit_calls) == 1
    payloads = _payloads(bus, "maas-auth-bootstrap-admin")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "maas_auth_bootstrap_admin"
    assert payload["service_name"] == "maas-auth-bootstrap-admin"
    assert payload["source_alias"] == "maas-auth-bootstrap-admin"
    assert payload["layer"] == "api_auth_bootstrap_admin_control"
    assert payload["stage"] == "bootstrap_admin_created"
    assert payload["status"] == "success"
    assert payload["request_summary"]["email_hash"] == (
        auth_mod._redacted_sha256_prefix(email.lower())
    )
    assert payload["request_summary"]["password_present"] is True
    assert payload["user_id_hash"] == auth_mod._redacted_sha256_prefix(user_id)
    assert payload["bootstrap_token_configured"] is True
    assert payload["provided_token_present"] is True
    assert payload["existing_admin_present"] is False
    assert payload["token_issued"] is True
    assert payload["local_db_write"] is True
    assert payload["audit_recorded"] is True
    assert payload["privilege_control"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (bootstrap_token, email, password, api_key, user_id):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_bootstrap_admin_invalid_token_publishes_redacted_denial(
    monkeypatch,
    tmp_path,
):
    bootstrap_token = "bootstrap-token-secret"
    provided_token = "wrong-bootstrap-token-secret"
    bus = EventBus(str(tmp_path))
    request = _JsonRequest(bus, headers={"X-Bootstrap-Token": provided_token})

    monkeypatch.setenv("BOOTSTRAP_TOKEN", bootstrap_token)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth_mod.bootstrap_admin(request, db=_Db(query_result=None)))

    assert exc.value.status_code == 403
    payloads = _payloads(bus, "maas-auth-bootstrap-admin")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["stage"] == "bootstrap_token_denied"
    assert payload["status"] == "denied"
    assert payload["bootstrap_token_configured"] is True
    assert payload["provided_token_present"] is True
    assert payload["http_status_code"] == 403
    assert payload["local_db_write"] is False

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (bootstrap_token, provided_token):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_oidc_login_not_configured_publishes_redacted_denial(
    monkeypatch,
    tmp_path,
):
    bus = EventBus(str(tmp_path))
    request = _OidcRequest(bus)
    monkeypatch.setattr(auth_mod.oidc_validator, "issuer", "")
    monkeypatch.setattr(auth_mod.oidc_validator, "client_id", "")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth_mod.login_oidc(request))

    assert exc.value.status_code == 501
    payloads = _payloads(bus, "maas-auth-oidc-login")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "maas_auth_oidc_login"
    assert payload["service_name"] == "maas-auth-oidc-login"
    assert payload["source_alias"] == "maas-auth-oidc-login"
    assert payload["layer"] == "api_auth_oidc_redirect_intent"
    assert payload["stage"] == "oidc_not_configured"
    assert payload["status"] == "denied"
    assert payload["oidc_enabled"] is False
    assert payload["redirect_uri_present"] is False
    assert payload["http_status_code"] == 501
    assert payload["raw_identifiers_redacted"] is True
    assert payload["raw_credentials_redacted"] is True


def test_oidc_login_success_publishes_redacted_redirect_evidence(
    monkeypatch,
    tmp_path,
):
    redirect_uri = "https://app.example.test/auth/callback?secret=redirect-secret"
    bus = EventBus(str(tmp_path))
    request = _OidcRequest(bus, redirect_uri=redirect_uri)
    fake_oauth = _FakeOAuth(redirect_response=SimpleNamespace(status_code=307))
    monkeypatch.setattr(auth_mod.oidc_validator, "issuer", "https://oidc.example.test")
    monkeypatch.setattr(auth_mod.oidc_validator, "client_id", "oidc-client")
    monkeypatch.setattr(auth_mod, "oauth", fake_oauth)

    result = asyncio.run(auth_mod.login_oidc(request))

    assert result.status_code == 307
    assert fake_oauth.oidc.redirect_uri == redirect_uri
    payloads = _payloads(bus, "maas-auth-oidc-login")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["stage"] == "oidc_redirect_created"
    assert payload["status"] == "success"
    assert payload["oidc_enabled"] is True
    assert payload["oauth_available"] is True
    assert payload["redirect_uri_present"] is True
    assert payload["http_status_code"] == 307
    assert payload["read_only"] is True
    assert payload["control_action"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    assert redirect_uri not in serialized
    assert redirect_uri not in raw_log
    assert "redirect-secret" not in serialized
    assert "redirect-secret" not in raw_log


def test_oidc_callback_success_publishes_redacted_session_evidence(
    monkeypatch,
    tmp_path,
):
    email = "oidc-callback-secret@example.test"
    subject = "oidc-subject-secret"
    issuer = "https://oidc-provider-secret.example.test"
    name = "OIDC Private Name"
    user_id = "oidc-existing-user-secret"
    id_token = "private-id-token"
    api_key = "x0t_oidc_secret_api_key"
    session_token = "private-session-token"
    bus = EventBus(str(tmp_path))
    request = _OidcRequest(bus)
    existing_user = SimpleNamespace(
        id=user_id,
        email=email,
        role="user",
        oidc_id=None,
        oidc_provider=None,
    )
    db = _SequenceDb([None, existing_user])
    claims = SimpleNamespace(sub=subject, email=email, name=name, issuer=issuer)

    monkeypatch.setattr(auth_mod.oidc_validator, "issuer", issuer)
    monkeypatch.setattr(auth_mod.oidc_validator, "client_id", "oidc-client")
    monkeypatch.setattr(auth_mod, "oauth", _FakeOAuth(token={"id_token": id_token}))
    monkeypatch.setattr(auth_mod.oidc_validator, "validate", lambda token: claims)
    monkeypatch.setattr(
        auth_mod.auth_service,
        "issue_api_key",
        lambda db, user: api_key,
    )
    monkeypatch.setattr(auth_mod.secrets, "token_urlsafe", lambda _size: session_token)

    result = asyncio.run(auth_mod.auth_callback(request, db=db))

    assert result["message"] == "Authenticated successfully"
    assert result["session_token"] == session_token
    assert result["user"]["api_key"] == api_key
    assert existing_user.oidc_id == subject
    assert existing_user.oidc_provider == issuer
    assert db.commit_count == 1
    assert db.refresh_count == 1
    payloads = _payloads(bus, "maas-auth-oidc-callback")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "maas_auth_oidc_callback"
    assert payload["service_name"] == "maas-auth-oidc-callback"
    assert payload["source_alias"] == "maas-auth-oidc-callback"
    assert payload["layer"] == "api_auth_oidc_callback_control"
    assert payload["stage"] == "oidc_callback_authenticated"
    assert payload["status"] == "success"
    assert payload["id_token_present"] is True
    assert payload["claims_validated"] is True
    assert payload["email_hash"] == auth_mod._redacted_sha256_prefix(email.lower())
    assert payload["oidc_subject_hash"] == auth_mod._redacted_sha256_prefix(subject)
    assert payload["oidc_issuer_hash"] == auth_mod._redacted_sha256_prefix(issuer)
    assert payload["user_id_hash"] == auth_mod._redacted_sha256_prefix(user_id)
    assert payload["existing_user_found"] is True
    assert payload["existing_user_linked"] is True
    assert payload["new_user_created"] is False
    assert payload["api_key_issued"] is True
    assert payload["session_token_issued"] is True
    assert payload["local_db_write"] is True
    assert payload["http_status_code"] == 200
    assert payload["raw_identifiers_redacted"] is True
    assert payload["raw_credentials_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        email,
        subject,
        issuer,
        name,
        user_id,
        id_token,
        api_key,
        session_token,
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_oidc_callback_missing_id_token_publishes_redacted_failure(
    monkeypatch,
    tmp_path,
):
    bus = EventBus(str(tmp_path))
    request = _OidcRequest(bus)
    private_detail = "Missing id_token"

    monkeypatch.setattr(auth_mod.oidc_validator, "issuer", "https://oidc.example.test")
    monkeypatch.setattr(auth_mod.oidc_validator, "client_id", "oidc-client")
    monkeypatch.setattr(auth_mod, "oauth", _FakeOAuth(token={}))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth_mod.auth_callback(request, db=_SequenceDb([])))

    assert exc.value.status_code == 401
    payloads = _payloads(bus, "maas-auth-oidc-callback")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["stage"] == "oidc_callback_failed"
    assert payload["status"] == "failed"
    assert payload["id_token_present"] is False
    assert payload["claims_validated"] is False
    assert payload["api_key_issued"] is False
    assert payload["session_token_issued"] is False
    assert payload["local_db_write"] is False
    assert payload["http_status_code"] == 401
    assert payload["reason"] == "http_400"
    assert payload["raw_credentials_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    assert private_detail not in serialized
    assert private_detail not in raw_log


def test_credential_resolver_api_key_success_publishes_redacted_evidence(
    monkeypatch,
    tmp_path,
):
    raw_api_key = "x0t_resolver_secret_api_key"
    user_id = "credential-resolver-user-secret"
    email = "resolver-secret@example.test"
    bus = EventBus(str(tmp_path))
    request = _JsonRequest(bus, headers={"X-API-Key": raw_api_key})
    user = SimpleNamespace(id=user_id, email=email, role="user", plan="starter")

    monkeypatch.setattr(auth_mod, "find_user_by_api_key", lambda db, key: user)

    result = asyncio.run(
        auth_mod.get_current_user_from_maas(request, db=SimpleNamespace())
    )

    assert result is user
    payloads = _payloads(bus, "maas-auth-credential-resolver")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "maas_auth_credential_resolver"
    assert payload["service_name"] == "maas-auth-credential-resolver"
    assert payload["source_alias"] == "maas-auth-credential-resolver"
    assert payload["layer"] == "api_auth_credential_observed_state"
    assert payload["stage"] == "api_key_authenticated"
    assert payload["status"] == "success"
    assert payload["actor_user_id_hash"] == auth_mod._redacted_sha256_prefix(user_id)
    assert payload["api_key_header_present"] is True
    assert payload["api_key_user_found"] is True
    assert payload["http_status_code"] == 200
    assert payload["observed_state"] is True
    assert payload["read_only"] is True
    assert payload["raw_credentials_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (raw_api_key, user_id, email):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_credential_resolver_failure_publishes_redacted_denial(
    monkeypatch,
    tmp_path,
):
    raw_api_key = "x0t_resolver_denied_secret_api_key"
    bus = EventBus(str(tmp_path))
    request = _JsonRequest(bus, headers={"X-API-Key": raw_api_key})

    monkeypatch.setattr(auth_mod, "find_user_by_api_key", lambda db, key: None)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(auth_mod.get_current_user_from_maas(request, db=SimpleNamespace()))

    assert exc.value.status_code == 401
    payloads = _payloads(bus, "maas-auth-credential-resolver")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["stage"] == "authentication_failed"
    assert payload["status"] == "denied"
    assert payload["api_key_header_present"] is True
    assert payload["api_key_user_found"] is False
    assert payload["http_status_code"] == 401
    assert payload["reason"] == "invalid_credentials"
    assert payload["raw_credentials_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    assert raw_api_key not in serialized
    assert raw_api_key not in raw_log


def test_profile_read_publishes_redacted_observed_state(tmp_path):
    email = "profile-read-secret@example.test"
    user_id = "profile-read-user-secret"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    user = SimpleNamespace(
        id=user_id,
        email=email,
        role="admin",
        plan="enterprise",
        oidc_id="oidc-profile-secret",
    )

    result = asyncio.run(auth_mod.get_my_profile(request, user=user))

    assert result["email"] == email
    assert result["role"] == "admin"
    assert result["oidc_linked"] is True
    payloads = _payloads(bus, "maas-auth-profile-read")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "maas_auth_profile_read"
    assert payload["service_name"] == "maas-auth-profile-read"
    assert payload["layer"] == "api_auth_profile_observed_state"
    assert payload["actor_user_id_hash"] == auth_mod._redacted_sha256_prefix(user_id)
    assert payload["email_hash"] == auth_mod._redacted_sha256_prefix(email.lower())
    assert payload["oidc_linked"] is True
    assert payload["profile_fields_returned"] == [
        "email",
        "role",
        "plan",
        "oidc_linked",
    ]
    assert payload["observed_state"] is True
    assert payload["control_action"] is False

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (email, user_id, "oidc-profile-secret"):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_api_key_list_publishes_redacted_observed_state(tmp_path):
    user_id = "api-key-read-user-secret"
    api_key_hash = "stored-api-key-hash-secret"
    created_at = datetime(2026, 5, 30, 14, 0, 0)
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    user = SimpleNamespace(
        id=user_id,
        role="user",
        plan="starter",
        api_key_hash=api_key_hash,
        created_at=created_at,
    )

    result = asyncio.run(
        auth_mod.list_api_keys(request, current_user=user, db=SimpleNamespace())
    )

    assert result[0]["key_masked"] == f"{api_key_hash[:12]}..."
    payloads = _payloads(bus, "maas-auth-api-key-read")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "maas_auth_api_key_read"
    assert payload["service_name"] == "maas-auth-api-key-read"
    assert payload["layer"] == "api_auth_api_key_observed_state"
    assert payload["actor_user_id_hash"] == auth_mod._redacted_sha256_prefix(user_id)
    assert payload["api_key_hash_present"] is True
    assert payload["masked_keys_returned"] == 1
    assert payload["created_at_present"] is True
    assert payload["observed_state"] is True
    assert payload["raw_credentials_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (user_id, api_key_hash, api_key_hash[:12]):
        assert raw_value not in serialized
        assert raw_value not in raw_log
