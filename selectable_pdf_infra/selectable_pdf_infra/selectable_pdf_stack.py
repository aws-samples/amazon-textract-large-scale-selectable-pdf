# load modules
# ------------
from aws_cdk import (
    aws_iam,
    aws_s3,
    aws_lambda,
    aws_lambda_event_sources,
    aws_sns,
    aws_sqs,
    aws_sns_subscriptions,
    aws_dynamodb,
    core
)

import os
import subprocess
import pathlib


# Module environment variables
# ----------------------------
CURRENT_FILEPATH = pathlib.Path(__file__).absolute()
CURRENT_DIRPATH = CURRENT_FILEPATH.parent.absolute()
LAMBDA_DIRPATH = CURRENT_DIRPATH.parent.joinpath('lambda')
LAMBDA_LAYER_DIRPATH = CURRENT_DIRPATH.parent.joinpath('lambda_layer')
LIB_DIRPATH = CURRENT_DIRPATH.parent.parent.joinpath('lib')


# classes
# -------
class SelectablePdfStack(core.Stack):

    def __init__(
        self, 
        scope: core.Construct, 
        construct_id: str,
        log_level: str,
        **kwargs
    ) -> None:
        '''
        '''
        super().__init__(scope, construct_id, **kwargs)

        # bucket for the original PDF. They might not be searchable, i.e. they 
        # are not made of characters, just images (e.g. scanned documents)
        doc_bucket = aws_s3.Bucket(
            self,
            id='InputDocuments',
            removal_policy=core.RemovalPolicy.DESTROY, #kept if not empty
        )
        processed_bucket = aws_s3.Bucket(
            self,
            id='ProcessedDocuments',
            removal_policy=core.RemovalPolicy.DESTROY, #kept if not empty
        )

        # create the DynamoDB tables. We create N tables:
        # 1. A table to store the info about documents processing
        ddb_documents_table = aws_dynamodb.Table(
            self,
            id='Documents',
            partition_key=aws_dynamodb.Attribute(
                name='document_id', type=aws_dynamodb.AttributeType.STRING
            ),
            sort_key=aws_dynamodb.Attribute(
                name='document_name', type=aws_dynamodb.AttributeType.STRING
            ),
            billing_mode=aws_dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        # SNS topic for Textract and role to use it. The role is used by textract to publish 
        # its status (i.e. success or fail). Textract processing can be long, especially in a 
        # busy the queue! Therefore we set the assume role timeout to 6 hours
        textract_job_topic = aws_sns.Topic(self, id='textract-job-status')
        assume_role_timeout = 6 * 3600
        sns_publish_role = aws_iam.Role(
            self,
            id='SnsPublishRole',
            assumed_by=aws_iam.ServicePrincipal('textract.amazonaws.com'),
            max_session_duration=core.Duration.seconds(assume_role_timeout),
        )
        sns_publish_role.add_to_policy(
            statement=aws_iam.PolicyStatement(
                sid='SnsPublishRight',
                effect=aws_iam.Effect.ALLOW,
                resources=[textract_job_topic.topic_arn],
                actions=['sns:Publish'],
            )
        )

        # Create the lambda layers
        textract_layer = aws_lambda.LayerVersion(
            self,
            id='TextracttoolsV101',
            code=aws_lambda.Code.from_asset(self.build_textracttools_layer()),
            compatible_runtimes=[aws_lambda.Runtime.PYTHON_3_8],
            description ='contains TextractTools module'
        )
        pypi_layer = aws_lambda.LayerVersion(
            self,
            id='pypimodules',
            code=aws_lambda.Code.from_asset(self.build_pypi_layer()),
            compatible_runtimes=[aws_lambda.Runtime.PYTHON_3_8],
            description ='contains various modules from pypi: PyMuPdf'
        )

        # lambda function starting textract. The lambda is triggered with a S3 PUT 
        # notification
        lambda_timeout_sec = 1 * 60  #1 minute 
        start_textract_lambda = aws_lambda.Function(
            self,
            id='StartTextract',
            runtime=aws_lambda.Runtime.PYTHON_3_8,
            handler='main.lambda_handler',
            code=aws_lambda.Code.asset(os.path.join(LAMBDA_DIRPATH, 'start_textract')),
            timeout=core.Duration.seconds(lambda_timeout_sec),
            environment={
                'LOG_LEVEL': log_level,
                'SNS_TOPIC_ARN': textract_job_topic.topic_arn,
                'SNS_ROLE_ARN': sns_publish_role.role_arn,
                'DDB_DOCUMENTS_TABLE': ddb_documents_table.table_name,
                # 'TEXTRACT_BUCKET': processed_bucket.bucket_name
            },
            retry_attempts=0,
            memory_size=128,  #128MB
        )

        # add the required policies to the default role creation with the lambda 
        # start_textract_lambda
        managed_policies = [
            'AmazonTextractFullAccess',
            'AmazonS3FullAccess',  
            'AmazonDynamoDBFullAccess'
        ]
        for policy in managed_policies:
            start_textract_lambda.role.add_managed_policy(
                aws_iam.ManagedPolicy.from_aws_managed_policy_name(policy)
            )
        # set the trigger: S3 PUT on doc_bucket
        start_textract_lambda.add_event_source(
            source=aws_lambda_event_sources.S3EventSource(
                bucket=doc_bucket, 
                events=[aws_s3.EventType.OBJECT_CREATED_PUT], 
                filters=[aws_s3.NotificationKeyFilter(prefix=None, suffix='.pdf')]
            )
        )

        # Lambda getting the textract results from S3 and feeding textract output 
        # status to a SQS for future faning
        
        sqs_visibility_timeout_sec = 10 * 60
        dlq_processed_textracted_queue_sqs = aws_sqs.Queue(self, id='DlqProcessedTextractQueue')
        processed_textracted_queue_sqs = aws_sqs.Queue(
            self,
            id='ProcessedTextractQueue',
            visibility_timeout=core.Duration.seconds(sqs_visibility_timeout_sec),
            dead_letter_queue=aws_sqs.DeadLetterQueue(
                max_receive_count=1, 
                queue=dlq_processed_textracted_queue_sqs
            )
        )
        lambda_timeout_sec = 5 * 60
        process_textract_lambda = aws_lambda.Function(
            self,
            id='ProcessTextract',
            runtime=aws_lambda.Runtime.PYTHON_3_8,
            handler='main.lambda_handler',
            code=aws_lambda.Code.asset(os.path.join(LAMBDA_DIRPATH, 'process_textract')),
            layers=[textract_layer],
            timeout=core.Duration.seconds(lambda_timeout_sec),
            environment={
                'LOG_LEVEL': log_level,
                'REGION': self.region,
                'DDB_DOCUMENTS_TABLE': ddb_documents_table.table_name,
                'TEXTRACT_BUCKET': processed_bucket.bucket_name,
                'TEXTRACT_RES_QUEUE_URL': processed_textracted_queue_sqs.queue_url
            },
            retry_attempts=0, 
            memory_size=4048,
        )
        # add the required policies to the default role create with the lambda
        managed_policies = [
            'AmazonTextractFullAccess',
            'AmazonS3FullAccess', 
            'AmazonDynamoDBFullAccess', 
            'AmazonSQSFullAccess'
        ]
        for policy in managed_policies:
            process_textract_lambda.role.add_managed_policy(
                aws_iam.ManagedPolicy.from_aws_managed_policy_name(policy)
            )
        # set the trigger
        textract_job_topic.add_subscription(
            aws_sns_subscriptions.LambdaSubscription(process_textract_lambda)
        )

        # Lambda function turning a scanned PDF (i.e. a PDF where we cannot select 
        # text) into a searchable PDF (i.e. a PDF where we can select text). This function 
        # received message from sqs, therefore its timeout MUST be smaller than the 
        # visibility timeout of the source SQS, otherwise, cyclic call!!.
        lambda_timeout_sec = sqs_visibility_timeout_sec-1 #second
        selectable_pdf_lambda = aws_lambda.Function(
            self,
            id='SelectablePdf',
            runtime=aws_lambda.Runtime.PYTHON_3_8,
            handler='LambdaSqs::handleRequest',
            code=aws_lambda.Code.asset(self.build_selectable_pdf_lib()),
            timeout=core.Duration.seconds(lambda_timeout_sec),
            environment={
                'DDB_DOCUMENTS_TABLE': ddb_documents_table.table_name,
                'OUTPUT_BUCKET': processed_bucket.bucket_name,
                'LOG_LEVEL': 'INFO',
                'ADD_WORD_BBOX': '0',
                'SHOW_CHARACTER': '0'

            },
            retry_attempts=0,
            memory_size=4048,  # 4GB to get a big CPU with the Lambda. Code is CPU intensive
        )
        # add the required policies to the default role creation with the lambda
        managed_policies = ['AmazonS3FullAccess']
        for policy in managed_policies:
            selectable_pdf_lambda.role.add_managed_policy(
                aws_iam.ManagedPolicy.from_aws_managed_policy_name(policy)
            )
        # add the SQS trigger
        selectable_pdf_lambda.add_event_source(
            source=aws_lambda_event_sources.SqsEventSource(
                queue=processed_textracted_queue_sqs,
                batch_size=1,
            )
        )

        # Outputs
        core.CfnOutput(
            self,
            id='DocumentInputBucket',
            value=doc_bucket.bucket_name,
            description='Bucket where to load the PDFs',
            export_name='DocumentInputBucket',
        )
        core.CfnOutput(
            self,
            id='DocumentOutputBucket',
            value=processed_bucket.bucket_name,
            description='Bucket where the processed PDFs and the intermediary files are stored',
            export_name='DocumentOutputBucket',
        )
        core.CfnOutput(
            self,
            id='ProcessingLogsDynamoDB',
            value=ddb_documents_table.table_name,
            description='Processing logs',
            export_name='ProcessingLogsDynamoDB',
        )


    @staticmethod
    def build_textracttools_layer() -> str:
        '''
        Build the textracttools Python module into a wheel then package it into 
        a zip-file which can be deploy as a AWS Lambda layer. The layer is build 
        within a container.

        Usage
        -----
        layer_zipfile = self.build_textracttools_layer()

        Arguments
        ---------
        None

        Returns
        -------
        layer_zippath
            Path to the layer zipfile.
        '''
        cwd = os.path.abspath(os.getcwd())
        textracttools_dirpath = os.path.join(LIB_DIRPATH,'textracttools')
        os.chdir(textracttools_dirpath)
        subprocess.run(['python', 'setup.py', 'sdist', 'bdist_wheel'], capture_output=True)
        layerbuilder_dirpath = os.path.join(LAMBDA_LAYER_DIRPATH,'textracttools_py38')
        os.chdir(layerbuilder_dirpath)
        subprocess.run(['./createlayer.sh','3.8'], capture_output=True)
        layer_zippath = os.path.join(layerbuilder_dirpath, 'textracttools_py38.zip')
        os.chdir(cwd)

        return layer_zippath


    @staticmethod
    def build_pypi_layer() -> str:
        '''
        Build the pypi layer which contains any module which can be installed from pypi.

        Usage
        -----
        layer_zipfile = self.build_pypi_layer()

        Arguments
        ---------
        None

        Returns
        -------
        layer_zippath
            Path to the layer zipfile.
        '''
        cwd = os.path.abspath(os.getcwd())
        layerbuilder_dirpath = os.path.join(LAMBDA_LAYER_DIRPATH,'pypi_py38')
        os.chdir(layerbuilder_dirpath)
        subprocess.run(['./createlayer.sh','3.8'], capture_output=True)
        layer_zippath = os.path.join(layerbuilder_dirpath, 'pypi_py38.zip')
        os.chdir(cwd)
        return layer_zippath

    
    @staticmethod
    def build_selectable_pdf_lib() -> str:
        '''
        Build the Java library SearchablePDF. the *.jar generated by the build is 
        then used in a lambda function. Maven, Java and the JAVA SDK must be available 
        for the build

        Usage
        -----
        layer_zipfile = self.build_textracttools_layer()

        Arguments
        ---------
        None

        Returns
        -------
        jarpath
            Path to the jarfile.
        '''
        cwd = os.path.abspath(os.getcwd())
        lib_dir = os.path.join(LAMBDA_DIRPATH, 'selectablePDF')
        os.chdir(lib_dir)
        subprocess.run(['mvn', 'package'], capture_output=True)
        jarpath = os.path.join(lib_dir, 'target', 'selectable-pdf-1.0.jar')
        os.chdir(cwd)
        return jarpath