"""Generate demo sample photos (synthetic, known widths) + printable marker. Run from the repo root."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2

from hairline import synth
from hairline.config import Config
from hairline.cvcore import make_marker_image

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples")
cfg = Config()
SAMPLES = {
    "sample_good_0p6mm": dict(seed=21, widths_mm=[0.6], tilt_deg=(6, 3)),
    "sample_wide_2p0mm": dict(seed=22, widths_mm=[2.0], tilt_deg=(4, 8)),
    "sample_tilted_45deg": dict(seed=23, widths_mm=[0.6], tilt_deg=(45, 0)),
    "sample_blurry": dict(seed=24, widths_mm=[0.6], blur=4.5),
    "sample_glare": dict(seed=25, widths_mm=[0.6], glare=0.9),
    "sample_too_far": dict(seed=26, widths_mm=[0.6], ppm=3.0),
    "sample_dark": dict(seed=27, widths_mm=[0.6], gain=0.25),
    "sample_no_marker": dict(seed=28, widths_mm=[0.6], marker=False),
}
os.makedirs(OUT, exist_ok=True)
for name, kw in SAMPLES.items():
    img, truth = synth.render(cfg=cfg, **kw)
    cv2.imwrite(os.path.join(OUT, name + ".jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 86])
    print("wrote", name)
cv2.imwrite(os.path.join(OUT, "hairline_marker_id7_50mm_300dpi.png"), make_marker_image(cfg))
print("wrote marker (print at 100% and verify the black square is 50 mm)")
