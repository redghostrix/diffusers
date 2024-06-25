<!--Copyright 2024 The HuggingFace Team. All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with
the License. You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
-->

# Perturbed-Attention Guidance

[Perturbed-Attention Guidance (PAG)](https://ku-cvlab.github.io/Perturbed-Attention-Guidance/) is a new diffusion sampling guidance that improves sample quality across both unconditional and conditional settings, achieving this without requiring further training or the integration of external modules. PAG is designed to progressively enhance the structure of synthesized samples throughout the denoising process by considering the self-attention mechanisms' ability to capture structural information. It involves generating intermediate samples with degraded structure by substituting selected self-attention maps in diffusion U-Net with an identity matrix, and guiding the denoising process away from these degraded samples.

This guide will show you how to use PAG for various tasks and use cases.


## General tasks

You can apply PAG to the [`StableDiffusionXLPipeline`] for tasks such as text-to-image, image-to-image, and inpainting. To enable PAG for a specific task, load the pipeline using the [AutoPipeline](../api/pipelines/auto_pipeline) API with the `enable_pag=True` flag and the `pag_applied_layers` argument.

> [!TIP]
> 🤗 Diffusers currently only supports using PAG with selected SDXL pipelines, but feel free to open a [feature request](https://github.com/huggingface/diffusers/issues/new/choose) if you want to add PAG support to a new pipeline!

<hfoptions id="tasks">
<hfoption id="Text-to-image">

```py
from diffusers import AutoPipelineForText2Image
from diffusers.utils import load_image
import torch

pipeline = AutoPipelineForText2Image.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    enable_pag=True,
    pag_applied_layers=["mid"],
    torch_dtype=torch.float16
)
pipeline.enable_model_cpu_offload()
```

> [!TIP]
> The `pag_applied_layers` argument allows you to specify which layers PAG is applied to. Additionally, you can use `set_pag_applied_layers` method to update these layers after the pipeline has been created. Check out the [pag_applied_layers](#pag_applied_layers) section to learn more about applying PAG to other layers.

To generate an image, you will also need to pass a `pag_scale`. When `pag_scale` increases, images gain more semantically coherent structures and exhibit fewer artifacts. However overly large guidance scale can lead to smoother textures and slight saturation in the images, similarly to CFG. `pag_scale=3.0` is used in the official demo and works well in most of the use cases, but feel free to experiment and select the appropriate value according to your needs! PAG is disabled when `pag_scale=0`.

```py
prompt = "an insect robot preparing a delicious meal, anime style"

for pag_scale in [0.0, 3.0]:
    generator = torch.Generator(device="cpu").manual_seed(0)
    images = pipeline(
        prompt=prompt,
        num_inference_steps=25,
        guidance_scale=7.0,
        generator=generator,
        pag_scale=pag_scale,
    ).images
```

<div class="flex flex-row gap-4">
  <div class="flex-1">
    <img class="rounded-xl" src="https://huggingface.co/datasets/YiYiXu/testing-images/resolve/main/pag_0.0_cfg_7.0_mid.png"/>
    <figcaption class="mt-2 text-center text-sm text-gray-500">generated image without PAG</figcaption>
  </div>
  <div class="flex-1">
    <img class="rounded-xl" src="https://huggingface.co/datasets/YiYiXu/testing-images/resolve/main/pag_3.0_cfg_7.0_mid.png"/>
    <figcaption class="mt-2 text-center text-sm text-gray-500">generated image with PAG</figcaption>
  </div>
</div>

</hfoption>
<hfoption id="Image-to-image">

Similary, you can use PAG with image-to-image pipelines.

```py
from diffusers import AutoPipelineForImage2Image
from diffusers.utils import load_image
import torch

pipeline = AutoPipelineForImage2Image.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    enable_pag=True,
    pag_applied_layers=["mid"],
    torch_dtype=torch.float16
)
pipeline.enable_model_cpu_offload()

pag_scales =  4.0
guidance_scales = 7.0

url = "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/diffusers/sdxl-text2img.png"
init_image = load_image(url)
prompt = "a dog catching a frisbee in the jungle"

generator = torch.Generator(device="cpu").manual_seed(0)
image = pipeline(
    prompt, 
    image=init_image, 
    strength=0.8, 
    guidance_scale=guidance_scale, 
    pag_scale=pag_scale,
    generator=generator).images[0]
```

</hfoption>
<hfoption id="Inpainting">

```py
from diffusers import AutoPipelineForInpainting
from diffusers.utils import load_image
import torch

pipeline = AutoPipelineForInpainting.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    enable_pag=True,
    torch_dtype=torch.float16
)
pipeline.enable_model_cpu_offload()

img_url = "https://raw.githubusercontent.com/CompVis/latent-diffusion/main/data/inpainting_examples/overture-creations-5sI6fQgYIuo.png"
mask_url = "https://raw.githubusercontent.com/CompVis/latent-diffusion/main/data/inpainting_examples/overture-creations-5sI6fQgYIuo_mask.png"
init_image = load_image(img_url).convert("RGB")
mask_image = load_image(mask_url).convert("RGB")

prompt = "A majestic tiger sitting on a bench"

pag_scales =  3.0
guidance_scales = 7.5

generator = torch.Generator(device="cpu").manual_seed(1)
images = pipeline(
    prompt=prompt,
    image=init_image,
    mask_image=mask_image,
    strength=0.8,
    num_inference_steps=50,
    guidance_scale=guidance_scale,
    generator=generator,
    pag_scale=pag_scale,
).images
images[0]
```
</hfoption>
</hfoptions>

## PAG with ControlNet

To use PAG with ControlNet, first create a `controlnet`. Then, pass the `controlnet` and other PAG arguments to the `from_pretrained` method of the AutoPipeline for the specified task.

```py
from diffusers import AutoPipelineForText2Image, ControlNetModel
import torch

controlnet = ControlNetModel.from_pretrained(
    "diffusers/controlnet-canny-sdxl-1.0", torch_dtype=torch.float16
)

pipeline = AutoPipelineForText2Image.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    controlnet=controlnet,
    enable_pag=True,
    pag_applied_layers="mid",
    torch_dtype=torch.float16
)
pipeline.enable_model_cpu_offload()
```

You can use the pipeline in the same way you normally use ControlNet pipelines, with the added option to specify a `pag_scale` parameter. Note that PAG works well for unconditional generation. In this example, we will generate an image without a prompt.

```py
from diffusers.utils import load_image
canny_image = load_image(
    "https://huggingface.co/datasets/YiYiXu/testing-images/resolve/main/pag_control_input.png"
)

for pag_scale in [0.0, 3.0]:
    generator = torch.Generator(device="cpu").manual_seed(1)
    images = pipeline(
        prompt="",
        controlnet_conditioning_scale=controlnet_conditioning_scale,
        image=canny_image,
        num_inference_steps=50,
        guidance_scale=0,
        generator=generator,
        pag_scale=pag_scale,
    ).images
    images[0]
```

<div class="flex flex-row gap-4">
  <div class="flex-1">
    <img class="rounded-xl" src="https://huggingface.co/datasets/YiYiXu/testing-images/resolve/main/pag_0.0_controlnet.png"/>
    <figcaption class="mt-2 text-center text-sm text-gray-500">generated image without PAG</figcaption>
  </div>
  <div class="flex-1">
    <img class="rounded-xl" src="https://huggingface.co/datasets/YiYiXu/testing-images/resolve/main/pag_3.0_controlnet.png"/>
    <figcaption class="mt-2 text-center text-sm text-gray-500">generated image with PAG</figcaption>
  </div>
</div>

## PAG with IP-Adapter 

[IP-Adapter](https://hf.co/papers/2308.06721) is a popular model that can be plugged into diffusion models to enable image prompting without any changes to the underlying model. You can enable PAG on a pipeline with IP-Adapter loaded.

```py
from diffusers import AutoPipelineForText2Image
from diffusers.utils import load_image
from transformers import CLIPVisionModelWithProjection
import torch

image_encoder = CLIPVisionModelWithProjection.from_pretrained(
    "h94/IP-Adapter",
    subfolder="models/image_encoder",
    torch_dtype=torch.float16
)

pipeline = AutoPipelineForText2Image.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    image_encoder=image_encoder,
    enable_pag=True,
    torch_dtype=torch.float16
).to("cuda")

pipeline.load_ip_adapter("h94/IP-Adapter", subfolder="sdxl_models", weight_name="ip-adapter-plus_sdxl_vit-h.bin")

pag_scales = 5.0
ip_adapter_scales = 0.8

image = load_image("https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/diffusers/ip_adapter_diner.png")

pipeline.set_ip_adapter_scale(ip_adapter_scale)
generator = torch.Generator(device="cpu").manual_seed(0)
images = pipeline(
    prompt="a polar bear sitting in a chair drinking a milkshake",
    ip_adapter_image=image,
    negative_prompt="deformed, ugly, wrong proportion, low res, bad anatomy, worst quality, low quality",
    num_inference_steps=25,
    guidance_scale=3.0,
    generator=generator,
    pag_scale=pag_scale,
).images
images[0]

```

PAG reduces artifacts and improves the overall compposition.

<div class="flex flex-row gap-4">
  <div class="flex-1">
    <img class="rounded-xl" src="https://huggingface.co/datasets/YiYiXu/testing-images/resolve/main/pag_0.0_ipa_0.8.png"/>
    <figcaption class="mt-2 text-center text-sm text-gray-500">generated image without PAG</figcaption>
  </div>
  <div class="flex-1">
    <img class="rounded-xl" src="https://huggingface.co/datasets/YiYiXu/testing-images/resolve/main/pag_5.0_ipa_0.8.png"/>
    <figcaption class="mt-2 text-center text-sm text-gray-500">generated image with PAG</figcaption>
  </div>
</div>


## Configure parameters 

### pag_applied_layers

The `pag_applied_layers` argument allows you to specify which layers PAG is applied to. By default, it applies only to the mid blocks. Changing this setting will significantly impact the output. You can use the `set_pag_applied_layers` method to adjust the PAG layers after the pipeline is created, helping you find the optimal layers for your model.

As an example, here is the images generated with `pag_layers = ["down.block_2"]` and `pag_layers = ["down.block_2", "up.block_1.attentions_0"]`

```py
prompt = "an insect robot preparing a delicious meal, anime style"
pipeline.set_pag_applied_layers(pag_layers)
generator = torch.Generator(device="cpu").manual_seed(0)
images = pipeline(
    prompt=prompt,
    num_inference_steps=25,
    guidance_scale=guidance_scale,
    generator=generator,
    pag_scale=pag_scale,
).images
images[0]
```

<div class="flex flex-row gap-4">
  <div class="flex-1">
    <img class="rounded-xl" src="https://huggingface.co/datasets/YiYiXu/testing-images/resolve/main/pag_3.0_cfg_7.0_down2_up1a0.png"/>
    <figcaption class="mt-2 text-center text-sm text-gray-500">down.block_2 + up.block1.attentions_0</figcaption>
  </div>
  <div class="flex-1">
    <img class="rounded-xl" src="https://huggingface.co/datasets/YiYiXu/testing-images/resolve/main/pag_3.0_cfg_7.0_down2.png"/>
    <figcaption class="mt-2 text-center text-sm text-gray-500">down.block_2</figcaption>
  </div>
</div>
