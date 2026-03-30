# ui/dialogs.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDoubleSpinBox, 
    QDialogButtonBox, QLabel, QGroupBox, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt
import numpy as np

class NpyParamsDialog(QDialog):
    """
    NPY 纯数据加载时的参数配置对话框。
    支持根据物理深度反推采样率 dt。
    """
    def __init__(self, data_shape, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NPY 导入参数设置 / Import Settings")
        self.resize(400, 350)
        
        # data_shape = (Nt, Nx) -> (Time/Depth points, Trace points)
        self.nt, self.nx = data_shape
        
        # 默认物理常数
        self.c = 0.299792458 # m/ns
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # --- 1. 信息显示区 ---
        info_group = QGroupBox("检测到的数据维度 (Data Shape)")
        info_layout = QFormLayout()
        self.lbl_shape = QLabel(f"{self.nt} (样点/深度) x {self.nx} (道/宽度)")
        self.lbl_shape.setStyleSheet("font-weight: bold; color: #2196F3;")
        info_layout.addRow("矩阵形状:", self.lbl_shape)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # --- 2. 核心参数输入区 ---
        param_group = QGroupBox("物理参数设置 (Physical Parameters)")
        param_layout = QFormLayout()

        # dx (道间距)
        self.spin_dx = QDoubleSpinBox()
        self.spin_dx.setRange(0.001, 1.0)
        self.spin_dx.setDecimals(4)
        self.spin_dx.setSuffix(" m")
        self.spin_dx.setSingleStep(0.001)
        self.spin_dx.setValue(0.025)  # ★ 默认值设为你提到的 0.025m
        param_layout.addRow("道间距 (dx):", self.spin_dx)

        # dt (时间采样间隔) - 这是决定深度的关键
        self.spin_dt = QDoubleSpinBox()
        self.spin_dt.setRange(0.001, 10.0)
        self.spin_dt.setDecimals(6)
        self.spin_dt.setSuffix(" ns")
        self.spin_dt.setSingleStep(0.01)
        self.spin_dt.setValue(0.1)    # 初始默认值
        param_layout.addRow("采样间隔 (dt):", self.spin_dt)
        
        # 背景介电常数 (影响深度显示的标尺)
        self.spin_eps = QDoubleSpinBox()
        self.spin_eps.setRange(1.0, 81.0)
        self.spin_eps.setValue(6.0)   # 默认混凝土/土壤
        param_layout.addRow("背景介电常数 (εr):", self.spin_eps)

        param_group.setLayout(param_layout)
        layout.addWidget(param_group)

        # --- 3. 辅助计算工具 (根据深度算 dt) ---
        calc_group = QGroupBox("辅助工具：根据物理深度估算 dt")
        calc_layout = QFormLayout()
        
        self.spin_target_depth = QDoubleSpinBox()
        self.spin_target_depth.setRange(0.1, 100.0)
        self.spin_target_depth.setSuffix(" m")
        self.spin_target_depth.setValue(0.8) # ★ 默认设为你提到的 0.8m
        
        btn_calc = QPushButton("计算 dt (Apply)")
        btn_calc.clicked.connect(self.calculate_dt_from_depth)
        
        calc_layout.addRow("目标物理深度:", self.spin_target_depth)
        calc_layout.addRow("", btn_calc)
        
        calc_group.setLayout(calc_layout)
        layout.addWidget(calc_group)

        # --- 4. 预览结果 ---
        self.lbl_preview = QLabel("预览: 宽 0.00 m x 深 0.00 m")
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview.setStyleSheet("color: gray;")
        layout.addWidget(self.lbl_preview)

        # 绑定变动事件以更新预览
        self.spin_dx.valueChanged.connect(self.update_preview)
        self.spin_dt.valueChanged.connect(self.update_preview)
        self.spin_eps.valueChanged.connect(self.update_preview)

        # 底部按钮
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # 初始化预览
        self.update_preview()

    def calculate_dt_from_depth(self):
        """
        根据公式反推 dt:
        Depth = (v * t) / 2
        t = (2 * Depth) / v
        dt = t / Nt
        v = c / sqrt(eps)
        """
        depth = self.spin_target_depth.value()
        eps = self.spin_eps.value()
        nt = self.nt
        
        if nt <= 0: return

        v = self.c / np.sqrt(eps)  # m/ns
        total_time_ns = (2 * depth) / v
        dt_calculated = total_time_ns / nt
        
        self.spin_dt.setValue(dt_calculated)
        QMessageBox.information(self, "计算完成", 
                                f"根据深度 {depth}m 和 εr={eps}，\n"
                                f"计算出时间窗口: {total_time_ns:.2f} ns\n"
                                f"采样间隔 dt: {dt_calculated:.6f} ns")

    def update_preview(self):
        dx = self.spin_dx.value()
        dt = self.spin_dt.value()
        eps = self.spin_eps.value()
        
        width = self.nx * dx
        
        v = self.c / np.sqrt(eps)
        total_time = self.nt * dt
        depth = total_time * v / 2.0
        
        self.lbl_preview.setText(f"物理范围预览: 宽 {width:.2f} m x 深 {depth:.2f} m")

    def get_values(self):
        return {
            "dx": self.spin_dx.value(),
            "dt": self.spin_dt.value() * 1e-9, # 转回秒
            "eps_bg": self.spin_eps.value()
        }