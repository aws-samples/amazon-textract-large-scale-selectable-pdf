import com.amazon.textract.pdf.ImageType;
import com.amazon.textract.pdf.PDFDocument;
import com.amazon.textract.pdf.TextLine;
import com.amazon.textract.pdf.TextractLineBlockManipulator;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.PDFRenderer;
import org.apache.pdfbox.tools.imageio.ImageIOUtil;
import java.awt.image.BufferedImage;
import java.io.*;
import java.nio.ByteBuffer;
import java.util.List;

import java.util.logging.Logger;
import java.util.logging.Level;

public class DemoPdfFromLocalPdfWithBlockJson {

    public Logger logger = Logger.getLogger(DemoPdfFromLocalPdfWithBlockJson.class.getName());

    public void run(String documentName, String blockFile, String outputDocumentName) throws IOException {

        logger.log(Level.INFO, "generating searchable pdf from: " + documentName);

        PDFDocument pdfDocument = new PDFDocument();

        List<TextLine> linesFromFile = null;
        BufferedImage image = null;
        ByteArrayOutputStream byteArrayOutputStream = null;
        ByteBuffer imageBytes = null;

        // Load the Textract blocks
        TextractLineBlockManipulator textractBlocks = new TextractLineBlockManipulator(blockFile);

        //Load pdf document and process each page as image
        PDDocument inputDocument = PDDocument.load(new File(documentName));
        PDFRenderer pdfRenderer = new PDFRenderer(inputDocument);
        for (int page = 0; page < inputDocument.getNumberOfPages(); ++page) {
            logger.log(Level.INFO, "processing page index: " + page);

            //Render image
            float imageDpi = 300;
            image = pdfRenderer.renderImageWithDPI(page, imageDpi, org.apache.pdfbox.rendering.ImageType.RGB);

            //Get image bytes
            String imageFormat = "jpeg";
            byteArrayOutputStream = new ByteArrayOutputStream();
            ImageIOUtil.writeImage(image, imageFormat, byteArrayOutputStream);
            byteArrayOutputStream.flush();
            imageBytes = ByteBuffer.wrap(byteArrayOutputStream.toByteArray());

            //Extract text
            linesFromFile = textractBlocks.getLineOnPage(page+1);

            //Add extracted text to pdf page
            pdfDocument.addPage(image, ImageType.JPEG, linesFromFile);
        }

        inputDocument.close();

        //Save PDF to local disk
        try (OutputStream outputStream = new FileOutputStream(outputDocumentName)) {
            pdfDocument.save(outputStream);
            pdfDocument.close();
        } 

        logger.log(Level.INFO, "Generated searchable pdf: " + outputDocumentName);
    }
}
