from typing import Any, TypedDict


class GrowthState(TypedDict, total=False):
    run_id: str
    vendor_id: str | None
    input: dict[str, Any]
    research: dict[str, Any]
    qualification: dict[str, Any]
    sales: dict[str, Any]
    marketing: dict[str, Any]
    validated_output: dict[str, Any]
    reasoning_trace: list[str]
    errors: list[str]
    retry_count: int
