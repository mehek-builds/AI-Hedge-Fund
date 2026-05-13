"""Wave 0 stubs — FR-5.4 (Transformer config)."""
import pytest
from rl.transformer_encoder import TransformerStateEncoder
from config import SACConfig


def test_layer_count():
    """FR-5.4: SACConfig.transformer_layers must be 3, not 4."""
    cfg = SACConfig()
    assert cfg.transformer_layers == 3, f"Expected 3 layers, got {cfg.transformer_layers}"


def test_encoder_config():
    """FR-5.4: TransformerStateEncoder default n_layers is 3, d_model=64, n_heads=4."""
    enc = TransformerStateEncoder()
    assert enc.d_model == 64
    # Count encoder layers via the underlying nn.TransformerEncoder
    n_layers = len(enc.encoder.layers)
    assert n_layers == 3, f"Expected 3 layers, got {n_layers}"


def test_frozen_encoder():
    """FR-5.4: After freeze(), no parameter has requires_grad=True."""
    enc = TransformerStateEncoder()
    enc.freeze()
    assert all(not p.requires_grad for p in enc.parameters())
