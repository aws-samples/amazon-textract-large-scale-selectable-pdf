package com.amazon.textract.pdf;

import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.graphics.image.JPEGFactory;
import org.apache.pdfbox.pdmodel.graphics.image.LosslessFactory;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;
import org.apache.pdfbox.pdmodel.graphics.state.RenderingMode;
import java.awt.image.BufferedImage;
import java.io.*;
import java.util.List;
import java.lang.Math;

public class PDFDocument {

    final PDFont font = PDType1Font.COURIER;
    // final PDFont font = PDType1Font.HELVETICA;
    private PDDocument document;

    public PDFDocument(){
        this.document = new PDDocument();
    }

    public PDFDocument(InputStream inputDocument) throws IOException {
        this.document = PDDocument.load(inputDocument);
    }

    public void addText(int pageIndex, List<TextLine> lines) throws IOException {
        PDPage page = document.getPage(pageIndex);

        float height = page.getMediaBox().getHeight();

        float width = page.getMediaBox().getWidth();

        PDPageContentStream contentStream = new PDPageContentStream(document, page, PDPageContentStream.AppendMode.APPEND, false );
        contentStream.setRenderingMode(RenderingMode.NEITHER); //transparent font

        for (TextLine cline : lines){
            FontInfo fontInfo = calculateFontSize(cline.text, (float)cline.width*width, (float)cline.height*height);
            contentStream.beginText();
            contentStream.setFont(this.font, fontInfo.fontSize);
            contentStream.newLineAtOffset((float)cline.left*width, (float)(height-height*cline.top-fontInfo.textHeight));
            contentStream.showText(cline.text);
            contentStream.endText();
        }

        contentStream.close();
    }

    /**
     * Compute the ideal font size to fit the text bounding box. 
     * @param text text
     * @param bbWidth absolute width of the bounding box containing the text
     * @param bbHeight absolute height of the bounding box containing the text
     * @return the font size
     * @throws IOException
     */
    private FontInfo calculateFontSize(String text, float bbWidth, float bbHeight) throws IOException {
        float floatFontSize = bbWidth / (font.getStringWidth(text) / (float)1000.0);
        int fontSize = Math.round(floatFontSize);
        float textWidth = font.getStringWidth(text) / 1000 * fontSize;
        float textHeight = font.getFontDescriptor().getFontBoundingBox().getHeight() / 1000 * fontSize;

        FontInfo fi = new FontInfo();
        fi.fontSize = fontSize;
        fi.textHeight = textHeight;
        fi.textWidth = textWidth;

        return fi;
    }

    /**
     * add a page to the PDF (self)
     *
     * @param image the image of the page to add to the PDF
     * @param imageType the image type
     * @param lines list of lines to add as transparent text to the page
     * @throws IOException
     */
    public void addPage(BufferedImage image, ImageType imageType, List<TextLine> lines) throws IOException {

        float width = image.getWidth();
        float height = image.getHeight();

        PDRectangle box = new PDRectangle(width, height);
        PDPage page = new PDPage(box);
        page.setMediaBox(box);
        this.document.addPage(page);

        PDImageXObject pdImage = null;

        if(imageType == ImageType.JPEG){
            pdImage = JPEGFactory.createFromImage(this.document, image);
        }
        else {
            pdImage = LosslessFactory.createFromImage(this.document, image);
        }

        PDPageContentStream contentStream = new PDPageContentStream(document, page);

        contentStream.drawImage(pdImage, 0, 0);

        contentStream.setRenderingMode(RenderingMode.NEITHER);

        for (TextLine cline : lines){
            FontInfo fontInfo = calculateFontSize(cline.text, (float)cline.width*width, (float)cline.height*height);
            contentStream.beginText();
            contentStream.setFont(this.font, fontInfo.fontSize);
            contentStream.newLineAtOffset(
                (float)cline.left*width, 
                (float)((1.0-cline.top)*height-fontInfo.textHeight)
            );
            contentStream.showText(cline.text);
            contentStream.endText();
        }

        contentStream.close();
    }

    public void save(String path) throws IOException {
        this.document.save(new File(path));
    }

    public void save(OutputStream os) throws IOException {
        this.document.save(os);
    }

    public void close() throws IOException {
        this.document.close();
    }
}
