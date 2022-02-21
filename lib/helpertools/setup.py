import setuptools

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()

setuptools.setup(
    name='helpertools',
    version='1.0.0',
    author='Marcel Vonlanthen',
    author_email='vonlanth@amazon.com',
    description='A collection of helper functions and classes for the lambda functions ',
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=setuptools.find_packages(),
    install_requires=['wheel', 'PyMuPDF'],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.8',
)