#!/usr/bin/env python3

'''
stack_tools.py
--------------

A set of functions and classes to support the deplyment of the stack
'''

# Import modules
# --------------
from aws_cdk import (aws_iam, core)
import jsii

from typing import Dict


# functions
# ---------


# Classes
# -------
# see https://docs.aws.amazon.com/cdk/latest/guide/aspects.html for implementation
@jsii.implements(core.IAspect)
class PermissionsBoundary():
    '''
    '''
    def __init__(self, permissionsBoundaryArn: str):
        '''
        Create a PermissionsBoundary object.

        Examples
        --------
        core.Aspects.of(my_stack).add(PermissionsBoundary(arn:aws:iam::aws:policy/my_policy))

        Arguments
        ---------
        permissionsBoundaryArn
            The policy ARN to be add to roles as permissions boundary

        Returns
        -------
        obj
            An instance of PermissionsBoundary class
        '''
        self.permissionsBoundaryArn = permissionsBoundaryArn

    def visit(self, node: core.IConstruct) -> None:
        '''
        Add the permissions boundaries to the node if this node is a role (CfnRole)
        '''
        if isinstance(node, aws_iam.CfnRole):
            node.add_property_override(
                property_path='PermissionsBoundary', 
                value=self.permissionsBoundaryArn
            )


@jsii.implements(core.IAspect)
class GlobalTagger():
    '''
    '''
    def __init__(self, tags: Dict):
        '''
        Create a Globaltagger object.

        Examples
        --------
        core.Aspects.of(my_stack).add({'stack': 'foo', 'type': 'dev'})

        Arguments
        ---------
        tags
            The policy ARN to be add to roles as permissions boundary

        Returns
        -------
        obj
            An instance of PermissionsBoundary class
        '''
        self.tags = tags

    def visit(self, node: core.IConstruct) -> None:
        '''
        Add the permissions boundaries to each node
        '''
        for key,value in  self.tags.items():
            core.Tags.of(node).add(key, value)





