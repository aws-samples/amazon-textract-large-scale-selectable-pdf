'''
# helpers

A collection of helper functions
'''
# import modules
# --------------
import json
import boto3
import datetime
import re
import copy

from typing import Dict, List, Union


# functions
# ---------
def extract_bucket_key(s3url: str) -> Dict:
    '''
    Extract the bucket and the key from a s3 url. Returns a dict with "bucket" 
    and "key" as keys. An s3 url has the following form:
        s3://my-bucket/localtion/of/my_file.json
    from the this s3 url, we can extract:
    * the bucket: my-bucket
    * the object key: localtion/of/my_file.json

    Usage
    -----
    s3_location = extract_bucket_key(s3url)

    Arguments
    ---------
    s3url: str
        S3 url of form `s3://my_bucket/key_folder/my_file.abc`

    Returns
    -------
    s3_location: dict
        dict with with `bucket` and `key` as key.
    '''
    splits = s3url.split('/')
    return {'bucket':splits[2], 'key':'/'.join(splits[3:])}


def load_json_from_s3(bucket: str, key: str) -> Dict:
    '''
    Load directly into memory a JSON file stored on S3.

    Usage
    -----
    json_dict = load_json_from_s3(bucket, key)

    Arguments
    ---------
    bucket: str
        The S3 bucket
    key: str
        The S3 key

    Returns
    -------
    json_dict: dict
    '''
    s3_res = boto3.resource('s3')
    s3_object = s3_res.Bucket(bucket).Object(key)
    response = s3_object.get()
    file_stream = response['Body']
    json_dict = json.load(file_stream)
    return json_dict


def save_json_to_s3(bucket: str, key: str, json_object: Dict) -> Dict:
    '''
    Save a JSON object to S3. `json_object` is a classic Pyhon dictonary. The 
    Jsonification of the dict is done with default Python package `json`, 
    therefore only type support by this package are supported in thsi function.
    
    Usage
    -----
    response = save_json_to_s3(bucket, key, json_object)

    Arguments
    ---------
    bucket
        The target S3 bucket name for the json.
    key
        The target S3 key name for the json, i.e. the filename and its "path" 
        in S3.
    json_object
        The Python dictonnary to jsonify. 

    Returns
    -------
    response
        The S3 response
    '''
    s3_client = boto3.client('s3')
    response = s3_client.put_object(
        Body=bytes(
            json.dumps(json_object, indent=None, separators=(',',':')).encode('UTF-8')
        ),
        Bucket=bucket,
        Key=key
    )
    return response


def convert_httpheaders_date(
    httpheader_date: str, 
    output_type: str='str'
) -> Union[str, datetime.datetime]:
    '''
    Convert the HTTPHeader date contained in most AWS service response (e.g. 
    'Mon, 19 Apr 2021 14:52:48 GMT') to a string following the ISO 8601 format 
    (e.g. '2021-04-19T14:52:48+00:00') or a Python datetime.datetime object.

    Usage
    -----
    dt = convert_httpheaders_date(httpheader_date, output_type='str')

    Arguments
    ---------
    httpheader_date:
        the date in the HTTPSHeaders which must follow this format: 
        'Mon, 19 Apr 2021 14:52:48 GMT'
    output_type:
        Output type, `str` for an ISO 8601 formatted string of `datetime` for the 
        python datetime.datetime object. Default: 'str'

    Returns
    -------
    dt
        The datetime as string or datetime.datetime object
    '''
    dt = datetime.datetime.strptime(httpheader_date, '%a, %d %b %Y %H:%M:%S %Z')
    if output_type=='str':
        return dt.strftime('%Y-%m-%dT%H:%M:%S')+'+00:00'
    elif output_type=='datetime':
        return dt
    else:
        raise AttributeError('unknown output_type. Valid options: ["str"|"datetime"]')


def from_str_to_float(text: str) -> float:
    '''
    Convert a string to a float if possible. if not, returns the original string

    Arguments
    ---------
    text:
        The input text
    
    Returns
    -------
    text_as_float:
        The input text converted to a float if possible, otherwise returned as 
        the input string
    '''
    orignial_text = copy.deepcopy(text)
    text = text.strip()
    if len(text)==0:
        return orignial_text

    # text is in bracket, i.e. (10 123.84), this means -10123.84 in financial 
    # jargon. Let's remove the bracket and add an minus in front of text
    is_negative = False
    if (text[0]=='(') & (text[-1]==')'):
        text = text[1:-1]
        is_negative = True
    if text[0]=='-':
        text = text[1:]
        is_negative = True
    if len(text)==0:
        return orignial_text

    # let's remove the + sign, if any
    if text[0]=='+':
        text = text[1:]
    if len(text)==0:
        return orignial_text
    
    # if the last character of text is %, then the text might be a percentage 
    # figure which we want to convert to decimal
    is_percent = False
    if text[-1]=='%':
        is_percent = True
        text = text[:-1]
    if len(text)==0:
        return orignial_text

    # Check if we have at least some number. Also check if text has anything 
    # else than numbers, point, comma, apostrophe, space, plus or minus. If it's 
    # the case, it's not a number and we return as a text
    # if re.match("\d", text)==None:
    #     return orignial_text
    if re.match("^[\d.,'\s]*$", text)==None:
        return orignial_text

    # `text` should be a number, let's process it
    text = text.replace(' ', '')
    separators = re.sub(r'\d', '', text, flags=re.U)
    for sep in separators[:-1]:
        text = text.replace(sep, '')
    if separators:
        text = text.replace(separators[-1], '.')

    # quick fix: The convertion to float can fail. Let's return the raw text 
    # if it does text_as_float = float(text)
    try:
        text_as_float = float(text)
    except:
        return orignial_text

    # convert a percent number to decimal, if required
    if is_percent:
        text_as_float /= 100
    
    # "minusify" the number
    if is_negative:
        text_as_float *= -1

    return text_as_float
