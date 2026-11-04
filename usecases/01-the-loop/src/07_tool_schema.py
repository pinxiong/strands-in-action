"""Show what a single tool adds to every model request.

The tool specs travel with each cycle, so the cost of one tool is paid on every
turn, not once. This prints the exact JSON the model sees for `calculator`.

Run:  python src/07_tool_schema.py
"""

import json
from importlib.metadata import version

from strands import Agent
from strands.models import BedrockModel
from strands_tools import calculator

print("SDK_VERSION :", version("strands-agents"))

model = BedrockModel(
    model_id="deepseek.v3.2",
    region_name="us-east-1",
)
agent = Agent(tools=[calculator], model=model, callback_handler=None)

specs = agent.tool_registry.get_all_tool_specs()
print("TOOL_COUNT  :", len(specs))
for spec in specs:
    rendered = json.dumps(spec)
    print(f"TOOL_NAME   : {spec['name']}")
    print("SPEC_CHARS  :", len(rendered))
    print(json.dumps(spec, indent=2))
