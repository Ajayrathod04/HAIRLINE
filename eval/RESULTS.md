# Synthetic benchmark (full)

144 synthetic scenes with known crack widths, OpenCV 4.13.0, 292 s on x86_64.
Synthetic only: validates geometry, gating and measurement, NOT accuracy on real walls. Re-shoot rows assume the user follows the advice.

| Strategy | n | MAE mm | median mm | p90 mm | notes |
|---|---|---|---|---|---|
| Naive: accept every first photo (no gates, no blur fix) | 142 | 0.187 | 0.167 | 0.532 | 35 outside tolerance, 2 with no scale |
| Agent (gates + blur fix): measured first shots only | 70 | 0.1 | 0.101 | 0.2 | 11 false accepts; accepted share 0.5 |
| Agent: rejected, then compliant re-shoot | 72 | 0.1 | 0.101 | 0.2 | rejected share 0.5 |

Tolerance rule: max(0.15 mm, 30% of true width).

Reject reasons (a scene can fail several gates): {"glare_fraction": 48, "tilt_deg": 36}

| True width mm | baseline MAE | agent-accepted MAE |
|---|---|---|
| 0.3 | 0.261 (n=34) | 0.13 (n=16) |
| 0.5 | 0.19 (n=36) | 0.078 (n=18) |
| 1.0 | 0.187 (n=36) | 0.107 (n=18) |
| 2.0 | 0.115 (n=36) | 0.09 (n=18) |
