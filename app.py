#!/usr/bin/env python3
import os

import aws_cdk as cdk

from aim361_riv.automation_stack import AutomationStack
from aim361_riv.guardrails_stack import GuardrailsStack
from aim361_riv.prompt_stack import PromptStack


app = cdk.App()

GuardrailsStack(app, "GuardrailsStack")
PromptStack(app, "PromptStack")
AutomationStack(app, "AutomationStack")

app.synth()
