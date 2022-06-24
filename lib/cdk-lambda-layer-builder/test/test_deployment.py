import pytest
import boto3
import json
import base64


def test_lambda_with_built_layers():
    lambda_name = 'test-lambda-for-cdk-lambda-layer-builder'
    lambda_client = boto3.client('lambda')
    payload = {'foo': 'bar'}
    response = lambda_client.invoke(
        FunctionName=lambda_name,
        InvocationType='RequestResponse',
        LogType='Tail',
        # Payload=bytes(json.dumps(payload)),
    )
    func_log = base64.b64decode(response['LogResult']).decode()
    func_log_lines = func_log.split('\n')
    ground_truth_lines = [
        'hello from lib1.tools.func!',
        'hello from lib2.tools.func!',
        '[0 1 2 3]'
    ]
    assert ground_truth_lines==func_log_lines[1:-3]
