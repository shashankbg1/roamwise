"""The interface every model backend implements.

Agents never talk to a vendor SDK directly. They ask a provider to produce a typed result for a
named task, which keeps the agents testable and lets the backend be swapped with one setting.
"""

from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

Task = Literal["research_brief", "plan", "critique"]


class LLMError(RuntimeError):
    """The model backend could not produce a usable answer."""


class LLMProvider(Protocol):
    name: str

    async def generate(
        self,
        *,
        task: Task,
        system: str,
        prompt: str,
        schema: type[T],
        context: dict[str, Any],
    ) -> T:
        """Return an instance of `schema` for the given task.

        `system` and `prompt` are what a real model reads. `context` carries the same
        information as Python objects, which the rule-based mock uses instead of reading text.
        """
        ...
