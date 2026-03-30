# algorithms/basic.py
import numpy as np
from scipy.signal import hilbert



def mute_top_window(data: np.ndarray, dt: float, mute_ns: float) -> np.ndarray:
    """
    顶部静音：把最开始的一段时间窗置零，用于抑制直达波 / 天线耦合等。

    参数
    ----
    data : ndarray, shape (Nt, Nx)
        B 扫数据 (time × trace)
    dt : float
        采样间隔 (秒)
    mute_ns : float
        顶部静音窗口长度 (纳秒). <=0 则不处理
    """
    if data is None:
        return data
    if mute_ns <= 0 or dt <= 0:
        return data

    nt, nx = data.shape
    n_mute = int(round(mute_ns * 1e-9 / dt))
    if n_mute <= 0:
        return data
    if n_mute > nt:
        n_mute = nt

    out = data.copy()
    out[:n_mute, :] = 0.0
    return out

def dewow(data, dt, window_ns):
    """去低频漂移 (原有逻辑)"""
    if window_ns <= 0: return data
    k = max(3, int(round((window_ns * 1e-9) / dt)))
    if k % 2 == 0: k += 1
    pad = k // 2
    kernel = np.ones(k) / k
    
    out = np.zeros_like(data)
    for j in range(data.shape[1]):
        tr = data[:, j]
        rp = np.pad(tr, (pad, pad), mode='reflect')
        trend = np.convolve(rp, kernel, mode='valid')
        out[:, j] = tr - trend
    return out

# --- 新增模块 ---

def dc_shift_remove(data: np.ndarray, n_head: int) -> np.ndarray:
    """
    DC shift 去直流：利用前 n_head 个样点估计直流偏置
    """
    if n_head <= 0: return data
    nt, nx = data.shape
    n_head = min(n_head, nt)
    
    # 计算每一道的直流分量
    head = data[:n_head, :] # (n_head, Nx)
    offset = head.mean(axis=0, keepdims=True) # (1, Nx)
    
    return data - offset

def estimate_common_t0(data: np.ndarray, dt: float, win_ns: float = 8.0, frac: float = 0.6) -> int:
    """
    粗略公共 time-zero 估计：
    返回 t0_idx (样点索引, int)
    """
    nt, nx = data.shape
    if dt <= 0: return 0

    nwin = int(win_ns * 1e-9 / dt)
    if nwin <= 1 or nwin > nt: nwin = min(nt, 64)

    d0 = np.abs(data[:nwin, :])
    max_per_trace = d0.max(axis=0)

    idx_list = []
    for i in range(nx):
        m = max_per_trace[i]
        if m <= 1e-9: continue
        thr = frac * m
        # 找第一个超过阈值的点
        above = np.where(d0[:, i] >= thr)[0]
        if above.size > 0:
            idx_list.append(int(above[0]))

    if not idx_list: return 0
    return int(np.median(idx_list))

def apply_t0_shift(data: np.ndarray, t0_idx: int) -> np.ndarray:
    """
    根据公共 t0 索引，把整张 B 扫沿时间轴上移
    """
    if t0_idx <= 0: return data
    nt, nx = data.shape
    if t0_idx >= nt: return np.zeros_like(data)

    out = np.zeros_like(data)
    # 上移：数据整体往上提，底部补0
    out[:-t0_idx, :] = data[t0_idx:, :]
    return out

def envelope_detection(data: np.ndarray, axis: int = 0) -> np.ndarray:
    """Hilbert 包络提取"""
    analytic = hilbert(data, axis=axis)
    return np.abs(analytic)

# ----------------- ROI / 静音带（新增） -----------------

def depth_to_sample(depth_m: float, dt: float, eps_bg: float) -> int:
    """把深度(m)换算为样点索引（与深度轴一致：depth = t_ns * v / 2）。"""
    if dt <= 0:
        return 0
    if depth_m <= 0:
        return 0
    eps = eps_bg if eps_bg and eps_bg > 0 else 6.0
    c = 0.299792458  # m/ns
    v = c / np.sqrt(eps)
    t_ns = (2.0 * depth_m) / v
    idx = int(round((t_ns * 1e-9) / dt))
    return max(0, idx)


def sample_to_depth(idx: int, dt: float, eps_bg: float) -> float:
    """样点索引 -> 深度(m)。"""
    if dt <= 0:
        return 0.0
    eps = eps_bg if eps_bg and eps_bg > 0 else 6.0
    c = 0.299792458
    v = c / np.sqrt(eps)
    t_ns = idx * dt * 1e9
    return float(t_ns * v / 2.0)


def mute_band_by_index(data: np.ndarray, i0: int, i1: int, taper: int = 0) -> np.ndarray:
    """在时间轴 [i0:i1] 做静音（置零），可选 taper(过渡样点数) 做平滑边缘。"""
    if data is None:
        return data
    nt, _ = data.shape
    i0 = int(max(0, min(nt, i0)))
    i1 = int(max(0, min(nt, i1)))
    if i1 <= i0:
        return data

    out = data.copy()

    # 纯硬切
    if taper is None or taper <= 0:
        out[i0:i1, :] = 0.0
        return out

    taper = int(max(1, taper))

    # 中间全静音
    core0 = i0 + taper
    core1 = i1 - taper
    if core0 < core1:
        out[core0:core1, :] = 0.0

    # 两侧做 raised-cosine 衰减
    # 左边：从1 -> 0
    left0 = i0
    left1 = min(i0 + taper, i1)
    nL = left1 - left0
    if nL > 0:
        w = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, nL)))  # 1->0
        out[left0:left1, :] *= w[:, None]

    # 右边：从0 -> 1
    right0 = max(i1 - taper, i0)
    right1 = i1
    nR = right1 - right0
    if nR > 0:
        w = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, nR)))  # 0->1
        out[right0:right1, :] *= w[:, None]

    return out


def crop_by_index(data: np.ndarray,
                  t0: int | None = None,
                  t1: int | None = None,
                  x0: int | None = None,
                  x1: int | None = None) -> np.ndarray:
    """按索引裁剪 (time, trace)。None 表示不裁剪该维度。"""
    if data is None:
        return data
    nt, nx = data.shape

    if t0 is None:
        t0 = 0
    if t1 is None:
        t1 = nt
    if x0 is None:
        x0 = 0
    if x1 is None:
        x1 = nx

    t0 = int(max(0, min(nt, t0)))
    t1 = int(max(0, min(nt, t1)))
    x0 = int(max(0, min(nx, x0)))
    x1 = int(max(0, min(nx, x1)))

    if t1 <= t0 or x1 <= x0:
        return data

    return data[t0:t1, x0:x1]
