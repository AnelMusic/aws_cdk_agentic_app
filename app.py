#!/usr/bin/env python3
import aws_cdk as cdk

from aws_cdk_agent_stack.aws_cdk_agent_stack import CombinedFrontendBackendStack


app = cdk.App()

CombinedFrontendBackendStack(app, "CombinedFrontendBackendStack")

app.synth()
