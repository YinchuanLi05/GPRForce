# io_module/loader.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import h5py
import numpy as np

from core.data_model import GPRData
from .parse_in import parse_in_file


def _read_first_existing_dataset(group, names):
    """在 group 中按顺序查找第一个存在的数据集"""
    for n in names:
        if n in group:
            return group[n][()]
    return None


def _scalar_item(x: Any) -> Any:
    """把 numpy 标量/0-d array 解包成 Python 标量"""
    try:
        if isinstance(x, np.ndarray) and x.shape == ():
            return x.item()
    except Exception:
        pass
    return x


def _safe_float(x: Any, default: float) -> float:
    """None/空/异常时回退 default。支持 numpy 标量、字符串数字等。"""
    x = _scalar_item(x)
    if x is None:
        return float(default)
    try:
        return float(x)
    except Exception:
        return float(default)


def _safe_int(x: Any, default: int) -> int:
    x = _scalar_item(x)
    if x is None:
        return int(default)
    try:
        return int(x)
    except Exception:
        return int(default)


def load_out_file(filepath: str | Path) -> GPRData:
    """
    加载 gprMax .out 文件，并尽可能根据同名 .in 填充物理参数。

    - 读取 /rxs/rx1/{Ez,Ey,Ex} 中的一个作为主数据；
    - 将数据 reshape 成 (Nt, Nx)，以列为 trace；
    - 读取 dt；
    - 若存在同名 .in，调用 parse_in_file 解析：
      * eps_bg, trace_step, fc, dx_dy_dz, domain 等
      * 保存到 gpr_data.in_info, gpr_data.in_path
    """
    filepath = Path(filepath)
    g = GPRData()
    g.filename = str(filepath)

    # -------- 读取 .out(HDF5) --------
    with h5py.File(filepath, "r") as f:
        # 尝试不同组件：Ez -> Ey -> Ex
        rxs = f.get("rxs")
        if rxs is None or "rx1" not in rxs:
            raise RuntimeError("HDF5 中未找到 /rxs/rx1，无法读取接收数据。")

        rx1 = rxs["rx1"]
        arr = _read_first_existing_dataset(rx1, ["Ez", "Ey", "Ex"])
        if arr is None:
            raise RuntimeError("在 /rxs/rx1 中找不到 Ez/Ey/Ex 数据集。")

        arr = np.asarray(arr, dtype=float)

        # 保证形状为 (Nt, Nx)
        if arr.ndim == 1:
            data = arr.reshape(-1, 1)
        elif arr.ndim == 2:
            # gprMax 默认 (Nt, Nx)
            data = arr
        else:
            # 其它情况展平成 (Nt, Nx)
            nt = arr.shape[0]
            data = arr.reshape(nt, -1, order="F")

        g.raw_data = data
        g.processed_data = np.array(data, copy=True, dtype=float)

        # dt 可以在 /input/dt 或文件属性中找到
        dt = None
        if "input" in f and "dt" in f["input"]:
            dt = float(f["input"]["dt"][()])
        elif "dt" in f.attrs:
            dt = float(f.attrs["dt"])
        if dt is None:
            raise RuntimeError("在 .out 文件中未找到 dt。")
        g.dt = dt

        # time_window 可选
        if "time_window" in f.attrs:
            g.time_window = float(f.attrs["time_window"])

    # -------- 查找并解析同名 .in --------
    in_path = filepath.with_suffix(".in")
    if in_path.exists():
        try:
            info = parse_in_file(in_path)
            g.in_info = info
            g.in_path = info.get("in_path", str(in_path))

            # 背景 eps
            if "eps_bg" in info and info["eps_bg"] is not None:
                g.eps_bg = float(info["eps_bg"])

            # trace_step / dx
            trace_step = info.get("trace_step", None)
            if trace_step is not None:
                g.dx = float(trace_step)
            elif "dx_dy_dz" in info and info["dx_dy_dz"] is not None:
                g.dx = float(info["dx_dy_dz"][0])

            # fc
            if "waveform" in info and isinstance(info["waveform"], dict) and "fc" in info["waveform"]:
                if info["waveform"]["fc"] is not None:
                    g.fc = float(info["waveform"]["fc"])

            # 网格 & 域
            if "dx_dy_dz" in info and info["dx_dy_dz"] is not None:
                g.grid_dims = tuple(info["dx_dy_dz"])
            if "domain" in info and info["domain"] is not None:
                g.domain = tuple(info["domain"])

            print(
                f"已解析 {in_path.name}: 背景εr={g.eps_bg:.2f}, "
                f"dx={g.dx:.4f} m, fc={g.fc/1e6 if g.fc else 0:.1f} MHz"
            )
        except Exception as e:
            print(f"解析 .in 文件 {in_path} 失败，使用默认物理参数。错误: {e}")
    else:
        print("未找到同名 .in 文件，使用默认物理参数。")

    return g


def load_npy_file(filepath: str | Path) -> GPRData:
    """
    加载 .npy 文件。

    支持两种格式：
    A) dict 格式（推荐，GPR_Studio 导出）：{'data': (Nt,Nx), 'dt':..., 'dx':..., 'eps_bg':..., 'roi':...}
    B) 纯数组格式：直接认为是 (Nt,Nx) 数据，dt/dx 等用默认值
    """
    filepath = Path(filepath)
    g = GPRData()
    g.filename = str(filepath)

    try:
        content = np.load(str(filepath), allow_pickle=True)

        # 情况 A: 0-d object array 包一个 dict
        if isinstance(content, np.ndarray) and content.ndim == 0:
            item = content.item()
            if isinstance(item, dict):
                data_dict: Dict[str, Any] = item

                if "data" not in data_dict:
                    raise ValueError("NPY 字典中未找到 'data' 字段")

                raw = np.asarray(data_dict["data"], dtype=float)

                # 元数据：允许缺失或为 None
                g.dt = _safe_float(data_dict.get("dt", None), 1e-10)
                g.dx = _safe_float(data_dict.get("dx", None), 0.02)
                g.eps_bg = _safe_float(data_dict.get("eps_bg", None), 6.0)
                g.time_window = _safe_float(data_dict.get("time_window", None), 0.0)

                fc = data_dict.get("fc", None)
                fc_f = _safe_float(fc, 0.0)
                g.fc = fc_f if fc_f > 0 else None

                # ROI：完全可选，保持原样放进 g.roi（不强依赖 data_model 加字段）
                roi = data_dict.get("roi", None)
                if roi is not None:
                    try:
                        setattr(g, "roi", roi)
                    except Exception:
                        pass

            else:
                # 0-d 但不是 dict，兜底当数组
                raw = np.asarray(item, dtype=float)

        # 情况 B: 纯二维数组
        else:
            raw = np.asarray(content, dtype=float)
            # 默认值（或留给 UI 让用户补）
            g.dt = 1e-10
            g.dx = 0.02
            g.eps_bg = 6.0
            g.time_window = 0.0
            g.fc = None
            print(f"警告: 加载了纯数据 NPY，使用默认 dt={g.dt}, dx={g.dx}")

        if raw.ndim != 2:
            raise ValueError(f"数据维度不正确: {raw.ndim}D，需要 2D 矩阵")

        g.raw_data = raw
        g.processed_data = np.array(raw, copy=True, dtype=float)

        # 可选：寻找同名 .in 覆盖默认
        in_path = filepath.with_suffix(".in")
        if in_path.exists():
            try:
                info = parse_in_file(in_path)
                g.in_info = info
                g.in_path = str(in_path)
                if "eps_bg" in info and info["eps_bg"] is not None:
                    g.eps_bg = float(info["eps_bg"])
                if "trace_step" in info and info["trace_step"] is not None:
                    g.dx = float(info["trace_step"])
            except Exception:
                pass

        return g

    except Exception as e:
        raise RuntimeError(f"加载 .npy 失败: {e}")


import io
import json
import zipfile

def load_repro_package(zip_path: str | Path) -> GPRData:
    """
    加载由 export_reproducible_package 导出的 .zip 可复现包。
    优先读：
      - data/raw.npy 作为 raw_data
      - data/processed.npy 作为 processed_data
    并恢复 meta.json 中的 dt/dx/eps/time_window/fc。
    params.json 会存到 g.repro_params 供 UI/脚本使用。
    """
    zip_path = Path(zip_path)
    g = GPRData()
    g.filename = str(zip_path)

    def _load_npy_from_zip(z: zipfile.ZipFile, name: str):
        with z.open(name, "r") as f:
            b = f.read()
        arr = np.load(io.BytesIO(b), allow_pickle=True)
        # arr is ndarray saved directly
        return np.asarray(arr, dtype=float)

    with zipfile.ZipFile(zip_path, "r") as z:
        # meta
        meta = {}
        if "meta.json" in z.namelist():
            meta = json.loads(z.read("meta.json").decode("utf-8"))

        params = {}
        if "params.json" in z.namelist():
            params = json.loads(z.read("params.json").decode("utf-8"))

        in_info = None
        if "in_info.json" in z.namelist():
            try:
                in_info = json.loads(z.read("in_info.json").decode("utf-8"))
            except Exception:
                in_info = None

        names = set(z.namelist())
        raw = None
        if "data/raw.npy" in names:
            raw = _load_npy_from_zip(z, "data/raw.npy")
        processed = None
        if "data/processed.npy" in names:
            processed = _load_npy_from_zip(z, "data/processed.npy")

        # fallback
        if processed is None and raw is None:
            raise RuntimeError("可复现包中未找到 data/raw.npy 或 data/processed.npy")

        if raw is None:
            raw = processed.copy()
        if processed is None:
            processed = raw.copy()

        g.raw_data = raw
        g.processed_data = processed

        # restore physical meta
        g.dt = _safe_float(meta.get("dt", None), 1e-10)
        g.dx = _safe_float(meta.get("dx", None), 0.02)
        g.eps_bg = _safe_float(meta.get("eps_bg", None), 6.0)
        g.time_window = _safe_float(meta.get("time_window", None), 0.0)
        fc_f = _safe_float(meta.get("fc", None), 0.0)
        g.fc = fc_f if fc_f > 0 else None

        if in_info is not None:
            g.in_info = in_info
        else:
            # 放一个非 None 的标记，避免 UI 当成纯数据反复弹对话框
            g.in_info = {"_repro_pack": True}

        try:
            setattr(g, "repro_params", params)
        except Exception:
            pass

        # optional: keep origin filename
        try:
            if meta.get("source_filename"):
                setattr(g, "source_filename", meta.get("source_filename"))
        except Exception:
            pass

    return g
