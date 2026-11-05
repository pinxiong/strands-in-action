"""E5: one MCP client, one stdio server, one agent.

Spawns mcp_server.py as a subprocess, lists its tools, and lets the agent
call one. Runs against deepseek.v3.2 on Bedrock (us-east-1).
"""
import os

from mcp import StdioServerParameters, stdio_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

HERE = os.path.dirname(os.path.abspath(__file__))
PYTHON = os.path.join(HERE, "..", "..", "..", ".venv", "bin", "python")

client = MCPClient(
    lambda: stdio_client(
        StdioServerParameters(command=PYTHON, args=[os.path.join(HERE, "mcp_server.py")])
    )
)


def main() -> None:
    model = BedrockModel(model_id="deepseek.v3.2", region_name="us-east-1")
    with client:
        tools = client.list_tools_sync()
        print("MCP_TOOLS   :", [t.tool_spec["name"] for t in tools])
        print("TOOL_ORIGIN :", type(tools[0]).__name__)

        agent = Agent(model=model, tools=tools)
        result = agent("How many words are in this sentence: 'the quick brown fox jumps over the lazy dog'?")
        print("ANSWER      :", result.message["content"][0]["text"].replace("\n", " ")[:200])
        print("CYCLES      :", result.metrics.cycle_count)
        used = [
            block["toolUse"]["name"]
            for msg in agent.messages
            for block in msg.get("content", [])
            if "toolUse" in block
        ]
        print("TOOLS_USED  :", used)


if __name__ == "__main__":
    main()
