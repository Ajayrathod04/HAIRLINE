"""All tunables in one place. Defaults are triage heuristics, NOT engineering standards."""
from __future__ import annotations
import os
from dataclasses import dataclass


def _f(name, default):
    return float(os.environ.get(name, default))


def _i(name, default):
    return int(os.environ.get(name, default))


@dataclass
class Config:
    # --- marker / geometry ---
    aruco_dict: str = "DICT_4X4_50"
    marker_id: int = 7
    marker_mm: float = 50.0          # printed black-square side; VERIFY with a ruler after printing
    marker_border_mm: float = 10.0   # white quiet zone printed around the marker
    window_mm: float = 240.0         # square monitoring window centred on the marker
    px_per_mm: float = 6.0           # resolution of the rectified (metric) canvas
    # --- quality gates (blockers stop measurement; warnings widen uncertainty) ---
    min_src_ppm_block: float = 3.5   # source px per mm
    min_src_ppm_warn: float = 5.0
    max_tilt_block: float = 35.0     # degrees
    max_tilt_warn: float = 18.0
    min_sharp_block: float = 0.12
    min_sharp_warn: float = 0.22
    max_glare_block: float = 0.06    # fraction of window pixels saturated
    max_glare_warn: float = 0.015
    min_mean: float = 45.0
    max_mean: float = 225.0
    min_contrast: float = 18.0
    min_coverage_block: float = 0.40
    min_coverage_warn: float = 0.70
    blur_k: float = 0.39              # sigma_px ~ blur_k / marker-edge sharpness (calibrated on synthetic step edges)
    blur_sigma0_px: float = 0.9       # intrinsic edge blur of a sharp photo; only blur beyond this is corrected
    blur_gain: float = 5.0            # width de-widening strength; 0 disables (fitted by scripts/calibrate_blur.py)
    blur_scale: float = 2.0           # correction fades out once crack width >> blur (fitted by scripts/calibrate_blur.py)
    # --- segmentation ---
    closing_mm: float = 10.0
    min_len_mm: float = 10.0
    mad_k: float = 4.5
    abs_min_contrast: float = 8.0
    # --- triage (configurable defaults; NOT code/standard thresholds) ---
    sev_watch_mm: float = 0.3
    sev_priority_mm: float = 1.0
    sev_urgent_mm: float = 3.0
    growth_escalate_mm: float = 0.2
    max_reshoots: int = 3
    repair_area_ratio: float = 0.15
    repair_len_ratio: float = 0.25
    dup_radius_m: float = 30.0
    # --- runtime ---
    max_upload_mb: int = 12
    max_image_side: int = 2800
    secret_key: str = "dev-only-change-me"
    auth_mode: str = "demo"           # demo | cognito
    store: str = "sqlite"             # sqlite | dynamodb
    sqlite_path: str = "data/hairline.db"
    blob_backend: str = "local"       # local | s3
    blob_dir: str = "data/blobs"
    s3_bucket: str = ""
    dynamo_table: str = ""
    planner: str = "rules"            # rules | bedrock
    bedrock_model_id: str = ""
    aws_region: str = "ap-south-1"
    seed_demo: bool = False
    cognito_region: str = ""
    cognito_pool_id: str = ""
    cognito_client_id: str = ""

    @staticmethod
    def from_env() -> "Config":
        c = Config()
        c.marker_id = _i("HL_MARKER_ID", c.marker_id)
        c.marker_mm = _f("HL_MARKER_MM", c.marker_mm)
        c.secret_key = os.environ.get("HL_SECRET_KEY", c.secret_key)
        c.auth_mode = os.environ.get("HL_AUTH_MODE", c.auth_mode)
        c.store = os.environ.get("HL_STORE", c.store)
        c.sqlite_path = os.environ.get("HL_SQLITE_PATH", c.sqlite_path)
        c.blob_backend = os.environ.get("HL_BLOB_BACKEND", c.blob_backend)
        c.blob_dir = os.environ.get("HL_BLOB_DIR", c.blob_dir)
        c.s3_bucket = os.environ.get("HL_S3_BUCKET", c.s3_bucket)
        c.dynamo_table = os.environ.get("HL_DYNAMO_TABLE", c.dynamo_table)
        c.planner = os.environ.get("HL_PLANNER", c.planner)
        c.bedrock_model_id = os.environ.get("HL_BEDROCK_MODEL_ID", c.bedrock_model_id)
        c.aws_region = os.environ.get("AWS_REGION", c.aws_region)
        c.seed_demo = os.environ.get("HL_SEED_DEMO", "0") == "1"
        c.cognito_region = os.environ.get("HL_COGNITO_REGION", c.cognito_region)
        c.cognito_pool_id = os.environ.get("HL_COGNITO_POOL_ID", c.cognito_pool_id)
        c.cognito_client_id = os.environ.get("HL_COGNITO_CLIENT_ID", c.cognito_client_id)
        c.max_upload_mb = _i("HL_MAX_UPLOAD_MB", c.max_upload_mb)
        return c
