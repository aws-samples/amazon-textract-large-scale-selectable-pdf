# TextractTools

A collection of tools to work with Amazon Textract

## Installation
* Go to `textracttools`
* Build the wheel file. A *.whl file is a Built Distribution. used to install the 
  module
  ```bash
  python setup.py sdist bdist_wheel
  ```
* Install the module 
  ```bash
  pip install dist/textracttools-1.0.1-py3-none-any.whl
  ```
  If you want to force a full reinstall, use
  ```bash
  pip install --force-reinstall  dist/textracttools-1.0.1-py3-none-any.whl
  ```
  The name of the wheel file might change in the future. Check it in the `dist` folder.

## Usage
```python
from textracttools import TextractParser, table_2_csv
TextractParser
# <class 'textracttools.parser.TextractParser'>
```