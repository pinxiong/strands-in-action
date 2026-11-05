"""E2: which docstring sections survive into the description.

The decorator (decorator.py:235-283) cuts the Args section with a hand-rolled
line scanner but keeps Returns / Raises / Examples. This script proves what
the model is shown, without calling any API.
"""
from strands import tool


@tool
def full_docstring(path: str) -> int:
    """Count lines under a directory.

    Args:
        path: this sentence describes the argument and should NOT appear in the description

    Returns:
        this Returns sentence SHOULD still be visible to the model

    Raises:
        this Raises sentence SHOULD still be visible to the model

    Examples:
        this Examples sentence SHOULD still be visible to the model
    """
    return 0


@tool
def bare_docstring(path: str) -> int:
    """Count lines under a directory.

    Args:
        path: directory to scan
    """
    return 0


def main() -> None:
    print("=== full docstring -> description ===")
    print(full_docstring.tool_spec["description"])
    print()
    print("=== bare docstring -> description ===")
    print(bare_docstring.tool_spec["description"])


if __name__ == "__main__":
    main()
