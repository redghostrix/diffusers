# coding=utf-8
# Copyright 2022 HuggingFace Inc.
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


import inspect
import tempfile
import unittest

import numpy as np
import torch

from diffusers.models.embeddings import get_timestep_embedding
from diffusers.models.resnet import Upsample
from diffusers.testing_utils import floats_tensor, slow, torch_device


torch.backends.cuda.matmul.allow_tf32 = False


class EmbeddingsTests(unittest.TestCase):
    def test_timestep_embeddings(self):
        embedding_dim = 256
        timesteps = torch.arange(16)

        t1 = get_timestep_embedding(timesteps, embedding_dim)

        # first vector should always be composed only of 0's and 1's
        assert (t1[0, : embedding_dim // 2] - 0).abs().sum() < 1e-5
        assert (t1[0, embedding_dim // 2 :] - 1).abs().sum() < 1e-5

        # last element of each vector should be one
        assert (t1[:, -1] - 1).abs().sum() < 1e-5

        # For large embeddings (e.g. 128) the frequency of every vector is higher
        # than the previous one which means that the gradients of later vectors are
        # ALWAYS higher than the previous ones
        grad_mean = np.abs(np.gradient(t1, axis=-1)).mean(axis=1)

        prev_grad = 0.0
        for grad in grad_mean:
            assert grad > prev_grad
            prev_grad = grad

    def test_timestep_defaults(self):
        embedding_dim = 16
        timesteps = torch.arange(10)

        t1 = get_timestep_embedding(timesteps, embedding_dim)
        t2 = get_timestep_embedding(
            timesteps, embedding_dim, flip_sin_to_cos=False, downscale_freq_shift=1, max_period=10_000
        )

        assert torch.allclose(t1.cpu(), t2.cpu(), 1e-3)

    def test_timestep_flip_sin_cos(self):
        embedding_dim = 16
        timesteps = torch.arange(10)

        t1 = get_timestep_embedding(timesteps, embedding_dim, flip_sin_to_cos=True)
        t1 = torch.cat([t1[:, embedding_dim // 2 :], t1[:, : embedding_dim // 2]], dim=-1)

        t2 = get_timestep_embedding(timesteps, embedding_dim, flip_sin_to_cos=False)

        assert torch.allclose(t1.cpu(), t2.cpu(), 1e-3)

    def test_timestep_downscale_freq_shift(self):
        embedding_dim = 16
        timesteps = torch.arange(10)

        t1 = get_timestep_embedding(timesteps, embedding_dim, downscale_freq_shift=0)
        t2 = get_timestep_embedding(timesteps, embedding_dim, downscale_freq_shift=1)

        # get cosine half (vectors that are wrapped into cosine)
        cosine_half = (t1 - t2)[:, embedding_dim // 2 :]

        # cosine needs to be negative
        assert (np.abs((cosine_half <= 0).numpy()) - 1).sum() < 1e-5

    def test_sinoid_embeddings_hardcoded(self):
        embedding_dim = 64
        timesteps = torch.arange(128)

        # standard unet, score_vde
        t1 = get_timestep_embedding(timesteps, embedding_dim, downscale_freq_shift=1, flip_sin_to_cos=False)
        # glide, ldm
        t2 = get_timestep_embedding(timesteps, embedding_dim, downscale_freq_shift=0, flip_sin_to_cos=True)
        # grad-tts
        t3 = get_timestep_embedding(timesteps, embedding_dim, scale=1000)

        assert torch.allclose(
            t1[23:26, 47:50].flatten().cpu(),
            torch.tensor([0.9646, 0.9804, 0.9892, 0.9615, 0.9787, 0.9882, 0.9582, 0.9769, 0.9872]),
            1e-3,
        )
        assert torch.allclose(
            t2[23:26, 47:50].flatten().cpu(),
            torch.tensor([0.3019, 0.2280, 0.1716, 0.3146, 0.2377, 0.1790, 0.3272, 0.2474, 0.1864]),
            1e-3,
        )
        assert torch.allclose(
            t3[23:26, 47:50].flatten().cpu(),
            torch.tensor([-0.9801, -0.9464, -0.9349, -0.3952, 0.8887, -0.9709, 0.5299, -0.2853, -0.9927]),
            1e-3,
        )


class UpsampleBlockTests(unittest.TestCase):
    def test_upsample_default(self):
        torch.manual_seed(0)
        sample = torch.randn(1, 32, 32, 32)
        upsample = Upsample(channels=32, use_conv=False)
        with torch.no_grad():
            upsampled = upsample(sample)

        assert upsampled.shape == (1, 32, 64, 64)
        output_slice = upsampled[0, -1, -3:, -3:]
        expected_slice = torch.tensor([-0.2173, -1.2079, -1.2079, 0.2952, 1.1254, 1.1254, 0.2952, 1.1254, 1.1254])
        assert torch.allclose(output_slice.flatten(), expected_slice, atol=1e-3)

    def test_upsample_with_conv(self):
        torch.manual_seed(0)
        sample = torch.randn(1, 32, 32, 32)
        upsample = Upsample(channels=32, use_conv=True)
        with torch.no_grad():
            upsampled = upsample(sample)

        assert upsampled.shape == (1, 32, 64, 64)
        output_slice = upsampled[0, -1, -3:, -3:]
        expected_slice = torch.tensor([0.7145, 1.3773, 0.3492, 0.8448, 1.0839, -0.3341, 0.5956, 0.1250, -0.4841])
        assert torch.allclose(output_slice.flatten(), expected_slice, atol=1e-3)

    def test_upsample_with_conv_out_dim(self):
        torch.manual_seed(0)
        sample = torch.randn(1, 32, 32, 32)
        upsample = Upsample(channels=32, use_conv=True, out_channels=64)
        with torch.no_grad():
            upsampled = upsample(sample)

        assert upsampled.shape == (1, 64, 64, 64)
        output_slice = upsampled[0, -1, -3:, -3:]
        expected_slice = torch.tensor([0.2703, 0.1656, -0.2538, -0.0553, -0.2984, 0.1044, 0.1155, 0.2579, 0.7755])
        assert torch.allclose(output_slice.flatten(), expected_slice, atol=1e-3)

    def test_upsample_with_transpose(self):
        torch.manual_seed(0)
        sample = torch.randn(1, 32, 32, 32)
        upsample = Upsample(channels=32, use_conv=False, use_conv_transpose=True)
        with torch.no_grad():
            upsampled = upsample(sample)

        assert upsampled.shape == (1, 32, 64, 64)
        output_slice = upsampled[0, -1, -3:, -3:]
        expected_slice = torch.tensor([-0.3028, -0.1582, 0.0071, 0.0350, -0.4799, -0.1139, 0.1056, -0.1153, -0.1046])
        assert torch.allclose(output_slice.flatten(), expected_slice, atol=1e-3)
