"""W&B Weave instrumentation.
weave.op() decorators on agent functions handle per-call tracing automatically.
This module handles project init and ground-truth labeling after match resolution.
"""
from __future__ import annotations
import wandb
import weave
from ..config import settings


def init() -> None:
    """Call once at app startup before any agent runs."""
    wandb.login(key=settings.wandb_api_key)
    weave.init(settings.wandb_project)


def label_trace(call_id: str, outcome: str) -> None:
    """Attach ground-truth outcome to a Weave trace after the match resolves.
    outcome: "team_a_win" | "draw" | "team_b_win"
    This is the entry point for building the v2 training dataset.
    """
    # TODO: use weave.Call.feedback() API when available in SDK
    # call = weave.get_call(call_id)
    # call.feedback({"ground_truth": outcome})
    print(f"[weave] label trace {call_id} → {outcome}")
