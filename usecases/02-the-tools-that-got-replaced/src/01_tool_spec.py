"""E1: what the model actually receives from a plain @tool function.

Prints the ToolSpec (name / description / inputSchema) that the @tool
decorator extracts, without calling any API.
"""
import json

from strands import tool


@tool
def count_lines(path: str, extension: str = ".py") -> int:
    """Count total lines in all files with a given extension under a directory.

    Use this when the user asks how large a codebase or a folder is.

    Args:
        path: directory to scan, relative or absolute
        extension: file extension filter, defaults to .py

    Returns:
        the summed line count across matching files
    """
    import pathlib

    return sum(
        len(p.read_text().splitlines())
        for p in pathlib.Path(path).rglob(f"*{extension}")
        if p.is_file()
    )


def main() -> None:
    spec = count_lines.tool_spec
    print("NAME       :", spec["name"])
    print("DESCRIPTION:")
    print(spec["description"])
    print("---")
    print("INPUT_SCHEMA:")
    print(json.dumps(spec["inputSchema"]["json"], indent=2)[:1600])


if __name__ == "__main__":
    main()
