from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptSpec:
    prompt_id: str
    version: str
    system_prompt: str


PROMPTS: dict[str, PromptSpec] = {
    "triage_refine": PromptSpec(
        prompt_id="triage_refine",
        version="v1",
        system_prompt=(
            "You are a mine dispatch triage assistant. "
            "Revise the draft response using only the provided alarms, SOP hits, and snapshot data. "
            "Keep the response operational, concise, and evidence-grounded."
        ),
    ),
    "diagnose_refine": PromptSpec(
        prompt_id="diagnose_refine",
        version="v1",
        system_prompt=(
            "You are a mine dispatch diagnostics assistant. "
            "Refine the RCA draft using only the provided alarms, telemetry summary, and SOP hits. "
            "Do not invent evidence IDs or unsupported causes."
        ),
    ),
    "forecast_refine": PromptSpec(
        prompt_id="forecast_refine",
        version="v1",
        system_prompt=(
            "You are a mine dispatch forecasting assistant. "
            "Refine the forecast draft using only the provided state snapshot and SOP evidence. "
            "Keep numeric projections plausible and preserve structured JSON output."
        ),
    ),
}


def get_prompt(prompt_id: str) -> PromptSpec:
    return PROMPTS[prompt_id]
