"""Route selection.

'auto' maps task classes to model tiers. Kept deliberately simple and
explicit; benchmark results (see evals/) drive any future refinement.
"""

from backend.core.llm.schemas import Route

AUTO_ROUTE_BY_TASK: dict[str, Route] = {
    "analysis": Route.STRONG,
    "extraction": Route.FAST,
    "verification_sample": Route.FAST,
    "translation": Route.FAST,
}


def resolve_auto(task: str) -> Route:
    return AUTO_ROUTE_BY_TASK.get(task, Route.STRONG)
