# algorithms/gain.py
import numpy as np


def time_gain(data, tvec, alpha, beta, max_gain=1e4):
    """
    时间增益: g(t) = t_ns^alpha * exp(beta * t_ns)

    参数
    ----
    data : ndarray, shape (Nt, Nx)
        B 扫数据，time × trace。
    tvec : ndarray, shape (Nt,)
        时间轴 (单位: 秒)。
    alpha : float
        幂次增益指数，对 t_ns 生效。
    beta : float
        指数增益系数，单位约为 1/ns。
    max_gain : float, 可选
        为避免数值溢出，限制最大增益因子 (默认 1e4)。
        设为 None 或 <=0 则不裁剪。

    说明
    ----
    - alpha = 0 且 beta = 0 时直接返回原数据；
    - 内部统一用 float64 计算；
    - 对 exp(beta * t_ns) 做了 [-50, 50] 的剪裁，避免溢出；
    - 最后整体增益再裁剪到 [0, max_gain]。
    """
    if data is None or tvec is None:
        return data
    if alpha == 0 and beta == 0:
        return data

    data = np.asarray(data, dtype=np.float64)
    tvec = np.asarray(tvec, dtype=np.float64)

    # 转为 ns，方便理解，也避免 t 很小时幂运算下溢
    t_ns = tvec * 1e9
    # 避免 t=0 时出现 0^alpha 或 log(0)
    t_ns_safe = np.maximum(t_ns, 1e-6)

    g = np.ones_like(t_ns_safe, dtype=np.float64)

    if alpha != 0:
        g *= np.power(t_ns_safe, alpha)

    if beta != 0:
        # 指数项防溢出：exp(±50) 已经非常大/非常小
        expo = beta * t_ns_safe
        expo = np.clip(expo, -50.0, 50.0)
        g *= np.exp(expo)

    # 最大增益限制，避免极端参数时数据直接变成 inf
    if max_gain is not None and max_gain > 0:
        g = np.clip(g, 0.0, max_gain)

    # 扩展到 (Nt, Nx)
    return data * g[:, None]


def agc(data, dt, window_ns, eps=1e-12):
    """
    自动增益控制 (AGC)

    参数
    ----
    data : ndarray, shape (Nt, Nx)
    dt : float
        采样间隔 (秒)。
    window_ns : float
        AGC 窗口长度 (纳秒)。
    eps : float
        防止除以 0 的小常数。

    实现
    ----
    - 对每一道 trace：
      * 在能量 (平方) 上做滑动平均，得到局部 RMS
      * 用原始振幅除以 RMS，达到能量均衡
    """
    if data is None:
        return data
    if window_ns <= 0 or dt is None or dt <= 0:
        return data

    data = np.asarray(data, dtype=np.float64)
    nt, nx = data.shape

    # 窗口长度（样点数）
    k = max(3, int(round((window_ns * 1e-9) / dt)))
    if k > nt:
        k = nt
    if k % 2 == 0:
        k += 1  # 保证奇数，卷积居中

    pad = k // 2
    kernel = np.ones(k, dtype=np.float64) / k

    out = np.empty_like(data, dtype=np.float64)

    for j in range(nx):
        tr = data[:, j]
        # 反射填充，避免边界效应
        rp = np.pad(tr**2, (pad, pad), mode="reflect")
        rms = np.sqrt(np.convolve(rp, kernel, mode="valid"))
        out[:, j] = tr / (rms + eps)

    return out
