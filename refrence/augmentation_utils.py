import cv2
import numpy as np
import logging
import torch
from diffusers import StableDiffusionImg2ImgPipeline
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import math

logger = logging.getLogger(__name__)

# Global cache for the AI pipeline so it stays in memory
_diffusion_pipeline = None

def _get_diffusion_pipeline():
    global _diffusion_pipeline
    if _diffusion_pipeline is None:
        logger.info("Loading Stable Diffusion Model into memory. This may take a minute...")
        model_id = "runwayml/stable-diffusion-v1-5"
        
        # Auto-detect GPU for massive speedup
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        _diffusion_pipeline = StableDiffusionImg2ImgPipeline.from_pretrained(
            model_id, 
            torch_dtype=torch.float16 if device == "cuda" else torch.float32
        )
        _diffusion_pipeline = _diffusion_pipeline.to(device)
        
        # Memory optimization
        _diffusion_pipeline.enable_attention_slicing()
        
    return _diffusion_pipeline

def augment_image(image, thumb_w=None, seed=None, fast=False):
    """
    AI Augmentation using Stable Diffusion (Image-to-Image).
    Replaces the old OpenCV-based logic entirely.
    """
    try:
        pipeline = _get_diffusion_pipeline()
        
        h, w = image.shape[:2]
        
        # Downscale for thumbnails if requested (saves processing time)
        if thumb_w and thumb_w < w:
            aspect = h / w
            thumb_h = int(thumb_w * aspect)
            image = cv2.resize(image, (thumb_w, thumb_h), interpolation=cv2.INTER_AREA)
        
        # Convert OpenCV image (BGR) to PIL Image (RGB)
        color_coverted = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_init_image = Image.fromarray(color_coverted)
        
        # Resize to 512x512 (Stable Diffusion expects dimensions as multiples of 8)
        original_size = pil_init_image.size
        pil_init_image = pil_init_image.resize((512, 512))

        # Setup Generator for reproducible variations (if seed is provided)
        generator = None
        if seed is not None:
            # Ensure seed is within valid bounds for torch
            safe_seed = seed % (2**32 - 1)
            device = "cuda" if torch.cuda.is_available() else "cpu"
            generator = torch.Generator(device=device).manual_seed(safe_seed)

        # Settings for Diffusion 
        # lower num_inference_steps = faster generation but lower quality
        prompt = "a highly detailed realistic hand making a gesture, different lighting, plain background, 4k"
        strength = 0.35 # 0.0 = exact same image, 1.0 = completely new image
        steps = 10 if fast else 25 

        # Generate new image
        generated_pil = pipeline(
            prompt=prompt, 
            image=pil_init_image, 
            strength=strength, 
            num_inference_steps=steps,
            generator=generator
        ).images[0]
        
        # Restore the image to its original requested dimensions
        generated_pil = generated_pil.resize(original_size)
        
        # Convert back to OpenCV format (BGR)
        numpy_image = np.array(generated_pil)
        final_cv_image = cv2.cvtColor(numpy_image, cv2.COLOR_RGB2BGR)
        
        return final_cv_image

    except Exception as e:
        logger.error(f"Diffusion generation failed: {e}. Returning original image as fallback.")
        return image

def generate_bulk_augmentations(image, count=100):
    """
    Generates a list of bulk augmentations using the AI model.
    NOTE: With diffusion, generating 100 images will be heavily GPU bound and slow.
    """
    return [augment_image(image, seed=i) for i in range(count)]

def generate_augmentation_sprite(image, count=100, thumb_w=128):
    """
    Sprite Generation mapped to the Diffusion model.
    """
    h, w = image.shape[:2]
    aspect = h / w
    thumb_h = int(thumb_w * aspect)
    
    # Process the images
    with ThreadPoolExecutor(max_workers=2) as executor: # Keep workers low so we don't OOM crash the GPU
        seeds = list(range(count))
        processed = list(executor.map(lambda s: augment_image(image, thumb_w=thumb_w, seed=s, fast=True), seeds))
    
    cols = 10 
    rows = int(math.ceil(count / cols))
    
    # Create empty background 
    sprite = np.zeros((rows * thumb_h, cols * thumb_w, 3), dtype=np.uint8)
    
    for idx, img in enumerate(processed):
        r, c = divmod(idx, cols)
        sprite[r*thumb_h:(r+1)*thumb_h, c*thumb_w:(c+1)*thumb_w] = img
            
    return sprite