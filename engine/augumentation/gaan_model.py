# engine/augumentation/gaan_model.py
import torch
import torch.nn as nn

class Generator(nn.Module):
    def __init__(self, z_dim=100):
        super(Generator, self).__init__()
        # DCGAN architecture: transforms noise into a 64x64 RGB image
        self.main = nn.Sequential(
            # Input is Z, going into a convolution
            nn.ConvTranspose2d(z_dim, 512, 4, 1, 0, bias=False),
            nn.BatchNorm2d(512),
            nn.ReLU(True),
            # State: 512 x 4 x 4
            nn.ConvTranspose2d(512, 256, 4, 2, 1, bias=False),
            nn.BatchNorm2d(256),
            nn.ReLU(True),
            # State: 256 x 8 x 8
            nn.ConvTranspose2d(256, 128, 4, 2, 1, bias=False),
            nn.BatchNorm2d(128),
            nn.ReLU(True),
            # State: 128 x 16 x 16
            nn.ConvTranspose2d(128, 64, 4, 2, 1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(True),
            # State: 64 x 32 x 32
            nn.ConvTranspose2d(64, 3, 4, 2, 1, bias=False),
            nn.Tanh()
            # Output: 3 x 64 x 64 (Values in range [-1, 1])
        )

    def forward(self, input_tensor):
        return self.main(input_tensor)

class GAANAugmentor:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.generator = Generator().to(self.device)
        self.generator.eval() # Evaluation mode for generation

    def generate_variants(self, num_variants=2):
        """Generates synthetic gesture images from latent noise."""
        variants = []
        with torch.no_grad():
            for _ in range(num_variants):
                # Create random noise vector (100-dim)
                noise = torch.randn(1, 100, 1, 1, device=self.device)
                fake_img = self.generator(noise)
                variants.append(fake_img)
        return variants