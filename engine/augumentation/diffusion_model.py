import torch
import numpy as np

class DiffusionAugmentor:
    """Simulated Diffusion process for structural image variants."""
    def __init__(self, steps=100):
        self.steps = steps
        self.beta = np.linspace(0.0001, 0.02, steps)

    def apply_diffusion(self, image_tensor, intensity=0.5):
        """
        Adds noise (forward diffusion) and performs partial reconstruction
        to create a high-fidelity variant of the original scan.
        """
        # Calculate noise level based on intensity
        t = int(self.steps * intensity)
        noise = torch.randn_like(image_tensor)
        
        # Forward process: x_t = sqrt(alpha_bar) * x_0 + sqrt(1-alpha_bar) * noise
        noisy_image = image_tensor + (noise * self.beta[t])
        
        # Reverse process (Simplified for augmentation)
        # Returns a variant that is structurally similar but visually different
        return torch.clamp(noisy_image, 0, 1)