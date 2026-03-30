# algorithms/spatial.py
import numpy as np
from scipy.ndimage import median_filter, grey_opening

def remove_background(data, method, win_traces):
    """根据方法选择去背景算法"""
    if method == 'mean':
        # 简单均值去除
        return data - data.mean(axis=1, keepdims=True)
    
    elif method == 'median':
        # 局部中值滤波 (bscan_from_out 原版逻辑)
        k = int(win_traces) | 1
        bg = median_filter(data, size=(1, k), mode='reflect')
        return data - bg
        
    elif method == 'tophat':
        # Tophat 变换
        k = int(win_traces) | 1
        bg = grey_opening(data, size=(1, k))
        return data - bg
        
    return data