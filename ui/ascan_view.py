# ui/ascan_view.py
import numpy as np
from PyQt6.QtWidgets import QDialog, QVBoxLayout
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

class AScanViewDialog(QDialog):
    def __init__(self, trace_data, dt, trace_idx, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"A-Scan Analysis - Trace #{trace_idx}")
        self.resize(800, 600)
        
        # 数据准备
        self.trace = trace_data
        self.dt = dt
        self.time = np.arange(len(trace_data)) * dt * 1e9  # ns
        
        # 布局
        layout = QVBoxLayout(self)
        
        # 画布
        self.fig = Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        
        self.plot_graphs()

    def plot_graphs(self):
        # 1. 波形图 (Time Domain)
        ax1 = self.fig.add_subplot(211)
        ax1.plot(self.time, self.trace, 'b-', linewidth=1.0)
        ax1.set_title("Time Domain (A-Scan)")
        ax1.set_xlabel("Time (ns)")
        ax1.set_ylabel("Amplitude")
        ax1.grid(True, alpha=0.5)
        ax1.margins(x=0)

        # 2. 频谱图 (Frequency Domain)
        ax2 = self.fig.add_subplot(212)
        
        n = len(self.trace)
        # 简单的 FFT
        fft_val = np.fft.fft(self.trace)
        fft_freq = np.fft.fftfreq(n, d=self.dt)
        
        # 只取正半轴
        mask = fft_freq > 0
        freqs = fft_freq[mask] / 1e6  # MHz
        amps = np.abs(fft_val[mask])
        
        ax2.plot(freqs, amps, 'r-', linewidth=1.0)
        ax2.set_title("Frequency Spectrum")
        ax2.set_xlabel("Frequency (MHz)")
        ax2.set_ylabel("Magnitude")
        ax2.grid(True, alpha=0.5)
        
        # 限制一下显示范围 (通常 GPR 都在 5000MHz 以内)
        ax2.set_xlim(0, min(5000, freqs.max())) 
        
        self.fig.tight_layout()
        self.canvas.draw()