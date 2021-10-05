public class Demo {
    public static void main(String args[]) {
        try {
            //Generate searchable PDF from local pdf with Block file already exsiting
            DemoPdfFromLocalPdfWithBlockJson localPdf = new DemoPdfFromLocalPdfWithBlockJson();
            localPdf.run(
                "./documents/SampleInput.pdf", 
                "./documents/SampleInput_blocks.json", 
                "./documents/SampleOutput.pdf"
            );
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
