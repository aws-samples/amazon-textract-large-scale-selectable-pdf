'''
# textractparser

A collection of tool the manipulate textract and a2i IO payloads: 
'''

# import modules
import os
import json
import boto3
from typing import List, Dict, Tuple, Any


# Classes
class TextractParser():
    '''
    A class to parse and manipulate textract results (the blocks).
    '''
    # constructors
    def __init__(self, blocks: List) -> None:
        '''
        Default constructor from a list of Textract blocks (only the blocks!).

        Usage
        -----
        tt_res = TextractParser(blocks)

        Arguments
        ---------
        blocks: List
            The value (a list) of the "blocks" key  in a textract output

        Returns
        -------
        tt_res: TextractParser
            The TextractParser object
        '''
        # store the blocks in a hashmap with the block ID as key
        self.blocks = dict()
        # Store special blocks for fast retrival (O(1)) in the main hashmap.
        self.table_ids = list()
        self.form_ids = list()
        for blk in blocks:
            blk_id = blk['Id']
            self.blocks[blk_id] = blk
            # check if the current block is a special block
            if blk['BlockType']=="TABLE":
                self.table_ids.append(blk_id)
            if blk['BlockType']=="FORM":
                self.form_ids.append(blk_id)


    @classmethod
    def from_textract_result(cls, job_id:str) -> None:
        '''
        Build a TextractParser object from a Textract Job ID
        '''
        return cls(get_textract_result_blocks(job_id)['Blocks'])


    # methods
    def table_as_list(self, Id: str, order: str = 'C') -> Tuple[List[List], 
        List[List], 
        List[List]]:
        '''
        Convert a table block into a list o list (i.e. a table).

        Usage
        -----
        table,table_avg_text_conf,table_cell_conf = self.table_as_list(Id, order='C')

        Arguments
        ---------
        Id: str
            the block ID of the table. the list of table ID can be retrived 
            with self.table_ids
        order: str. Default: 'C' ['C', 'F']
            Specify the layout of the table in the list of list. 'C' for row 
            major and 'F' for column major. Only 'C' order supported at the 
            moment.

        Returns
        -------
        table: List[List]
            The table as a list of list
        table_avg_text_conf: List[List]
            The average confidence in each cell of `table`. Given as a list of list
        table_cell_conf: List[List]
            The cell confidence in each cell of `table`. Given as a list of list. 
            Cell confidence is a mesure on how much Textract is sure that it is 
            a cell.
        '''
        table_blk = self.blocks[Id]
        rows = {}
        rows_avg_text_conf = {}
        rows_cell_conf = {}
        for relationship in table_blk['Relationships']:
            if relationship['Type'] == 'CHILD':
                for child_id in relationship['Ids']:
                    cell = self.blocks[child_id]
                    if cell['BlockType'] == 'CELL':
                        row_index = cell['RowIndex']
                        col_index = cell['ColumnIndex']
                        if row_index not in rows:
                            # create new row
                            rows[row_index] = {}
                            rows_avg_text_conf[row_index] = {}
                            rows_cell_conf[row_index] = {}
                            
                        # get various info about the cell: the text the average 
                        # confidence on the text and the cell confidence
                        rows[row_index][col_index] = self.get_cell_text(child_id)
                        rows_avg_text_conf[row_index][col_index] = self.get_cell_text_confidence(child_id)
                        rows_cell_conf[row_index][col_index] = self.get_cell_confidence(child_id)

        # rows is a dict of dict with the key being the rows index and the column 
        # index. lets rebuild the table as a list of list.
        def rows_to_table(rows):
            '''helper function'''
            nrows = len(rows)
            ncols = len(rows[list(rows.keys())[0]])
            table = [ncols*[None] for i in range(nrows)]
            for i in range(nrows):
                for j in range(ncols):
                    tt = rows[i+1][j+1]
                    table[i][j] = tt
            return table

        table = rows_to_table(rows)
        table_avg_text_conf = rows_to_table(rows_avg_text_conf)
        table_cell_conf = rows_to_table(rows_cell_conf)

        return table, table_avg_text_conf, table_cell_conf


    def tables_as_list(self, order: str = 'C') -> Tuple[Dict[str, List[List]],
        Dict[str, List[List]],
        Dict[str, List[List]]]:
        '''
        Return all the tables in a hashmap with the table block ID as key. The 
        tables are in form of list of list.

        Usage
        -----
        tables, tables_avg_text_conf, tables_cell_conf = self.tables_as_list()

        Arguments
        ---------
        order: str. Default: 'C' ['C', 'F']
            Specify the layout of the table in the list of list. 'C' for row 
            major and 'F' for column major. Only 'C' order supported at the 
            moment.

        Returns
        -------
        tables:
            The tables stored in a dict with the table IDs as dict key.
        tables_avg_text_conf:
            The tables average text confidence stored in a dict with the table 
            IDs as dict key.
        tables_cell_conf:
            The tables cell confidence stored in a dict with the table IDs as dict 
            key.
        '''
        tables = dict()
        tables_avg_text_conf = dict()
        tables_cell_conf = dict()
        for table_id in self.table_ids:
            table, table_avg_text_conf, table_cell_conf = self.table_as_list(table_id)
            tables[table_id] = table
            tables_avg_text_conf[table_id] = table_avg_text_conf
            tables_cell_conf[table_id] = table_cell_conf
        return tables, tables_avg_text_conf, tables_cell_conf


    def get_cell_text(self, cell_id: str) -> str:
        '''
        Return the text in a cell. A cell is an entry of a table. If the cell_id 
        does not contain text, the function returns '' (empty string).
        '''
        text = ''
        cell_blk = self.blocks[cell_id]
        if cell_blk['BlockType']!='CELL':
            return text
        if 'Relationships' in cell_blk:
            for relationship in cell_blk['Relationships']:
                if relationship['Type'] == 'CHILD':
                    for child_id in relationship['Ids']:
                        word = self.blocks[child_id]
                        if word['BlockType'] == 'WORD':
                            text += word['Text'] + ' '
                        if word['BlockType'] == 'SELECTION_ELEMENT':
                            if word['SelectionStatus'] =='SELECTED':
                                text +=  'X '
        return text[:-1]

    
    def get_cell_confidence(self, cell_id: str) -> float:
        '''
        Return the cell confidence, i.e. how sure this item cover by this id 
        (cell_id) is really a cell. If the cell_id does not contain a confidence 
        score, the function returns 0.0.
        '''
        default_confidence = 100.0
        confidence = 0.0
        cell_blk = self.blocks[cell_id]
        if cell_blk['BlockType']!='CELL':
            return default_confidence
        if 'Confidence' in cell_blk:
            confidence = cell_blk['Confidence']
        return confidence


    def get_cell_text_confidence(self, cell_id: str) -> float:
        '''
        Return the average confidence (as percent decimal) of all the text within 
        a cell. If the cell_id does not contain text, the function returns 0.0.
        '''
        default_confidence = 100.0
        confidences = list()
        cell_blk = self.blocks[cell_id]
        if cell_blk['BlockType']!='CELL':
            return default_confidence
        if 'Relationships' in cell_blk:
            for relationship in cell_blk['Relationships']:
                if relationship['Type'] == 'CHILD':
                    for child_id in relationship['Ids']:
                        word = self.blocks[child_id]
                        if word['BlockType'] == 'WORD':
                            confidences.append(float(word['Confidence']))
        if len(confidences)==0:
            return default_confidence
        else:
            return sum(confidences)/len(confidences)


    def get_table_column(self, index: int, Id: str) -> List:
        '''
        Return the column `index` of the table identified by Id. The list of table 
        Ids can be fetch with self.table_ids.
        '''
        table, _, _ = self.table_as_list(Id)
        return [row[index] for row in table]


    def get_table_row(self, index: int, Id: str) -> List:
        '''
        Return the row `index` of the table identified by Id. The list of table 
        Ids can be fetch with self.table_ids.
        '''
        table, _, _ = self.table_as_list(Id)
        return table[index]


    def string_representation(self) -> str:
        '''
        Return object info as a string. Helper function used for print and 
        representation calls
        '''
        return (
            'textract_a2i_tools.TextractResults, nb_blocks: {}, nb_tables: {}, nb_forms: {}'
        ).format(len(self.blocks), len(self.table_ids), len(self.form_ids))


    def tables_to_a2i_payload(
        self, 
        s3url_original_pdf: str, 
        a2i_input_object: str,
        a2i_output_object: str,
        dummy_titles: List[str] = None,
        add_signed_urls: bool = True
    ) -> Dict:
        '''
        convert the tables to payload for the a2i custom UI. The custom UI needs 
        the tables (provided by self) and the s3 url. This method generates ONLY
        the payload for the custom UI, which must be embedded into the A2I 
        payload.

        Usage
        -----
        a2i_payload = self.tables_to_a2i_payload(stuff...)

        Arguments
        ---------

        Returns
        -------
        a2i_payload
        '''
        tables, tables_avg_text_conf, tables_cell_conf = self.tables_as_list()

        # create the payload dict
        a2i_payload = dict()
        if dummy_titles==None:
            dummy_titles = 100*['']
        a2i_payload['Titles'] = dummy_titles # is it still required?
        a2i_payload['Pages'] = list()

        # loop through the tables
        for table_id,table in tables.items():
            table_avg_text_conf = tables_avg_text_conf[table_id]
            table_cell_conf = tables_cell_conf[table_id]
            page = dict()
            page['Table'] = table_id
            page['PageNumber'] = self.blocks[table_id]['Page']
            rows = list()
            for i in range(len(table)):
                row = dict()
                row['Row'] = str(i+1)
                cells = list()
                for j in range(len(table[i])):
                    cell = dict()
                    cell['Text'] = table[i][j]
                    # cell['Confidence'] = table_cell_conf[i][j] # this one seems wrong
                    # cell['WordConfidence'] = [table_avg_text_conf[i][j]]
                    cell['Confidence'] = table_avg_text_conf[i][j]  # this is one used in the UI
                    cell['WordConfidence'] = [table_avg_text_conf[i][j]]
                    cell['Column'] = str(j+1)
                    cells.append(cell)
                row['Cells'] = cells
                rows.append(row)
            page['Rows'] = rows
            a2i_payload['Pages'].append(page)

        # add the s3 urls
        a2i_payload['meta-data'] = {
            "original-object": s3url_original_pdf,
            "a2i_input_object": a2i_input_object,
            "a2i_output_object": a2i_output_object,
        }

        if add_signed_urls:
            a2i_payload = add_presignedurl_to_A2Ipayload(
                a2i_payload=a2i_payload, 
                a2i_input_object=a2i_input_object, 
                a2i_output_object=a2i_output_object,
                expiration_input=7*24*3600,  #seven days
                expiration_output=7*24*3600,  #seven days
                s3_client=None,
            )
        
        # return
        return a2i_payload


    def __repr__(self):
        '''
        Representation call. Example:
        ```
        self
        ```
        '''
        return self.string_representation()


    def __str__(self):
        '''
        print call. Example:
        ```
        print(self)
        ```
        '''
        return self.string_representation()


    @staticmethod
    def get_textract_result_blocks(job_id: str) -> Dict[str, Any]:
        '''
        Return the textract results blocks. In the Textract language, a block is 
        a `piece of text`, i.e. a sentence, a title, a footnote, a table, etc
        
        Usage
        -----
        textract_output = TextractParser.get_textract_result_blocks(job_id)

        Arguments
        ---------
        job_id
            Textract job ID. When starting a Textract job, the http response 
            contains the job ID which you can use to get the results back with 
            this function.

        Returns
        -------
        textract_output
            The Textract output. with the following structure:
            {
                'Blocks': ..., 
                'DocumentMetadata': ..., 
                'JobStatus': ..., 
                'NextToken': ..., 
                'AnalyzeDocumentModelVersion': ..., 
                'ResponseMetadata': ...
            ]
        '''
        textract_client = boto3.client('textract')
        extraArgs = {}
        result_value = {'Blocks': list()}
        while True:
            textract_results = textract_client.get_document_analysis(
                JobId=job_id, **extraArgs
            )
            for k,v in textract_results.items():
                if k=='Blocks':
                    result_value['Blocks'].extend(textract_results['Blocks'])
                else:
                    result_value[k] = v
            if 'NextToken' in textract_results:
                extraArgs['NextToken'] = textract_results['NextToken']
            else:
                break
        return result_value


# functions
# ---------
def table_2_csv(table: List[List], output_csv: str, sep: str = ',') -> None:
    '''
    Convert a list of list (i.e. a table) to a csv

    Usage
    -----
    table_2_csv(table, output_csv, sep=',')

    Arguments
    ---------
    table: List[List]
        A table as a list of list
    output_csv: str
        The filename of the output csv
    sep: string
        The separator used in the csv. Default: ','.
    '''
    csv_str = ''
    for i in range(len(table)):
        for j in range(len(table[i])):
            csv_str += '{}{}'.format(table[i][j], sep)
        csv_str = csv_str[:-1]+'\n'

    with open(output_csv, 'w') as fw:
        fw.write(csv_str)


def get_textract_result_blocks(job_id: str) -> Dict:
    '''
    Return the textract results blocks. In the Textract language, a block is 
    a `piece of text`, i.e. a sentence, a title, a footnote, a table, etc. The 
    Textract job status must be SUCCEEDED.
    
    Usage
    -----
    blocks = get_textract_result_blocks(job_id)
    '''
    textract_client = boto3.client('textract')

    # check job status
    job_status = textract_client.get_document_analysis(JobId=job_id)['JobStatus']
    if job_status!='SUCCEEDED':
        raise ValueError('Textract job in progress')

    extraArgs = {}
    result_value = {"Blocks": []}
    while True:
        textract_results = textract_client.get_document_analysis(
            JobId=job_id, **extraArgs
        )
        result_value['Blocks'].extend(textract_results['Blocks'])
        if 'NextToken' in textract_results:
            extraArgs['NextToken'] = textract_results['NextToken']
        else:
            break
    return result_value


def add_presignedurl_to_A2Ipayload(
    a2i_payload: Dict, 
    a2i_input_object: str, 
    a2i_output_object: str,
    expiration_input: int = 3600,
    expiration_output: int = 3600,
    s3_client=None,
) -> Dict:
    '''
    Add the presigned s3urls to an A2I payload. The A2I payload is a dict with 
    several keys (currently: "Titles", "Pages" and "meta-data"). This function 
    adds (or create) to the keys"a2i_input_presigned" and "a2i_output_presigned" 
    in "meta-data". The A2I payload can be created with a TextractParser object.

    Usage
    -----
    a2i_payload = add_presignedurl_to_A2Ipayload(
        a2i_payload, 
        a2i_input_object, 
        a2i_output_object,
        expiration_input,
        expiration_output,
        s3_client
    )

    Arguments  (TODO: complete description)
    ---------
    a2i_payload
    a2i_input_object 
    a2i_output_object
    expiration_input
    expiration_output
    s3_client

    Returns  (TODO: complete description)
    -------
    a2i_payload
    '''
    if s3_client is None:
        s3_client = boto3.client('s3')
    
    # presigned url for the input
    a2i_input_parts = extract_bucket_key(a2i_input_object)
    resp_presign_in = s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket':a2i_input_parts['bucket'], 'Key':a2i_input_parts['key']},
        ExpiresIn=expiration_input
    )
    a2i_payload['meta-data']['a2i_input_presigned'] = resp_presign_in

    # presigned url for the output
    a2i_output_parts = extract_bucket_key(a2i_output_object)
    resp_presign_out = s3_client.generate_presigned_post(
        a2i_output_parts['bucket'],
        a2i_output_parts['key'],
        Fields=None,
        Conditions=None,
        ExpiresIn=expiration_output
    )
    a2i_payload['meta-data']['a2i_output_presigned'] = resp_presign_out

    return a2i_payload


def extract_bucket_key(s3url: str) -> Dict:
    '''
    Extract the bucket and the key from a s3 url. Returns a dict with "bucket" 
    and "key" as keys. An s3 url has the following form:
        s3://my-bucket/localtion/of/my_file.json
    from the this s3 url, we can extract:
    * the bucket: my-bucket
    * the object key: localtion/of/my_file.json
    '''
    splits = s3url.split('/')
    return {'bucket':splits[2], 'key':'/'.join(splits[3:])}




