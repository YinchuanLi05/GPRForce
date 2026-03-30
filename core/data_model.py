# core/data_model.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

import numpy as np


@dataclass
class GPRData:
    """
    程序内部统一使用的 GPR 数据模型。

    主要字段：
    - raw_data       : 原始 B 扫 (Nt, Nx)
    - processed_data : 处理后的 B 扫 (Nt, Nx)
    - dt             : 采样间隔 (s)
    - dx             : 道间距 / trace step (m)
    - time_window    : 总时间窗 (s)
    - eps_bg         : 背景介电常数 (用于深度换算)
    - fc             : 中心频率 (Hz)
    - grid_dims      : (dx, dy, dz) 网格步长 (m)
    - domain         : (X, Y, Z) 计算域大小 (m)
    - filename       : .out 文件路径
    - in_path        : 对应 .in 文件路径（若有）
    - in_info        : 解析 .in 得到的完整信息字典

    - gt_mask / gt_eps / gt_x / gt_z : 几何真值视图使用的缓存
    """

    raw_data: Optional[np.ndarray] = None
    processed_data: Optional[np.ndarray] = None

    dt: float = 1e-10
    time_window: Optional[float] = None

    dx: float = 0.02
    eps_bg: float = 6.0
    fc: Optional[float] = None

    grid_dims: Optional[Tuple[float, float, float]] = None
    domain: Optional[Tuple[float, float, float]] = None

    filename: Optional[str] = None       # .out 路径
    in_path: Optional[str] = None        # .in 路径（若存在）
    in_info: Optional[Dict[str, Any]] = None

    # 几何真值缓存
    gt_mask: Optional[np.ndarray] = None
    gt_eps: Optional[np.ndarray] = None
    gt_x: Optional[np.ndarray] = None
    gt_z: Optional[np.ndarray] = None

    def __post_init__(self):
        if self.raw_data is not None and self.processed_data is None:
            self.processed_data = np.array(self.raw_data, copy=True, dtype=float)

    # ---- 坐标轴 ----
    @property
    def time_axis(self) -> Optional[np.ndarray]:
        if self.raw_data is None:
            return None
        nt = self.raw_data.shape[0]
        return np.arange(nt) * self.dt

    @property
    def depth_axis(self) -> Optional[np.ndarray]:
        """基于 eps_bg 和 dt 估算深度轴（单位 m）"""
        t = self.time_axis
        if t is None:
            return None
        eps = self.eps_bg if self.eps_bg > 0 else 6.0
        v = 0.299792458 / np.sqrt(eps)  # m/ns
        t_ns = t * 1e9
        return t_ns * v / 2.0

    # ---- 实用方法 ----
    def reset_processing(self):
        """把 processed_data 重置成 raw_data 的拷贝"""
        if self.raw_data is not None:
            self.processed_data = np.array(self.raw_data, copy=True, dtype=float)

    @property
    def out_path(self) -> Optional[Path]:
        return Path(self.filename) if self.filename else None

    @property
    def in_path_obj(self) -> Optional[Path]:
        return Path(self.in_path) if self.in_path else None
