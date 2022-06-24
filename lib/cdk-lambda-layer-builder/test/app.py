import os
import aws_cdk as cdk
from stack.stacks import BuildLambdaLayerStack


app = cdk.App()
BuildLambdaLayerStack(
    app, 
    "TestLayerBuilder",
)
app.synth()
