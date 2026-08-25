"""Frozen DINOv2 ViT-S/14 backbone (REUSE from research, unchanged).

This module is a verbatim extraction of the frozen backbone from
``src/experiments/dinov2_features.py`` (model classes + ``_imagenet_preprocess``).
The model IS the frozen algorithm baseline (MVP_ARCHITECTURE §8 item 1) and must
NOT be modified. Per the research-isolation rule, MVP does ``import`` the research
script; the model code is extracted here so the device layer is self-contained.

Weight loading (``load_state_dict(ckpt)``) matches the official bare pretrained
state_dict (no ``model`` wrapper key).
"""
from __future__ import annotations

import cv2
import numpy as np
import torch
import torch.nn as nn

# Official pretrained URL — for reference/documentation; the MVP ships weights
# bundled or resolves via config (see device.resolve_dinov2_weights).
WEIGHTS_URL = ("https://dl.fbaipublicfiles.com/dinov2/dinov2_vits14/"
               "dinov2_vits14_pretrain.pth")
EMBED_DIM = 384


class _PatchEmbed(nn.Module):
    def __init__(self, img_size=518, patch_size=14, in_chans=3, embed_dim=384):
        super().__init__()
        self.num_patches = (img_size // patch_size) ** 2
        self.proj = nn.Conv2d(in_chans, embed_dim, kernel_size=patch_size,
                              stride=patch_size)

    def forward(self, x):
        x = self.proj(x)
        x = x.flatten(2).transpose(1, 2)  # B, num_patches, embed_dim
        return x


class _Mlp(nn.Module):
    """DINOv2 MLP, matching official state_dict keys mlp.fc1 / mlp.fc2."""
    def __init__(self, in_features, hidden_features):
        super().__init__()
        self.fc1 = nn.Linear(in_features, hidden_features, bias=True)
        self.act = nn.GELU(approximate="tanh")
        self.fc2 = nn.Linear(hidden_features, in_features, bias=True)

    def forward(self, x):
        return self.fc2(self.act(self.fc1(x)))


class _LayerScale(nn.Module):
    """DINOv2 layer scale: a single learnable gamma, stored as .gamma."""
    def __init__(self, dim):
        super().__init__()
        self.gamma = nn.Parameter(torch.ones(dim))

    def forward(self, x):
        return x * self.gamma


class _Attention(nn.Module):
    def __init__(self, dim=384, num_heads=6, qkv_bias=True):
        super().__init__()
        self.num_heads = num_heads
        self.head_dim = dim // num_heads
        self.scale = self.head_dim ** -0.5
        self.qkv = nn.Linear(dim, dim * 3, bias=qkv_bias)
        self.proj = nn.Linear(dim, dim)

    def forward(self, x):
        B, N, D = x.shape
        qkv = self.qkv(x).reshape(B, N, 3, self.num_heads, self.head_dim)
        q, k, v = qkv.permute(2, 0, 3, 1, 4).unbind(0)
        attn = (q @ k.transpose(-2, -1)) * self.scale
        attn = attn.softmax(dim=-1)
        x = (attn @ v).transpose(1, 2).reshape(B, N, D)
        return self.proj(x)


class _Block(nn.Module):
    """DINOv2 block: layernorm pre-attn, qkv fused, layer scale, MLP (fc1/fc2)."""
    def __init__(self, dim=384, num_heads=6, mlp_ratio=4.0, qkv_bias=True):
        super().__init__()
        self.norm1 = nn.LayerNorm(dim, eps=1e-6)
        self.attn = _Attention(dim, num_heads, qkv_bias)
        self.ls1 = _LayerScale(dim)
        self.norm2 = nn.LayerNorm(dim, eps=1e-6)
        self.mlp = _Mlp(dim, int(dim * mlp_ratio))
        self.ls2 = _LayerScale(dim)

    def forward(self, x):
        x = x + self.ls1(self.attn(self.norm1(x)))
        x = x + self.ls2(self.mlp(self.norm2(x)))
        return x


class DinoV2Small(nn.Module):
    """ViT-S/14 matching the official dinov2_vits14 pretrained state_dict."""
    def __init__(self, img_size=518, patch_size=14, embed_dim=384, depth=12,
                 num_heads=6, mlp_ratio=4.0):
        super().__init__()
        self.patch_embed = _PatchEmbed(img_size, patch_size, 3, embed_dim)
        self.cls_token = nn.Parameter(torch.zeros(1, 1, embed_dim))
        self.pos_embed = nn.Parameter(torch.zeros(1, self.patch_embed.num_patches + 1, embed_dim))
        self.mask_token = nn.Parameter(torch.zeros(1, embed_dim))
        self.blocks = nn.ModuleList(
            [_Block(embed_dim, num_heads, mlp_ratio) for _ in range(depth)])
        self.norm = nn.LayerNorm(embed_dim, eps=1e-6)

    def forward(self, x):
        B = x.shape[0]
        x = self.patch_embed(x)
        x = torch.cat((self.cls_token.expand(B, -1, -1), x), dim=1)
        x = x + self.pos_embed
        for blk in self.blocks:
            x = blk(x)
        x = self.norm(x)
        return x[:, 0]  # CLS token


def _imagenet_preprocess(frame_bgr):
    """BGR (H,W,3) np.uint8 frame -> RGB tensor, resize to 518x518, normalize
    with ImageNet stats (DINOv2 official preprocessing). Frozen."""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (518, 518), interpolation=cv2.INTER_LINEAR)
    rgb = rgb.astype(np.float32) / 255.0
    mean = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float32)
    std = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float32)
    t = torch.from_numpy(rgb).permute(2, 0, 1)  # 3,518,518
    t = (t - mean[:, None, None]) / std[:, None, None]
    return t.unsqueeze(0)
