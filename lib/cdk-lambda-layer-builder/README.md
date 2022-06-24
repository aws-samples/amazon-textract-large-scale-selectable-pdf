 # cdk-lambda-layer-builder

 A collection of cdk constructs to build Python Lambda layer with minimum requirements
  on the user side, e.g. no docker, bash or zip cli has to be available on the user machine.


## Requirements
* AWS CLI: installed and configure
* Python>=3.6
* AWS CDK >=2.X

This construct works on Linux, will very likely on MacOS and should work on Windows.

## Installation
You  need to install `cdk-lambda-layer-builder` in the python environment you intent 
to use to build your stack. In the folder of this `README.md`, install the module with
```bash
$ pip install . --upgrade
```

## Usage
Here is a full example for creating a Lambda layer with two modules available on 
[pypi](https://pypi.org/). The modules are [numpy](https://pypi.org/project/numpy/) 
and [requests](https://pypi.org/project/requests/):
```python
from aws_cdk import Stack, aws_lambda, Duration
from constructs import Construct
from cdk_lambda_layer_builder.constructs import BuildPyLayerAsset

class BuildLambdaLayerStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        '''
        '''
        super().__init__(scope, construct_id, **kwargs)

        # create the pipy layer
        pypi_layer_asset = BuildPyLayerAsset.from_pypi(self, 'PyPiLayerAsset',
            pypi_requirements=['numpy', 'requests'],
            py_runtime=py_version_runtime,
            asset_bucket=asset_bucket
        )
        pypi_layer = aws_lambda.LayerVersion(
            self,
            id='PyPiLayer',
            code=aws_lambda.Code.from_bucket(pypi_layer_asset.asset_bucket, pypi_layer_asset.asset_key),
            compatible_runtimes=[aws_lambda.Runtime.PYTHON_3_8],
            description ='PyPi python modules'
        )

        test_function = aws_lambda.Function(
            self,
            id='test',
            runtime=aws_lambda.Runtime.PYTHON_3_8,
            handler='main.lambda_handler',
            code=aws_lambda.Code.from_asset('lambda_code'),
            timeout=Duration.seconds(60),
            layers=[pypi_layer],
            retry_attempts=0,
        )
```
If you a some custom code, package it into a module (see `cdk_lambda_layer_builder/test/lib/lib1`
as example) and use `BuildPyLayerAsset.from_modules` to build the Lambda layer assets:
```python


from aws_cdk import Stack, aws_lambda, Duration
from constructs import Construct
from cdk_lambda_layer_builder.constructs import BuildPyLayerAsset

class BuildLambdaLayerStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        '''
        '''
        super().__init__(scope, construct_id, **kwargs)

        # create a Lambda layer with two custom python modules
        module_layer_asset = BuildPyLayerAsset.from_modules(self, 'ModuleLayerAsset',
            local_module_dirs=['lib/lib1','lib/lib2'],
            py_runtime=py_version_runtime,
        )
        module_layer = aws_lambda.LayerVersion(
            self,
            id='ModuleLayer',
            code=aws_lambda.Code.from_bucket(module_layer_asset.asset_bucket, module_layer_asset.asset_key),
            compatible_runtimes=[aws_lambda.Runtime.PYTHON_3_8],
            description ='custom python modules lib1, lib2'
        )

        test_function = aws_lambda.Function(
            self,
            id='test',
            runtime=aws_lambda.Runtime.PYTHON_3_8,
            handler='main.lambda_handler',
            code=aws_lambda.Code.from_asset('lambda_code'),
            timeout=Duration.seconds(60),
            layers=[module_layer],
            retry_attempts=0,
        )
```
You can find an example of a full stack creating a lambda function with a pypi layer 
and a custom module layer in `cdk_lambda_layer_builder/test/app.py`.

## Test
Test procedure:
1. clone the repo
2. deploy the CDK test stack `cdk-lambda-layer-builder/test/app.py`
3. Go to `cdk-lambda-layer-builder/test/`
3. Run `pytest test_deployment.py`