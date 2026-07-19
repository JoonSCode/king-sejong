from __future__ import annotations

from typing import assert_never

from discord_contract_types import ControlContractError, JsonObject, JsonValue


def object_value(value: JsonValue, field: str) -> JsonObject:
    match value:
        case dict():
            return value
        case str() | int() | float() | bool() | None | list():
            raise ControlContractError("malformed_input", f"{field} must be an object")
        case unreachable:
            assert_never(unreachable)


def text_value(value: JsonValue, field: str) -> str:
    match value:
        case str() if value:
            return value
        case str() | int() | float() | bool() | None | list() | dict():
            raise ControlContractError("malformed_input", f"{field} must be non-empty text")
        case unreachable:
            assert_never(unreachable)


def text_set(value: JsonValue, field: str) -> frozenset[str]:
    match value:
        case list():
            return frozenset(text_value(item, field) for item in value)
        case str() | int() | float() | bool() | None | dict():
            raise ControlContractError("malformed_input", f"{field} must be an array")
        case unreachable:
            assert_never(unreachable)


def text_tuple(value: JsonValue, field: str) -> tuple[str, ...]:
    match value:
        case list():
            return tuple(text_value(item, field) for item in value)
        case str() | int() | float() | bool() | None | dict():
            raise ControlContractError("malformed_input", f"{field} must be an array")
        case unreachable:
            assert_never(unreachable)


def positive_integer(value: JsonValue, field: str) -> int:
    match value:
        case bool():
            raise ControlContractError("malformed_input", f"{field} must be an integer")
        case int() if value > 0:
            return value
        case int() | str() | float() | None | list() | dict():
            raise ControlContractError("malformed_input", f"{field} must be a positive integer")
        case unreachable:
            assert_never(unreachable)


def boolean_value(value: JsonValue, field: str) -> bool:
    match value:
        case bool():
            return value
        case str() | int() | float() | None | list() | dict():
            raise ControlContractError("malformed_input", f"{field} must be a boolean")
        case unreachable:
            assert_never(unreachable)


def exact_fields(value: JsonObject, expected: frozenset[str], field: str) -> None:
    if set(value) != expected:
        raise ControlContractError("malformed_input", f"{field} fields do not match the versioned contract")
