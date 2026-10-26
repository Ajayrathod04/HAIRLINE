"""OpenCV perception engine: marker -> pose/tilt -> metric rectification -> quality gates
-> crack segmentation -> width measurement in millimetres -> visit-to-visit comparison.

Only long-stable OpenCV APIs are used so the same code runs on 4.x and 5.x.
scripts/verify_opencv5.py checks the installed major version.
"""
from __future__ import annotations
import math
from typing import Optional
import cv2
import numpy as np
from skimage.morphology import skeletonize

from .config import Config


# ----------------------------------------------------------------------------- marker
def _dictionary(cfg: Config):
    return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, cfg.aruco_dict))


def make_marker_image(cfg: Config, marker_id: Optional[int] = None, px_per_mm: float = 11.81) -> np.ndarray:
    """Printable marker with white quiet zone. Default 11.81 px/mm = 300 dpi."""
    mid = cfg.marker_id if marker_id is None else marker_id
    side = int(round(cfg.marker_mm * px_per_mm))
    border = int(round(cfg.marker_border_mm * px_per_mm))
    d = _dictionary(cfg)
    try:
        m = cv2.aruco.generateImageMarker(d, mid, side)
    except AttributeError:  # very old builds
        m = cv2.aruco.drawMarker(d, mid, side)
    return cv2.copyMakeBorder(m, border, border, border, border, cv2.BORDER_CONSTANT, value=255)


def detect_marker(gray: np.ndarray, cfg: Config, expected_id: Optional[int] = None) -> Optional[dict]:
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    det = cv2.aruco.ArucoDetector(_dictionary(cfg), params)
    corners, ids, _ = det.detectMarkers(gray)
    if ids is None or len(ids) == 0:
        return None
    best = None
    for c, i in zip(corners, ids.flatten()):
        c = c.reshape(4, 2).astype(np.float32)
        side = float(np.mean([np.linalg.norm(c[k] - c[(k + 1) % 4]) for k in range(4)]))
        if expected_id is not None and int(i) != int(expected_id):
            continue
        if best is None or side > best["side_px"]:
            best = {"id": int(i), "corners": c, "side_px": side}
    if best is None:  # markers present but none with the expected id
        c = corners[0].reshape(4, 2).astype(np.float32)
        return {"id": int(ids.flatten()[0]), "corners": c, "side_px": 0.0, "wrong_id": True}
    return best


# ----------------------------------------------------------------------------- geometry
def rectify(gray: np.ndarray, corners: np.ndarray, cfg: Config) -> dict:
    """Warp the wall plane to a metric canvas. Canvas centre == marker centre; 1 mm == px_per_mm px."""
    s = int(round(cfg.window_mm * cfg.px_per_mm))
    c = s / 2.0
    h = cfg.marker_mm / 2.0 * cfg.px_per_mm
    dst = np.float32([[c - h, c - h], [c + h, c - h], [c + h, c + h], [c - h, c + h]])
    H = cv2.getPerspectiveTransform(corners.astype(np.float32), dst)
    canvas = cv2.warpPerspective(gray, H, (s, s), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    ones = np.full(gray.shape[:2], 255, np.uint8)
    valid = cv2.warpPerspective(ones, H, (s, s), flags=cv2.INTER_NEAREST) > 0
    valid = cv2.erode(valid.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    # local anisotropy of the homography at the marker centre -> tilt estimate (no intrinsics needed)
    c0 = corners.mean(axis=0)

    def proj(p):
        v = H @ np.array([p[0], p[1], 1.0])
        return v[:2] / v[2]

    p0, p1, p2 = proj(c0), proj(c0 + [1, 0]), proj(c0 + [0, 1])
    J = np.stack([p1 - p0, p2 - p0], axis=1)
    sv = np.linalg.svd(J, compute_uv=False)
    tilt = math.degrees(math.acos(float(np.clip(sv.min() / sv.max(), 0.0, 1.0))))
    return {"canvas": canvas, "valid": valid, "H": H, "tilt_deg": tilt}


def exclusion_mask(cfg: Config, shape) -> np.ndarray:
    """Marker + printed paper border (+ margin for the closing kernel) is never searched for cracks."""
    s = shape[0]
    c = s / 2.0
    half = (cfg.marker_mm / 2.0 + cfg.marker_border_mm + 0.6 * cfg.closing_mm) * cfg.px_per_mm
    m = np.zeros(shape, bool)
    m[int(c - half):int(c + half), int(c - half):int(c + half)] = True
    return m


def roi_mask(cfg: Config, shape, boxes_mm) -> np.ndarray:
    """Boolean mask of boxes given in mm relative to the marker centre (x0, y0, x1, y1)."""
    m = np.zeros(shape, bool)
    c = shape[0] / 2.0
    for (x0, y0, x1, y1) in boxes_mm:
        m[max(0, int(c + y0 * cfg.px_per_mm)):int(c + y1 * cfg.px_per_mm), max(0, int(c + x0 * cfg.px_per_mm)):int(c + x1 * cfg.px_per_mm)] = True
    return m


def _marker_sharpness(gray: np.ndarray, corners: np.ndarray) -> float:
    x0, y0 = np.floor(corners.min(axis=0)).astype(int)
    x1, y1 = np.ceil(corners.max(axis=0)).astype(int)
    pad = int(0.05 * max(x1 - x0, y1 - y0))
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    patch = gray[y0:y1 + pad, x0:x1 + pad].astype(np.float32)
    if patch.size < 400:
        return 0.0
    contrast = float(np.percentile(patch, 95) - np.percentile(patch, 5))
    if contrast < 10:
        return 0.0
    gx = cv2.Sobel(patch, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(patch, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    mag = np.hypot(gx, gy).ravel()
    n = max(50, int(0.01 * mag.size))
    return float(np.sort(mag)[-n:].mean() / contrast)


# ----------------------------------------------------------------------------- quality gates
def quality_gates(gray: np.ndarray, marker: Optional[dict], rect: Optional[dict], cfg: Config,
                  roi_boxes_mm: Optional[list] = None) -> dict:
    gates = []

    def add(name, value, ok, level, advice, threshold=None):
        gates.append({"name": name, "value": None if value is None else round(float(value), 3),
                      "threshold": threshold, "pass": bool(ok), "level": level, "advice": advice})

    if marker is None or marker.get("wrong_id"):
        why = "A marker was seen but it is not this case's marker id." if marker else "No marker found."
        add("marker", 0, False, "block",
            f"{why} Place the printed HAIRLINE marker flat on the wall within 15 cm of the crack, "
            "whole marker in frame, no shadow across it.")
        return {"gates": gates, "blocked": True, "warned": False, "metrics": {}}

    ppm = marker["side_px"] / cfg.marker_mm
    add("resolution_px_per_mm", ppm, ppm >= cfg.min_src_ppm_block, "block",
        f"Move closer: the marker is only {ppm:.1f} px/mm, need at least {cfg.min_src_ppm_block}.", cfg.min_src_ppm_block)
    if ppm >= cfg.min_src_ppm_block and ppm < cfg.min_src_ppm_warn:
        add("resolution_warn", ppm, False, "warn", f"Resolution is marginal ({ppm:.1f} px/mm); uncertainty is larger.", cfg.min_src_ppm_warn)
    tilt = rect["tilt_deg"]
    add("tilt_deg", tilt, tilt <= cfg.max_tilt_block, "block",
        f"Camera is tilted about {tilt:.0f} degrees. Hold the phone parallel to the wall (aim for under {cfg.max_tilt_warn:.0f}).", cfg.max_tilt_block)
    if tilt <= cfg.max_tilt_block and tilt > cfg.max_tilt_warn:
        add("tilt_warn", tilt, False, "warn", f"Tilt of {tilt:.0f} degrees is acceptable but adds error.", cfg.max_tilt_warn)
    sharp = _marker_sharpness(gray, marker["corners"])
    add("sharpness", sharp, sharp >= cfg.min_sharp_block, "block",
        "Photo is blurry. Hold steady, tap to focus on the marker, and use better light.", cfg.min_sharp_block)
    if sharp >= cfg.min_sharp_block and sharp < cfg.min_sharp_warn:
        add("sharpness_warn", sharp, False, "warn", "Slightly soft photo; thin cracks may be under-measured.", cfg.min_sharp_warn)

    if roi_boxes_mm:   # e.g. gauge-card lines: judge the photo only where we will measure
        want = roi_mask(cfg, rect["canvas"].shape, roi_boxes_mm)
    else:
        want = ~exclusion_mask(cfg, rect["canvas"].shape)
    region = rect["valid"] & want
    coverage = float(region.sum()) / float(max(1, want.sum()))
    add("coverage", coverage, coverage >= cfg.min_coverage_block, "block",
        "Too little of the wall around the marker is in the photo. Frame the crack and the marker together.", cfg.min_coverage_block)
    if coverage >= cfg.min_coverage_block and coverage < cfg.min_coverage_warn:
        add("coverage_warn", coverage, False, "warn", "Part of the monitoring window is outside the photo; only the visible part is measured.", cfg.min_coverage_warn)
    vals = rect["canvas"][region]
    if vals.size < 1000:
        return {"gates": gates, "blocked": True, "warned": False, "metrics": {}}
    glare = float((vals >= 245).mean())
    add("glare_fraction", glare, glare <= cfg.max_glare_block, "block",
        f"Glare covers {glare * 100:.0f}% of the wall. Step sideways so light does not reflect; avoid flash.", cfg.max_glare_block)
    if glare <= cfg.max_glare_block and glare > cfg.max_glare_warn:
        add("glare_warn", glare, False, "warn", f"Some glare ({glare * 100:.1f}%); cracks under it are invisible.", cfg.max_glare_warn)
    mean = float(vals.mean())
    contrast = float(np.percentile(vals, 95) - np.percentile(vals, 5))
    add("exposure_mean", mean, cfg.min_mean <= mean <= cfg.max_mean, "block",
        "Too dark: add light (no flash glare)." if mean < cfg.min_mean else "Too bright: reduce exposure or move out of direct light.")
    add("contrast", contrast, contrast >= cfg.min_contrast, "block", "Image is flat or washed out; improve lighting.", cfg.min_contrast)

    blocked = any((not g["pass"]) and g["level"] == "block" for g in gates)
    warned = any((not g["pass"]) and g["level"] == "warn" for g in gates)
    eff = min(ppm, cfg.px_per_mm)
    # blur radius implied by the marker's edge sharpness (empirical: sigma_px ~ 0.39 / sharpness on step edges)
    sigma_px = cfg.blur_k / max(sharp, 1e-3)
    sigma_mm = math.sqrt(max(sigma_px ** 2 - cfg.blur_sigma0_px ** 2, 0.0)) / ppm   # EXCESS blur beyond the optics' own
    unc = math.hypot((1.0 if warned else 0.75) / eff, 0.5 * sigma_mm)
    return {"gates": gates, "blocked": blocked, "warned": warned,
            "metrics": {"src_ppm": ppm, "tilt_deg": tilt, "sharpness": sharp, "blur_sigma_mm": sigma_mm, "glare": glare,
                        "coverage": coverage, "mean": mean, "contrast": contrast, "uncertainty_mm": unc}}


# ----------------------------------------------------------------------------- crack measurement
def _odd(n: int) -> int:
    return n if n % 2 == 1 else n + 1


def deblur_width(w_mm, sigma_mm: float, cfg: Config):
    """Remove blur-induced widening. Blur only inflates cracks that are narrow relative to the blur, so the
    correction fades out as width grows: w' = sqrt(max(w^2 - a*(g*sigma)^2, (0.35 w)^2)), a = exp(-(w/(c*sigma))^2).
    (g, c) are fitted on calibration seeds by scripts/calibrate_blur.py, disjoint from the evaluation seeds."""
    w = np.asarray(w_mm, dtype=np.float64)
    if sigma_mm <= 0 or cfg.blur_gain <= 0:
        return w
    a = np.exp(-((w / (cfg.blur_scale * sigma_mm)) ** 2))
    return np.sqrt(np.maximum(w ** 2 - a * (cfg.blur_gain * sigma_mm) ** 2, (0.35 * w) ** 2))


def segment_and_measure(rect: dict, cfg: Config, roi_boxes_mm: Optional[list] = None,
                        uncertainty_mm: float = 0.2, blur_sigma_mm: float = 0.0) -> dict:
    canvas, valid = rect["canvas"], rect["valid"]
    ppm = cfg.px_per_mm
    g = cv2.GaussianBlur(canvas, (0, 0), 0.8)
    k = _odd(int(round(cfg.closing_mm * ppm)))
    closed = cv2.morphologyEx(g, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    bh = cv2.subtract(closed, g).astype(np.float32)

    search = valid.copy()
    if roi_boxes_mm:
        search &= roi_mask(cfg, canvas.shape, roi_boxes_mm)
    else:
        search &= ~exclusion_mask(cfg, canvas.shape)
    # do not search the border where the closing kernel is unreliable
    m = k // 2 + 2
    inner = np.zeros_like(search)
    inner[m:-m, m:-m] = True
    search &= inner

    vals = bh[search]
    if vals.size < 1000:
        return _empty(canvas.shape, uncertainty_mm)
    med = float(np.median(vals))
    mad = float(np.median(np.abs(vals - med)))
    thr = max(cfg.abs_min_contrast, med + cfg.mad_k * 1.4826 * mad)
    mask = ((bh > thr) & search).astype(np.uint8)

    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n <= 1:
        return _empty(canvas.shape, uncertainty_mm)
    skel_all = skeletonize(mask > 0)
    dt = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    keep = np.zeros(n, bool)
    comp_info = {}
    min_len_px = cfg.min_len_mm * ppm
    sk_labels = labels[skel_all]
    counts = np.bincount(sk_labels, minlength=n)
    for lab in range(1, n):
        L = int(counts[lab])
        if L < min_len_px:
            continue
        sel = (labels == lab) & skel_all
        w = 2.0 * dt[sel] - 1.0
        if L < 3.0 * max(1.0, float(np.median(w))):  # blobs, pits, stains: not elongated
            continue
        keep[lab] = True
        comp_info[lab] = L
    if not keep.any():
        return _empty(canvas.shape, uncertainty_mm)
    final = keep[labels]
    skel = skel_all & final
    # half-maximum refinement: the loose detection threshold inflates widths by ~1 px, so re-threshold
    # each crack at 50% of its own local depth and re-measure on the tighter mask.
    depth = np.where(skel, bh, 0.0).astype(np.float32)
    r = max(3, int(round(2.0 * ppm)))
    peak = cv2.dilate(depth, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
    near = cv2.dilate(final.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    refined = (bh > 0.5 * peak) & near & (peak > 0)
    refined |= skel  # never lose the centreline
    final = refined
    dt = cv2.distanceTransform(final.astype(np.uint8), cv2.DIST_L2, 5)
    widths_px = np.clip(2.0 * dt[skel] - 1.0, 1.0, None)
    raw_mm = widths_px / ppm
    widths_mm = deblur_width(raw_mm, blur_sigma_mm, cfg)
    return {
        "found": True,
        "width_raw_med_mm": float(np.median(raw_mm)),
        "blur_sigma_mm": float(blur_sigma_mm),
        "n_cracks": int(keep.sum()),
        "length_mm": float(skel.sum() / ppm),
        "width_med_mm": float(np.median(widths_mm)),
        "width_p90_mm": float(np.percentile(widths_mm, 90)),
        "width_max_mm": float(np.percentile(widths_mm, 98)),
        "area_mm2": float(final.sum() / (ppm * ppm)),
        "uncertainty_mm": float(uncertainty_mm),
        "mask": final.astype(np.uint8),
        "skeleton": skel.astype(np.uint8),
    }


def _empty(shape, unc):
    return {"found": False, "width_raw_med_mm": 0.0, "blur_sigma_mm": 0.0, "n_cracks": 0, "length_mm": 0.0, "width_med_mm": 0.0, "width_p90_mm": 0.0,
            "width_max_mm": 0.0, "area_mm2": 0.0, "uncertainty_mm": float(unc),
            "mask": np.zeros(shape, np.uint8), "skeleton": np.zeros(shape, np.uint8)}


def severity(meas: dict, cfg: Config) -> str:
    if not meas["found"]:
        return "none"
    w = meas["width_p90_mm"]
    if w >= cfg.sev_urgent_mm:
        return "urgent"
    if w >= cfg.sev_priority_mm:
        return "priority"
    if w >= cfg.sev_watch_mm:
        return "watch"
    return "low"


# ----------------------------------------------------------------------------- comparison
def compare_visits(prev_mask: np.ndarray, prev_meas: dict, new_mask: np.ndarray, new_meas: dict, cfg: Config) -> dict:
    """Both masks live in the same marker-anchored metric frame, so comparison is direct."""
    tol = max(3, int(round(0.7 * cfg.px_per_mm)))
    prev_d = cv2.dilate(prev_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * tol + 1, 2 * tol + 1)))
    new_only = (new_mask > 0) & (prev_d == 0)
    sk_new = skeletonize(new_only)
    new_len_mm = float(sk_new.sum() / cfg.px_per_mm)
    d_w = new_meas["width_p90_mm"] - prev_meas["width_p90_mm"]
    d_len = new_meas["length_mm"] - prev_meas["length_mm"]
    unc = math.hypot(new_meas["uncertainty_mm"], prev_meas["uncertainty_mm"])
    return {"delta_width_mm": float(d_w), "delta_length_mm": float(d_len), "new_crack_length_mm": new_len_mm,
            "uncertainty_mm": float(unc), "significant": bool(d_w > unc or new_len_mm > 15.0)}


# ----------------------------------------------------------------------------- overlay
def draw_overlay(rect: dict, meas: dict, cfg: Config, max_side: int = 1000) -> np.ndarray:
    base = cv2.cvtColor(rect["canvas"], cv2.COLOR_GRAY2BGR)
    base[~rect["valid"]] = (40, 40, 40)
    if meas["found"]:
        crack = meas["mask"] > 0
        base[crack] = (0.35 * base[crack] + 0.65 * np.array([110, 90, 255])).astype(np.uint8)  # BGR coral
        sk = cv2.dilate(meas["skeleton"], np.ones((3, 3), np.uint8)) > 0
        base[sk] = (0, 255, 215)
    s = base.shape[0]
    c = s / 2
    h = cfg.marker_mm / 2 * cfg.px_per_mm
    cv2.rectangle(base, (int(c - h), int(c - h)), (int(c + h), int(c + h)), (255, 180, 60), 3)
    bar = int(50 * cfg.px_per_mm)
    cv2.line(base, (30, s - 40), (30 + bar, s - 40), (0, 0, 0), 8)
    cv2.line(base, (30, s - 40), (30 + bar, s - 40), (215, 255, 63), 4)
    cv2.putText(base, "50 mm", (30, s - 55), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(base, "50 mm", (30, s - 55), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
    scale = max_side / float(s)
    if scale < 1:
        base = cv2.resize(base, (max_side, max_side), interpolation=cv2.INTER_AREA)
    return base


def analyse_image(img_bgr: np.ndarray, cfg: Config, expected_id: Optional[int] = None,
                  roi_boxes_mm: Optional[list] = None) -> dict:
    """One full perception pass. Used by the agent and by evaluation scripts."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY) if img_bgr.ndim == 3 else img_bgr
    marker = detect_marker(gray, cfg, expected_id)
    rect = None
    if marker is not None and not marker.get("wrong_id"):
        rect = rectify(gray, marker["corners"], cfg)
    q = quality_gates(gray, marker, rect, cfg, roi_boxes_mm)
    return {"gray": gray, "marker": marker, "rect": rect, "quality": q}
