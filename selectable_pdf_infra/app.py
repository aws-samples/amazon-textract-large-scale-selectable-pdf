#!/usr/bin/env python3

from aws_cdk import core
from selectable_pdf_infra.selectable_pdf_stack import SelectablePdfStack
from selectable_pdf_infra.stack_tools import GlobalTagger


# user parameters
# ---------------
# stack name and description
stack_id = 'selectablePDF'
stack_desc = 'infrastructure for the large scale selectable PDF application'
# Region
region = "eu-west-1"

# stacks to deploy
# ----------------
app = core.App()

# deploy the backend infrastructure
log_level = 'INFO'  #log level for the Lambdas. only INFO is implemented atm.

infra_stack = SelectablePdfStack(
    app, 
    construct_id=stack_id, 
    log_level=log_level,
    description=stack_desc,
    env={"region": region},
)
