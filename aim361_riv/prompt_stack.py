from aws_cdk import Stack, CfnOutput, aws_bedrock as bedrock

from constructs import Construct


class PromptStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Configure model inference parameters
        inference_config_prop = (
            bedrock.CfnPrompt.PromptModelInferenceConfigurationProperty(
                max_tokens=200, temperature=0
            )
        )

        inference_config = bedrock.CfnPrompt.PromptInferenceConfigurationProperty(
            text=inference_config_prop
        )

        # Configure prompt template
        template_config = bedrock.CfnPrompt.PromptTemplateConfigurationProperty(
            text=bedrock.CfnPrompt.TextPromptTemplateConfigurationProperty(
                text="Generate a JSON object about this text",
            )
        )

        # Create prompt variant
        prompt_variant = bedrock.CfnPrompt.PromptVariantProperty(
            name="defaultVariant",
            template_type="TEXT",
            inference_configuration=inference_config,
            template_configuration=template_config,
        )

        # Create the prompt resource
        extraction_prompt = bedrock.CfnPrompt(
            self,
            "extraction-prompt",
            name="extraction-prompt",
            default_variant="defaultVariant",
            variants=[prompt_variant],
        )

        # Output the prompt name
        CfnOutput(
            self,
            "prompt-arn",
            export_name="promptArn",
            value=extraction_prompt.attr_arn,
        )
