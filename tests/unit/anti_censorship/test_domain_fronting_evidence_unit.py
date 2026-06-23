from src.anti_censorship.domain_fronting import (
    CDNProvider,
    DomainFrontingClient,
    FrontingConfig,
    create_fronting_client,
)
from src.coordination.events import EventBus, EventType


def _payloads(bus: EventBus) -> list[dict]:
    return [
        event.data
        for event in bus.get_event_history(
            source_agent="anti-censorship-domain-fronting-client",
            limit=30,
        )
    ]


class _Response:
    status_code = 200
    headers = {"X-Secret": "SECRET-RESPONSE-HEADER"}
    text = "SECRET-RESPONSE-BODY"


class _Session:
    def __init__(self, response=None, error=None):
        self.response = response or _Response()
        self.error = error
        self.closed = False

    def request(self, _method, _url, **_kwargs):
        if self.error is not None:
            raise self.error
        return self.response

    def close(self):
        self.closed = True


def test_request_publishes_redacted_local_evidence(tmp_path):
    bus = EventBus(str(tmp_path))
    client = DomainFrontingClient(
        FrontingConfig(
            event_bus=bus,
            max_retries=1,
            user_agent="SECRET-USER-AGENT",
        )
    )
    client._get_session = lambda _provider, _target_host: _Session()  # type: ignore[method-assign]

    response = client.request(
        "GET",
        "https://secret-target.example/path?token=SECRET",
        headers={"X-Secret": "SECRET-REQUEST-HEADER"},
    )
    payloads = _payloads(bus)
    request_payload = [p for p in payloads if p["operation"] == "request"][0]
    text = repr(payloads)

    assert response.status_code == 200
    assert request_payload["status"] == "request_completed"
    assert request_payload["service_name"] == "anti-censorship-domain-fronting-client"
    assert request_payload["layer"] == "anti_censorship_domain_fronting_local_evidence"
    assert request_payload["provider"] == CDNProvider.CLOUDFLARE.value
    assert request_payload["url_hash"]
    assert request_payload["target_host_hash"]
    assert request_payload["raw_url_redacted"] is True
    assert request_payload["raw_target_host_redacted"] is True
    assert request_payload["raw_request_kwargs_redacted"] is True
    assert request_payload["raw_response_headers_redacted"] is True
    assert request_payload["dataplane_confirmed"] is False
    assert request_payload["dpi_bypass_confirmed"] is False
    assert request_payload["bypass_confirmed"] is False
    assert request_payload["external_dpi_tested"] is False
    assert request_payload["service_identity"]["raw_identity_redacted"] is True
    assert "secret-target.example" not in text
    assert "SECRET-REQUEST-HEADER" not in text
    assert "SECRET-RESPONSE-HEADER" not in text
    assert "SECRET-RESPONSE-BODY" not in text
    assert "SECRET-USER-AGENT" not in text


def test_request_failure_publishes_failed_event_without_url_or_error(tmp_path):
    bus = EventBus(str(tmp_path))
    client = DomainFrontingClient(
        FrontingConfig(event_bus=bus, max_retries=1)
    )
    client._get_session = (  # type: ignore[method-assign]
        lambda _provider, _target_host: _Session(error=RuntimeError("SECRET-FAIL"))
    )

    try:
        client.request("POST", "https://secret-fail.example/path")
        assert False, "Expected ConnectionError"
    except ConnectionError:
        pass

    failed_events = bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="anti-censorship-domain-fronting-client",
        limit=10,
    )

    assert len(failed_events) == 1
    payload = failed_events[0].data
    text = repr(payload)
    assert payload["operation"] == "request"
    assert payload["status"] == "request_failed"
    assert payload["error"]["type"] == "RuntimeError"
    assert payload["raw_errors_redacted"] is True
    assert "secret-fail.example" not in text
    assert "SECRET-FAIL" not in text


def test_stats_close_and_factory_publish_redacted_config(tmp_path):
    bus = EventBus(str(tmp_path))
    client = create_fronting_client(
        provider="cloudflare",
        target_host="secret-host.example",
        front_domain="secret-front.example",
        event_bus=bus,
        user_agent="SECRET-UA",
    )
    client._sessions[CDNProvider.CLOUDFLARE] = _Session()

    stats = client.get_stats()
    client.close()
    payloads = _payloads(bus)
    text = repr(payloads)

    assert stats["config"]["provider"] == CDNProvider.CLOUDFLARE.value
    assert [payload["operation"] for payload in payloads] == [
        "initialize",
        "get_stats",
        "close",
    ]
    assert payloads[0]["config"]["target_host_present"] is True
    assert payloads[0]["config"]["front_domain_present"] is True
    assert payloads[0]["config"]["raw_target_host_redacted"] is True
    assert payloads[0]["config"]["raw_front_domain_redacted"] is True
    assert payloads[1]["active_provider_count"] == 0
    assert payloads[2]["closed_session_count"] == 1
    assert "secret-host.example" not in text
    assert "secret-front.example" not in text
    assert "SECRET-UA" not in text
