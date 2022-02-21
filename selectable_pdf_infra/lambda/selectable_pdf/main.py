'''
process_pdf
-----------

Add selectable characters to a PDF. Useful to convert a scanned PDF (i.e. pixel 
characters) into a selectable PDF.

Algorithm:
1. load the original PDF from S3 (S3 localtion info located in the SQS message)
2. read all the page and convert them to image. Indeed, the original PDF might already 
   have selectable characters, or a mix with pixel characters, so we want to avoid 
   overlay characters on characters
3. Add the character to the images. the characters are added by words. For each word, 
   the best fitting fontsize is computed to the character word length equal the pixel 
   word length
4. Save the pdf with selectable characters

Required environment variable
* OUTPUT_BUCKET
* DDB_DOCUMENTS_TABLE
'''

# import modules
# --------------
# standard modules
import os
import boto3
import json
import datetime

# custom modules from layers
from textracttools import load_json_from_s3
from helpertools import (
    get_logger,
    load_pdf_from_s3, 
    save_pdf_to_s3, 
    make_pdf_doc_searchable
)

# typing
from typing import Dict, Optional


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
    logger.info(f'args: {args}')

    # Get AWS connectors.
    ddb_ress = boto3.resource('dynamodb')
    ddb_doc_table = ddb_ress.Table(args['ddb_documents_table'])

    returns = list()
    for rec in args['records']:
        document_id = rec['document_id']
        document_name = rec['document_name']
        logger.info('document id: {}'.format(document_id))
        logger.info('document name: {}'.format(document_name))
        logger.info(f"document bucket: {rec['original_document_s3']['bucket']}")
        logger.info(f"document key: {rec['original_document_s3']['key']}")

        # store info about starting creating the selectable PDF document
        try:
            ddb_doc_table.update_item(
                Key={
                    'document_id': document_id,  # HASH key
                    'document_name': document_name  # RANGE key
                },
                UpdateExpression='SET selectable_pdf=:att1',  # This will set a new attribute
                ExpressionAttributeValues={
                    ':att1': {
                        'datetime': datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S') + '+00:00'
                    }
                }
            )
        except Exception as ex:
            logger.error(f'Cannot update item in DynamoDB table {args["ddb_documents_table"]}')
            raise ex

        # process the PDF
        pdf_doc = load_pdf_from_s3(rec['original_document_s3']['bucket'], rec['original_document_s3']['key'])
        textract_blocks = load_json_from_s3(rec['textract_output_s3']['bucket'], rec['textract_output_s3']['key'])
        textract_blocks = textract_blocks['Blocks']
        logger.info(f'nb blocks: {len(textract_blocks)}')
        num_word_blocks = 0
        for blk in textract_blocks:
            if blk['BlockType'] == 'WORD':
                num_word_blocks += 1
        logger.info(f'number of WORD blocks {num_word_blocks}')

        selectable_pdf_doc = make_pdf_doc_searchable(
            pdf_doc=pdf_doc,
            textract_blocks=textract_blocks,
            add_word_bbox=args['add_word_bbox'],
            show_selectable_char=args['show_character'],
            pdf_image_dpi=args['pdf_image_dpi'],
            verbose=True
        )
        output_key = document_name
        save_pdf_to_s3(selectable_pdf_doc, args['output_bucket'], output_key)

        # store info about ending the selectable PDF document creation
        try:
            ddb_doc_table.update_item(
                Key={
                    'document_id': document_id,  # HASH key
                    'document_name': document_name  # RANGE key
                },
                UpdateExpression='SET selectable_pdf=:att1',  # This will set a new attribute
                ExpressionAttributeValues={
                    ':att1': {
                        'datetime': datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S') + '+00:00'
                    }
                }
            )
        except Exception as ex:
            logger.error(f'Cannot update item in DynamoDB table {args["ddb_documents_table"]}')
            raise ex

        # perpare return dict
        returns.append({
            'selectable_pdf_s3': {
                'bucket': args['output_bucket'],
                'key': output_key,
            }
        })

    # return
    return_dict = {'records': returns}
    return {'statusCode': 200, 'body': return_dict}


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
    # get args from event
    args = dict()
    args['records'] = list()
    for rec in event['Records']:
        body = json.loads(rec['body'])
        record = dict()
        record['document_id'] = body['document_id']
        record['document_name'] = body['document_name']
        record['original_document_s3'] = body['original_document_s3']
        record['textract_output_s3'] = body['textract_output_s3']
    args['records'].append(record)
    # get the environnement variables. They are the same for all records
    args['ddb_documents_table'] = os.getenv('DDB_DOCUMENTS_TABLE')
    args['output_bucket'] = os.getenv('OUTPUT_BUCKET')
    args['log_level'] = os.getenv('LOG_LEVEL', default='INFO')
    args['add_word_bbox'] = os.getenv('ADD_WORD_BBOX', default=False)
    args['show_character'] = os.getenv('SHOW_CHARACTER', default=False)
    args['pdf_image_dpi'] = os.getenv('PDF_IMAGE_DPI', default='200')
    

    # post process some environment variable (Lambda allow only strings)
    args['add_word_bbox'] = True if args['add_word_bbox'] in ['1', 'True', 'true'] else False
    args['show_character'] = True if args['show_character'] in ['1', 'True', 'true'] else False
    args['pdf_image_dpi'] = int(args['pdf_image_dpi'])

    return args


