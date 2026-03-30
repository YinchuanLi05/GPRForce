# io_module/exporter.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import scipy.io as sio

from core.data_model import GPRData


def _safe_float(x: Any, default: float) -> float:
    if x is None:
        return float(default)
    try:
        # numpy 标量
        if isinstance(x, np.ndarray) and x.shape == ():
            x = x.item()
        return float(x)
    except Exception:
        return float(default)


def export_to_npy(data: GPRData, filepath: str | Path):
    """
    导出处理后的数据为 NumPy (.npy)。

    保存为 dict（便于二次加载不丢物理参数）：
      - data: processed_data (Nt, Nx)
      - dt, dx, eps_bg, time_window, fc
      - roi（可选）：若 data 上挂了 data.roi，则一并保存
    """
    if data is None or data.processed_data is None:
        raise ValueError("No processed data to export")

    filepath = Path(filepath)

    payload: Dict[str, Any] = {
        "data": np.asarray(data.processed_data, dtype=np.float32),
        "dt": _safe_float(getattr(data, "dt", None), 1e-10),
        "dx": _safe_float(getattr(data, "dx", None), 0.02),
        "eps_bg": _safe_float(getattr(data, "eps_bg", None), 6.0),
        "time_window": _safe_float(getattr(data, "time_window", None), 0.0),
        "fc": _safe_float(getattr(data, "fc", None), 0.0),
        "note": "Exported from GPR_Studio",
    }

    # ROI 可选（不会强依赖 data_model 的字段）
    roi = getattr(data, "roi", None)
    if roi is not None:
        payload["roi"] = roi

    np.save(str(filepath), payload)


def export_to_mat(data: GPRData, filepath: str | Path):
    """
    导出处理后的数据为 MATLAB (.mat)。
    """
    if data is None or data.processed_data is None:
        raise ValueError("No processed data to export")

    filepath = Path(filepath)

    mat_dict: Dict[str, Any] = {
        "data": np.asarray(data.processed_data, dtype=np.float32),
        "dt": _safe_float(getattr(data, "dt", None), 1e-10),
        "dx": _safe_float(getattr(data, "dx", None), 0.02),
        "eps_bg": _safe_float(getattr(data, "eps_bg", None), 6.0),
        "time_window": _safe_float(getattr(data, "time_window", None), 0.0),
        "fc": _safe_float(getattr(data, "fc", None), 0.0),
    }

    roi = getattr(data, "roi", None)
    if roi is not None:
        mat_dict["roi"] = roi

    sio.savemat(str(filepath), mat_dict)


def export_image(canvas, filepath: str | Path):
    """
    导出当前画布为图片 (png/jpg/pdf)。
    canvas: matplotlib FigureCanvas 对象
    """
    if canvas is None or getattr(canvas, "figure", None) is None:
        raise ValueError("画布无效")

    filepath = Path(filepath)
    canvas.figure.savefig(str(filepath), dpi=300, bbox_inches="tight")


import io
import json
import hashlib
import datetime

def _sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()

def export_reproducible_package(
    gpr: GPRData,
    filepath: str | Path,
    *,
    params: Optional[Dict[str, Any]] = None,
    raw_data: Optional[np.ndarray] = None,
    heavy_data: Optional[np.ndarray] = None,
    canvas=None,
    extra_meta: Optional[Dict[str, Any]] = None,
):
    """
    导出“可复现包” (zip)：
      - meta.json: 物理参数、形状、来源等
      - params.json: 当前处理参数（UI 参数快照）
      - data/raw.npy: 原始数据 (可选)
      - data/heavy.npy: 重处理后的中间结果（可选，便于比对）
      - data/processed.npy: 最终显示/导出的 processed_data
      - preview.png: 当前画布截图（可选）
      - in_info.json: 解析得到的 .in 信息（若存在）

    目标：拿到 zip 就能在别的机器上“复现/追溯”：
      - 直接查看 processed.npy
      - 读取 params/meta 重新跑同样处理链
    """
    if gpr is None or gpr.processed_data is None:
        raise ValueError("无处理数据可导出可复现包")

    filepath = Path(filepath)
    if filepath.suffix.lower() != ".zip":
        filepath = filepath.with_suffix(".zip")

    # ---- meta ----
    meta: Dict[str, Any] = {
        "app": "GPRForge",
        "package_version": 1,
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "source_filename": getattr(gpr, "filename", None),
        "dt": _safe_float(getattr(gpr, "dt", None), 1e-10),
        "dx": _safe_float(getattr(gpr, "dx", None), 0.02),
        "eps_bg": _safe_float(getattr(gpr, "eps_bg", None), 6.0),
        "time_window": _safe_float(getattr(gpr, "time_window", None), 0.0),
        "fc": _safe_float(getattr(gpr, "fc", None), 0.0),
        "shape_processed": list(np.asarray(gpr.processed_data).shape),
    }

    if raw_data is not None:
        meta["shape_raw"] = list(np.asarray(raw_data).shape)
    if heavy_data is not None:
        meta["shape_heavy"] = list(np.asarray(heavy_data).shape)

    if extra_meta:
        meta.update(extra_meta)

    # ---- in_info（可选）----
    in_info = getattr(gpr, "in_info", None)
    in_path = getattr(gpr, "in_path", None)
    if in_path:
        meta["in_path"] = in_path

    # ---- params（可选）----
    params_dict: Dict[str, Any] = params.copy() if isinstance(params, dict) else {}

    # ---- 组织 zip 内容 ----
    manifest: Dict[str, Any] = {"files": []}

    def _writestr(z: zipfile.ZipFile, arcname: str, b: bytes):
        z.writestr(arcname, b)
        manifest["files"].append({"path": arcname, "sha256": _sha256_bytes(b), "size": len(b)})

    import zipfile
    with zipfile.ZipFile(filepath, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # meta.json / params.json
        meta_b = json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8")
        params_b = json.dumps(params_dict, ensure_ascii=False, indent=2).encode("utf-8")
        _writestr(z, "meta.json", meta_b)
        _writestr(z, "params.json", params_b)

        # in_info.json
        if in_info is not None:
            in_b = json.dumps(in_info, ensure_ascii=False, indent=2).encode("utf-8")
            _writestr(z, "in_info.json", in_b)

        # data arrays as .npy bytes
        def _npy_bytes(arr: np.ndarray) -> bytes:
            buf = io.BytesIO()
            np.save(buf, np.asarray(arr, dtype=np.float32))
            return buf.getvalue()

        if raw_data is not None:
            _writestr(z, "data/raw.npy", _npy_bytes(raw_data))
        if heavy_data is not None:
            _writestr(z, "data/heavy.npy", _npy_bytes(heavy_data))

        _writestr(z, "data/processed.npy", _npy_bytes(gpr.processed_data))

        # preview image
        if canvas is not None and getattr(canvas, "figure", None) is not None:
            img_buf = io.BytesIO()
            canvas.figure.savefig(img_buf, format="png", dpi=200, bbox_inches="tight")
            _writestr(z, "preview.png", img_buf.getvalue())

        # manifest
        mani_b = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        z.writestr("MANIFEST.json", mani_b)
