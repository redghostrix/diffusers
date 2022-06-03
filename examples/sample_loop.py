#!/usr/bin/env python3
from diffusers import UNetModel, GaussianDiffusion
import torch
import torch.nn.functional as F

unet = UNetModel.from_pretrained("fusing/ddpm_dummy")
diffusion = GaussianDiffusion.from_config("fusing/ddpm_dummy")

# 2. Do one denoising step with model
batch_size, num_channels, height, width = 1, 3, 32, 32
dummy_noise = torch.ones((batch_size, num_channels, height, width))


TIME_STEPS = 10


# Helper
def extract(a, t, x_shape):
    b, *_ = t.shape
    out = a.gather(-1, t)
    return out.reshape(b, *((1,) * (len(x_shape) - 1)))


def noise_like(shape, device, repeat=False):
    def repeat_noise():
        return torch.randn((1, *shape[1:]), device=device).repeat(shape[0], *((1,) * (len(shape) - 1)))

    def noise():
        return torch.randn(shape, device=device)

    return repeat_noise() if repeat else noise()


# Schedule
def cosine_beta_schedule(timesteps, s=0.008):
    """
    cosine schedule
    as proposed in https://openreview.net/forum?id=-NEXDKk8gZ
    """
    steps = timesteps + 1
    x = torch.linspace(0, timesteps, steps, dtype=torch.float64)
    alphas_cumprod = torch.cos(((x / timesteps) + s) / (1 + s) * torch.pi * 0.5) ** 2
    alphas_cumprod = alphas_cumprod / alphas_cumprod[0]
    betas = 1 - (alphas_cumprod[1:] / alphas_cumprod[:-1])
    return torch.clip(betas, 0, 0.999)


betas = cosine_beta_schedule(TIME_STEPS)
alphas = 1.0 - betas
alphas_cumprod = torch.cumprod(alphas, axis=0)
alphas_cumprod_prev = F.pad(alphas_cumprod[:-1], (1, 0), value=1.0)

posterior_mean_coef1 = betas * torch.sqrt(alphas_cumprod_prev) / (1.0 - alphas_cumprod)
posterior_mean_coef2 = (1.0 - alphas_cumprod_prev) * torch.sqrt(alphas) / (1.0 - alphas_cumprod)

posterior_variance = betas * (1.0 - alphas_cumprod_prev) / (1.0 - alphas_cumprod)
posterior_log_variance_clipped = torch.log(posterior_variance.clamp(min=1e-20))


sqrt_recip_alphas_cumprod = torch.sqrt(1.0 / alphas_cumprod)
sqrt_recipm1_alphas_cumprod = torch.sqrt(1.0 / alphas_cumprod - 1)

torch.manual_seed(0)

# Compare the following to Algorithm 2 Sampling of paper: https://arxiv.org/pdf/2006.11239.pdf
# 1: x_t ~ N(0,1)
x_t = dummy_noise
# 2: for t = T, ...., 1 do
for i in reversed(range(TIME_STEPS)):
    t = torch.tensor([i])
    # 3: z ~ N(0, 1)
    noise = noise_like(x_t.shape, "cpu")

    # 4:  √1αtxt − √1−αt1−α¯tθ(xt, t) + σtz
    # ------------------------- MODEL ------------------------------------#
    pred_noise = unet(x_t, t)  # pred epsilon_theta
    pred_x = extract(sqrt_recip_alphas_cumprod, t, x_t.shape) * x_t - extract(sqrt_recipm1_alphas_cumprod, t, x_t.shape) * pred_noise
    pred_x.clamp_(-1.0, 1.0)
    # pred mean
    posterior_mean = extract(posterior_mean_coef1, t, x_t.shape) * pred_x + extract(posterior_mean_coef2, t, x_t.shape) * x_t
    # --------------------------------------------------------------------#

    # ------------------------- Variance Scheduler -----------------------#
    # pred variance
    posterior_log_variance = extract(posterior_log_variance_clipped, t, x_t.shape)
    b, *_, device = *x_t.shape, x_t.device
    nonzero_mask = (1 - (t == 0).float()).reshape(b, *((1,) * (len(x_t.shape) - 1)))
    posterior_variance = nonzero_mask * (0.5 * posterior_log_variance).exp()
    # --------------------------------------------------------------------#

    x_t_1 = (posterior_mean + posterior_variance * noise).to(torch.float32)

    # FOR PATRICK TO VERIFY: make sure manual loop is equal to function
    # --------------------------------------------------------------------#
    x_t_12 = diffusion.p_sample(unet, x_t, t, noise=noise)
    assert (x_t_1 - x_t_12).abs().sum().item() < 1e-3
    # --------------------------------------------------------------------#

    x_t = x_t_1
