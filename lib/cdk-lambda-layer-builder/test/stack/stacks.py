from aws_cdk import (
    Stack,
    aws_lambda,
    Duration,
    CfnOutput
)
from constructs import Construct
from cdk_lambda_layer_builder.constructs import BuildPyLayerAsset

class BuildLambdaLayerStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        '''
        '''
        super().__init__(scope, construct_id, **kwargs)

        # create the pipy layer
        pypi_layer_asset = BuildPyLayerAsset.from_pypi(self, 'PyPiLayerAsset',
            pypi_requirements=['numpy'],
            py_runtime=aws_lambda.Runtime.PYTHON_3_8,
        )
        pypi_layer = aws_lambda.LayerVersion(
            self,
            id='PyPiLayer',
            code=aws_lambda.Code.from_bucket(pypi_layer_asset.asset_bucket, pypi_layer_asset.asset_key),
            compatible_runtimes=[aws_lambda.Runtime.PYTHON_3_8],
            description ='PyPi python modules'
        )

        # create a Lambda layer with two custom python modules
        module_layer_asset = BuildPyLayerAsset.from_modules(self, 'ModuleLayerAsset',
            local_module_dirs=['lib/lib1','lib/lib2'],
            py_runtime=aws_lambda.Runtime.PYTHON_3_8,
        )
        module_layer = aws_lambda.LayerVersion(
            self,
            id='ModuleLayer',
            code=aws_lambda.Code.from_bucket(module_layer_asset.asset_bucket, module_layer_asset.asset_key),
            compatible_runtimes=[aws_lambda.Runtime.PYTHON_3_8],
            description ='custom python modules lib1, lib2'
        )

        # create a dummy lambda function
        test_function = aws_lambda.Function(
            self,
            id='test',
            function_name='test-lambda-for-cdk-lambda-layer-builder',
            runtime=aws_lambda.Runtime.PYTHON_3_8,
            handler='main.lambda_handler',
            code=aws_lambda.Code.from_asset('lambda_code'),
            timeout=Duration.seconds(60),
            layers=[pypi_layer, module_layer],
            retry_attempts=0,
            memory_size=128,  #128MB
        )

        # outputs
        output_prefix = construct_id
        CfnOutput(
            self,
            id=f'TestLambda',
            value=test_function.function_name,
            description='test lambda',
            export_name=f'{output_prefix}TestLambda',
        )
