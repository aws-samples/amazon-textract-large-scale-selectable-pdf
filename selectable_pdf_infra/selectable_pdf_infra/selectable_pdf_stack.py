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
import pathlib
from cdk_lambda_layer_builder import BuildPyLayerAsset


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
        self.doc_bucket = aws_s3.Bucket(
            self,
            id='InputDocuments',
            removal_policy=RemovalPolicy.DESTROY, #kept if not empty
        )
        doc_bucket_r_policy = aws_iam.Policy(self, 'DocBucketRead',
            statements=[aws_iam.PolicyStatement(actions=['s3:GetObject'],
            resources=[self.doc_bucket.bucket_arn+'/*'])]
        )

        self.processed_bucket = aws_s3.Bucket(
            self,
            id='ProcessedDocuments',
            removal_policy=RemovalPolicy.DESTROY, #kept if not empty
        )
        processed_bucket_rw_policy = aws_iam.Policy(self, 'ProcessedBucketReadWrite',
            statements=[aws_iam.PolicyStatement(actions=['s3:GetObject','s3:PutObject'],
            resources=[self.processed_bucket.bucket_arn+'/*'])]
        )

        # create the DynamoDB tables. We create N tables:
        # 1. A table to store the info about documents processing
        self.ddb_documents_table = aws_dynamodb.Table(
            self,
            id='Documents',
            partition_key=aws_dynamodb.Attribute(
                name='document_id', type=aws_dynamodb.AttributeType.STRING
            ),
            sort_key=aws_dynamodb.Attribute(
                name='document_name', type=aws_dynamodb.AttributeType.STRING
            ),
            billing_mode=aws_dynamodb.BillingMode.PAY_PER_REQUEST
        )
        ddb_documents_table_policy = aws_iam.Policy(self,f'DdbDocTablePolicy',
            statements=[aws_iam.PolicyStatement(
                actions=['dynamodb:PutItem','dynamodb:UpdateItem','dynamodb:UpdateTable', 'dynamodb:DescribeTable'],
                resources=[self.ddb_documents_table.table_arn]
            )]
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
        textracttools_layer_asset = BuildPyLayerAsset.from_modules(self, 'TextractToolsLayerAsset',
            local_module_dirs=[str(LIB_DIRPATH.joinpath('textracttools'))],
            py_runtime=aws_lambda.Runtime.PYTHON_3_8,
        )
        textracttools_layer = aws_lambda.LayerVersion(
            self,
            id='TextractTools',
            code=aws_lambda.Code.from_bucket(
                textracttools_layer_asset.asset_bucket,
                textracttools_layer_asset.asset_key
            ),
            compatible_runtimes=[aws_lambda.Runtime.PYTHON_3_8],
            description ='TextractTools python module'
        )
        helpertools_layer_asset = BuildPyLayerAsset.from_modules(self, 'HelpertoolsLayerAsset',
            local_module_dirs=[str(LIB_DIRPATH.joinpath('helpertools'))],
            py_runtime=aws_lambda.Runtime.PYTHON_3_8,
        )
        helpertools_layer = aws_lambda.LayerVersion(
            self,
            id='HelperTools',
            code=aws_lambda.Code.from_bucket(
                helpertools_layer_asset.asset_bucket,
                helpertools_layer_asset.asset_key
            ),
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
                'DDB_DOCUMENTS_TABLE': self.ddb_documents_table.table_name,
            },
            retry_attempts=0,
            memory_size=128,  #128MB
        )
        # add the required policies to the default role creation with the lambda 
        # start_textract_lambda
        start_textract_lambda.role.add_managed_policy(
                aws_iam.ManagedPolicy.from_aws_managed_policy_name('AmazonTextractFullAccess')
        )
        start_textract_lambda.role.attach_inline_policy(doc_bucket_r_policy)
        start_textract_lambda.role.attach_inline_policy(ddb_documents_table_policy)
        # set the trigger: S3 PUT on doc_bucket
        start_textract_lambda.add_event_source(
            source=aws_lambda_event_sources.S3EventSource(
                bucket=self.doc_bucket, 
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
        textract_output_sqs_w_policy = aws_iam.Policy(self, 'SqsPublishMessage',
            statements=[aws_iam.PolicyStatement(actions=['sqs:SendMessage'],
                resources=[processed_textracted_queue_sqs.queue_arn])]
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
                'DDB_DOCUMENTS_TABLE': self.ddb_documents_table.table_name,
                'TEXTRACT_BUCKET': self.processed_bucket.bucket_name,
                'TEXTRACT_RES_QUEUE_URL': processed_textracted_queue_sqs.queue_url
            },
            retry_attempts=0, 
            memory_size=3000,
        )
        # add the required policies to the default role create with the lambda
        process_textract_lambda.role.add_managed_policy(
                aws_iam.ManagedPolicy.from_aws_managed_policy_name('AmazonTextractFullAccess')
            )
        process_textract_lambda.role.attach_inline_policy(ddb_documents_table_policy)
        process_textract_lambda.role.attach_inline_policy(doc_bucket_r_policy)
        process_textract_lambda.role.attach_inline_policy(processed_bucket_rw_policy)
        process_textract_lambda.role.attach_inline_policy(textract_output_sqs_w_policy)
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
                'DDB_DOCUMENTS_TABLE': self.ddb_documents_table.table_name,
                'OUTPUT_BUCKET': self.processed_bucket.bucket_name,
                'LOG_LEVEL': 'INFO',
                'ADD_WORD_BBOX': '0',
                'SHOW_CHARACTER': '0',
                'PDF_IMAGE_DPI': '200',

            },
            retry_attempts=0,
            memory_size=2048
        )
        # add the required policies to the default role creation with the lambda
        selectable_pdf_lambda.role.attach_inline_policy(ddb_documents_table_policy)
        selectable_pdf_lambda.role.attach_inline_policy(doc_bucket_r_policy)
        selectable_pdf_lambda.role.attach_inline_policy(processed_bucket_rw_policy)
        # add the SQS trigger
        selectable_pdf_lambda.add_event_source(
            source=aws_lambda_event_sources.SqsEventSource(
                queue=processed_textracted_queue_sqs,
                batch_size=1,
            )
        )

        # stack output
        # output_prefix = 'SelectablePdf'
        output_prefix = construct_id
        CfnOutput(
            self,
            id='DocumentInputBucket',
            value=self.doc_bucket.bucket_name,
            description='Bucket where to load the PDFs',
            export_name=f'{output_prefix}DocumentInputBucket',
        )
        CfnOutput(
            self,
            id='DocumentOutputBucket',
            value=self.processed_bucket.bucket_name,
            description='Bucket where the processed PDFs and the intermediary files are stored',
            export_name=f'{output_prefix}DocumentOutputBucket',
        )
        CfnOutput(
            self,
            id='ProcessingLogsDynamoDB',
            value=self.ddb_documents_table.table_name,
            description='Processing logs',
            export_name=f'{output_prefix}ProcessingLogsDdb',
        )