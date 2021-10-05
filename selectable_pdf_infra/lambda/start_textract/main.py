'''
start_textract
--------------

Lambda function which starts an asychronous Textract job on a S3 PUT trigger.

Requirements
------------
* S3 PUT trigger on documents (PDFs or images)
* Env variables:
    * LOG_LEVEL (optional): the log level of the lambda function.
    * SNS_TOPIC_ARN: SNS topic used by Textract to publish the result of a job.
    * SNS_ROLE_ARN: Role used by Textract to publish job results messages on a SNS topic.
    * DDB_DOCUMENTS_TABLE: a dynamoDB table for logging.
'''
# import modules
# --------------
import json
import boto3
import os
import logging
import uuid
import random
import string
from datetime import datetime, timedelta
from urllib.parse import unquote_plus
from typing import Dict

# prepare the logger. If no LOG_LEVEL env var or wrong LOG_LEVEL env var, fallback 
# to INFO log level
log_level = os.getenv('LOG_LEVEL', default='INFO')
log_level_int = int()
if log_level=='WARNING':
    log_level_int = logging.WARNING
elif log_level=='ERROR':
    log_level_int = logging.WARNING
elif log_level=='DEBUG':
    log_level_int = logging.DEBUG
else:
    log_level_int = logging.INFO
logging.basicConfig(
    format='%(levelname)s %(message)s',
    level=log_level_int,
    force=True  #new in py3.8
)
logger = logging.getLogger()


def lambda_handler(event, context):
    '''
    the event is a S3 PUT formatted as JSON. Example:
    {
        "Records": [
            {
                "eventVersion": "2.0",
                "eventSource": "aws:s3",
                "awsRegion": "eu-west-1",
                "eventTime": "1970-01-01T00:00:00.000Z",
                "eventName": "ObjectCreated:Put",
                "userIdentity": {
                    "principalId": "EXAMPLE"
                },
                "requestParameters": {
                    "sourceIPAddress": "127.0.0.1"
                },
                "responseElements": {
                    "x-amz-request-id": "EXAMPLE123456789",
                    "x-amz-id-2": "EXAMPLE123/5678abcdefghijklambdaisawesome/mnopqrstuvwxyzABCDEFGH"
                },
                "s3": {
                    "s3SchemaVersion": "1.0",
                    "configurationId": "testConfigRule",
                    "bucket": {
                        "name": "example-bucket",
                        "ownerIdentity": {
                            "principalId": "EXAMPLE"
                        },
                        "arn": "arn:aws:s3:::example-bucket"
                    },
                    "object": {
                        "key": "test/key",
                        "size": 1024,
                        "eTag": "0123456789abcdef0123456789abcdef",
                        "sequencer": "0A1B2C3D4E5F678901"
                    }
                }
            }
        ]
    }
    '''
    logger.info('event: {}'.format(event))

    # get args
    args = parse_args(event)

    # create AWS connectors
    ddb_ress = boto3.resource('dynamodb')
    ddb_doc_table = ddb_ress.Table(args['ddb_documents_table'])

    # start textract for each s3 rcords. But generally, there is only one record
    responses = list()
    for r,record in enumerate(args['records']):
        logger.info(f"prcessing document {r} of {len(args['records'])}")
        # Get the document ID. This ID will follow the document during all the
        # processing. We could use `uuid.uuid1` which generates a random list
        # characters, but we want something slightly more usable, like the date +
        # a few random chars.
        document_id = generate_uid()
        logger.info(f"document ID: {document_id}")
        logger.info(f"document bucket: {record['bucket']}")
        logger.info(f"document key: {record['key']}")

        # Create the item in DDB
        try:
            document_name = record['key'].split('/')[-1]
            ddb_doc_table.put_item(
                Item={
                    'document_id': document_id,
                    'document_name': document_name,
                    'document_s3': {
                        'bucket': record['bucket'],
                        'key': record['key'],
                    },
                    'document_put_event': {
                        'datetime': convert_datetime_s3_event(record['event_datetime']),
                        'user_id': record['event_user_id'],
                        'user_ip': record['event_user_ip']
                    }
                }
            )
        except Exception as ex:
            logger.error(f'Cannot put item to DynamoDB table {args["ddb_documents_table"]}')
            raise ex

        # start textract
        try:
            logger.info('start Textract async job')
            tt_resp = textract_start_async_processing(
                input_bucket=record['bucket'],
                input_key=record['key'],
                sns_topic_arn=args['sns_topic_arn'],
                sns_role_arn=args['sns_role_arn'],
                job_tag=document_id,
            )
            logger.info('textract response: {}'.format(tt_resp))
        except Exception as ex:
            logger.error('Textract async job failed to start')
            raise ex


        # add textract response to DDB
        try:
            ddb_doc_table.update_item(
                Key={
                    'document_id': document_id,  # HASH key
                    'document_name': document_name  # RANGE key
                },
                UpdateExpression='SET textract_async_start=:att1',  # This will set a new attribute
                ExpressionAttributeValues={
                    ':att1': {
                        'job_id': tt_resp['JobId'],
                        'datetime': convert_datetime_textract(
                            tt_resp['ResponseMetadata']['HTTPHeaders']['date']
                        ),
                    }
                }
            )
        except Exception as ex:
            logger.error(f'Cannot update item in DynamoDB table {args["ddb_documents_table"]}')
            raise ex

        # build a nice return
        responses.append({
            'textract_job_id': tt_resp['JobId'],
            'original_document_id': document_id,
            'original_document': {
                'bucket': record['bucket'],
                'key': record['key'],
            }
        })

    # prepare the response dict and return it
    return_response = {'textract_job_started': responses}
    return {
        'statusCode': 200,
        'body': json.dumps(return_response)
    }


# functions    
def parse_args(event: Dict) -> Dict:
    '''
    Parse the environment variables and the event payload (from the lambda 
    entrypoint). Process them further if required.
    
    Usage
    -----
    args = parse_args(event)
    '''
    args = dict()
    
    # get arguments from the event
    args['records'] = list()
    for record in event['Records']:
        args['records'].append({
            'bucket': record['s3']['bucket']['name'],
            'key': unquote_plus(record['s3']['object']['key']),
            'event_datetime': record['eventTime'],
            'event_user_id': record['userIdentity']['principalId'],
            'event_user_ip': record['requestParameters']['sourceIPAddress'],
        })
    
    # get the environement variables
    args['log_level'] = os.getenv('LOG_LEVEL', default='INFO')
    args['sns_topic_arn'] = os.getenv('SNS_TOPIC_ARN')
    args['sns_role_arn'] = os.getenv('SNS_ROLE_ARN')
    args['ddb_documents_table'] = os.getenv('DDB_DOCUMENTS_TABLE')
    
    # return
    return args


def textract_start_async_processing(
    input_bucket: str, 
    input_key: str, 
    sns_topic_arn: str, 
    sns_role_arn: str,
    job_tag: str,
) -> Dict:
    '''
    start an Amazon Textract asynchronous operation on a pdf document, which can be 
    a single-page or multi-page document.
    
    Usage
    -----
    job_id =  textract_start_async_processing(
        input_bucket, input_key, 
        sns_topic_arn, sns_role_arn,
        job_tag
    )
    '''
    textract_client = boto3.client('textract')

    textract_parameters = {
        'DocumentLocation': {
            'S3Object': {
                'Bucket': input_bucket,
                'Name': input_key
            }
        },
        'FeatureTypes': ['FORMS', 'TABLES'],  # get everything + table and form features
        'JobTag': job_tag,
        'NotificationChannel': {
            'SNSTopicArn': sns_topic_arn,
            'RoleArn': sns_role_arn
        }
    }

    response = textract_client.start_document_analysis(**textract_parameters)

    # return
    return response


def convert_datetime_s3_event(
    datetime_str: str, 
    output_datetime_format: str='%Y-%m-%dT%H:%M:%S+00:00'
) -> str:
    '''
    S3 events as recieved by the lambda function have the format `2021-04-15T16:20:02.994Z`.
    This function (and all functions convert_datetime*) converts it to 
    `2021-04-15T16:20:02.994+00:00`, the ISO 8601 format. The output format can be 
    modified via the output_datetime_format argument.
    '''
    dt = datetime.strptime(datetime_str[:-5], '%Y-%m-%dT%H:%M:%S')
    dt = dt + timedelta(milliseconds=int(datetime_str[-4:-1]))
    dt_str = dt.strftime(output_datetime_format)
    return dt_str


def convert_datetime_textract(
    datetime_str: str,
    output_datetime_format: str='%Y-%m-%dT%H:%M:%S+00:00'
) -> str:
    '''
    Convert the date of a textract async response (e.g. 'Mon, 19 Apr 2021 14:52:48 GMT') 
    to the ISO 8601 format (e.g. '2021-04-19T14:52:48+00:00'). The output format can be 
    modified via the output_datetime_format argument.
    '''
    dt = datetime.strptime(datetime_str, '%a, %d %b %Y %H:%M:%S %Z')
    dt_str = dt.strftime(output_datetime_format)
    return dt_str


def generate_uid(
    method: str='date', 
    datetime_format: str='%Y%m%dT%H%M%S-%f'
) -> str:
    '''
    Generate a random Unique ID (UID) base on the current datetime + a string of 
    8 random characters (default behavior).

    Usage
    -----
    random_uid = generate_uid(method='date')

    Arguments
    ---------
    type
        The method used to generate the random UID. either 'date' or 'uuid1'

    Returns
    -------
    random_uid
        The random UID
    '''
    if method == 'date':
        now = datetime.now()
        now_as_str = now.strftime(datetime_format)
        random_chars = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        return now_as_str + '-' + random_chars
    elif method == 'uuid1':
        return str(uuid.uuid1())
    else:
        raise AttributeError('Unknown "method". Valid options: [date|uuid1]')
