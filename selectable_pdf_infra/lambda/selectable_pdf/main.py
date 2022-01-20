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
import logging
import datetime
import math

# custom modules from layers
import fitz  #This is PyMuPdf
from textracttools import load_json_from_s3

# typing
from typing import Dict, Optional, List, Any


# logger
# ------ 
#If no LOG_LEVEL env var or wrong LOG_LEVEL env var, fallback 
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
            if blk['BlockType']=='WORD':
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


def load_pdf_from_s3(bucket: str, key: str) -> fitz.Document:
    '''
    Read a PDF document from S3 and load it into a fitz.Document object. Fitz is 
    part of the module PyMuPDF
    '''
    s3_res = boto3.resource('s3')
    s3_object = s3_res.Object(bucket, key)
    fs = s3_object.get()['Body'].read()
    pdf_doc = fitz.open(stream=fs, filetype='pdf')
    return pdf_doc


def save_pdf_to_s3(pdf_doc:fitz.Document, bucket: str, key: str) -> Dict[str, Any]:
    '''
    Save a fitz.Document object (i.e. a PDF in PyMuPDF module) directly to S3 without 
    passing via a local save to disk. Returns the response from S3.
    '''
    s3_client = boto3.client('s3')
    response = s3_client.put_object(
        Body=pdf_doc.tobytes(
            garbage=3, 
            clean=True, 
            deflate=True, 
            deflate_images=True, 
            deflate_fonts=True, 
            expand=0, 
        ),
        Bucket=bucket,
        Key=key
    )
    return response


def make_pdf_doc_searchable(
    pdf_doc: fitz.Document,
    textract_blocks: List[Dict[str, Any]],
    add_word_bbox: bool=False,
    show_selectable_char: bool=False,
    pdf_image_dpi: int=200,
    verbose: bool=False,
) -> fitz.Document:
    '''
    '''
    # save the pages as images (jpg) and buddle these images into a pdf document (pdf_doc_img)
    pdf_doc_img = fitz.open()
    for ppi,pdf_page in enumerate(pdf_doc.pages()):
        pdf_pix_map = pdf_page.get_pixmap(dpi=pdf_image_dpi, colorspace='RGB')
        pdf_page_img = pdf_doc_img.new_page(width=pdf_page.rect.width, height=pdf_page.rect.height)
        xref = pdf_page_img.insert_image(rect=pdf_page.rect, pixmap=pdf_pix_map)
    pdf_doc.close()

    # add the searchable character to the image PDF and bounding boxes if required by user
    for blocki,block in enumerate(textract_blocks):
        if verbose:
            step = 1000
            if blocki%1000==0:
                logger.info(
                    (f'processing blocks {blocki} to {blocki+1000} out of {len(textract_blocks)} blocks')
                )
        if block['BlockType']=='WORD':
            # get the page object
            page = block['Page']-1 #zero-counting
            pdf_page = pdf_doc_img[page]
            # get the bbox object and scale it to the page pixel size
            bbox = BoundingBox.from_textract_bbox(block['Geometry']['BoundingBox'])
            bbox.scale(pdf_page.rect.width, pdf_page.rect.height)

            color = (220/255, 20/255, 60/255) #red-ish color

            # draw a bbox around each word
            if add_word_bbox:
                pdf_rect  = fitz.Rect(bbox.left, bbox.top, bbox.right, bbox.bottom)
                pdf_page.draw_rect(
                    pdf_rect, 
                    color = color,
                    fill = None, 
                    width = 0.7, 
                    dashes = None, 
                    overlay = True, 
                    morph = None
                )

            # add some text next to the bboxs
            fill_opacity = 1 if show_selectable_char else 0
            text = block['Text']
            fontsize_initial = 15
            text_length = fitz.get_text_length(text, fontname='helv', fontsize=fontsize_initial)
            fontsize_optimal = int(math.floor((bbox.width/text_length)*fontsize_initial))
            rc = pdf_page.insert_text(
                point=fitz.Point(bbox.left, bbox.bottom),  # bottom-left of 1st char
                text=text,
                fontname = 'helv',  # the default font
                fontsize = fontsize_optimal,
                rotate = 0,
                color = color,
                fill_opacity=fill_opacity
            )

    return pdf_doc_img


# classes
# -------
class BoundingBox():
    '''
    Class to manipulate a bounding box. A bounding box is a rectangle aligned with 
    the corrdinate system
    '''
    # constructors
    def __init__(self, left: float, bottom: float, right: float, top: float) -> None:
        '''
        constructor
        '''
        self.bounds = [left, bottom, right, top]
        
    @classmethod
    def from_textract_bbox(cls, textract_bbox: Dict[str, float]) -> None:
        return cls(
            left=textract_bbox['Left'],
            bottom=textract_bbox['Top']+textract_bbox['Height'],
            right=textract_bbox['Left']+textract_bbox['Width'],
            top=textract_bbox['Top'],
        )

    # class methods
    def scale(self, x_scale: None, y_scale: Optional[float]=None) -> None:
        if not y_scale:
            y_scale = x_scale
        self.bounds[0] *= x_scale
        self.bounds[1] *= y_scale
        self.bounds[2] *= x_scale
        self.bounds[3] *= y_scale

    # overload methods
    def __getitem__(self, key):
        return self.bounds[key]

    def __setitem__(self, key, value):
        self.bounds[key] = value

    # getters
    @property
    def left(self) -> float:
        return self.bounds[0]

    @property
    def bottom(self) -> float:
        return self.bounds[1]

    @property
    def right(self) -> float:
        return self.bounds[2]

    @property
    def top(self) -> float:
        return self.bounds[3]

    @property
    def width(self) -> float:
        return abs(self.bounds[0]-self.bounds[2])

    @property
    def height(self) -> float:
        return abs(self.bounds[3]-self.bounds[1])