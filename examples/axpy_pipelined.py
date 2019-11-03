# ==============================================================================
#  Copyright 2019 Intel Corporation
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
import warnings
warnings.filterwarnings('ignore', category=FutureWarning)

import tensorflow as tf
tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)

import os
os.environ['NGRAPH_TF_BACKEND'] = "INTERPRETER"
#os.environ['NGRAPH_TF_USE_PREFETCH'] = "1"
import ngraph_bridge

import sys


def build_model(input_array):
    labels = tf.cast(input_array, tf.int64)

    mul = tf.compat.v1.math.multiply(labels, 5)
    add = tf.compat.v1.math.add(mul, 10)

    output = add
    return output


def build_data_pipeline(input_array, map_function, batch_size):
    dataset = (tf.data.Dataset.from_tensor_slices(
        (tf.constant(input_array)
        )).map(map_function).batch(batch_size).prefetch(1))

    iterator = dataset.make_initializable_iterator()
    data_to_be_prefetched_and_used = iterator.get_next()

    return data_to_be_prefetched_and_used, iterator


if __name__ == '__main__':
    input_array = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    map_function = lambda x: x * 10
    pipeline, iterator = build_data_pipeline(input_array, map_function, 1)
    model = build_model(pipeline)

    with tf.Session() as sess:
        # Initialize the globals and the dataset
        sess.run(tf.global_variables_initializer())
        sess.run(iterator.initializer)

        for i in range(1, 10):
            # Expected value is:
            expected_output = ((input_array[i - 1] * 10) * 5) + 10

            # Run one iteration
            output = sess.run(model)

            # Results?
            print("Iteration:", i, " Input: ", input_array[i - 1], " Output: ",
                  output[0], " Expected: ", expected_output)
            sys.stdout.flush()
