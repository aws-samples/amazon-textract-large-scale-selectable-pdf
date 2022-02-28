# load modules
# ------------
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_iam,
    aws_s3,
    aws_lambda,
    aws_lambda_event_sources,
    aws_sns,
    aws_sqs,
    aws_sns_subscriptions,
    aws_dynamodb,
    RemovalPolicy,
    Duration,
    CfnOutput
)

import os
import subprocess
import pathlib
import uuid


# Module environment variables
# ----------------------------
CURRENT_FILEPATH = pathlib.Path(__file__).absolute()
CURRENT_DIRPATH = CURRENT_FILEPATH.parent.absolute()
LAMBDA_DIRPATH = CURRENT_DIRPATH.parent.joinpath('lambda')
LAMBDA_LAYER_DIRPATH = CURRENT_DIRPATH.parent.joinpath('lambda_layer')
LIB_DIRPATH = CURRENT_DIRPATH.parent.parent.joinpath('lib')


# classes
# -------
class SelectablePdfStack(Stack):

    def __init__(
        self, 
        scope: Construct, 
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
            removal_policy=RemovalPolicy.DESTROY, #kept if not empty
        )
        processed_bucket = aws_s3.Bucket(
            self,
            id='ProcessedDocuments',
            removal_policy=RemovalPolicy.DESTROY, #kept if not empty
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
            max_session_duration=Duration.seconds(assume_role_timeout),
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
        textracttools_layer = aws_lambda.LayerVersion(
            self,
            id='TextractTools',
            code=aws_lambda.Code.from_asset(self.build_textracttools_layer()),
            compatible_runtimes=[aws_lambda.Runtime.PYTHON_3_8],
            description ='TextractTools python module'
        )
        helpertools_layer = aws_lambda.LayerVersion(
            self,
            id='HelperTools',
            code=aws_lambda.Code.from_asset(self.build_helpertools_layer()),
            compatible_runtimes=[aws_lambda.Runtime.PYTHON_3_8],
            description ='HelperTools and PyMuPdf python modules'
        )

        # lambda function starting textract. The lambda is triggered with a S3 PUT 
        # notification
        lambda_timeout_sec = 1 * 60  #1 minute 
        start_textract_lambda = aws_lambda.Function(
            self,
            id='StartTextract',
            runtime=aws_lambda.Runtime.PYTHON_3_8,
            handler='main.lambda_handler',
            code=aws_lambda.Code.from_asset(os.path.join(LAMBDA_DIRPATH, 'start_textract')),
            timeout=Duration.seconds(lambda_timeout_sec),
            layers=[helpertools_layer],
            environment={
                'LOG_LEVEL': log_level,
                'SNS_TOPIC_ARN': textract_job_topic.topic_arn,
                'SNS_ROLE_ARN': sns_publish_role.role_arn,
                'DDB_DOCUMENTS_TABLE': ddb_documents_table.table_name,
            },
            retry_attempts=0,
            memory_size=128,  #128MB
        )
        # add the required policies to the default role creation with the lambda 
        # start_textract_lambda
        start_textract_lambda.role.add_managed_policy(
                aws_iam.ManagedPolicy.from_aws_managed_policy_name('AmazonTextractFullAccess')
        )
        start_textract_lambda.role.add_managed_policy(
                aws_iam.ManagedPolicy.from_aws_managed_policy_name('AmazonS3ReadOnlyAccess')
        )
        start_textract_lambda.role.attach_inline_policy(
            self.get_policy_write_to_ddb_table(ddb_documents_table)
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
            visibility_timeout=Duration.seconds(sqs_visibility_timeout_sec),
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
            code=aws_lambda.Code.from_asset(os.path.join(LAMBDA_DIRPATH, 'process_textract')),
            layers=[textracttools_layer, helpertools_layer],
            timeout=Duration.seconds(lambda_timeout_sec),
            environment={
                'LOG_LEVEL': log_level,
                'REGION': self.region,
                'DDB_DOCUMENTS_TABLE': ddb_documents_table.table_name,
                'TEXTRACT_BUCKET': processed_bucket.bucket_name,
                'TEXTRACT_RES_QUEUE_URL': processed_textracted_queue_sqs.queue_url
            },
            retry_attempts=0, 
            memory_size=3000,
        )
        # add the required policies to the default role create with the lambda
        process_textract_lambda.role.add_managed_policy(
                aws_iam.ManagedPolicy.from_aws_managed_policy_name('AmazonTextractFullAccess')
            )
        process_textract_lambda.role.attach_inline_policy(
            self.get_policy_write_to_ddb_table(ddb_documents_table)
        )
        process_textract_lambda.role.attach_inline_policy(
            aws_iam.Policy(self, 'S3ReadWriteObject',
                statements=[aws_iam.PolicyStatement(actions=['s3:GetObject','s3:PutObject'],
                    resources=[doc_bucket.bucket_arn+'/*',processed_bucket.bucket_arn+'/*'])]
            )
        )
        process_textract_lambda.role.attach_inline_policy(
            aws_iam.Policy(self, 'SqsPublishMessage',
                statements=[aws_iam.PolicyStatement(actions=['sqs:SendMessage'],
                    resources=[processed_textracted_queue_sqs.queue_arn])]
            )
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
            handler='main.lambda_handler',
            code=aws_lambda.Code.from_asset(os.path.join(LAMBDA_DIRPATH, 'selectable_pdf')),
            layers=[textracttools_layer, helpertools_layer],
            timeout=Duration.seconds(lambda_timeout_sec),
            environment={
                'DDB_DOCUMENTS_TABLE': ddb_documents_table.table_name,
                'OUTPUT_BUCKET': processed_bucket.bucket_name,
                'LOG_LEVEL': 'INFO',
                'ADD_WORD_BBOX': '0',
                'SHOW_CHARACTER': '0',
                'PDF_IMAGE_DPI': '200',

            },
            retry_attempts=0,
            memory_size=2048
        )
        # add the required policies to the default role creation with the lambda
        selectable_pdf_lambda.role.attach_inline_policy(
            self.get_policy_write_to_ddb_table(ddb_documents_table)
        )
        selectable_pdf_lambda.role.attach_inline_policy(
            aws_iam.Policy(self, 'S3ReadWrite',
                statements=[aws_iam.PolicyStatement(actions=['s3:GetObject','s3:PutObject'],
                    resources=[doc_bucket.bucket_arn+'/*',processed_bucket.bucket_arn+'/*'])]
            )
        )
        # add the SQS trigger
        selectable_pdf_lambda.add_event_source(
            source=aws_lambda_event_sources.SqsEventSource(
                queue=processed_textracted_queue_sqs,
                batch_size=1,
            )
        )

        # Outputs
        CfnOutput(
            self,
            id='DocumentInputBucket',
            value=doc_bucket.bucket_name,
            description='Bucket where to load the PDFs',
            export_name='DocumentInputBucket',
        )
        CfnOutput(
            self,
            id='DocumentOutputBucket',
            value=processed_bucket.bucket_name,
            description='Bucket where the processed PDFs and the intermediary files are stored',
            export_name='DocumentOutputBucket',
        )
        CfnOutput(
            self,
            id='ProcessingLogsDynamoDB',
            value=ddb_documents_table.table_name,
            description='Processing logs',
            export_name='ProcessingLogsDynamoDB',
        )


    
    def get_policy_write_to_ddb_table(self, table: aws_dynamodb.Table) -> aws_iam.Policy:
        '''
        return a Policy object to write to a DDB table
        '''
        policy = aws_iam.Policy(
            self,
            f'DynamoDB_writeToTable_{str(uuid.uuid4())[:4]}',
            statements=[aws_iam.PolicyStatement(
                actions=["dynamodb:PutItem","dynamodb:UpdateItem","dynamodb:UpdateTable"],
                resources=[table.table_arn]
            )]
        )
        return policy 


    @staticmethod
    def build_helpertools_layer() -> str:
        '''
        Build the helpertools Python module into a wheel then package it into 
        a zip-file which can be deploy as a AWS Lambda layer. The layer is build 
        within a container.

        Usage
        -----
        layer_zipfile = self.build_helpertools_layer()

        Arguments
        ---------
        None

        Returns
        -------
        layer_zippath
            Path to the layer zipfile.
        '''
        cwd = os.path.abspath(os.getcwd())
        layerbuilder_dirpath = os.path.join(LAMBDA_LAYER_DIRPATH,'helpertools_py38')
        os.chdir(layerbuilder_dirpath)
        subprocess.run(['./createlayer.sh','3.8'], capture_output=True)
        layer_zippath = os.path.join(layerbuilder_dirpath, 'helpertools.zip')
        os.chdir(cwd)
        return layer_zippath


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
        layerbuilder_dirpath = os.path.join(LAMBDA_LAYER_DIRPATH,'textracttools_py38')
        os.chdir(layerbuilder_dirpath)
        subprocess.run(['./createlayer.sh','3.8'], capture_output=True)
        layer_zippath = os.path.join(layerbuilder_dirpath, 'textracttools.zip')
        os.chdir(cwd)
        return layer_zippath