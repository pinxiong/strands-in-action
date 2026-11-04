"""UC01 - show the OpenTelemetry spans the loop emits by default.

setup_console_exporter() prints each span to stdout, so we can see the
Agent -> Cycle -> LLM / Tool structure without standing up a collector.
"""
import logging

logging.disable(logging.CRITICAL)  # keep the console readable: spans only

from strands import Agent
from strands.models import BedrockModel
from strands.telemetry import StrandsTelemetry
from strands_tools import calculator

StrandsTelemetry().setup_console_exporter()

model = BedrockModel(model_id="amazon.nova-pro-v1:0", region_name="us-east-1")
agent = Agent(tools=[calculator], model=model)
agent("What is the square root of 1764, plus 8?")
