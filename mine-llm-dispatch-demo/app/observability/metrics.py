from __future__ import annotations

from collections import Counter
from typing import Any

from app.models.proposal import IncidentWorkflowResponse


def summarize_metrics(audit_events: list[dict[str, Any]], workflows: list[IncidentWorkflowResponse]) -> dict[str, Any]:
    llm_status_counter: Counter[str] = Counter()
    prompt_usage_counter: Counter[str] = Counter()
    embedding_status_counter: Counter[str] = Counter()
    duplicate_telemetry_count = 0
    duplicate_alarm_count = 0
    gatekeeper_pass_count = 0
    gatekeeper_fail_count = 0
    workflow_run_count = 0
    rag_top_scores: list[float] = []
    rag_hit_counts: list[int] = []

    for event in audit_events:
        event_type = event.get("event_type")
        actor = event.get("actor")
        meta = event.get("meta", {})
        payload = event.get("payload", {})

        if event_type == "workflow_run":
            workflow_run_count += 1
        if event_type == "telemetry_ingest" and meta.get("result") == "duplicate":
            duplicate_telemetry_count += 1
        if event_type == "alarm_ingest" and meta.get("result") == "duplicate":
            duplicate_alarm_count += 1
        if actor == "gatekeeper_agent_v1":
            if payload.get("status") == "PASS":
                gatekeeper_pass_count += 1
            elif payload.get("status") == "FAIL":
                gatekeeper_fail_count += 1
        llm_status = meta.get("llm_status")
        if llm_status:
            llm_status_counter[str(llm_status)] += 1
        prompt_id = meta.get("prompt_id")
        prompt_version = meta.get("prompt_version")
        if prompt_id and prompt_version:
            prompt_usage_counter[f"{prompt_id}:{prompt_version}"] += 1
        embedding_status = meta.get("embedding_status")
        if embedding_status:
            embedding_status_counter[str(embedding_status)] += 1
        rag_top_score = meta.get("rag_top_score")
        rag_hit_count = meta.get("rag_hit_count")
        if rag_top_score is not None:
            rag_top_scores.append(float(rag_top_score))
        if rag_hit_count is not None:
            rag_hit_counts.append(int(rag_hit_count))

    llm_attempt_statuses = {
        key: value
        for key, value in llm_status_counter.items()
        if key not in {"disabled_mock", "not_applicable"}
    }
    llm_attempt_count = sum(llm_attempt_statuses.values())
    llm_fallback_count = sum(
        value
        for key, value in llm_attempt_statuses.items()
        if key in {"unavailable_configuration", "sdk_missing", "not_live", "request_error", "invalid_json", "validation_error"}
    )
    gatekeeper_total = gatekeeper_pass_count + gatekeeper_fail_count
    workflow_status_counter = Counter(record.approval_status for record in workflows)

    return {
        "workflow_run_count": workflow_run_count,
        "workflow_pending_approval_count": workflow_status_counter.get("PENDING_APPROVAL", 0),
        "workflow_approved_count": workflow_status_counter.get("APPROVED", 0),
        "workflow_rejected_count": workflow_status_counter.get("REJECTED", 0),
        "workflow_failed_gatekeeper_count": workflow_status_counter.get("FAILED_GATEKEEPER", 0),
        "gatekeeper_pass_count": gatekeeper_pass_count,
        "gatekeeper_fail_count": gatekeeper_fail_count,
        "gatekeeper_reject_rate": round(gatekeeper_fail_count / gatekeeper_total, 4) if gatekeeper_total else 0.0,
        "llm_status_counts": dict(llm_status_counter),
        "llm_attempt_count": llm_attempt_count,
        "llm_fallback_count": llm_fallback_count,
        "llm_fallback_rate": round(llm_fallback_count / llm_attempt_count, 4) if llm_attempt_count else 0.0,
        "prompt_usage_counts": dict(prompt_usage_counter),
        "embedding_status_counts": dict(embedding_status_counter),
        "rag_avg_top_score": round(sum(rag_top_scores) / len(rag_top_scores), 4) if rag_top_scores else 0.0,
        "rag_avg_hit_count": round(sum(rag_hit_counts) / len(rag_hit_counts), 4) if rag_hit_counts else 0.0,
        "duplicate_telemetry_count": duplicate_telemetry_count,
        "duplicate_alarm_count": duplicate_alarm_count,
    }
