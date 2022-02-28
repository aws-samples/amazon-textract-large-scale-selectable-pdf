# import modules
# --------------
import os
import logging
import datetime

from typing import Dict

# preparation
# -----------
# get the root logger
logger = logging.getLogger()

# functions
# ---------
def get_logger(
    log_level: str='INFO', 
    log_format: str='%(levelname)s %(message)s'
) -> logging.RootLogger:
    '''
    Returns a RootLogger object with the logging level defined by `log_level` and 
    the logging format defined by `log_format`. To be used in Lambda functions to 
    have a unified logging across functions.

    Usage
    -----
    ```
    logger = get_logger()
    ```

    Arguments
    ---------
    log_level: str
        the log level. Possible values: ['INFO','WARNING','ERROR','DEBUG']. 
        Default: 'INFO'. If garbage passed, the function falls back to 'INFO'.
    log_format: str
        Log format. see https://docs.python.org/3/library/logging.html#logrecord-attributes
        for more info. default: '%(levelname)s %(message)s' 

    Returns
    -------
    logger: logging.RootLogger
        The RootLogger object
    '''
    log_level = os.getenv('LOG_LEVEL', default='INFO')
    log_level_int = int()
    if log_level=='WARNING':
        log_level_int = logging.WARNING
    elif log_level=='ERROR':
        log_level_int = logging.ERROR
    elif log_level=='DEBUG':
        log_level_int = logging.DEBUG
    else:
        log_level_int = logging.INFO
    logging.basicConfig(
        format=log_format,
        level=log_level_int,
        force=True  #new in py3.8
    )
    logger = logging.getLogger()
    return logger


def ddb_update_item(table, hash_key: str, range_key: str, item: str, value: Dict) -> None:
    '''
    Update an existing item in a DynamoDB table with a new value
    '''
    try:
        table.update_item(
            Key={
                'document_id': hash_key,  # HASH key
                'document_name': range_key  # RANGE key
            },
            UpdateExpression=f'SET {item}=:att1',  # This will set a new attribute
            ExpressionAttributeValues={
                f':{value}': {
                    'datetime': datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S') + '+00:00'
                }
            }
        )
    except Exception as ex:
        logger.error(f'Cannot update item in DynamoDB table {table}')
        raise ex