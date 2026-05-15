---
name: python-typing-patterns
description: "Type hint patterns for this repo: Protocol, TypeVar, TypedDict, Literal, Final, and strict ty usage. Triggers on: type hints, typing, TypeVar, Protocol, Generic, TypedDict, ty check."
compatibility: "Python 3.13+, Pydantic v2, uv run ty check src/ tests/."
---

# Python Typing Patterns

Use modern, precise type hints in this codebase.

## Non-Negotiables

- Prefer `X | Y` over `Union[X, Y]`.
- Prefer built-in generics: `list[T]`, `dict[K, V]`, `tuple[T, ...]`.
- Avoid `Any`; use concrete types, `Protocol`, `TypeVar`, or `object`.
- Prefer `Sequence[T]` and `Mapping[K, V]` for read-only collection contracts.
- Do not use `@runtime_checkable` in domain ports.
- Do not use runtime `isinstance(..., Protocol)` checks in normal app code.
- In this repo, keep OAuth provider result typing invariant: `OAuthResultT` (no covariance unless explicitly required).
- For protocol compliance tests, prefer structural assignment with concrete instances.
- Do not ignore `ty` errors in `src/` or `tests/`.

## Core Patterns

### Variables, Functions, Optional

```python
name: str = "Alice"
items: list[str] = ["a", "b"]


def greet(name: str, times: int = 1) -> str:
    return f"Hello, {name}!" * times


def find(user_id: int) -> User | None:
    return db.get(user_id)
```

### Collections

```python
from collections.abc import Mapping, Sequence


def process(items: Sequence[str]) -> list[str]:
    return [item.upper() for item in items]


def lookup(data: Mapping[str, int], key: str) -> int:
    return data.get(key, 0)
```

### TypedDict

```python
from typing import TypedDict


class UserDict(TypedDict):
    id: int
    name: str
    email: str | None
```

### Protocol and Callable

```python
from collections.abc import Callable
from typing import Protocol


class Handler(Protocol):
    def __call__(self, data: str, *, verbose: bool = False) -> int:
        ...


def register(callback: Callable[[str], None]) -> None:
    ...
```

### TypeVar and Generics

```python
from typing import TypeVar

T = TypeVar("T")


def first(items: list[T]) -> T | None:
    return items[0] if items else None
```

### Protocol Compliance Test Pattern

```python
def test_example_publisher_implements_protocol() -> None:
    publisher = ExamplePublisher(...)
    _: VideoPublisher = publisher
```

## Anti-Patterns

- Using `typing.List`, `typing.Dict`, or `typing.Optional` in new code.
- Returning `dict[str, Any]` across domain boundaries.
- Adding `@runtime_checkable` to domain protocols.
- Using `isinstance(x, SomeProtocol)` in runtime business logic.
- Using `create_autospec` as the primary proof of protocol conformance.
- Introducing covariance in OAuth result type variables without a concrete need.

## Exit Checks

- `uv run ruff format src/ tests/`
- `uv run ruff check src/ tests/`
- `uv run ty check src/ tests/`
- `uv run pytest`
