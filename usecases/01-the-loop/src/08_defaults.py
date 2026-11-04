"""Print the region and model the provider resolves, without calling Bedrock.

Constructing BedrockModel does not call the API, so this is the cheapest way to
see what the defaults actually are on this machine.

Run:  python src/08_defaults.py
"""

import boto3

import strands.models.bedrock as bedrock
from strands.models import BedrockModel

print("BOTO_REGION             :", boto3.Session().region_name)
print("DEFAULT_BEDROCK_REGION  :", bedrock.DEFAULT_BEDROCK_REGION)
print("DEFAULT_BEDROCK_MODEL_ID:", bedrock.DEFAULT_BEDROCK_MODEL_ID)
print("PREFIXED_VARIANT        :", bedrock._DEFAULT_BEDROCK_MODEL_ID.format("us"))

model = BedrockModel()
print("RESOLVED_MODEL_ID       :", model.config["model_id"])
print("CLIENT_REGION           :", model.client.meta.region_name)
