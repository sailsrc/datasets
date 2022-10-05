# Copyright 2020 The HuggingFace Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Lint as: python3
import sys
from typing import TYPE_CHECKING

import numpy as np
import pyarrow as pa

from .. import config
from ..utils.py_utils import map_nested
from .formatting import Formatter


if TYPE_CHECKING:
    import tensorflow as tf


class TFFormatter(Formatter[dict, "tf.Tensor", dict]):
    def __init__(self, features=None, decoded=True, **tf_tensor_kwargs):
        super().__init__(features=features, decoded=decoded)
        self.tf_tensor_kwargs = tf_tensor_kwargs
        import tensorflow as tf  # noqa: import tf at initialization

    def _tensorize(self, value):
        import tensorflow as tf

        if value is None:
            return value

        default_dtype = {}

        if isinstance(value, (np.number, np.ndarray)) and np.issubdtype(value.dtype, np.integer):
            default_dtype = {"dtype": tf.int64}
        elif isinstance(value, (np.number, np.ndarray)) and np.issubdtype(value.dtype, np.floating):
            default_dtype = {"dtype": tf.float32}
        elif config.PIL_AVAILABLE and "PIL" in sys.modules:
            import PIL.Image

            if isinstance(value, PIL.Image.Image):
                value = np.asarray(value)

        # Saving the most expensive methods for last
        try:
            return tf.convert_to_tensor(value, **{**default_dtype, **self.tf_tensor_kwargs})
        except ValueError:
            try:
                return tf.ragged.stack(
                    [tf.convert_to_tensor(subarr, **{**default_dtype, **self.tf_tensor_kwargs}) for subarr in value]
                )
            except ValueError:
                # tf.ragged.constant is orders of magnitude slower than tf.ragged.stack
                return tf.ragged.constant(value, **{**default_dtype, **self.tf_tensor_kwargs})

    def _recursive_tensorize(self, data_struct: dict):
        # support for nested types like struct of list of struct
        if isinstance(data_struct, np.ndarray):
            if data_struct.dtype == object:  # tf tensors cannot be instantied from an array of objects
                try:
                    return self._tensorize(data_struct)
                except ValueError:
                    return [self.recursive_tensorize(substruct) for substruct in data_struct]
        return self._tensorize(data_struct)

    def recursive_tensorize(self, data_struct: dict):
        return map_nested(self._recursive_tensorize, data_struct)

    def format_row(self, pa_table: pa.Table) -> dict:
        row = self.numpy_arrow_extractor().extract_row(pa_table)
        if self.decoded:
            row = self.python_features_decoder.decode_row(row)
        return self.recursive_tensorize(row)

    def format_column(self, pa_table: pa.Table) -> "tf.Tensor":
        column = self.numpy_arrow_extractor().extract_column(pa_table)
        if self.decoded:
            column = self.python_features_decoder.decode_column(column, pa_table.column_names[0])
        return self.recursive_tensorize(column)

    def format_batch(self, pa_table: pa.Table) -> dict:
        batch = self.numpy_arrow_extractor().extract_batch(pa_table)
        if self.decoded:
            batch = self.python_features_decoder.decode_batch(batch)
        return self.recursive_tensorize(batch)
