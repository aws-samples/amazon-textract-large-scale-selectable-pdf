# amazon-textract-large-scale-selectable-pdf

This repository contains an application which converts non-selectable or scanned 
PDF's to selectable PDF's. This application can handle any size of PDF (any number 
of pages) and can process 100's of PDF in parallel. Moreover, the application uses 
a serverless architecture, which reduce maintenance and operation costs (e.g. free 
while not in use).

A non-selectable PDF does not allow text selection, meaning the characters are 
images. a selectable PDF allow text selection. Selectable PDF's can be used in 
several downstream tasks, such as:
* document search
* document indexing
* Machine Learning tasks, such as:
    * Natural Language Processing (NLP)
    * NLP annotations
    * Document summarization
    * Document classification
    * Document topic analysis

## Architecture

![Selectable PDF architecture](selectable_pdf_architecture.png "Selectable PDF architecture")

__Fig.1:__ Architecture diagram of the _large-scale-selectable-pdf_ application.

Figure 1 shows the architecture used by the _large-scale-selectable-pdf_ application. 
The workflow runs as follow:
1. Start by uploading one or several PDF's in the _InputDocument_ Amazon 
   S3 bucket. You can use any folder structure to store the PDFs in the 
   _InputDocument_ bucket: the application is trigger by any uploaded document ending 
   with the `.pdf` extension. An example PDF is available in `examples/SampleInput.pdf`. 
   As you can see, it's a scanned document, hence the text is neither selectable, 
   nor searchable. The application will also process PDFs that are already selectable, 
   therefore you don't need to seprated scanned and original PDFs beforehand.
2. Each document uploaded to S3 will automatically trigger the _Starttextract_ Amazon
   Lambda function. This is where the parallel processing of document starts.
3. Each _Starttextract_ Lambda function triggers an asynchronous Textract job which
   can last from 1 minute to 30 minutes, depending on the size (i.e. number of pages) 
   of the document. Each Textract job will write a message in Amazon SNS topic 
   _TextractJobStatus_ when finished.
4. Each SNS message triggers the Lambda function _ProcessTextract_ which downloads 
   the Textract response and saves it to S3. Below, you can find the Textract response 
   for the sample document in `examples/SampleInput.pdf` (see full response in 
   `examples/SampleInput_blocks.json`):
   ```json
   {
      "Blocks": [
         {
            "BlockType": "PAGE",
            "Geometry": {
                  "BoundingBox": { "Width": 1.0, "Height": 1.0, "Left": 0.0, "Top": 0.0},
                  "Polygon": [...]
            },
            "Id": "f8a7ea3f-d3a9-4bdd-8f5c-352c13aa0af4",
            "Relationships": [
                  {
                     "Type": "CHILD",
                     "Ids": [
                        "f4e5af39-69a2-449c-ba5c-939e1440297c",
                        "2a9335b7-93f4-43f2-8c4d-3df8d19530b4",
                        ...
                     ]
                  }
            ],
            "Page": 1
         },
         {
            "BlockType": "LINE",
            "Confidence": 99.76974487304688,
            "Text": "Employment Application",
            "Geometry": {
                  "BoundingBox": { "Width": 0.2864, "Height": 0.0335, "Left": 0.3521, "Top": 0.04381},
                  "Polygon": [...]
            },
            "Id": "f4e5af39-69a2-449c-ba5c-939e1440297c",
            "Relationships": [
                  {
                     "Type": "CHILD",
                     "Ids": [
                        "70ee8de2-684e-4377-af5b-c0fa35b7fb53",
                        "804546c6-9e23-4a58-adc2-8ae40c4ed95c"
                     ]
                  }
            "Page": 1
         },
      ]
   }
   ```
   The Textract response is a collection of `blocks`, where each block describes an 
   element in the PDF, such as a `PAGE`, a `TABLE`, a `LINE`, a `WORD`, etc. Each 
   block also is located in the PDF by the page number and its bounding box (see 
   `BoundingBox` key). Each block also describes the content of the block, if possible. 
   In the example above, the second block is of type `LINE` and its content, i.e. 
   the content of the line, is `Employment Application` (see the `Text` key). More 
   information about the Textract response can be found in th5 
   [Amazon Textract documentation](https://docs.aws.amazon.com/textract/latest/dg/how-it-works-document-layout.html). Once the Lambda function _ProcessTextract_ is done, it publishes a message 
   in the Amazon SQS queue _ProcessedTextractQueue_.
5. Each message in SQS queue triggers the Lambda function _SelectablePDF_ which takes 
   as argument the input PDF and its textract response. The function rasterizes each 
   page of the PDF and overlay transparent characters over each page. These characters 
   are selectable and don't interfere with the PDF visuals as they are transparent. The 
   pages are rasterized to avoid the "double character" overlay problem if the original 
   PDF already contains selectable text. To place the transparent characters at the right 
   position on the pages, the Lambda function _SelectablePDF_ uses the bounding boxes 
   defined for each `WORD` blocks in the Textract response. The font size of the transparent 
   characters is optimized to improve the overlay. The document `examples/SampleOutput.pdf` is the processed version of `examples/SampleInput.pdf`.

The Application Logging Layer uses DynamoDB to log the status of each file uploaded 
_InputDocuments_ S3 bucket. These logs are stored in the _Documents_ table. The code 
logs (e.g. the Lambda function logs) are stored in CloudWatch, as usual.

This architecture can easily be integrated to a more complex document processing 
infrastructure,such as the [amazon-textract-serverless-large-scale-document-processing](https://github.com/aws-samples/amazon-textract-serverless-large-scale-document-processing) reference 
architecture.

## Installation

Follow ths instructions in `selectable_pdf_infra/README.md` to deploy the application 
and its infrastructure.

## Usage
1. Upload one or more PDF's in the Amazon S3 bucket _InputDocuments_ (see figure 1). 
   For example, you can upload the file `examples/SampleInput.pdf` included in this 
   repo with:
   ```bash
   aws s3 cp examples/SampleInput.pdf s3://<InputDocuments>
   ```
2. Wait from 1 minute to 30 minutes (depending on the size of the PDF's), then you 
   can find the selectable version of the input PDF's in the S3 bucket 
   _ProcessedDocuments_. The processed document will have the same name than the input 
   document. You can fetch it with:
   ```bash
   aws s3 cp s3://<ProcessedDocuments>/SampleInput.pdf  examples/SampleInput_selectable.pdf 
   ```

In the _ProcessedDocuments_ bucket, you can also find folders which contains the Textract 
output for each processed document. The folders are named according the document_id generated 
for each processed document. You can link `document_id` and `document_name` with the DynamoDB 
table named `<STACK_NAME>-Documents<UID>`. This table is sorted with the document_id as ID key and 
the document name as hash key. Here is a code snippet to extract `document_id` and 
`document_name` from the DynamoDB table:
```python
import boto3
import json

# after deployment you can find the table name:
# 1. in the CDK outputs
# 2. In the AWS Console: go to the DynamoDB table and look for a table named 
#    `<stack_name>-Documents<UID>` where UID is a set of 15 to 25 random characters 
#    give by CDK to this resource.
table_name = '<stack_name>-Documents<UID>'

ddb_client = boto3.client('dynamodb')
response = ddb_client.scan(TableName=table_name)
for item in response['Items']:
    print(f"doc name: {item['document_name']['S']}, doc ID: {item['document_id']['S']}")
```
You can also get similar results using the DynamoDB helper class in the `helpertools` 
library included in this repository (see `lib/helpertools`). In this example below, 
you need to specify the document ID:
```python
from helpertools import ProcessingDdbTable

# after deployment you can find the table name:
# 1. in the CDK outputs
# 2. In the AWS Console: go to the DynamoDB table and look for a table named 
#    `<stack_name>-Documents<UID>` where UID is a set of 15 to 25 random characters 
#    give by CDK to this resource.
table_name = '<stack_name>-Documents<UID>'
doc_id = 'my_doc_id'
ddb_table = ProcessingDdbTable(table_name)
items = ddb_table.get_items(doc_id)
for item in items: #only one item
   print(f"doc name: {item['document_name']}, doc ID: {item['document_id']}")
```

The Textract output is key for downstream tasks such as Natural Language Processing (NLP).

## Usage as a module
The main goal of this stack is to convert scanned PDF into selectable PDF. Nevertheless, 
this is rarely the end goal. These selectable PDF can be used for downstream tasks 
such as language processing (AI/ML) or indexing for a search engine. You can integrate 
`amazon-textract-large-scale-selectable-pdf` in your stack as follow:
1. install `amazon-textract-large-scale-selectable-pdf` in your python environnement 
   with 
   ```bash
   $ pip install "git+https://github.com/aws-samples/amazon-textract-large-scale-selectable-pdf.git#egg=selectable_pdf_infra&subdirectory=selectable_pdf_infra"
   ```
2. in your CDK app (e.g. `app.py`), deploy the `amazon-textract-large-scale-selectable-pdf` 
   stack and reuse its resources with:
   ```python
   import aws_cdk as cdk
   from selectable_pdf_infra.selectable_pdf_stack import SelectablePdfStack
   from my_downstream_stack import DownstreamStack

   app = cdk.App()
   ocr_stack = SelectablePdfStack(app, 'ocr-stack', add_final_sns=True)
   ds_stack = DownstreamStack(app, 'ds-stack',
      bucket_with_original_pdfs=ocr_stack.doc_bucket,
      bucket_with_process_pdfs=ocr_stack.processed_bucket,
      sns_trigger=ocr_stack.final_sns_topic
   )
   ```
   the variable `ocr_stack.final_sns_topic` is an object representing an Amazon SNS topic.
   The topic is created in `ocr-stack` only if `add_final_sns=True`. The `ocr-stack` 
   will publish a message in this topic with information about each processed document.
   Example of message:
   ```json
   {
      "document_name": "SampleInput.pdf",
      "document_id": "<doc-id>",
      "textract_response_s3": {
         "bucket": "",
         "key": "<doc-id>/"
      }
      "processed_document_s3": {
         "bucket": "<processed_doc_bucket>",
         "key": "SampleInput.pdf"
      },
      
      "original_document_s3": {
         "bucket": "<input_doc_bucket>",
         "key": "SampleInput.pdf"
      }
   }
   ```
   You can use this sns message by subscribing the SNS topic to one of the resources 
   in `ds_stack`.

## Notes
* Partially based on this (AWS blog post)[https://aws.amazon.com/blogs/machine-learning/generating-searchable-pdfs-from-scanned-documents-automatically-with-amazon-textract/].

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.