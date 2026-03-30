# algorithms/fk.py
# 频率-波数域 F-K 滤波（带 k 轴平滑窗版本）

from __future__ import annotations
from typing import Optional

import numpy as np


def _cos_taper_1d(x: np.ndarray,
                  x0: float,
                  x1: float,
                  invert: bool = False) -> np.ndarray:
    """
    1D 余弦平滑窗：
    - 对于 |x| < x0:   返回 0
    - 对于 |x| > x1:   返回 1
    - 中间 |x|∈[x0,x1]: 用 0→1 的半个 cos 过渡
    - invert=True 时反转（中间段从 1 过渡到 0）

    这里 x 可以是任意 ndarray，会广播到同形状。
    """
    ax = np.abs(x)

    w = np.ones_like(ax, dtype=np.float64)
    if x1 <= x0:
        # 没法构建过渡区，直接 1
        return w

    inner = ax < x0
    trans = (ax >= x0) & (ax <= x1)
    outer = ax > x1

    # 内部区域：0
    w[inner] = 0.0

    # 过渡区域：0~1 半个 cos
    t = (ax[trans] - x0) / (x1 - x0)  # 0~1
    base = 0.5 * (1.0 - np.cos(np.pi * t))  # 0~1
    w[trans] = base

    # 外部区域：1（已经是 1 了）

    if invert:
        w = 1.0 - w

    return w


def fk_filter_basic(
    data: np.ndarray,
    dt: float,
    dx: float,
    fmin: Optional[float] = None,
    fmax: Optional[float] = None,
    kmin: Optional[float] = None,
    kmax: Optional[float] = None,
    k_taper_ratio: float = 0.7,
) -> np.ndarray:
    """
    简单 2D F-K 滤波 (time × x -> f × kx)：

    参数
    ----
    data : ndarray
        (Nt, Nx) 实数数据，time × trace。
    dt : float
        时间采样间隔 (秒)。
    dx : float
        道间距 / B 扫步进 (米)。
    fmin, fmax : float or None
        频率窗口 (Hz)。None 或 <=0 表示不限制对应一端。
        - |f| < fmin 会被抑制
        - |f| > fmax 会被抑制
    kmin, kmax : float or None
        波数窗口 (1/m)。None 或 <=0 表示不限制对应一端。
        - |k| < kmin 使用平滑高通 (cos taper)
        - |k| > kmax 使用平滑低通 (cos taper)
    k_taper_ratio : float
        用于构造过渡带，0<ratio<1。
        - 例如 k_taper_ratio=0.7 时：
          * 内部截止为 kmin0 = kmin * ratio
          * 完全通过为 kmin1 = kmin
          内部以下为 0，区间 [kmin0,kmin1] 余弦上升到 1。

    返回
    ----
    out : ndarray
        滤波后的数据 (Nt, Nx)，实数。
    """
    if data is None:
        return data
    if dt is None or dt <= 0 or dx is None or dx <= 0:
        # 没有采样信息就不做 F-K
        return data

    nt, nx = data.shape
    if nt < 2 or nx < 2:
        return data

    # 2D FFT：time × x -> f × k
    F = np.fft.fft2(data)

    # 构建频率 / 波数轴
    freqs = np.fft.fftfreq(nt, d=dt)   # Hz, shape (nt,)
    kx = np.fft.fftfreq(nx, d=dx)      # 1/m, shape (nx,)

    # 频率掩膜（硬窗）
    mask_f = np.ones_like(freqs, dtype=np.float64)
    if fmin is not None and fmin > 0:
        mask_f[np.abs(freqs) < fmin] = 0.0
    if fmax is not None and fmax > 0:
        mask_f[np.abs(freqs) > fmax] = 0.0

    # 波数掩膜（带平滑过渡）
    mask_k = np.ones_like(kx, dtype=np.float64)

    # 1）高通：|k| < kmin 区域衰减
    if kmin is not None and kmin > 0:
        # 过渡带 [kmin0, kmin1]，内 0 外 1
        ratio = np.clip(k_taper_ratio, 0.0, 0.99)
        kmin0 = kmin * ratio
        kmin1 = kmin
        mask_k *= _cos_taper_1d(kx, kmin0, kmin1, invert=False)

    # 2）低通：|k| > kmax 区域衰减
    if kmax is not None and kmax > 0 and kmax > (kmin or 0.0):
        # 这里用“外部从 1 过渡到 0”的反向窗
        ratio = np.clip(k_taper_ratio, 0.0, 0.99)
        kmax0 = kmax
        kmax1 = kmax / ratio if ratio > 0 else kmax
        # 上面的设计：|k| <= kmax 为 1，(kmax, kmax1] 余弦下降为 0
        w_lowpass = _cos_taper_1d(kx, kmax0, kmax1, invert=True)
        mask_k *= w_lowpass

    # 将 1D 掩膜扩展为 2D，与 F 形状匹配
    # F 的 shape 是 (nt, nx)，因此：
    mask_2d = mask_f[:, None] * mask_k[None, :]

    # 如果掩膜全是 1，就不用做额外计算了
    if np.all(mask_2d == 1.0):
        return data

    F_filtered = F * mask_2d

    # 逆变换回时空域，只取实部
    out = np.fft.ifft2(F_filtered).real
    return out
