from aws_cdk import (
    DockerImage,
    aws_s3_assets,
    aws_lambda,
    BundlingOptions,
    AssetStaging
)
from constructs import Construct
from typing import Dict, List, Optional
import zipfile
import os
import shutil


class BuildPyLayerAsset(Construct):
    def __init__(
        self,
        scope: Construct,
        id: str,
        py_runtime: aws_lambda.Runtime,
        asset_dir: str,
        pip_install_specifier: List[str],
    ) -> None:
        '''
        '''
        super().__init__(scope, id)

        self.py_runtime = py_runtime
        self.asset_dir = asset_dir

        # build the layer within a docker container. The container does not seem 
        # to run locally (really!?!)
        entrypoint = ['/bin/sh', '-c']
        command = ['/usr/local/bin/pip','install']
        command.extend(pip_install_specifier)
        command.extend(
            ['-t',f'/asset-output/python/lib/python{self.get_pyversion()}/site-packages/','--force-reinstall']
        )
        self.s3_asset = aws_s3_assets.Asset(self, 's3asset', 
            path=asset_dir,
            bundling=BundlingOptions(
                image=DockerImage.from_registry(self.get_docker_image()),
                command=command, 
                entrypoint=entrypoint,
                environment=None, 
                local=None,
                output_type=None, 
                security_opt=None, 
                user=None, 
                volumes=None, 
                working_directory=None
            )
        )

        self.asset_bucket = self.s3_asset.bucket
        self.asset_bucket_name = self.s3_asset.bucket.bucket_name
        self.asset_key = self.s3_asset.s3_object_key


    @classmethod
    def from_pypi(
        cls,
        scope: Construct,
        id: str,
        pypi_requirements: List[str],
        py_runtime: aws_lambda.Runtime,
    ) -> None:
        '''
        '''
        # create the source assets
        asset_dir = BuildPyLayerAsset.build_local_asset_directory(id)
        with open(os.path.join(asset_dir,'requirements.txt'), 'w') as fw:
            fw.write('\n'.join(pypi_requirements))

        asset_staging = AssetStaging(scope, f'{id}AssetStaging',
            source_path=asset_dir
        )

        # cleaning
        shutil.rmtree(asset_dir)

        # create the pip install specifier
        pip_install_specifier = ['-r','requirements.txt']

        # call the default constructor
        return cls(scope, id,
            py_runtime=py_runtime,
            asset_dir=asset_staging.absolute_staged_path,
            pip_install_specifier=pip_install_specifier
        )


    @classmethod
    def from_modules(
        cls,
        scope: Construct,
        id: str,
        local_module_dirs: List[str],
        py_runtime: aws_lambda.Runtime,
    ) -> None:
        '''
        '''
        # check if the modules contain a setup.py file
        for loc_module_dir in local_module_dirs:
            if os.path.isdir(loc_module_dir):
                if not os.path.isfile(os.path.join(loc_module_dir, 'setup.py')):
                    raise ValueError(
                        (f'local module "{loc_module_dir}" does not have a setup.py file. '
                        f'Local modules must be installable with pip')
                    )
            else:
                raise ValueError(f'{loc_module_dir} does not seems to be a directory')

        # create the source assets
        asset_dir = BuildPyLayerAsset.build_local_asset_directory(id)
        for loc_module_dir in local_module_dirs:
            shutil.copytree(loc_module_dir, os.path.join(asset_dir,os.path.basename(loc_module_dir)))
        asset_staging = AssetStaging(scope, f'{id}AssetStaging',
            source_path=asset_dir
        )

        # cleaning
        shutil.rmtree(asset_dir)

        # create the pip install specifier
        modules = [os.path.basename(lmd) for lmd in local_module_dirs]
        pip_install_specifier = [m+'/.' for m in modules]

        # call the default constructor
        return cls(scope, id,
            py_runtime=py_runtime,
            asset_dir=asset_staging.absolute_staged_path,
            pip_install_specifier=pip_install_specifier
        )


    @staticmethod
    def build_local_asset_directory(id) -> str:
        '''
        '''
        work_dir = os.getcwd()
        asset_dir = os.path.join(work_dir, f'asset.{id}')
        if os.path.isdir(asset_dir):
            shutil.rmtree(asset_dir)
        os.makedirs(asset_dir)
        return asset_dir


    def get_docker_image(self) -> str:
        '''
        Returns the docker image name and tag from the python runtime used for the
        Lambda layer.
        '''
        image_name: str = ''
        if self.py_runtime.to_string()=='python3.7':
            image_name = 'python:3.7.13'
        elif self.py_runtime.to_string()=='python3.8':
            image_name = 'python:3.8.13'
        elif self.py_runtime.to_string()=='python3.9':
            image_name = 'python:3.9.13'
        else:
            raise ValueError(
                (f'py_runtime must be aws_lambda.Runtime.[PYTHON_3_7 | PYTHON_3_8 | PYTHON_3_9]. '
                 f'{self.py_runtime.to_string()} passed')
            )
        return image_name


    def get_pyversion(self) -> str:
        '''
        Returns the python version name (e.g. 3.8) from the python runtime used for the
        Lambda layer.
        '''
        pyver_name: str = ''
        if self.py_runtime.to_string()=='python3.7':
            pyver_name = '3.7'
        elif self.py_runtime.to_string()=='python3.8':
            pyver_name = '3.8'
        elif self.py_runtime.to_string()=='python3.9':
            pyver_name = '3.9'
        else:
            raise ValueError(
                (f'py_runtime must be aws_lambda.Runtime.[PYTHON_3_7 | PYTHON_3_8 | PYTHON_3_9]. '
                 f'{self.py_runtime.to_string()} passed')
            )
        return pyver_name


    @staticmethod
    def zip_file(filename: str, zip_name: str) -> None:
        '''
        Compress a file to a zip file. only the tail of `filename` is
        zipped (as one would expect).
        '''
        with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as outZipFile:
            outZipFile.write(filename, os.path.basename(filename))


    @staticmethod
    def zip_dir(directory: str, zip_name: str) -> None:
        '''
        Compress a directory to a zip file. only the tail of `directory` is
        zipped (as one would expect).
        '''
        with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as outZipFile:
            rootdir = os.path.basename(directory)
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    parentpath = os.path.relpath(filepath, directory)
                    arcname = os.path.join(rootdir, parentpath)
                    outZipFile.write(filepath, arcname)






