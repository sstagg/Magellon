"""In-process smoke test for the topaz plugin.

Bypasses RMQ entirely. Builds a TaskDto for the bundled sandbox
micrograph, invokes plugin.run(), and asserts the SDK schemas + an
expected pick count. The reference range comes from running the same
ONNX pipeline directly via the sandbox's e2e_onnx_pick.py (1713 picks
total at radius=14, threshold=-3, scale=8 — within 1 of upstream's
1712 produced by the topaz CLI).

Slow: ~30-60 s on the bundled 7676x7420 micrograph because the GMM
normalize step iterates 12 pi candidates each fitting a 2-component
mixture over ~900k pixels.

Skip with -k 'not denoise' if you only want the picking path. The
denoise smoke runs the full UNet over a small synthetic image so it's
fast.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
sys.path.insert(0, str(PLUGIN_ROOT))

SANDBOX = Path(r"C:/projects/Magellon/Sandbox/particle_picking_topaz")
TEST_MRC = SANDBOX / "example_images" / "14sep05c_00024sq_00003hl_00002es_c.mrc"


def test_pick_on_bundled_mrc(tmp_path):
    """End-to-end pick + parity vs the sandbox e2e_onnx_pick.py result."""
    from magellon_sdk.categories.outputs import ParticlePickingOutput
    from magellon_sdk.models.tasks import TopazPickTaskData
    from plugin import TopazPickPlugin

    plug = TopazPickPlugin()
    inp = TopazPickTaskData(input_file=str(TEST_MRC))
    out = plug.run(inp)

    assert isinstance(out, ParticlePickingOutput)
    # The bundled sandbox e2e parity check produces 1713 picks at the
    # default tutorial settings; allow a small +/- window for the
    # GMM EM iteration (which terminates by tolerance, not iter count).
    assert 1700 <= out.num_particles <= 1730, (
        f"unexpected pick count {out.num_particles}; "
        f"sandbox baseline is 1713 at radius=14 threshold=-3 scale=8"
    )

    # Inline picks are always populated for <5k results.
    assert out.picks is not None
    assert len(out.picks) == out.num_particles

    # Top pick has score ~6.26 in our reference run — accept >=4 as a
    # very loose lower bound (GMM jitter doesn't move top picks much).
    top = out.picks[0]
    assert top.score >= 4.0
    assert top.radius == 14 * 8  # default radius * default scale
    assert len(top.center) == 2

    # particles_json_path was written
    assert out.particles_json_path
    assert os.path.exists(out.particles_json_path)


def test_denoise_synthetic(tmp_path):
    """Run the denoiser on a small synthetic patch — confirms ONNX pipeline
    + tile-stitch driver wires up. We don't denoise the full bundled MRC
    here because that takes minutes."""
    from magellon_sdk.categories.outputs import MicrographDenoisingOutput
    from magellon_sdk.models.tasks import MicrographDenoiseTaskData
    from plugin import TopazDenoisePlugin

    # Create a small synthetic MRC
    import mrcfile
    rng = np.random.default_rng(0)
    fake = (rng.standard_normal((512, 512)) * 0.5 + 1.2).astype(np.float32)
    src = tmp_path / "fake.mrc"
    with mrcfile.new(str(src), overwrite=True) as m:
        m.set_data(fake)
    out_mrc = tmp_path / "fake_denoised.mrc"

    plug = TopazDenoisePlugin()
    inp = MicrographDenoiseTaskData(
        input_file=str(src), output_file=str(out_mrc),
        engine_opts={"patch_size": 256, "padding": 32},
    )
    out = plug.run(inp)

    assert isinstance(out, MicrographDenoisingOutput)
    assert out.image_shape == [512, 512]
    assert os.path.exists(out_mrc)
    with mrcfile.open(str(out_mrc)) as m:
        assert m.data.shape == (512, 512)
