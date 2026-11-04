"""Default configuration. Expected to fail: Anthropic models are geo-gated.

Run:  python src/01_default.py
"""

import os
import sys
from importlib.metadata import version

import boto3
import strands
from strands import Agent

print("SDK_VERSION :", version("strands-agents"))
print("BOTO_REGION :", boto3.Session().region_name)
print("AWS_REGION  :", os.environ.get("AWS_REGION", "<unset>"))
print("DEFAULT_MODEL_ID :", strands.models.bedrock.DEFAULT_BEDROCK_MODEL_ID)
print("DEFAULT_REGION   :", strands.models.bedrock.DEFAULT_BEDROCK_REGION)
print("-" * 60)

agent = Agent()
result = agent("In one sentence, what is the largest ocean on Earth?")
print("STOP_REASON :", result.stop_reason)
sys.exit(0)
