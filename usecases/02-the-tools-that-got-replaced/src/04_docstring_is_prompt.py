"""E3: your docstring is a prompt.

Same function, two docstrings. One neutral, one carrying a restriction.
The model reads the restriction and changes its decision.
Runs against deepseek.v3.2 on Bedrock (us-east-1).
"""
from strands import Agent, tool
from strands.models import BedrockModel

QUESTION = "What is 199950 cents in dollars? Give me the exact amount."


def make_agent(docstring: str) -> Agent:
    def impl(cents: int) -> str:
        return f"${cents / 100:.2f}"

    impl.__name__ = "format_price"
    impl.__doc__ = docstring
    wrapped = tool(impl)

    model = BedrockModel(model_id="deepseek.v3.2", region_name="us-east-1")
    return Agent(model=model, tools=[wrapped])


NEUTRAL = "Format a price given in cents as a dollar string."
RESTRICTED = (
    "Format a price given in cents as a dollar string. "
    "Do NOT use this for amounts over 10000 cents; it is inaccurate for large amounts."
)


def probe(label: str, docstring: str) -> None:
    agent = make_agent(docstring)
    result = agent(QUESTION)
    text = result.message["content"][0]["text"]
    used_tool = any(
        "toolUse" in block for msg in agent.messages for block in msg.get("content", [])
    )
    print(f"=== {label} ===")
    print("TOOL_CALLED :", used_tool)
    print("CYCLES      :", result.metrics.cycle_count)
    print("ANSWER      :", text.replace("\n", " ")[:300])
    print()


def main() -> None:
    probe("NEUTRAL docstring", NEUTRAL)
    probe("RESTRICTED docstring", RESTRICTED)


if __name__ == "__main__":
    main()
