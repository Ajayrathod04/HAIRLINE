# Synthetic benchmark (quick)

24 synthetic scenes with known crack widths, OpenCV 5.0.0, 56 s on AMD64.
Synthetic only: validates geometry, gating and measurement, NOT accuracy on real walls. Re-shoot rows assume the user follows the advice.

| Strategy | n | MAE mm | median mm | p90 mm | notes |
|---|---|---|---|---|---|
| Naive: accept every first photo (no gates, no blur fix) | 24 | 0.266 | 0.167 | 0.532 | 8 outside tolerance, 0 with no scale |
| Agent (gates + blur fix): measured first shots only | 16 | 0.112 | 0.085 | 0.167 | 1 false accepts; accepted share 0.667 |
| Agent: rejected, then compliant re-shoot | 8 | 0.075 | 0.05 | 0.167 | rejected share 0.333 |

Tolerance rule: max(0.15 mm, 30% of true width).

Reject reasons (a scene can fail several gates): {"tilt_deg": 8}

| True width mm | baseline MAE | agent-accepted MAE |
|---|---|---|
| 0.5 | 0.311 (n=12) | 0.038 (n=8) |
| 1.0 | 0.222 (n=12) | 0.186 (n=8) |
