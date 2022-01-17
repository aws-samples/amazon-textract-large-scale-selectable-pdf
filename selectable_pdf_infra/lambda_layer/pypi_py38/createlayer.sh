#!/bin/bash

# script from: https://github.com/aws-samples/aws-lambda-layer-create-script
# create the layer with:
# ./createlayer.sh 3.X

if [ "$1" != "" ] || [$# -gt 1]; then
	echo "Creating layer compatible with python version $1"
	docker run -v "$PWD":/var/task "lambci/lambda:build-python$1" /bin/sh -c "pip install -r requirements.txt -t python/lib/python$1/site-packages/ --upgrade; exit"
	zip -r pypi_py38.zip python > /dev/null
	echo "Done creating layer!"
	ls -lah pypi_py38.zip

else
	echo "Enter python version as argument - ./createlayer.sh 3.6"
fi
