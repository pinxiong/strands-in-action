"""E4: where bad parameters die.

The decorator builds a Pydantic model from the signature (decorator.py:193,
stored at :117). When a tool call comes in, validate_input runs it
(decorator.py:631 -> :388) and wraps failures into ValueError (:395).
Wrong types fail before the function body runs.
No API call needed.
"""
from strands import tool


@tool
def count_lines(path: str, extension: str = ".py") -> int:
    """Count lines under a directory.

    Args:
        path: directory to scan
        extension: file extension filter, defaults to .py
    """
    return 0


def main() -> None:
    meta = count_lines._metadata
    print("INPUT_MODEL :", meta.input_model.__name__)

    ok = meta.validate_input({"path": "/tmp", "extension": ".py"})
    print("VALID       :", ok)

    try:
        meta.validate_input({"path": "/tmp", "extension": 123})
    except ValueError as e:
        # decorator.py:395 wraps the Pydantic error into a ValueError
        print("REJECTED    :", str(e).splitlines()[1].strip())

    try:
        meta.validate_input({})
    except ValueError as e:
        print("MISSING     :", str(e).splitlines()[1].strip())


if __name__ == "__main__":
    main()
