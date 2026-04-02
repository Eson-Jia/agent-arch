from pathlib import Path

from app.embeddings.providers import HttpEmbeddingProvider, HashEmbeddingProvider
from app.eval.offline_quality import run_offline_evaluation
from app.llm.client import LLMClient


class _FailingMessages:
    def create(self, **_kwargs):
        raise RuntimeError("boom")


class _FailingClient:
    messages = _FailingMessages()


def test_llm_client_circuit_breaker_opens_after_repeated_failures():
    client = LLMClient(
        provider="anthropic",
        model="test-model",
        api_key=None,
        strategy="prefer_live",
        failure_threshold=2,
        cooldown_seconds=60,
    )
    client._live = True
    client._client = _FailingClient()

    assert client.generate_json(system_prompt="x", user_prompt="y") is None
    assert client.generate_json(system_prompt="x", user_prompt="y") is None
    assert client.last_outcome_reason == "circuit_open"
    assert client.is_live is False


def test_http_embedding_provider_falls_back_to_hash(monkeypatch):
    fallback = HashEmbeddingProvider(dims=8)
    provider = HttpEmbeddingProvider(
        api_url="https://invalid.local/embeddings",
        api_key=None,
        model="test-embedding",
        timeout_seconds=1,
        fallback=fallback,
    )

    def _raise(*_args, **_kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(provider._client, "post", _raise)
    vector = provider.embed("road obstacle reroute")
    assert len(vector) == 8
    assert provider.last_outcome_reason == "request_error"


def test_offline_evaluation_cases_pass():
    project_root = Path(__file__).resolve().parents[1]
    result = run_offline_evaluation(project_root / "eval" / "cases" / "workflow_cases.json")
    assert result["case_count"] == 2
    assert result["pass_count"] == 2
    assert result["blocked_route_avoidance_rate"] == 1.0
