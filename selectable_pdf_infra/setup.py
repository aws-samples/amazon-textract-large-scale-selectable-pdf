import setuptools
import pathlib

CURRENT_FILEPATH = pathlib.Path(__file__).absolute()
CURRENT_DIRPATH = CURRENT_FILEPATH.parent.absolute()
LIB_DIRPATH = CURRENT_DIRPATH.parent.joinpath('lib')


with open('README.md') as fp:
    long_description = fp.read()

setuptools.setup(
    name='selectable_pdf_infra',
    version='2.1.0',
    description='infrastructure to convert scanned PDF\'s into selectable PDF\'s with AWS',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Marcel Vonlanthen',
    email='vonlanth@amazon.com',
    package_dir={'': 'selectable_pdf_infra'},
    packages=setuptools.find_packages(where='selectable_pdf_infra'),
    install_requires=[
        'wheel',
        'boto3',
        f'aws-cdk-lib>=2.8', 
        f'cdk_lambda_layer_builder @ file://localhost/{str(LIB_DIRPATH.joinpath("cdk-lambda-layer-builder"))}#egg=cdk_lambda_layer_builder'
    ],
    python_requires='>=3.6',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT No Attribution License (MIT-0)',
        'Programming Language :: JavaScript',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Software Development :: Code Generators',
        'Topic :: Utilities',
        'Typing :: Typed',
    ],
)
