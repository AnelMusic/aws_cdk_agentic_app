#!/usr/bin/env python3
import aws_cdk as cdk

from aws_cdk_rag_fargate.aws_cdk_rag_fargate_stack import CombinedFrontendBackendStack


app = cdk.App()

CombinedFrontendBackendStack(app, "CombinedFrontendBackendStack")

app.synth()
