import setuptools

cdk_libs_version = '1.109.0'

with open("README.md") as fp:
    long_description = fp.read()

setuptools.setup(
    name="selectable_pdf_infra",
    version="1.0.0",

    description="infrastructure to convert scanned PDF's into selectable PDF's with AWS",
    long_description=long_description,
    long_description_content_type="text/markdown",

    author="author",

    package_dir={"": "selectable_pdf_infra"},
    packages=setuptools.find_packages(where="selectable_pdf_infra"),

    install_requires=[
        f"aws-cdk.core=={cdk_libs_version}",
        f"aws-cdk.aws_iam=={cdk_libs_version}",
        f"aws-cdk.aws_sqs=={cdk_libs_version}",
        f"aws-cdk.aws_sns=={cdk_libs_version}",
        f"aws-cdk.aws_sns_subscriptions=={cdk_libs_version}",
        f"aws-cdk.aws_s3=={cdk_libs_version}",
        f"aws-cdk.aws_s3_notifications=={cdk_libs_version}",
        f"aws-cdk.aws_events=={cdk_libs_version}",
        f"aws-cdk.aws_events_targets=={cdk_libs_version}",
        f"aws-cdk.aws_lambda_event_sources=={cdk_libs_version}",
        f"aws-cdk.aws_lambda_destinations=={cdk_libs_version}",
        f"aws-cdk.aws_dynamodb=={cdk_libs_version}",
        f"aws-cdk.aws_s3_deployment=={cdk_libs_version}",
        f"aws-cdk.aws_sagemaker=={cdk_libs_version}",
        f"aws-cdk.aws_ecr=={cdk_libs_version}",
        f"aws-cdk.aws_ecr_assets=={cdk_libs_version}",
    ],

    python_requires=">=3.6",

    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT No Attribution License (MIT-0)",
        "Programming Language :: JavaScript",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Utilities",
        "Typing :: Typed",
    ],
)
