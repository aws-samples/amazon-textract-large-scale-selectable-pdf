import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="textracttools",
    version="1.0.1",
    author="Marcel Vonlanthen",
    author_email="vonlanth@amazon.com",
    description="A collection of tools to work with Amazon Textract",
    long_description=long_description,
    long_description_content_type="text/markdown",
    # url="https://github.com/pypa/sampleproject",
    packages=setuptools.find_packages(),
    install_requires=['wheel'],
    classifiers=[
        "Programming Language :: Python :: 3",
    #     "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)