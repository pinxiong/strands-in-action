"""E6: limits are validated up front, before any model call.

Three bad payloads against one agent. Each raises TypeError before the
loop starts: an unknown key, a zero, and a boolean. No Bedrock call is
made in this experiment.
"""
from strands import Agent


def probe(label: str, limits: dict) -> None:
    try:
        agent = Agent()
        agent("hi", limits=limits)
        print(f"[{label}] NO ERROR (unexpected)")
    except TypeError as exc:
        print(f"[{label}] TypeError: {exc}")


def main() -> None:
    probe("unknown key", {"tuns": 3})
    probe("zero", {"turns": 0})
    probe("bool", {"turns": True})


if __name__ == "__main__":
    main()
