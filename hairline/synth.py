"""Synthetic wall photos with KNOWN crack widths: used for tests, demo samples and the synthetic benchmark.

Honest scope: this validates the geometry + measurement pipeline against ground truth. It does NOT
prove accuracy on real walls; scripts/eval_card.py covers real printed-card photos.
"""
from __future__ import annotations
import math
from typing import Optional, Sequence
import cv2
import numpy as np

from .config import Config
from .cvcore import make_marker_image

PG = 8.0                        # plane texture resolution, px per mm
PLANE_MM = (560.0, 440.0)       # plane size (x, y) centred on the marker


def _texture(rng: np.random.Generator, shape) -> np.ndarray:
    h, w = shape
    base = np.full(shape, 172.0, np.float32)
    low = cv2.resize(rng.normal(0, 1, (h // 400 + 2, w // 400 + 2)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    mid = cv2.resize(rng.normal(0, 1, (h // 24 + 2, w // 24 + 2)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    grain = cv2.GaussianBlur(rng.normal(0, 1, shape).astype(np.float32), (0, 0), 0.9)
    tex = base + 9 * low + 5 * mid + 7 * grain
    # pits / stains that must NOT be reported as cracks
    for _ in range(40):
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
        r = float(rng.uniform(0.6, 2.2) * PG)
        cv2.circle(tex, (x, y), max(1, int(r)), float(172 - rng.uniform(15, 45)), -1, cv2.LINE_AA)
    return cv2.GaussianBlur(tex, (0, 0), 0.7)


def crack_path(rng: np.random.Generator, start_mm=(55.0, -95.0), length_mm=130.0, step_mm=4.0):
    pts = [np.array(start_mm, np.float64)]
    ang = math.radians(rng.uniform(80, 100))  # mostly downward
    n = int(length_mm / step_mm)
    for _ in range(n):
        ang += rng.normal(0, 0.22)
        ang = float(np.clip(ang, math.radians(55), math.radians(125)))
        p = pts[-1] + step_mm * np.array([math.cos(ang), math.sin(ang)])
        p[0] = float(np.clip(p[0], 45, 110))
        pts.append(p)
    return np.array(pts)


def _draw_crack(tex: np.ndarray, path_mm: np.ndarray, width_mm: float, depth: float, ox: float, oy: float) -> None:
    line = np.full(tex.shape, 255, np.uint8)
    pix = np.round(np.stack([path_mm[:, 0] * PG + ox, path_mm[:, 1] * PG + oy], axis=1) * 16).astype(np.int32)
    cv2.polylines(line, [pix.reshape(-1, 1, 2)], False, 0, 1, cv2.LINE_8, shift=4)
    dist = cv2.distanceTransform(line, cv2.DIST_L2, 5)
    w_px = width_mm * PG
    alpha = np.clip(w_px / 2.0 - dist + 0.5, 0.0, 1.0)
    tex *= (1.0 - depth * alpha)


def render(seed: int = 0, widths_mm: Sequence[float] = (0.5,), ppm: float = 6.0,
           tilt_deg=(0.0, 0.0), blur: float = 0.0, glare: float = 0.0, gain: float = 1.0,
           noise: float = 2.0, marker: bool = True, size=(2400, 1800), path_seed: Optional[int] = None,
           aim_mm=(0.0, 0.0), roll_deg: float = 0.0, cfg: Optional[Config] = None, depth: float = 0.55,
           marker_id: Optional[int] = None):
    cfg = cfg or Config()
    rng = np.random.default_rng(seed)
    W, Hh = int(PLANE_MM[0] * PG), int(PLANE_MM[1] * PG)
    ox, oy = W / 2.0, Hh / 2.0
    tex = _texture(rng, (Hh, W))
    prng = np.random.default_rng(seed if path_seed is None else path_seed)
    paths = []
    for i, w in enumerate(widths_mm):
        start = (55.0 + 12 * i, -95.0)
        path = crack_path(prng, start_mm=start)
        _draw_crack(tex, path, float(w), depth, ox, oy)
        paths.append(path)
    if marker:
        m = make_marker_image(cfg, marker_id=marker_id, px_per_mm=PG).astype(np.float32)
        mh, mw = m.shape
        y0, x0 = int(oy - mh / 2), int(ox - mw / 2)
        tex[y0:y0 + mh, x0:x0 + mw] = m * 0.93 + 8  # printed paper, slightly off-white
    # camera
    D = 400.0
    f = ppm * D
    a, b = math.radians(tilt_deg[0]), math.radians(tilt_deg[1])
    Rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    Ry = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
    r = math.radians(roll_deg)
    Rz = np.array([[math.cos(r), -math.sin(r), 0], [math.sin(r), math.cos(r), 0], [0, 0, 1]])
    R = Rz @ Rx @ Ry
    P0 = np.array([aim_mm[0], aim_mm[1], 0.0])
    t = -R @ P0 + np.array([0, 0, D])
    K = np.array([[f, 0, size[0] / 2.0], [0, f, size[1] / 2.0], [0, 0, 1]])
    Hmm = K @ np.column_stack([R[:, 0], R[:, 1], t])
    T = np.array([[1 / PG, 0, -ox / PG], [0, 1 / PG, -oy / PG], [0, 0, 1]])
    Hpx = Hmm @ T
    ratio = PG / max(ppm, 0.5)
    pre = tex if ratio <= 1.2 else cv2.GaussianBlur(tex, (0, 0), 0.45 * ratio)
    img = cv2.warpPerspective(pre, Hpx, size, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    img = img * gain
    if glare > 0:
        yy, xx = np.mgrid[0:size[1], 0:size[0]]
        gx, gy = size[0] * 0.80, size[1] * 0.32
        sig = size[0] * (0.03 + 0.10 * glare)
        img = img + 480.0 * np.exp(-(((xx - gx) ** 2 + (yy - gy) ** 2) / (2 * sig ** 2)))
    if blur > 0:
        img = cv2.GaussianBlur(img, (0, 0), blur)
    if noise > 0:
        img = img + np.random.default_rng(seed + 1).normal(0, noise, img.shape)
    img = np.clip(img, 0, 255).astype(np.uint8)
    bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    truth = {"widths_mm": [float(w) for w in widths_mm], "paths_mm": [p.tolist() for p in paths],
             "ppm": ppm, "tilt_deg": list(tilt_deg), "blur": blur, "glare": glare}
    return bgr, truth
