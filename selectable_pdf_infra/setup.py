import setuptools
import pathlib
import os
from typing import List


CURRENT_FILEPATH = pathlib.Path(__file__).absolute()
CURRENT_DIRPATH = CURRENT_FILEPATH.parent.absolute()
LIB_DIRPATH = CURRENT_DIRPATH.parent.joinpath('lib')


with open('README.md') as fp:
    long_description = fp.read()

def build_package_data(dir: str) -> List[str]:
    '''
    build the list of files with their path from package directory, but with the 
    package name in the returns. Imagine the following package structure:

    |- mypackage
        |- mypackage
            |- __init__.py
            |- code_for_mypackage.py
            |- somedir
                |- somefile.txt
        |- setup.py

    If we want to include somefile.txt in the installed package, we need to include 
    in setup.py the following:

    setuptools.setup(
        packages=['mypackage'],
        package_data={'mypackage': ['somedir/somefile.txt']}
    )

    this function helps to build the values of the package_data dict: 

    package_data={'mypackage': build_package_data('mypackage/somedir')}
    '''
    file_list = list()
    dir_tail = os.path.dirname(dir)
    for path, subdirs, files in os.walk(dir):
        join_path = path.replace(dir_tail+'/', '')
        for name in files:
            file_list.append(os.path.join(join_path, name))
    return file_list

package_data = list()
package_data.extend(build_package_data('selectable_pdf_infra/lambda'))
package_data.extend(build_package_data('selectable_pdf_infra/lambda_layer'))

setuptools.setup(
    name='selectable_pdf_infra',
    version='2.2.0',
    description='infrastructure to convert scanned PDF\'s into selectable PDF\'s with AWS',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Marcel Vonlanthen',
    email='vonlanth@amazon.com',
    packages=['selectable_pdf_infra'],
    package_data={'selectable_pdf_infra': package_data},
    install_requires=[
        'wheel',
        'boto3',
        f'aws-cdk-lib>=2.8', 
        f'cdk_lambda_layer_builder @ git+https://github.com/aws-samples/aws-cdk-lambda-layer-builder.git#egg=cdk_lambda_layer_builder'
    ],
    python_requires='>=3.6',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT No Attribution License (MIT-0)',
        'Programming Language :: JavaScript',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Software Development :: Code Generators',
        'Topic :: Utilities',
        'Typing :: Typed',
    ],
)
