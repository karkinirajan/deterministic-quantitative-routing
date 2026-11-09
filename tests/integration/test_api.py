import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.api import main as api
from src.api.models import MAX_ITERATIONS, MAX_QUERY_LENGTH
from tests.conftest import orchestrator_for

client = TestClient(api.app)


@pytest.fixture
def use(monkeypatch):
    """Replace the API's orchestrator."""

    def _use(orchestrator):
        monkeypatch.setattr(api, "orchestrator", orchestrator)

    return _use


class TestHealth:
    def test_health(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "version": "1.0.0"}


class TestQuery:
    def test_a_plain_query(self):
        response = client.post("/query", json={"query": "Show me the trend of BTC"})
        assert response.status_code == 200
        body = response.json()
        assert len(body["regime"]) == 100
        assert set(body["regime"]) <= {0, 1}
        assert body["blueprint"]["description"] == "Trend following strategy using SMA Crossover (20/50)"
        assert body["provenance"].startswith("Executed via Quant Library Orchestrator")
        assert body["iterations"] is None and body["initial_regime"] is None and body["stop_reason"] is None

    def test_a_recursive_query(self):
        response = client.post("/query", json={"query": "trend", "recursive_stability": True, "max_iterations": 20})
        assert response.status_code == 200
        body = response.json()
        assert body["stop_reason"] in {"stable", "oscillation", "max_iterations"}
        assert 1 <= body["iterations"] <= 20
        assert len(body["initial_regime"]) == 100 and len(body["regime"]) == 100

    def test_max_iterations_is_passed_on(self, use, monkeypatch, alternating):
        orchestrator = orchestrator_for("alt", alt=alternating)
        seen = {}
        original = orchestrator.run_until_stable
        monkeypatch.setattr(orchestrator, "run_until_stable", lambda q, max_iterations: seen.update(q=q, n=max_iterations) or original(q, max_iterations))
        use(orchestrator)
        client.post("/query", json={"query": "hello", "recursive_stability": True, "max_iterations": 7})
        assert seen == {"q": "hello", "n": 7}

    def test_the_recursive_flag_off_runs_a_single_pass(self, use, monkeypatch, alternating):
        orchestrator = orchestrator_for("alt", alt=alternating)
        monkeypatch.setattr(orchestrator, "run_until_stable", lambda *a, **k: pytest.fail("must not loop"))
        use(orchestrator)
        assert client.post("/query", json={"query": "x"}).status_code == 200

    def test_the_default_max_iterations_is_ten(self, use, monkeypatch, alternating):
        orchestrator = orchestrator_for("alt", alt=alternating)
        seen = []
        original = orchestrator.run_until_stable
        monkeypatch.setattr(orchestrator, "run_until_stable", lambda q, max_iterations: seen.append(max_iterations) or original(q, max_iterations))
        use(orchestrator)
        client.post("/query", json={"query": "x", "recursive_stability": True})
        assert seen == [10]

    def test_an_average_composition_returns_a_binary_regime(self, use):
        a = lambda p: np.tile([0, 1], len(p) // 2)  # noqa: E731
        b = lambda p: np.tile([0, 0, 1, 1], len(p) // 4)  # noqa: E731
        c = lambda p: np.tile([1, 1, 1, 0], len(p) // 4)  # noqa: E731
        use(orchestrator_for("a", "b", "c", composition="AVERAGE", a=a, b=b, c=c))
        response = client.post("/query", json={"query": "x"})
        assert response.status_code == 200
        regime = response.json()["regime"]
        assert set(regime) == {0, 1} and all(type(v) is int for v in regime)

    def test_a_sum_composition_returns_counts(self, use, ones):
        use(orchestrator_for("a", "b", composition="SUM", a=ones, b=ones))
        assert set(client.post("/query", json={"query": "x"}).json()["regime"]) == {2}


class TestRequestValidation:
    def post(self, **body):
        return client.post("/query", json=body)

    def test_a_query_is_required(self):
        assert client.post("/query", json={}).status_code == 422

    def test_an_empty_query_is_refused(self):
        assert self.post(query="").status_code == 422
        assert self.post(query="a").status_code == 200

    def test_the_query_length_is_limited(self):
        assert MAX_QUERY_LENGTH == 2000
        assert self.post(query="a" * 2000).status_code == 200
        assert self.post(query="a" * 2001).status_code == 422

    def test_max_iterations_is_limited_to_1_through_100(self):
        assert MAX_ITERATIONS == 100
        for value, expected in [(0, 422), (-1, 422), (1, 200), (100, 200), (101, 422), (10**9, 422)]:
            assert self.post(query="trend", recursive_stability=True, max_iterations=value).status_code == expected, value

    def test_unknown_fields_are_refused(self):
        assert self.post(query="x", admin=True).status_code == 422

    @pytest.mark.parametrize("body", [{"query": 5}, {"query": ["x"]}, {"query": "x", "recursive_stability": "maybe"}, {"query": "x", "max_iterations": "ten"}])
    def test_wrong_types_are_refused(self, body):
        assert client.post("/query", json=body).status_code == 422

    def test_a_body_that_is_not_json_is_refused(self):
        assert client.post("/query", content="query=x", headers={"content-type": "text/plain"}).status_code == 422
        assert client.post("/query", content="{", headers={"content-type": "application/json"}).status_code == 422

    def test_only_post_is_allowed(self):
        assert client.get("/query").status_code == 405


class TestErrors:
    def test_a_blueprint_that_cannot_run_is_a_422_that_says_why(self, use):
        use(orchestrator_for("no_such_function"))
        response = client.post("/query", json={"query": "x"})
        assert response.status_code == 422
        assert "'no_such_function' is not in the registry" in response.json()["detail"]

    def test_a_bad_argument_is_a_422(self, use):
        use(orchestrator_for(("sma_crossover", {"short_window": -4})))
        response = client.post("/query", json={"query": "x"})
        assert response.status_code == 422 and "short_window" in response.json()["detail"]

    def test_a_non_binary_recursive_request_is_a_422(self, use, ones):
        use(orchestrator_for("a", "b", composition="SUM", a=ones, b=ones))
        response = client.post("/query", json={"query": "x", "recursive_stability": True})
        assert response.status_code == 422 and "binary" in response.json()["detail"]

    def test_an_internal_failure_is_a_500_that_reveals_nothing(self, use):
        def boom(prices):
            raise ZeroDivisionError("secret detail at /srv/app/internal.py")

        use(orchestrator_for("boom", boom=boom))
        response = client.post("/query", json={"query": "x"})
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal error"}
        assert "secret" not in response.text

    def test_a_hook_failure_is_a_500_that_reveals_nothing(self, use):
        use(orchestrator_for("bad", bad=lambda p: np.full(len(p), 7)))
        response = client.post("/query", json={"query": "x"})
        assert response.status_code == 500 and response.json() == {"detail": "Internal error"}

    def test_the_failure_is_logged(self, use, caplog):
        use(orchestrator_for("bad", bad=lambda p: np.full(len(p), 7)))
        with caplog.at_level("ERROR", logger="uvicorn.error"):
            client.post("/query", json={"query": "x"})
        assert any("query failed" in r.message for r in caplog.records)


class TestWiring:
    def test_the_default_app_uses_the_mock_router(self):
        assert type(api.router).__name__ == "MockSemanticRouter"
        assert api.orchestrator.router is api.router

    def test_the_endpoints_are_plain_functions_so_they_run_in_the_thread_pool(self):
        import inspect

        assert not inspect.iscoroutinefunction(api.query_endpoint)
        assert not inspect.iscoroutinefunction(api.health_check)

    def test_the_openapi_schema_describes_the_response(self):
        schema = client.get("/openapi.json").json()
        ok = schema["paths"]["/query"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
        assert ok["$ref"].endswith("/RegimeResponse")

    def test_the_app_describes_itself(self):
        assert api.app.title == "Quant Library Orchestrator"
        assert api.app.version == "1.0.0"


class TestMain:
    """Running the module directly starts uvicorn; it must listen on loopback unless told otherwise."""

    def run(self, monkeypatch, **env):
        import runpy
        import sys

        import uvicorn

        captured = {}
        monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: captured.update(kwargs))
        for name in ("HOST", "PORT"):
            monkeypatch.delenv(name, raising=False)
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        # run_module warns when the module is already imported; take it out for the run (restored afterwards)
        monkeypatch.delitem(sys.modules, "src.api.main", raising=False)
        runpy.run_module("src.api.main", run_name="__main__")
        return captured

    def test_defaults_to_loopback_on_8000(self, monkeypatch):
        assert self.run(monkeypatch) == {"host": "127.0.0.1", "port": 8000}

    def test_host_and_port_come_from_the_environment(self, monkeypatch):
        assert self.run(monkeypatch, HOST="0.0.0.0", PORT="9100") == {"host": "0.0.0.0", "port": 9100}  # noqa: S104
