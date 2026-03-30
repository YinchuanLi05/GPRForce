# core/worker.py
from PyQt6.QtCore import QObject, pyqtSignal, QThread
import numpy as np
import traceback

# 导入算法库
import algorithms.basic as algo_basic
import algorithms.spatial as algo_spatial
import algorithms.gain as algo_gain
import algorithms.filters as algo_filters
import algorithms.fk as algo_fk

class PipelineWorker(QObject):
    """
    在后台线程运行的 GPR 处理工兵。
    负责执行耗时的 'Heavy Pipeline'。
    """
    # 信号：处理完成，返回处理后的数据矩阵
    sig_finished = pyqtSignal(np.ndarray)
    # 信号：处理出错，返回错误信息
    sig_error = pyqtSignal(str)

    def __init__(self, raw_data, dt, dx, params):
        super().__init__()
        # 深拷贝数据，避免多线程竞争修改原始数据
        self.raw_data = raw_data.astype(np.float64, copy=True)
        self.dt = dt
        self.dx = dx
        self.params = params

    def run(self):
        """执行处理流水线"""
        try:
            data = self.raw_data
            p = self.params
            dt = self.dt

            # 1. DC 去直流
            if p["dc_ns"] > 0:
                n_head = int(p["dc_ns"] * 1e-9 / dt)
                if n_head > 0:
                    data = algo_basic.dc_shift_remove(data, n_head)

            # 2. Time-zero
            if p["t0_auto"]:
                # 注意：这里如果 t0 失败可能会抛异常，会被 except 捕获
                t0_idx = algo_basic.estimate_common_t0(data, dt)
                data = algo_basic.apply_t0_shift(data, t0_idx)

            # 3. Dewow
            # 3. Dewow
            if p["dewow"]:
                win_ns = float(p.get("dewow_win_ns", 6.0))
                if win_ns > 0:
                    data = algo_basic.dewow(data, dt, win_ns)


            # 4. 顶部静音
            if p.get("mute_ns", 0.0) > 0:
                data = algo_basic.mute_top_window(data, dt, p["mute_ns"])

            # 5. 空间/背景 (耗时操作)
            if p["bg_method"] != "none" and p["bg_win"] > 0:
                data = algo_spatial.remove_background(
                    data,
                    method=p["bg_method"],
                    win_traces=p["bg_win"],
                )

            # 6. 时间增益
            if p["gain_on"]:
                tvec = np.arange(data.shape[0]) * dt
                data = algo_gain.time_gain(
                    data,
                    tvec,
                    p["gain_alpha"],
                    p["gain_beta"],
                )

            # 7. AGC
            if p["agc_win"] > 0:
                data = algo_gain.agc(data, dt, p["agc_win"])

            # 8. 带通滤波
            if p["use_bp"]:
                data = algo_filters.bandpass_filter(
                    data, dt, p["bp_low"], p["bp_high"]
                )

            # 9. F-K 滤波 (最耗时操作)
            if p.get("fk_enabled", False) and self.dx > 0:
                fmin = p.get("fk_fmin_mhz", 0.0) * 1e6
                fmax = p.get("fk_fmax_mhz", 0.0) * 1e6
                kmin = p.get("fk_kmin", 0.0)
                kmax = p.get("fk_kmax", 0.0)
                
                # 简单参数检查
                fnyq = 0.5 / dt
                valid_f = not (fmin and fmax and fmin >= fmax)
                valid_k = not (kmin and kmax and kmin >= kmax)
                
                if valid_f and valid_k:
                    # 再次清理一下范围
                    if fmax > fnyq: fmax = fnyq
                    data = algo_fk.fk_filter_basic(
                        data, dt, self.dx,
                        fmin=fmin if fmin > 0 else None,
                        fmax=fmax if fmax > 0 else None,
                        kmin=kmin if kmin > 0 else None,
                        kmax=kmax if kmax > 0 else None,
                    )

            # 10. 横向 SavGol 平滑
            if p["smooth_x"] > 0:
                data = algo_filters.savgol_smooth_x(data, p["smooth_x"])

            # 全部完成，发送结果
            self.sig_finished.emit(data)

        except Exception as e:
            # 捕获所有错误并发送给主线程显示
            err_msg = f"{str(e)}\n{traceback.format_exc()}"
            self.sig_error.emit(err_msg)