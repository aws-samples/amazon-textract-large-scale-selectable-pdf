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
* Machine Leanring tasks, such as:
    * Natural Language Processing (NLP)
    * NLP annotations
    * Document summarization
    * Document classification
    * Document topic analysis

## Architecture

The figure 1 shows the archecture used by the _large-scale-selectable-pdf_ application. 
The workflow runs as follow:
1. The user starts by uploading one or several PDF's in the _InputDocument_ Amazon 
   S3 bucket. 
2. Each document uploaded to S3 will automatically trigger the _Starttextract_ Amazon
   Lambda function. This is where the parallel processing of document starts.
3. Each _Starttextract_ Lambda function triggers an asychronous Textract job which
   can last from 1 minute to 30 minutes, depending on the size (i.e. number of pages) 
   of the document. Each Textract job will write a message in Amazon SNS when finished.
4. Each SNS message triggers the Lambda function _ProcessTextract_ which download 
   the results from Textract and save them to S3. Once done, it publishes a message 
   in the Amazon SQS queue _ProcessedTextractQueue_.
5. Each message in SQS triggers the Lambda _SelectablePDF_ which takes as argument 
   the input PDF and the textract results of this  PDF. The function convert each 
    page of the PDF into an image and overlay transparent text to make the characters 
    in each page selectable. The output PDF is written in the S3 bucket 
    _ProcessedDocuments_ with the same name as the input PDF.

The Application Logging Layer uses DynamoDB to log the status of each file uploaded 
_InputDocuments_ S3 bucket. These logs are stored in the _Documents_ table. The code 
logs (e.g. the Lambda function logs) are stored in CloudWatch, as usual.

This architecutre can easily be integrated to a more complex document processing 
infrastructure,such as the [amazon-textract-serverless-large-scale-document-processing](https://github.com/aws-samples/amazon-textract-serverless-large-scale-document-processing) reference 
architecture.

![Selectable PDF architecture](selectable_pdf_architecture.png "Selectable PDF architecture")

__Fig.1:__ Architecture diagram of the _large-scale-selectable-pdf_ application.

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

## Notes
* Partially based on this (AWS blog post)[https://aws.amazon.com/blogs/machine-learning/generating-searchable-pdfs-from-scanned-documents-automatically-with-amazon-textract/].

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.