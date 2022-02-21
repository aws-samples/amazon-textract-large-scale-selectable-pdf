'''
process_textract
----------------

Lambda function processing a Textract job. Once a textract job is processed, the output of 
the job is written on S3 and a meassage is push on a SQS queue with the output localtion.

Textract publishs its job status on a SNS topic. This Lambda function is trigger by a 
SNS topic used by Textract.

Requirements
------------
* SNS push event from a topic used by Textract to publish its job status.
* Env variables:
    * LOG_LEVEL (optional): the log level of the lambda function .
    * DDB_DOCUMENTS_TABLE: a dynamoDB table for logging.
    * TEXTRACT_RES_QUEUE_URL: SQS queue used to publish the S3 location of Textract outputs.
    * REGION: the region of the of the SQS queue defined by TEXTRACT_RES_QUEUE_URL.
'''
# import modules
# --------------
# standard modules
import boto3
import json
import logging
import os

from datetime import datetime

# custom modules from layers
from textracttools import TextractParser, save_json_to_s3
from helpertools import get_logger

# typing
from typing import Dict

# logger
# ------ 
#If no LOG_LEVEL env var or wrong LOG_LEVEL env var, fallback 
# to INFO log level
logger = get_logger(os.getenv('LOG_LEVEL', default='INFO'))


# lambda entrypoint
# -----------------
def lambda_handler(event, context):
    logger.info('event: {}'.format(event))
    args = parse_args(event)

    # Get AWS connectors. The SQS client need the legacy endpoint, but when calling
    # a queue with the client, the queue URL must have the new endpoint:
    # https://docs.aws.amazon.com/general/latest/gr/sqs-service.html#sqs_region
    ddb_ress = boto3.resource('dynamodb')
    ddb_doc_table = ddb_ress.Table(args['ddb_documents_table'])
    sqs_legacy_endpoint_url = f"https://{args['region']}.queue.amazonaws.com"
    sqs_client = boto3.client('sqs', endpoint_url=sqs_legacy_endpoint_url)

    # for each job (generally, only one per sns message):
    # 1. get the textract blocks
    # 2. save the blocks to S3
    # 4. send back the token to the step function
    returnDict = dict()
    returnDict['textract_jobs'] = list()
    tt_bucket = args['textract_bucket']
    logger.info('nb of textract jobs: {}'.format(len(args['textract_jobs'])))
    for t,tt_job in enumerate(args['textract_jobs']):
        logger.info(f"prcessing Textract job {t} of {len(args['textract_jobs'])}")

        document_id = tt_job['job_tag']
        document_name = tt_job['original_document']['key'].split('/')[-1]
        logger.info('document_id: {}'.format(document_id))
        logger.info(f"document bucket: {tt_job['original_document']['bucket']}")
        logger.info(f"document key: {tt_job['original_document']['key']}")

        # store info about textract job end in DynamoDB
        try:
            ddb_doc_table.update_item(
                Key={
                    'document_id': document_id,  # HASH key
                    'document_name': document_name  # RANGE key
                },
                UpdateExpression='SET textract_async_end=:att1',  # This will set a new attribute
                ExpressionAttributeValues={
                    ':att1': {
                        'datetime': tt_job['end_datetime'].strftime('%Y-%m-%dT%H:%M:%S') + '+00:00'
                    }
                }
            )
        except Exception as ex:
            logger.error(f"Cannot update item in DynamoDB table {args['ddb_documents_table']}")
            raise ex

        # get the blocks and save them to s3
        blocks = TextractParser.get_textract_result_blocks(tt_job['job_id'])
        tt_output_key = os.path.join(document_id, 'textract_output_blocks.json')
        save_json_to_s3(tt_bucket, tt_output_key, blocks)

        # package the job info into a dict for returns and for the textract results SQS
        tt_job_info = {
            'document_id': document_id,
            'document_name': document_name,
            'original_document_s3': {
                'bucket': tt_job['original_document']['bucket'],
                'key': tt_job['original_document']['key'],
            },
            'textract_output_s3': {
                'bucket': tt_bucket,
                'key': tt_output_key
            }
        }
        returnDict['textract_jobs'].append(tt_job_info)

        try:
            sqs_client.send_message(
                QueueUrl=args['textract_res_queue_url'],
                MessageBody=json.dumps(tt_job_info),
            )
        except Exception as ex:
            logger.error(f"Cannot send message to SQS queue {args['textract_res_queue_url']}")
            raise ex


    return {
        'statusCode': 200,
        'body': json.dumps(returnDict)
    }


# functions
# ---------
def parse_args(event: Dict) -> Dict:
    '''
    Parse the environment variables and the event payload (from the lambda 
    entrypoint). Process them further if required.
    
    Usage
    -----
    args = parse_args(event)
    '''
    args = dict()
    
    # get arguments from the sns payload sent by textract at the end of the job
    args['textract_jobs'] = list()
    for record in event['Records']:
        message = json.loads(record['Sns']['Message'])
        # store the textract infos
        args['textract_jobs'].append({
            'job_id': message['JobId'],
            'status': message['Status'],
            'job_tag': message['JobTag'],
            'end_datetime': datetime.utcfromtimestamp(message['Timestamp']/1000),
            'original_document': {
                'bucket': message['DocumentLocation']['S3Bucket'],
                'key': message['DocumentLocation']['S3ObjectName'],
            }
        })
    
    # get the environement variables
    args['log_level'] = os.getenv('LOG_LEVEL', default='INFO')
    args['region'] = os.getenv('REGION')
    args['ddb_documents_table'] = os.getenv('DDB_DOCUMENTS_TABLE')
    args['textract_bucket'] = os.getenv('TEXTRACT_BUCKET')
    args['textract_res_queue_url'] = os.getenv('TEXTRACT_RES_QUEUE_URL')

    return args
