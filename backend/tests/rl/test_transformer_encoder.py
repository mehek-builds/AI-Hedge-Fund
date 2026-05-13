"""Wave 0 stubs -- FR-5.4 (Transformer config)."""
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


def test_frozen_encoder_loads_weights(tmp_path):
    """FR-5.4: from_pretrained loads checkpoint AND freezes every parameter."""
    import torch
    from rl.transformer_encoder import TransformerStateEncoder

    src = TransformerStateEncoder(input_dim=31, d_model=64, n_heads=4, n_layers=3)
    # Capture a sentinel weight to verify the load actually wrote weights
    sentinel_before = next(src.parameters()).detach().clone()

    ckpt = tmp_path / "transformer_pretrained.pt"
    torch.save(src.state_dict(), ckpt)

    loaded = TransformerStateEncoder.from_pretrained(
        str(ckpt), input_dim=31, d_model=64, n_heads=4, n_layers=3
    )

    # Frozen: no parameter trains
    assert all(not p.requires_grad for p in loaded.parameters()), \
        "from_pretrained must call freeze() -- every parameter requires_grad must be False"

    # Loaded weights match what was saved (within float tolerance)
    sentinel_after = next(loaded.parameters()).detach().clone()
    assert torch.allclose(sentinel_before, sentinel_after, atol=1e-6), \
        "Loaded weights do not match saved weights -- load_state_dict failed silently?"
