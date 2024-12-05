import os
import boto3
import json
from aws_lambda_powertools import Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

tracer = Tracer()

bedrock = boto3.client(service_name="bedrock-runtime")
s3 = boto3.client("s3")


@tracer.capture_method
def get_file_content(bucket, key):
    # Load file content
    tracer.put_annotation(key="FileName", value=key)
    file_obj = s3.get_object(Bucket=bucket, Key=key)
    return file_obj["Body"].read().decode("utf-8")


@tracer.capture_method
def analyze_document(file_content):

    # Construct prompt ID from environment variables with proper string formatting
    prompt_arn = os.getenv("promptArn")
    prompt_version = os.getenv("promptVersion")

    prompt_id = f"{prompt_arn}:{prompt_version}"

    response = bedrock.converse(
        modelId=prompt_id, promptVariables={"text_input": {"text": file_content}}
    )

    tracer.put_metadata(key="BedrockResponse", value=response)

    for content in response["output"]["message"]["content"]:
        if isinstance(content, dict) and "toolUse" in content:
            tool_use = content["toolUse"]
            if tool_use["name"] == "print_document_metadata":
                return tool_use["input"]

    raise ValueError("Invalid JSON Generated.")


@tracer.capture_method
def apply_guardrail(file_content, json_entities):
    guardrail_response = bedrock.apply_guardrail(
        guardrailIdentifier=os.getenv("guardrailId"),
        guardrailVersion=os.getenv("guardrailVersion"),
        source="INPUT",
        content=[
            {
                "text": {
                    "text": file_content,
                    "qualifiers": ["grounding_source", "guard_content"],
                }
            },
            {
                "text": {
                    "text": "Generate a JSON object indicating the language used, the document type, and a summary.",
                    "qualifiers": ["query"],
                }
            },
            {
                "text": {
                    "text": json.dumps(json_entities, indent=4),
                    "qualifiers": ["guard_content"],
                }
            },
        ],
    )
    tracer.put_annotation(key="GuardrailAction", value=guardrail_response["action"])
    return guardrail_response["action"]


@tracer.capture_lambda_handler
def lambda_handler(event, context: LambdaContext):
    bucket = None
    key = None
    try:
        bucket = event["body"]["detail"]["bucket"]["name"]
        key = event["body"]["detail"]["object"]["key"]

        # Get file content and analyze
        file_content = get_file_content(bucket, key)
        json_entities = analyze_document(file_content)

        guardrail_action = apply_guardrail(file_content, json_entities)

        if guardrail_action == "GUARDRAIL_INTERVENED":
            return {
                "status": guardrail_action,
                "bucket": bucket,
                "key": key,
                "llm-response": json_entities,
            }

        return {
            "status": "SUCCEEDED",
            "bucket": bucket,
            "key": key,
            "llm-response": json_entities,
        }

    except ValueError as ve:
        return {
            "status": "FAILED",
            "error": str(ve),
            "bucket": bucket,
            "key": key,
        }
    except Exception as e:
        return {
            "status": "FAILED",
            "error": f"An unexpected error occurred: {str(e)}",
            "bucket": bucket,
            "key": key,
        }
