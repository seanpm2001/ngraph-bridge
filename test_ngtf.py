#!/usr/bin/env python3
# ==============================================================================
#  Copyright 2018 Intel Corporation
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# ==============================================================================
import argparse
import errno
import os
from subprocess import check_output, call
import sys
import shutil
import glob
import platform
from distutils.sysconfig import get_python_lib

from build_ngtf import load_venv, command_executor


def run_ngtf_gtests(build_dir):
    root_pwd = os.getcwd()
    build_dir = os.path.abspath(build_dir)

    if not os.path.isdir(build_dir):
        raise Exception("build directory doesn't exist: " + build_dir)

    # First run the C++ gtests
    os.chdir(os.path.join(build_dir, "test"))
    command_executor("./gtest_ngtf")

    os.chdir(root_pwd)


def run_ngtf_pytests(venv_dir, build_dir):
    root_pwd = os.getcwd()

    build_dir = os.path.abspath(build_dir)
    venv_dir = os.path.abspath(venv_dir)

    test_dir = os.path.join(build_dir, "test")
    test_dir = os.path.join(test_dir, "python")

    if not os.path.isdir(test_dir):
        raise Exception("test directory doesn't exist: " + test_dir)

    # Change the directory to the test_dir
    os.chdir(test_dir)

    # Load venv
    load_venv(venv_dir)

    # Next run the ngraph-tensorflow python tests
    command_executor(["pip", "install", "-U", "pytest"])
    command_executor(["pip", "install", "-U", "psutil"])
    command_executor(["python", "-m", "pytest"])

    os.chdir(root_pwd)


def run_tensorflow_pytests(venv_dir, build_dir, ngraph_tf_src_dir, tf_src_dir):
    root_pwd = os.getcwd()

    build_dir = os.path.abspath(build_dir)
    venv_dir = os.path.abspath(venv_dir)
    ngraph_tf_src_dir = os.path.abspath(ngraph_tf_src_dir)

    patch_file = os.path.abspath(
        os.path.join(ngraph_tf_src_dir,
                     "test/python/tensorflow/tf_unittest_ngraph.patch"))

    # Load the virtual env
    venv_dir_absolute = load_venv(venv_dir)

    # Next patch the TensorFlow so that the tests run using ngraph_bridge
    pwd = os.getcwd()

    # Go to the site-packages
    os.chdir(glob.glob(venv_dir_absolute + "/lib/py*/site-packages")[0])
    print("CURRENT DIR: " + os.getcwd())

    print("Patching TensorFlow using: %s" % patch_file)
    result = call(["patch", "-p1", "-N", "-i", patch_file])
    print("Patch result: %d" % result)
    os.chdir(pwd)

    # Now run the TensorFlow python tests
    test_src_dir = os.path.join(ngraph_tf_src_dir, "test/python/tensorflow")
    test_script = os.path.join(test_src_dir, "tf_unittest_runner.py")
    test_manifest_file = os.path.join(test_src_dir, "python_tests_list.txt")

    import psutil
    num_cores = int(psutil.cpu_count(logical=False))
    print("OMP_NUM_THREADS: %s " % str(num_cores))
    os.environ['OMP_NUM_THREADS'] = str(num_cores)
    os.environ['NGRAPH_TF_DISABLE_DEASSIGN_CLUSTERS'] = '1'

    command_executor([
            "python", test_script, "--tensorflow_path", tf_src_dir,
            "--run_tests_from_file", test_manifest_file
    ])

    os.chdir(root_pwd)


def run_resnet50(build_dir):

    root_pwd = os.getcwd()
    build_dir = os.path.abspath(build_dir)
    os.chdir(build_dir)

    call(['git', 'clone', 'https://github.com/tensorflow/benchmarks.git'])
    os.chdir('benchmarks/scripts/tf_cnn_benchmarks/')

    call(['git', 'checkout', '4c7b09ad87bbfc4b1f89650bcee40b3fc5e7dfed'])

    # Update the script by adding `import ngraph_bridge`
    with open('convnet_builder.py', 'a') as outfile:
        call(['echo', 'import ngraph_bridge'], stdout=outfile)

    # Setup the env flags
    import psutil
    num_cores = int(psutil.cpu_count(logical=False))
    print("OMP_NUM_THREADS: %s " % str(num_cores))

    os.environ['OMP_NUM_THREADS'] = str(num_cores)
    os.environ["KMP_AFFINITY"] = 'granularity=fine,compact,1,0'

    # Delete the temporary model save directory
    model_save_dir = os.getcwd() + '/modelsavepath'
    if os.path.exists(model_save_dir) and os.path.isdir(model_save_dir):
        shutil.rmtree(model_save_dir)

    # Run training job
    cmd = [
        'python', 'tf_cnn_benchmarks.py', '--data_format', 'NCHW',
        '--num_inter_threads', '1', '--train_dir=' + model_save_dir,
        '--num_batches', '10', '--model=resnet50', '--batch_size=128'
    ]
    command_executor(cmd)

    # Run inference job
    cmd = [
        'python', 'tf_cnn_benchmarks.py', '--data_format', 'NCHW',
        '--num_inter_threads', '1', '--train_dir=' + model_save_dir,
        '--model=resnet50', '--batch_size=128', '--num_batches', '10', '--eval'
    ]
    command_executor(cmd)

    os.chdir(root_pwd)


def main():
    '''
    Tests nGraph-TensorFlow Python 3. This script needs to be run after 
    running build_ngtf.py which builds the ngraph-tensorflow-bridge
    and installs it to a virtual environment that would be used by this script.
    '''
    parser = argparse.ArgumentParser()
    arguments = parser.parse_args()

    #-------------------------------
    # Recipe
    #-------------------------------

    root_pwd = os.getcwd()

    # Constants
    build_dir = 'build'
    venv_dir = 'build/venv-tf-py3'

    # First run the C++ gtests
    run_ngtf_gtests(build_dir)

    # Next run Python unit tests
    run_ngtf_pytests(venv_dir, build_dir)

    # Next run the TensorFlow python tests
    run_tensorflow_pytests(venv_dir, build_dir, './', 'build/tensorflow')

    # Finally run Resnet50 based training and inferences
    run_resnet50(build_dir)

    os.chdir(root_pwd)


if __name__ == '__main__':
    main()