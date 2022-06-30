'''
ddb_tools
---------

A collection of function to read, write and create the dynamoDB table use to log the 
stack operations
'''
import logging
import boto3
import datetime
from boto3.dynamodb.conditions import Key
from typing import Dict, Any, List


# preparation
# -----------
# get the root logger
logger = logging.getLogger()

# global variables
LOGGING_DATETIME_FORMAT = '%Y-%m-%dT %H:%M:%S.%f'


# classes
# -------
class ProcessingDdbTable():
    def __init__(self, ddb_table_name: str) -> None:
        '''
        Construct a Processing Dynamo DB (ProcessingDdbTable) object. The DynamoDB table 
        must exist and keys must be:
        * hash key: document_id (string)
        * range key: document_name (string)
        '''
        self.table_name = ddb_table_name
        self.ddb_ress = boto3.resource('dynamodb')
        self.table = self.ddb_ress.Table(ddb_table_name)
        if self.is_table_well_defined() is not True:
            raise ValueError(
                f'DynamoDB table {self.table_name} is not defined to be a ProcessingDdbTable object'
            )


    def is_table_well_defined(self) -> bool:
        '''
        Test if self.table is defined properly, with the keys:
        * hash key: document_id (string)
        * range key: document_name (string)
        '''
        atts = self.table.attribute_definitions
        if (   (len(atts)!=2) 
             | (atts[0]['AttributeName']!='document_id') 
             | (atts[0]['AttributeType']!='S')
             | (atts[1]['AttributeName']!='document_name') 
             | (atts[1]['AttributeType']!='S')
        ):
            return False
        else:
            return True


    def update_item(
        self, 
        doc_id: str, 
        doc_name: str, 
        key: str, 
        value: Dict, 
        add_logging_datetime: bool=True,
        logging_datetime_format: str=LOGGING_DATETIME_FORMAT
    ) -> Dict[str, Any]:
        '''
        Update a key-value pair of an existing item oin DynamoDB. 
        
        Notes
        -----
        * This function is designed to be used with this project, i.e. the DynamoDB hash 
        key and range key use the document id and document name, respectively
        '''
        try:
            if add_logging_datetime:
                value = self.add_logging_datetime_to_dict(value, format=logging_datetime_format)
            resp = self.table.update_item(
                Key={
                    'document_id': doc_id,  # HASH key
                    'document_name': doc_name  # RANGE key
                },
                UpdateExpression=f'SET {key}=:att1',  # This will set a new attribute for the selected item
                ExpressionAttributeValues={f':att1': value}
            )
            return resp
        except Exception as ex:
            logger.error(
                (f'Cannot update item "doc_id={doc_id}, doc_name={doc_name}" '
                f'in DynamoDB table {self.table_name}')
            )
            raise ex


    def put_item(
        self, 
        doc_id: str, 
        doc_name: str, 
        item: Dict,
        add_logging_datetime: bool=True,
        logging_datetime_format: str=LOGGING_DATETIME_FORMAT
    ) -> Dict[str, Any]:
        '''
        Put a new item in a DynamoDB table, where the doc_id is the hash key and the 
        document name is the range key.

        Notes
        -----
        * This function is designed to be used with this project, i.e. the DynamoDB hash 
        key and range key use the document id and document name, respectively
        '''
        try:
            keys = {
                'document_id': doc_id,
                'document_name': doc_name,
            }
            item.update(keys)
            if add_logging_datetime:
                item = self.add_logging_datetime_to_dict(item, format=logging_datetime_format)
            resp = self.table.put_item(Item=item)
            return resp
        except Exception as ex:
            logger.error(
                (f'Cannot put item "doc_id={doc_id}, doc_name={doc_name}" '
                f'into DynamoDB table {self.table_name}')
            )
            raise ex


    def get_item(self, doc_id: str, doc_name: str) -> Dict:
        '''
        Get an item and all its key-value pairs, where the doc_id is the hash key and the 
        document name is the range key.

        Notes
        -----
        * This function is designed to be used with this project, i.e. the DynamoDB hash 
        key and range key use the document id and document name, respectively
        '''
        try:
            resp = self.table.get_item(
                Key={
                    'document_id': doc_id,  # HASH key
                    'document_name': doc_name  # RANGE key    
                },
                ConsistentRead=True,
            )
            return resp['Item']
        except Exception as ex:
            logger.error(
                (f'Cannot get item "doc_id={doc_id}, doc_name={doc_name}" '
                f'from DynamoDB table {self.table_name}')
            )
            raise ex


    def get_items(self, doc_id: str, doc_name: str='') -> List[Dict]:
        '''
        Get all items and  with the hash_key=doc_id. Use this function to retrive 
        information about a document if you don't know the document name. 
        
        Notes
        -----
        * This function might return more than 1 document. If it's the case, then 
          you have an issue as we want the doc_id to be unique!
        * This function is designed to be used with this project, i.e. the DynamoDB 
          hash key and range key use the document id and document name, respectively
        '''
        if doc_name=='':
            resp = self.table.query(
                KeyConditionExpression=Key('document_id').eq(doc_id),
                ConsistentRead=True,
            )
            return resp['Items']
        else:
            item = self.get_item(doc_id, doc_name)
            return [item]


    def add_logging_datetime_to_dict(
        self,
        hashmap: Dict[str, Any],
        key: str='logging_datetime',
        format: str=LOGGING_DATETIME_FORMAT,
    ) -> Dict[str, Any]:
        '''
        '''
        if key in hashmap.keys():
            raise KeyError(f'key key is already in dict.keys()={hashmap.keys()}')
        hashmap[key] = datetime.datetime.now().strftime(format)
        return hashmap

