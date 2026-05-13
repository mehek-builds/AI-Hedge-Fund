"""Transformer state encoder for earnings sequence pre-training."""

from __future__ import annotations

import torch
import torch.nn as nn
import math


class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 512, dropout: float = 0.1) -> None:
        super().__init__()
        self.dropout = nn.Dropout(dropout)
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len).unsqueeze(1).float()
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))  # (1, max_len, d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.pe[:, : x.size(1)]
        return self.dropout(x)


class TransformerStateEncoder(nn.Module):
    """
    4-layer transformer encoder over earnings event sequences.

    Input:  (batch, seq_len, input_dim) — raw feature sequences
    Output: (batch, d_model) — CLS-token pooled representation

    Pre-trained on earnings sequences; frozen in initial deployment (v1).
    """

    def __init__(
        self,
        input_dim: int = 31,
        d_model: int = 64,
        n_heads: int = 4,
        n_layers: int = 4,
        dim_feedforward: int = 256,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.d_model = d_model
        self.input_proj = nn.Linear(input_dim, d_model)
        self.pos_enc = PositionalEncoding(d_model, dropout=dropout)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=n_heads,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
            norm_first=True,  # pre-norm for training stability
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        self.cls_token = nn.Parameter(torch.zeros(1, 1, d_model))
        nn.init.trunc_normal_(self.cls_token, std=0.02)
        self.norm = nn.LayerNorm(d_model)

    def forward(self, x: torch.Tensor, src_key_padding_mask: torch.Tensor | None = None) -> torch.Tensor:
        """
        Args:
            x: (batch, seq_len, input_dim)
            src_key_padding_mask: (batch, seq_len+1) — True for padding positions
        Returns:
            (batch, d_model) — CLS token embedding
        """
        batch = x.size(0)
        x = self.input_proj(x)                          # (batch, seq_len, d_model)
        x = self.pos_enc(x)
        cls = self.cls_token.expand(batch, -1, -1)       # (batch, 1, d_model)
        x = torch.cat([cls, x], dim=1)                  # (batch, 1+seq_len, d_model)
        x = self.encoder(x, src_key_padding_mask=src_key_padding_mask)
        cls_out = self.norm(x[:, 0])                     # (batch, d_model)
        return cls_out

    def freeze(self) -> None:
        for p in self.parameters():
            p.requires_grad = False

    def unfreeze(self) -> None:
        for p in self.parameters():
            p.requires_grad = True

    @classmethod
    def from_pretrained(cls, path: str, **kwargs) -> "TransformerStateEncoder":
        model = cls(**kwargs)
        state = torch.load(path, map_location="cpu", weights_only=True)
        model.load_state_dict(state)
        model.freeze()
        return model
