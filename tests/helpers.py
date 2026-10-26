import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cv2

from hairline import synth
from hairline.blobs import LocalBlobs
from hairline.config import Config
from hairline.service import Service
from hairline.store import SqliteStore

_cache = {}


def render(**kw):
    key = repr(sorted(kw.items()))
    if key not in _cache:
        _cache[key] = synth.render(**kw)
    return _cache[key]


def jpg(img, q=90) -> bytes:
    ok, b = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])
    return b.tobytes()


def make_service(cfg=None):
    cfg = cfg or Config()
    d = tempfile.mkdtemp(prefix="hl_test_")
    cfg.sqlite_path = os.path.join(d, "t.db")
    cfg.blob_dir = os.path.join(d, "blobs")
    return Service(cfg, SqliteStore(cfg.sqlite_path), LocalBlobs(cfg.blob_dir)), cfg


RES = {"id": "resident:aaa", "name": "Asha", "role": "resident"}
ENG = {"id": "engineer:bbb", "name": "Rao", "role": "engineer"}
ENG2 = {"id": "engineer:ccc", "name": "Iyer", "role": "engineer"}
ANON = {"id": "anonymous", "name": "Visitor", "role": "anonymous"}
