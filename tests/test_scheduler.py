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
import pdb
import tempfile
import unittest

import numpy as np
import torch

from diffusers import DDIMScheduler, DDPMScheduler, PNDMScheduler, ScoreSdeVeScheduler


torch.backends.cuda.matmul.allow_tf32 = False


class SchedulerCommonTest(unittest.TestCase):
    scheduler_classes = ()
    forward_default_kwargs = ()

    @property
    def dummy_sample(self):
        batch_size = 4
        num_channels = 3
        height = 8
        width = 8

        sample = np.random.rand(batch_size, num_channels, height, width)

        return sample

    @property
    def dummy_sample_deter(self):
        batch_size = 4
        num_channels = 3
        height = 8
        width = 8

        num_elems = batch_size * num_channels * height * width
        sample = np.arange(num_elems)
        sample = sample.reshape(num_channels, height, width, batch_size)
        sample = sample / num_elems
        sample = sample.transpose(3, 0, 1, 2)

        return sample

    def get_scheduler_config(self):
        raise NotImplementedError

    def dummy_model(self):
        def model(sample, t, *args):
            return sample * t / (t + 1)

        return model

    def check_over_configs(self, time_step=0, **config):
        kwargs = dict(self.forward_default_kwargs)

        num_inference_steps = kwargs.pop("num_inference_steps", None)

        for scheduler_class in self.scheduler_classes:
            scheduler_class = self.scheduler_classes[0]
            sample = self.dummy_sample
            residual = 0.1 * sample

            scheduler_config = self.get_scheduler_config(**config)
            scheduler = scheduler_class(**scheduler_config)

            with tempfile.TemporaryDirectory() as tmpdirname:
                scheduler.save_config(tmpdirname)
                new_scheduler = scheduler_class.from_config(tmpdirname)

            if num_inference_steps is not None and hasattr(scheduler, "set_timesteps"):
                scheduler.set_timesteps(num_inference_steps)
                new_scheduler.set_timesteps(num_inference_steps)
            elif num_inference_steps is not None and not hasattr(scheduler, "set_timesteps"):
                kwargs["num_inference_steps"] = num_inference_steps

            output = scheduler.step(residual, time_step, sample, **kwargs)["prev_sample"]
            new_output = new_scheduler.step(residual, time_step, sample, **kwargs)["prev_sample"]

            assert np.sum(np.abs(output - new_output)) < 1e-5, "Scheduler outputs are not identical"

    def check_over_forward(self, time_step=0, **forward_kwargs):
        kwargs = dict(self.forward_default_kwargs)
        kwargs.update(forward_kwargs)

        num_inference_steps = kwargs.pop("num_inference_steps", None)

        for scheduler_class in self.scheduler_classes:
            sample = self.dummy_sample
            residual = 0.1 * sample

            scheduler_class = self.scheduler_classes[0]
            scheduler_config = self.get_scheduler_config()
            scheduler = scheduler_class(**scheduler_config)

            with tempfile.TemporaryDirectory() as tmpdirname:
                scheduler.save_config(tmpdirname)
                new_scheduler = scheduler_class.from_config(tmpdirname)

            if num_inference_steps is not None and hasattr(scheduler, "set_timesteps"):
                scheduler.set_timesteps(num_inference_steps)
                new_scheduler.set_timesteps(num_inference_steps)
            elif num_inference_steps is not None and not hasattr(scheduler, "set_timesteps"):
                kwargs["num_inference_steps"] = num_inference_steps

            torch.manual_seed(0)
            output = scheduler.step(residual, time_step, sample, **kwargs)["prev_sample"]
            torch.manual_seed(0)
            new_output = new_scheduler.step(residual, time_step, sample, **kwargs)["prev_sample"]

            assert np.sum(np.abs(output - new_output)) < 1e-5, "Scheduler outputs are not identical"

    def test_from_pretrained_save_pretrained(self):
        kwargs = dict(self.forward_default_kwargs)

        num_inference_steps = kwargs.pop("num_inference_steps", None)

        for scheduler_class in self.scheduler_classes:
            sample = self.dummy_sample
            residual = 0.1 * sample

            scheduler_config = self.get_scheduler_config()
            scheduler = scheduler_class(**scheduler_config)

            with tempfile.TemporaryDirectory() as tmpdirname:
                scheduler.save_config(tmpdirname)
                new_scheduler = scheduler_class.from_config(tmpdirname)

            if num_inference_steps is not None and hasattr(scheduler, "set_timesteps"):
                scheduler.set_timesteps(num_inference_steps)
                new_scheduler.set_timesteps(num_inference_steps)
            elif num_inference_steps is not None and not hasattr(scheduler, "set_timesteps"):
                kwargs["num_inference_steps"] = num_inference_steps

            output = scheduler.step(residual, 1, sample, **kwargs)["prev_sample"]
            new_output = new_scheduler.step(residual, 1, sample, **kwargs)["prev_sample"]

            assert np.sum(np.abs(output - new_output)) < 1e-5, "Scheduler outputs are not identical"

    def test_step_shape(self):
        kwargs = dict(self.forward_default_kwargs)

        num_inference_steps = kwargs.pop("num_inference_steps", None)

        for scheduler_class in self.scheduler_classes:
            scheduler_config = self.get_scheduler_config()
            scheduler = scheduler_class(**scheduler_config)

            sample = self.dummy_sample
            residual = 0.1 * sample

            if num_inference_steps is not None and hasattr(scheduler, "set_timesteps"):
                scheduler.set_timesteps(num_inference_steps)
            elif num_inference_steps is not None and not hasattr(scheduler, "set_timesteps"):
                kwargs["num_inference_steps"] = num_inference_steps

            output_0 = scheduler.step(residual, 0, sample, **kwargs)["prev_sample"]
            output_1 = scheduler.step(residual, 1, sample, **kwargs)["prev_sample"]

            self.assertEqual(output_0.shape, sample.shape)
            self.assertEqual(output_0.shape, output_1.shape)

    def test_pytorch_equal_numpy(self):
        kwargs = dict(self.forward_default_kwargs)

        num_inference_steps = kwargs.pop("num_inference_steps", None)

        for scheduler_class in self.scheduler_classes:
            sample = self.dummy_sample
            residual = 0.1 * sample

            sample_pt = torch.tensor(sample)
            residual_pt = 0.1 * sample_pt

            scheduler_config = self.get_scheduler_config()
            scheduler = scheduler_class(**scheduler_config)

            scheduler_pt = scheduler_class(tensor_format="pt", **scheduler_config)

            if num_inference_steps is not None and hasattr(scheduler, "set_timesteps"):
                scheduler.set_timesteps(num_inference_steps)
                scheduler_pt.set_timesteps(num_inference_steps)
            elif num_inference_steps is not None and not hasattr(scheduler, "set_timesteps"):
                kwargs["num_inference_steps"] = num_inference_steps

            output = scheduler.step(residual, 1, sample, **kwargs)["prev_sample"]
            output_pt = scheduler_pt.step(residual_pt, 1, sample_pt, **kwargs)["prev_sample"]

            assert np.sum(np.abs(output - output_pt.numpy())) < 1e-4, "Scheduler outputs are not identical"


class DDPMSchedulerTest(SchedulerCommonTest):
    scheduler_classes = (DDPMScheduler,)

    def get_scheduler_config(self, **kwargs):
        config = {
            "num_train_timesteps": 1000,
            "beta_start": 0.0001,
            "beta_end": 0.02,
            "beta_schedule": "linear",
            "variance_type": "fixed_small",
            "clip_sample": True,
        }

        config.update(**kwargs)
        return config

    def test_timesteps(self):
        for timesteps in [1, 5, 100, 1000]:
            self.check_over_configs(num_train_timesteps=timesteps)

    def test_betas(self):
        for beta_start, beta_end in zip([0.0001, 0.001, 0.01, 0.1], [0.002, 0.02, 0.2, 2]):
            self.check_over_configs(beta_start=beta_start, beta_end=beta_end)

    def test_schedules(self):
        for schedule in ["linear", "squaredcos_cap_v2"]:
            self.check_over_configs(beta_schedule=schedule)

    def test_variance_type(self):
        for variance in ["fixed_small", "fixed_large", "other"]:
            self.check_over_configs(variance_type=variance)

    def test_clip_sample(self):
        for clip_sample in [True, False]:
            self.check_over_configs(clip_sample=clip_sample)

    def test_time_indices(self):
        for t in [0, 500, 999]:
            self.check_over_forward(time_step=t)

    def test_variance(self):
        scheduler_class = self.scheduler_classes[0]
        scheduler_config = self.get_scheduler_config()
        scheduler = scheduler_class(**scheduler_config)

        assert np.sum(np.abs(scheduler.get_variance(0) - 0.0)) < 1e-5
        assert np.sum(np.abs(scheduler.get_variance(487) - 0.00979)) < 1e-5
        assert np.sum(np.abs(scheduler.get_variance(999) - 0.02)) < 1e-5

    def test_full_loop_no_noise(self):
        scheduler_class = self.scheduler_classes[0]
        scheduler_config = self.get_scheduler_config()
        scheduler = scheduler_class(**scheduler_config)

        num_trained_timesteps = len(scheduler)

        model = self.dummy_model()
        sample = self.dummy_sample_deter

        for t in reversed(range(num_trained_timesteps)):
            # 1. predict noise residual
            residual = model(sample, t)

            # 2. predict previous mean of sample x_t-1
            pred_prev_sample = scheduler.step(residual, t, sample)["prev_sample"]

            if t > 0:
                noise = self.dummy_sample_deter
                variance = scheduler.get_variance(t) ** (0.5) * noise

            sample = pred_prev_sample + variance

        result_sum = np.sum(np.abs(sample))
        result_mean = np.mean(np.abs(sample))

        assert abs(result_sum.item() - 732.9947) < 1e-2
        assert abs(result_mean.item() - 0.9544) < 1e-3


class DDIMSchedulerTest(SchedulerCommonTest):
    scheduler_classes = (DDIMScheduler,)
    forward_default_kwargs = (("eta", 0.0), ("num_inference_steps", 50))

    def get_scheduler_config(self, **kwargs):
        config = {
            "num_train_timesteps": 1000,
            "beta_start": 0.0001,
            "beta_end": 0.02,
            "beta_schedule": "linear",
            "clip_sample": True,
        }

        config.update(**kwargs)
        return config

    def test_timesteps(self):
        for timesteps in [100, 500, 1000]:
            self.check_over_configs(num_train_timesteps=timesteps)

    def test_betas(self):
        for beta_start, beta_end in zip([0.0001, 0.001, 0.01, 0.1], [0.002, 0.02, 0.2, 2]):
            self.check_over_configs(beta_start=beta_start, beta_end=beta_end)

    def test_schedules(self):
        for schedule in ["linear", "squaredcos_cap_v2"]:
            self.check_over_configs(beta_schedule=schedule)

    def test_clip_sample(self):
        for clip_sample in [True, False]:
            self.check_over_configs(clip_sample=clip_sample)

    def test_time_indices(self):
        for t in [1, 10, 49]:
            self.check_over_forward(time_step=t)

    def test_inference_steps(self):
        for t, num_inference_steps in zip([1, 10, 50], [10, 50, 500]):
            self.check_over_forward(num_inference_steps=num_inference_steps)

    def test_eta(self):
        for t, eta in zip([1, 10, 49], [0.0, 0.5, 1.0]):
            self.check_over_forward(time_step=t, eta=eta)

    def test_variance(self):
        scheduler_class = self.scheduler_classes[0]
        scheduler_config = self.get_scheduler_config()
        scheduler = scheduler_class(**scheduler_config)

        assert np.sum(np.abs(scheduler._get_variance(0, 0) - 0.0)) < 1e-5
        assert np.sum(np.abs(scheduler._get_variance(420, 400) - 0.14771)) < 1e-5
        assert np.sum(np.abs(scheduler._get_variance(980, 960) - 0.32460)) < 1e-5
        assert np.sum(np.abs(scheduler._get_variance(0, 0) - 0.0)) < 1e-5
        assert np.sum(np.abs(scheduler._get_variance(487, 486) - 0.00979)) < 1e-5
        assert np.sum(np.abs(scheduler._get_variance(999, 998) - 0.02)) < 1e-5

    def test_full_loop_no_noise(self):
        scheduler_class = self.scheduler_classes[0]
        scheduler_config = self.get_scheduler_config()
        scheduler = scheduler_class(**scheduler_config)

        num_inference_steps, eta = 10, 0.0

        model = self.dummy_model()
        sample = self.dummy_sample_deter

        scheduler.set_timesteps(num_inference_steps)
        for t in scheduler.timesteps:
            residual = model(sample, t)

            sample = scheduler.step(residual, t, sample, eta)["prev_sample"]

        result_sum = np.sum(np.abs(sample))
        result_mean = np.mean(np.abs(sample))

        assert abs(result_sum.item() - 172.0067) < 1e-2
        assert abs(result_mean.item() - 0.223967) < 1e-3


class PNDMSchedulerTest(SchedulerCommonTest):
    scheduler_classes = (PNDMScheduler,)
    forward_default_kwargs = (("num_inference_steps", 50),)

    def get_scheduler_config(self, **kwargs):
        config = {
            "num_train_timesteps": 1000,
            "beta_start": 0.0001,
            "beta_end": 0.02,
            "beta_schedule": "linear",
        }

        config.update(**kwargs)
        return config

    def check_over_configs_pmls(self, time_step=0, **config):
        kwargs = dict(self.forward_default_kwargs)
        sample = self.dummy_sample
        residual = 0.1 * sample
        dummy_past_residuals = [residual + 0.2, residual + 0.15, residual + 0.1, residual + 0.05]

        for scheduler_class in self.scheduler_classes:
            scheduler_class = self.scheduler_classes[0]
            scheduler_config = self.get_scheduler_config(**config)
            scheduler = scheduler_class(**scheduler_config)
            # copy over dummy past residuals
            scheduler.ets = dummy_past_residuals[:]
            scheduler.set_plms_mode()

            with tempfile.TemporaryDirectory() as tmpdirname:
                scheduler.save_config(tmpdirname)
                new_scheduler = scheduler_class.from_config(tmpdirname)
                # copy over dummy past residuals
                new_scheduler.ets = dummy_past_residuals[:]
                new_scheduler.set_plms_mode()

            output = scheduler.step(residual, time_step, sample, **kwargs)["prev_sample"]
            new_output = new_scheduler.step(residual, time_step, sample, **kwargs)["prev_sample"]

            assert np.sum(np.abs(output - new_output)) < 1e-5, "Scheduler outputs are not identical"

    def check_over_forward_pmls(self, time_step=0, **forward_kwargs):
        kwargs = dict(self.forward_default_kwargs)
        kwargs.update(forward_kwargs)
        sample = self.dummy_sample
        residual = 0.1 * sample
        dummy_past_residuals = [residual + 0.2, residual + 0.15, residual + 0.1, residual + 0.05]

        for scheduler_class in self.scheduler_classes:
            scheduler_class = self.scheduler_classes[0]
            scheduler_config = self.get_scheduler_config()
            scheduler = scheduler_class(**scheduler_config)
            # copy over dummy past residuals
            scheduler.ets = dummy_past_residuals[:]
            scheduler.set_plms_mode()

            with tempfile.TemporaryDirectory() as tmpdirname:
                scheduler.save_config(tmpdirname)
                new_scheduler = scheduler_class.from_config(tmpdirname)
                # copy over dummy past residuals
                new_scheduler.ets = dummy_past_residuals[:]
                new_scheduler.set_plms_mode()

            output = scheduler.step(residual, time_step, sample, **kwargs)["prev_sample"]
            new_output = new_scheduler.step(residual, time_step, sample, **kwargs)["prev_sample"]

            assert np.sum(np.abs(output - new_output)) < 1e-5, "Scheduler outputs are not identical"

    def test_timesteps(self):
        for timesteps in [100, 1000]:
            self.check_over_configs(num_train_timesteps=timesteps)

    def test_timesteps_pmls(self):
        for timesteps in [100, 1000]:
            self.check_over_configs_pmls(num_train_timesteps=timesteps)

    def test_betas(self):
        for beta_start, beta_end in zip([0.0001, 0.001, 0.01], [0.002, 0.02, 0.2]):
            self.check_over_configs(beta_start=beta_start, beta_end=beta_end)

    def test_betas_pmls(self):
        for beta_start, beta_end in zip([0.0001, 0.001, 0.01], [0.002, 0.02, 0.2]):
            self.check_over_configs_pmls(beta_start=beta_start, beta_end=beta_end)

    def test_schedules(self):
        for schedule in ["linear", "squaredcos_cap_v2"]:
            self.check_over_configs(beta_schedule=schedule)

    def test_schedules_pmls(self):
        for schedule in ["linear", "squaredcos_cap_v2"]:
            self.check_over_configs(beta_schedule=schedule)

    def test_time_indices(self):
        for t in [1, 5, 10]:
            self.check_over_forward(time_step=t)

    def test_time_indices_pmls(self):
        for t in [1, 5, 10]:
            self.check_over_forward_pmls(time_step=t)

    def test_inference_steps(self):
        for t, num_inference_steps in zip([1, 5, 10], [10, 50, 100]):
            self.check_over_forward(time_step=t, num_inference_steps=num_inference_steps)

    def test_inference_steps_pmls(self):
        for t, num_inference_steps in zip([1, 5, 10], [10, 50, 100]):
            self.check_over_forward_pmls(time_step=t, num_inference_steps=num_inference_steps)

    def test_inference_pmls_no_past_residuals(self):
        with self.assertRaises(ValueError):
            scheduler_class = self.scheduler_classes[0]
            scheduler_config = self.get_scheduler_config()
            scheduler = scheduler_class(**scheduler_config)

            scheduler.set_plms_mode()

            scheduler.step(self.dummy_sample, 1, self.dummy_sample, 50)["prev_sample"]

    def test_full_loop_no_noise(self):
        scheduler_class = self.scheduler_classes[0]
        scheduler_config = self.get_scheduler_config()
        scheduler = scheduler_class(**scheduler_config)

        num_inference_steps = 10
        model = self.dummy_model()
        sample = self.dummy_sample_deter

        prk_time_steps = scheduler.get_prk_time_steps(num_inference_steps)
        for t in range(len(prk_time_steps)):
            t_orig = prk_time_steps[t]
            residual = model(sample, t_orig)

            sample = scheduler.step_prk(residual, t, sample, num_inference_steps)["prev_sample"]

        timesteps = scheduler.get_time_steps(num_inference_steps)
        for t in range(len(timesteps)):
            t_orig = timesteps[t]
            residual = model(sample, t_orig)

            sample = scheduler.step_plms(residual, t, sample, num_inference_steps)["prev_sample"]

        result_sum = np.sum(np.abs(sample))
        result_mean = np.mean(np.abs(sample))

        assert abs(result_sum.item() - 199.1169) < 1e-2
        assert abs(result_mean.item() - 0.2593) < 1e-3


class ScoreSdeVeSchedulerTest(SchedulerCommonTest):
    scheduler_classes = (ScoreSdeVeScheduler,)

    def get_scheduler_config(self, **kwargs):
        config = {
            "num_train_timesteps": 2000,
            "snr": 0.15,
            "sigma_min": 0.01,
            "sigma_max": 1348,
            "sampling_eps": 1e-5,
            "tensor_format": "np",  # TODO add test for tensor formats
        }

        config.update(**kwargs)
        return config

    def check_over_configs(self, time_step=0, **config):
        kwargs = dict(self.forward_default_kwargs)

        for scheduler_class in self.scheduler_classes:
            scheduler_class = self.scheduler_classes[0]
            sample = self.dummy_sample
            residual = 0.1 * sample

            scheduler_config = self.get_scheduler_config(**config)
            scheduler = scheduler_class(**scheduler_config)

            with tempfile.TemporaryDirectory() as tmpdirname:
                scheduler.save_config(tmpdirname)
                new_scheduler = scheduler_class.from_config(tmpdirname)

            output = scheduler.step_pred(residual, sample, time_step, **kwargs)
            new_output = new_scheduler.step_pred(residual, sample, time_step, **kwargs)

            assert np.sum(np.abs(output - new_output)) < 1e-5, "Scheduler outputs are not identical"

            output = scheduler.step_correct(residual, sample, **kwargs)
            new_output = new_scheduler.step_correct(residual, sample, **kwargs)

            assert np.sum(np.abs(output - new_output)) < 1e-5, "Scheduler correction are not identical"

    def check_over_forward(self, time_step=0, **forward_kwargs):
        kwargs = dict(self.forward_default_kwargs)
        kwargs.update(forward_kwargs)

        for scheduler_class in self.scheduler_classes:
            sample = self.dummy_sample
            residual = 0.1 * sample

            scheduler_class = self.scheduler_classes[0]
            scheduler_config = self.get_scheduler_config()
            scheduler = scheduler_class(**scheduler_config)

            with tempfile.TemporaryDirectory() as tmpdirname:
                scheduler.save_config(tmpdirname)
                new_scheduler = scheduler_class.from_config(tmpdirname)

            output = scheduler.step_pred(residual, sample, time_step, **kwargs)
            new_output = new_scheduler.step_pred(residual, sample, time_step, **kwargs)

            assert np.sum(np.abs(output - new_output)) < 1e-5, "Scheduler outputs are not identical"

            output = scheduler.step_correct(residual, sample, **kwargs)
            new_output = new_scheduler.step_correct(residual, sample, **kwargs)

            assert np.sum(np.abs(output - new_output)) < 1e-5, "Scheduler correction are not identical"

    def test_timesteps(self):
        for timesteps in [10, 100, 1000]:
            self.check_over_configs(num_train_timesteps=timesteps)

    def test_sigmas(self):
        for sigma_min, sigma_max in zip([0.0001, 0.001, 0.01], [1, 100, 1000]):
            self.check_over_configs(sigma_min=sigma_min, sigma_max=sigma_max)

    def test_time_indices(self):
        for t in [1, 5, 10]:
            self.check_over_forward(time_step=t)

    def test_full_loop_no_noise(self):
        np.random.seed(0)
        scheduler_class = self.scheduler_classes[0]
        scheduler_config = self.get_scheduler_config()
        scheduler = scheduler_class(**scheduler_config)

        num_inference_steps = 3

        model = self.dummy_model()
        sample = self.dummy_sample_deter

        scheduler.set_sigmas(num_inference_steps)

        for i, t in enumerate(scheduler.timesteps):
            sigma_t = scheduler.sigmas[i]

            for _ in range(scheduler.correct_steps):
                with torch.no_grad():
                    result = model(sample, sigma_t)
                sample = scheduler.step_correct(result, sample)

            with torch.no_grad():
                result = model(sample, sigma_t)

            sample, sample_mean = scheduler.step_pred(result, sample, t)

        result_sum = np.sum(np.abs(sample))
        result_mean = np.mean(np.abs(sample))

        assert abs(result_sum.item() - 10629923278.7104) < 1e-2
        assert abs(result_mean.item() - 13841045.9358) < 1e-3
