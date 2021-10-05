#!/bin/bash

# script from: https://github.com/aws-samples/aws-lambda-layer-create-script
# create the layer with:
# ./createlayer.sh 3.8

if [ "$1" != "" ] || [$# -gt 1]; then
	echo "Creating layer compatible with python version $1"
	cp "../../../lib/textracttools/dist/textracttools-1.0.1-py3-none-any.whl" .
	# pwd
	docker run -v "$PWD":/var/task "lambci/lambda:build-python$1" /bin/sh -c "pip install textracttools-1.0.1-py3-none-any.whl -t python/lib/python$1/site-packages/ --upgrade; exit"
	zip -r textracttools_py38.zip python > /dev/null
	# rm -rf python
	rm textracttools-1.0.1-py3-none-any.whl
	echo "Done creating layer!"
	ls -lah textracttools_py38.zip

else
	echo "Enter python version as argument - ./createlayer.sh 3.6"
fi