"""Printable validation card: ArUco marker + five gauge lines of known width. For the REAL-photo evaluation.

Print at 100% (no 'fit to page'), on matte paper, 600 dpi or better. VERIFY with a ruler that the black marker
square is 50 mm and the 100 mm ruler bar is 100 mm. The accuracy you can claim is limited by your printer.
Outputs samples/gauge_card_A4_600dpi.png and samples/gauge_card_layout.json (ROI boxes in mm from marker centre).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2
import numpy as np

from hairline.config import Config
from hairline.cvcore import make_marker_image

DPI = 600
PX = DPI / 25.4
cfg = Config()
W_MM, H_MM = 210, 297
WIDTHS = [0.2, 0.3, 0.5, 1.0, 2.0]
LINE_LEN, GAP = 80.0, 12.0


def mm(v):
    return int(round(v * PX))


card = np.full((mm(H_MM), mm(W_MM)), 255, np.uint8)
marker = make_marker_image(cfg, px_per_mm=PX)
mh, mw = marker.shape
cx_mm, cy_mm = W_MM / 2, 40.0                       # marker centre on the sheet
x0, y0 = mm(cx_mm) - mw // 2, mm(cy_mm) - mh // 2
card[y0:y0 + mh, x0:x0 + mw] = marker
layout = {"marker_id": cfg.marker_id, "marker_mm": cfg.marker_mm, "dpi": DPI, "lines": []}
y_start = cy_mm + 50.0
for i, w in enumerate(WIDTHS):
    y = y_start + i * GAP
    x_a, x_b = cx_mm - LINE_LEN / 2, cx_mm + LINE_LEN / 2
    cv2.rectangle(card, (mm(x_a), mm(y - w / 2)), (mm(x_b), mm(y - w / 2) + max(1, mm(w)) - 1), 0, -1)
    cv2.putText(card, f"{w:.1f} mm", (mm(x_b + 4), mm(y + 1.5)), cv2.FONT_HERSHEY_SIMPLEX, 1.6, 0, 3, cv2.LINE_AA)
    # ROI relative to the marker centre, thin band around the line
    layout["lines"].append({"width_mm": w, "roi_mm": [x_a - cx_mm + 6, y - cy_mm - 4.0, x_b - cx_mm - 6, y - cy_mm + 4.0]})
yr = y_start + len(WIDTHS) * GAP + 2
cv2.line(card, (mm(cx_mm - 50), mm(yr)), (mm(cx_mm + 50), mm(yr)), 0, 6)
cv2.putText(card, "100 mm ruler bar: measure it with a ruler before trusting this card", (mm(cx_mm - 80), mm(yr + 9)), cv2.FONT_HERSHEY_SIMPLEX, 1.1, 0, 2, cv2.LINE_AA)
cv2.putText(card, "HAIRLINE gauge card. Print at 100%. Marker square must be 50 mm.", (mm(14), mm(H_MM - 12)), cv2.FONT_HERSHEY_SIMPLEX, 1.1, 0, 2, cv2.LINE_AA)
out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples")
cv2.imwrite(os.path.join(out, "gauge_card_A4_600dpi.png"), card)
with open(os.path.join(out, "gauge_card_layout.json"), "w") as f:
    json.dump(layout, f, indent=1)
print("wrote gauge card + layout")
