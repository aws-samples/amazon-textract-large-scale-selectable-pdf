#!/usr/bin/env python3

from aws_cdk import App
from selectable_pdf_infra.selectable_pdf_stack import SelectablePdfStack

# user parameters
# ---------------
# stack name and description
stack_id = 'SelectablePDF'
stack_desc = 'infrastructure to generate selectable PDF at scale'
# Region
region = 'eu-west-1'
# logging level for the lambda functions
log_level = 'INFO'  #log level for the Lambdas. only INFO is implemented atm.

# stacks to deploy
# ----------------
app = App()

infra_stack = SelectablePdfStack(
    app, 
    construct_id=stack_id, 
    log_level=log_level,
    description=stack_desc,
    env={'region': region},
)

app.synth()
