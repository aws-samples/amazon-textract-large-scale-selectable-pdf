'''
start_textract
--------------

Lambda function which starts an asynchronous Textract job on a S3 PUT trigger.

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

from helpertools import ProcessingDdbTable, get_logger

from typing import Dict

#If no LOG_LEVEL env var or wrong LOG_LEVEL env var, fallback 
# to INFO log level
logger = get_logger(os.getenv('LOG_LEVEL', default='INFO'))


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

    # get logging table object
    ddb_doc_table = ProcessingDdbTable(args['ddb_documents_table'])

    # start textract for each s3 records. But generally, there is only one record
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
        document_name = record['key'].split('/')[-1]
        ddb_doc_table.put_item(
            doc_id=document_id, 
            doc_name=document_name,  
            item={
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
            },
            add_logging_datetime=False
        )

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
        ddb_doc_table.update_item(
            doc_id=document_id, 
            doc_name=document_name, 
            key='textract_async_start', 
            value={'job_id': tt_resp['JobId']},
            add_logging_datetime=True
        )

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
    S3 events as received by the lambda function have the format `2021-04-15T16:20:02.994Z`.
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
    8 random characters extracted from a UUID1 (default behavior).

    Usage
    -----
    random_uid = generate_uid(method='date')

    Arguments
    ---------
    type
        The method used to generate the random UID. either 'date' or 'uuid1'.

    Returns
    -------
    random_uid
        The random UID
    '''
    if method == 'date':
        now = datetime.now()
        now_as_str = now.strftime(datetime_format)
        random_chars = str(uuid.uuid1())[:8]
        return now_as_str + '-' + random_chars
    elif method == 'uuid1':
        return str(uuid.uuid1())
    else:
        raise AttributeError('Unknown "method". Valid options: [date|uuid1]')
