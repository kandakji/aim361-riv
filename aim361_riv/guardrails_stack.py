from aws_cdk import Stack, aws_bedrock as bedrock, CfnOutput

from constructs import Construct


class GuardrailsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        contextual_grounding_config = (
            bedrock.CfnGuardrail.ContextualGroundingPolicyConfigProperty(
                filters_config=[
                    bedrock.CfnGuardrail.ContextualGroundingFilterConfigProperty(
                        threshold=0.5, type="GROUNDING"
                    )
                ]
            )
        )

        content_policy_config = bedrock.CfnGuardrail.ContentPolicyConfigProperty(
            filters_config=[
                bedrock.CfnGuardrail.ContentFilterConfigProperty(
                    input_strength="HIGH", output_strength="HIGH", type="HATE"
                )
            ]
        )

        extraction_guardrail = bedrock.CfnGuardrail(
            self,
            "extraction_guardrail",
            blocked_input_messaging="Blocked by guardrail",
            blocked_outputs_messaging="Blocked by guardrail",
            name="extraction_guardrail",
            contextual_grounding_policy_config=contextual_grounding_config,
            content_policy_config=content_policy_config,
        )

        extraction_guardrail_version = bedrock.CfnGuardrailVersion(
            self,
            "extraction_guardrail-version",
            guardrail_identifier=extraction_guardrail.attr_guardrail_id,
        )

        CfnOutput(
            self,
            "guardrail-id",
            export_name="guardrailId",
            value=extraction_guardrail.attr_guardrail_id,
        )
        CfnOutput(
            self,
            "guardrail-version",
            export_name="guardrailVersion",
            value=extraction_guardrail_version.attr_version,
        )
