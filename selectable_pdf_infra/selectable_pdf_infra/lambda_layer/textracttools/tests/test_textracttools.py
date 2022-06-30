import unittest 
import os
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(os.path.dirname(__file__)).parent))

from textracttools import  (
    from_str_to_float
)
  
class TestTextractTools(unittest.TestCase): 
  
    # Returns True or False.  
    def test_from_str_to_float(self):
        numerics = [
            ["1000", 1000],
            ["1000.99", 1000.99],
            ["1000,99", 1000.99],
            ["1 000 000.9",1000000.9],
            ["1 000 000,9",1000000.9],
            ["(1 000.9)",-1000.9],
            ["12.65%",0.1265],
            ["(12.65%)",-0.1265],
            ["(1 092.65%)",-10.9265],
        ]

        for num_str, num_true in numerics:

            num_func = from_str_to_float(num_str)
            self.assertEqual(num_func,num_true)

  
if __name__ == '__main__': 
    unittest.main() 