from aws_cdk import (
    # Duration,
    Stack,
    Duration,
    aws_s3 as s3,
    RemovalPolicy,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_bedrock as bedrock,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_dynamodb as dynamodb,
    aws_sns as sns,
    aws_sns_subscriptions as subscriptions,
    CfnOutput,
    Fn,
)
from constructs import Construct
from aws_solutions_constructs.aws_s3_stepfunctions import S3ToStepfunctions


class AutomationStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        input_bucket = s3.Bucket(
            self,
            "input-bucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.RETAIN,
            enforce_ssl=True,
            event_bridge_enabled=True,
        )

        model = bedrock.FoundationModel.from_foundation_model_id(
            self,
            "model",
            bedrock.FoundationModelIdentifier.ANTHROPIC_CLAUDE_3_HAIKU_20240307_V1_0,
        )

        bedrock_lambda = lambda_.Function(
            self,
            "bedrock-lambda",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset(
                "lambdas/bedrock",
                bundling={
                    "image": lambda_.Runtime.PYTHON_3_13.bundling_image,
                    "command": [
                        "bash",
                        "-c",
                        "pip install --no-cache -Ur requirements.txt -t /asset-output && cp -au . /asset-output",
                    ],
                },
            ),
            timeout=Duration.minutes(10),
            tracing=lambda_.Tracing.ACTIVE,
            environment={
                "modelId": model.model_id,
                "guardrailId": Fn.import_value("guardrailId"),
                "guardrailVersion": Fn.import_value("guardrailVersion"),
                "promptArn": Fn.import_value("promptArn"),
                "promptVersion": "1",
            },
        )

        bedrock_lambda.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonBedrockFullAccess")
        )

        bedrock_lambda.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3ReadOnlyAccess")
        )

        dynamodb_table = dynamodb.TableV2(
            self,
            "metadata-table",
            partition_key=dynamodb.Attribute(
                name="id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="language", type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        sns_topic = sns.Topic(self, "human-in-the-loop-topic")

        generation_task = tasks.LambdaInvoke(
            self,
            "Generate Metadata",
            lambda_function=bedrock_lambda,
            payload=sfn.TaskInput.from_object(
                {
                    "body": sfn.JsonPath.entire_payload,
                }
            ),
            result_path="$.generation",
        )

        dynamodb_task = tasks.DynamoPutItem(
            self,
            "Store Results",
            table=dynamodb_table,
            item={
                "id": tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.generation.Payload.key")
                ),
                "status": tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.generation.Payload.status")
                ),
                "llm_response": tasks.DynamoAttributeValue.map_from_json_path(
                    "$.generation.Payload.llm-response"
                ),
                "document_type": tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at(
                        "$.generation.Payload.llm-response.document_type"
                    )
                ),
                "language": tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.generation.Payload.llm-response.language")
                ),
                "summary": tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.generation.Payload.llm-response.summary")
                ),
            },
            result_path=sfn.JsonPath.DISCARD,
        )

        sns_message = sfn.JsonPath.format(
            """Hello Human,
                
                This notification is to inform you that LLM metadata generation for the file {} has triggered one of our guardrails.

                Please validate and take the appropriate action.
                """,
            sfn.JsonPath.string_at("$.generation.Payload.key"),
        )

        HIL_task = tasks.SnsPublish(
            self,
            "Notify Human",
            topic=sns_topic,
            message=sfn.TaskInput.from_text(sns_message),
            result_path=sfn.JsonPath.DISCARD,
            subject="RIV2024 AIM361: Guardrail Intervened",
        )

        step_function_def = sfn.DefinitionBody.from_chainable(
            generation_task.next(
                sfn.Choice(self, "Success?")
                .when(
                    sfn.Condition.string_equals(
                        "$.generation.Payload.status", "SUCCEEDED"
                    ),
                    dynamodb_task,
                )
                .when(
                    sfn.Condition.string_equals(
                        "$.generation.Payload.status", "GUARDRAIL_INTERVENED"
                    ),
                    HIL_task.next(dynamodb_task),
                )
                .otherwise(
                    sfn.Fail(self, "Failed", error="$.generation.Payload.error")
                ),
            )
        )

        step_function = S3ToStepfunctions(
            self,
            "step_function",
            existing_bucket_obj=input_bucket,
            state_machine_props=sfn.StateMachineProps(
                definition_body=step_function_def,
                tracing_enabled=True,
            ),
        )

        CfnOutput(self, "input-bucket-name", value=input_bucket.bucket_name)
