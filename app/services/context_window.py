"""Sliding window context truncation for token-efficient LLM calls.

RULE: Never send full conversation history to ANY LLM call.
Always truncate to the last N messages and reconstruct context
from the recovered memory object.
"""

from __future__ import annotations

from typing import Any


def truncate_messages(
    messages: list[dict[str, Any]],
    window_size: int = 3,
    preserve_system: bool = True,
) -> list[dict[str, Any]]:
    """Return a sliding window of the most recent messages.

    Args:
        messages: Full conversation history as list of {"role": ..., "content": ...}.
        window_size: Number of recent user/assistant messages to keep (default 3).
        preserve_system: If True, always keep the first system message at index 0.

    Returns:
        Truncated message list: [system_msg?] + messages[-window_size:]
    """
    if not messages:
        return []

    system_msgs: list[dict[str, Any]] = []
    non_system: list[dict[str, Any]] = []

    for msg in messages:
        if msg.get("role") == "system" and preserve_system:
            system_msgs.append(msg)
        else:
            non_system.append(msg)

    # Keep only the first system message (if present) + last N non-system messages
    truncated = system_msgs[:1] + non_system[-window_size:]
    return truncated


def estimate_token_count(text: str) -> int:
    """Rough token estimate: ~4 characters per token for English text."""
    return max(1, len(text) // 4)


def truncate_to_budget(
    messages: list[dict[str, Any]],
    max_tokens: int = 2000,
    preserve_system: bool = True,
) -> list[dict[str, Any]]:
    """Truncate messages to fit within a token budget.

    Starts from the most recent message and works backward until the budget
    is exhausted. System message is always included if preserve_system is True.
    """
    if not messages:
        return []

    system_msgs: list[dict[str, Any]] = []
    non_system: list[dict[str, Any]] = []

    for msg in messages:
        if msg.get("role") == "system" and preserve_system:
            system_msgs.append(msg)
        else:
            non_system.append(msg)

    budget = max_tokens
    if system_msgs:
        budget -= estimate_token_count(system_msgs[0].get("content", ""))

    result: list[dict[str, Any]] = []
    for msg in reversed(non_system):
        cost = estimate_token_count(msg.get("content", ""))
        if budget - cost < 0 and result:
            break
        budget -= cost
        result.append(msg)

    result.reverse()
    return system_msgs[:1] + result
