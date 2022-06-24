import setuptools

requirements = [
    'aws-cdk-lib',
    'boto3',
    'pytest',
]

with open('README.md') as fp:
    long_description = fp.read()

setuptools.setup(
    name='cdk_lambda_layer_builder',
    version='1.0.0',

    description='cdk constructs to build Python Lambda layer with minimum requirements on the user side',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Marcel Vonlanthen',
    email='vonlanth@amazon.com',
    packages=['cdk_lambda_layer_builder'],
    install_requires=requirements,
    python_requires='>=3.6',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT No Attribution License (MIT-0)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Topic :: Software Development :: Code Generators',
        'Topic :: Utilities',
        'Typing :: Typed',
    ],
)