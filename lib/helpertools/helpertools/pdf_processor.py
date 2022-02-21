# import modules
# --------------
import os
import logging
import math
import boto3
import fitz  #This is PyMuPdf

# typing
from typing import Dict, Optional, List, Any

# preparation
# -----------
# get the root logger
logger = logging.getLogger()


# functions
# ---------
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
    print_step = 1000
    bbox_color = (220/255, 20/255, 60/255) #red-ish color
    fontsize_initial = 15
    for blocki,block in enumerate(textract_blocks):
        if verbose:
            if blocki%print_step == 0:
                logger.info(
                    (f'processing blocks {blocki} to {blocki+print_step} out of {len(textract_blocks)} blocks')
                )
        if block['BlockType']=='WORD':
            # get the page object
            page = block['Page']-1 #zero-counting
            pdf_page = pdf_doc_img[page]
            # get the bbox object and scale it to the page pixel size
            bbox = BoundingBox.from_textract_bbox(block['Geometry']['BoundingBox'])
            bbox.scale(pdf_page.rect.width, pdf_page.rect.height)

            # draw a bbox around each word
            if add_word_bbox:
                pdf_rect  = fitz.Rect(bbox.left, bbox.top, bbox.right, bbox.bottom)
                pdf_page.draw_rect(
                    pdf_rect, 
                    color = bbox_color,
                    fill = None, 
                    width = 0.7, 
                    dashes = None, 
                    overlay = True, 
                    morph = None
                )

            # add some text next to the bboxs
            fill_opacity = 1 if show_selectable_char else 0
            text = block['Text']
            text_length = fitz.get_text_length(text, fontname='helv', fontsize=fontsize_initial)
            fontsize_optimal = int(math.floor((bbox.width/text_length)*fontsize_initial))
            rc = pdf_page.insert_text(
                point=fitz.Point(bbox.left, bbox.bottom),  # bottom-left of 1st char
                text=text,
                fontname = 'helv',  # the default font
                fontsize = fontsize_optimal,
                rotate = 0,
                color = bbox_color,
                fill_opacity=fill_opacity
            )

    return pdf_doc_img


# classes
# -------
class BoundingBox():
    '''
    Class to manipulate a bounding box (bbox). A bounding box is a rectangle aligned with 
    the coordinate system. The bounding box are defined on coordinate system with x 
    pointing toward east and y pointing toward north. This is the usual coordinate 
    system used in euclidian geometry (i.e. lower left origin). Note that images 
    generally have a a cordinate system defined with a upper left origin. 
    '''
    # constructors
    def __init__(self, left: float, bottom: float, right: float, top: float) -> None:
        '''
        constructor.
        '''
        self.bounds = [left, bottom, right, top]
        
    @classmethod
    def from_textract_bbox(cls, textract_bbox: Dict[str, float]) -> None:
        '''
        Construct a BoundingBox object from the bounding box defined by an AWS Textract 
        output json. As Textract uses a coordinate system with a upper left origin 
        (i.e. y pointing downward), the definition of bottom=top+height (note 
        the "+", instead of a "-").
        '''
        return cls(
            left=textract_bbox['Left'],
            bottom=textract_bbox['Top']+textract_bbox['Height'],
            right=textract_bbox['Left']+textract_bbox['Width'],
            top=textract_bbox['Top'],
        )

    # class methods
    def scale(self, x_scale: None, y_scale: Optional[float]=None) -> None:
        '''
        Scale a bounding box by a  x and y factor. If y is not defined, the bbox is 
        scaled by x in all directions
        '''
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