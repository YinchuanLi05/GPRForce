# algorithms/filters.py
import numpy as np
from scipy.signal import savgol_filter, firwin, filtfilt, butter

def savgol_smooth_x(data, window_len):
    """横向平滑 (Savitzky-Golay)"""
    w = int(window_len)
    if w < 3: return data
    if w % 2 == 0: w += 1
    return savgol_filter(data, window_length=w, polyorder=2, axis=1, mode='mirror')

def lowpass_filter(data, dt, cutoff_freq_hz):
    """低通滤波 (FIR)"""
    if cutoff_freq_hz <= 0: return data
    nyq = 0.5 / dt
    norm_cutoff = cutoff_freq_hz / nyq
    if norm_cutoff >= 1.0 or norm_cutoff <= 0: return data
    
    b = firwin(129, norm_cutoff, window='hamming')
    return filtfilt(b, [1.0], data, axis=0)

# --- 新增模块 ---

def bandpass_filter(data: np.ndarray, dt: float, f_low: float, f_high: float, order: int = 4) -> np.ndarray:
    """
    Butterworth 带通滤波 (零相位 filtfilt)
    f_low, f_high 单位: Hz
    """
    if dt <= 0: return data
    nyq = 0.5 / dt
    
    low = f_low / nyq if f_low > 0 else 0.0
    high = f_high / nyq if f_high > 0 else 0.0
    
    # 检查参数合理性
    if low <= 0.0 and (high <= 0.0 or high >= 1.0):
        return data # 全通
        
    if high >= 1.0: high = 0.999 # 防止超出 Nyquist
    
    # 确定滤波器类型
    if low > 0.0 and high > 0.0 and low < high:
        btype = 'bandpass'
        Wn = [low, high]
    elif low > 0.0 and (high <= 0.0 or high >= 1.0):
        btype = 'highpass'
        Wn = low
    elif high > 0.0:
        btype = 'lowpass'
        Wn = high
    else:
        return data

    b, a = butter(order, Wn, btype=btype)
    return filtfilt(b, a, data, axis=0)