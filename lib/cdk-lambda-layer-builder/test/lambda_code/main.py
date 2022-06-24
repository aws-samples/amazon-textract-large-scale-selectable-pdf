import lib1
import lib2
import numpy as np

def lambda_handler(event, context):
    lib1.func()
    lib2.func()
    eye = np.arange(4)
    print(eye)
    return {'statusCode': 200,'body': 'test done'}