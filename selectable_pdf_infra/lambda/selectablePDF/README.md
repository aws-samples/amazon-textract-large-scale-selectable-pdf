# Searchable PDF

AWS Lambda function code to turn non-searchable PDFs (i.e. where the text is not 
selectable) into searchable PDFs (i.e. where the text can be selected).

The source code also contains demo code which can run locally on the document 
examples.

## installation
The following tools need to be installed and correctly set up:
* Java 11 or higher (it might work with previous version of Java)
    * Java Runtime Environment (JRE)
    * Java Development Kit (JDK)
* Apache [Maven](https://maven.apache.org/)

In the folder of this README.md, run the following command in a terminal:
```bash
$ mvn package
```
The build process creates the standalone jar-file `searchable-pdf-1.0.jar` in 
the `target` folder.

## local execution
You can run an example locally with 
```bash
$ java -cp target/selectable-pdf-1.0.jar Demo
```

## deploy in a AWS Lambda function
After having compile the code with `mvn package` (see installation section), you can use the jar-file `target/selectable-pdf-1.0.jar` in a Lambda function 