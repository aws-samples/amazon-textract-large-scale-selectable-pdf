import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.SQSEvent;
import com.amazonaws.services.lambda.runtime.LambdaLogger;
import com.amazonaws.services.lambda.runtime.events.SQSEvent.SQSMessage;

import org.json.JSONObject;
import org.json.JSONTokener;

import com.amazonaws.services.s3.AmazonS3;
import com.amazonaws.services.s3.model.S3Object;
import com.amazonaws.services.s3.AmazonS3ClientBuilder;
import com.amazonaws.services.s3.model.GetObjectRequest;
import com.amazonaws.services.s3.model.PutObjectRequest;

import java.io.File;
import java.io.IOException;
import org.apache.commons.io.FileUtils;

// import java.util.logging.Logger;
// import java.util.logging.Level;

public class LambdaSqs implements RequestHandler<SQSEvent, String> {

    @Override
    public String handleRequest(SQSEvent event, Context context) {
        LambdaLogger logger = context.getLogger();

        for(SQSMessage msg : event.getRecords()) {

            logger.log("sqs message body: " + msg.getBody());

            // convert the message body (a JSON formatted string) into something more usable
            JSONObject msgObj = (JSONObject) new JSONTokener(msg.getBody()).nextValue();
            String documentId = msgObj.getString("document_id");
            String documentName = msgObj.getString("document_name");

            logger.log("document ID: " + documentId);
            logger.log("document name: " + documentName);

            // download the required files from s3
            // future imporvement: load directly in memory
            JSONObject docS3Url = msgObj.getJSONObject("original_document_s3");
            this.downloadFileFromS3(
                docS3Url.getString("bucket"), 
                docS3Url.getString("key"), 
                "/tmp/input.pdf"
            );
            JSONObject ttBlocksS3Url = msgObj.getJSONObject("textract_output_s3");
            this.downloadFileFromS3(
                ttBlocksS3Url.getString("bucket"), 
                ttBlocksS3Url.getString("key"), 
                "/tmp/textract_output_blocks.json"
            );

            // process the pdf
            try {
                DemoPdfFromLocalPdfWithBlockJson localPdf = new DemoPdfFromLocalPdfWithBlockJson();
                localPdf.run(
                    "/tmp/input.pdf", 
                    "/tmp/textract_output_blocks.json", 
                    "/tmp/output.pdf"
                );
            } catch (IOException err) {
                err.printStackTrace();
                System.out.println(err.getMessage());
            }

            // write ouput.pdf back to s3
            // try catch/retry
            String outputBucket = System.getenv("OUTPUT_BUCKET");
            this.uploadFileToS3("/tmp/output.pdf", outputBucket, documentName);
        }
        return null;
    }


    /**
     * Download an object (i.e. a file) from S3
     * @param bucket bucket name where the object is located
     * @param key key name of the object
     * @param fileName file name to give to the downloaded object
     */
    public void downloadFileFromS3(String bucket, String key, String fileName) {
        AmazonS3 s3Client = AmazonS3ClientBuilder.defaultClient();
        S3Object s3Object = s3Client.getObject(new GetObjectRequest(bucket, key));

        try {
            FileUtils.copyInputStreamToFile(s3Object.getObjectContent(), new File(fileName));
        } catch (IOException err) {
            err.printStackTrace();
            System.out.println(err.getMessage());
        }
    }

    
    /**
     * Upload a file to S3
     * @param fileName name of the file to upload
     * @param bucket bucket name where the object is uploaded
     * @param key key name of the uploaded object
     */
    public void uploadFileToS3(String fileName, String bucket, String key) {
        AmazonS3 s3Client = AmazonS3ClientBuilder.defaultClient();
        PutObjectRequest request = new PutObjectRequest(bucket, key, new File(fileName));
        s3Client.putObject(request);
    }

}