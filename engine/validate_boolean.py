from __future__ import annotations

import re


class BooleanSyntaxError(ValueError):
    """Raised when a Boolean search expression is malformed."""


OPERATORS = {"AND", "OR", "NOT"}
BINARY_OPERATORS = {"AND", "OR"}


def _tokenize(query: str) -> list[str]:
    pattern = re.compile(r'"[^"]*"|\(|\)|\bAND\b|\bOR\b|\bNOT\b|[^\s()]+', re.IGNORECASE)
    return [match.group(0) for match in pattern.finditer(query)]


def validate_boolean(query: str) -> bool:
    """Validate balanced quotes/parentheses and basic Boolean operator placement."""
    if not query or not query.strip():
        raise BooleanSyntaxError("Boolean query is empty")
    if query.count('"') % 2:
        raise BooleanSyntaxError("Unbalanced quotes in Boolean query")

    tokens = _tokenize(query)
    if not tokens:
        raise BooleanSyntaxError("Boolean query is empty")

    balance = 0
    previous: str | None = None
    for index, token in enumerate(tokens):
        upper = token.upper()
        if token == "(":
            balance += 1
            if previous and previous not in {"AND", "OR", "NOT", "("}:
                raise BooleanSyntaxError(f"Missing operator before '(' at token {index + 1}")
        elif token == ")":
            balance -= 1
            if balance < 0:
                raise BooleanSyntaxError(f"Unexpected ')' at token {index + 1}")
            if previous in BINARY_OPERATORS or previous in {"NOT", "("}:
                raise BooleanSyntaxError(f"Operator before ')' at token {index + 1}")
        elif upper in OPERATORS:
            if upper in BINARY_OPERATORS and (previous is None or previous in OPERATORS or previous == "("):
                raise BooleanSyntaxError(f"{upper} cannot appear at token {index + 1}")
            if upper == "NOT" and previous not in {None, "AND", "OR", "NOT", "("}:
                raise BooleanSyntaxError(f"NOT must follow an operator or '(' at token {index + 1}")
        else:
            if previous == ")":
                raise BooleanSyntaxError(f"Missing operator after ')' at token {index + 1}")
        previous = upper if upper in OPERATORS else token

    if balance:
        raise BooleanSyntaxError("Unbalanced parentheses in Boolean query")
    if previous in BINARY_OPERATORS or previous == "NOT":
        raise BooleanSyntaxError("Boolean query cannot end with an operator")
    return True


