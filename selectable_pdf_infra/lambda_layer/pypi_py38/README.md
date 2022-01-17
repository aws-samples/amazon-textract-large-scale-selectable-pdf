# build_layer

A script to build Python X.Y AWS Lambda Layers and package them into a zip file. 
This script can only build layers with packages publish on PyPi.

## Usage
1. Copy the folder `build_layer` to `my_new_layer`
    ```bash
    cp -r build_layer my_new_layer
    ```
2. Update requirement.txt with the package to install
3. Launch the layer builder with
    ```bash
    ./createlayer.sh X.Y
    ```
   where X.Y is the target python version of the layer (i.e. `3.8`). The script 
   generates `layer.zip`, which is your layer. You can upload this file to AWS 
   Layer.
