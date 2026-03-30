# ui/controls.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QCheckBox,
    QLabel, QComboBox, QDoubleSpinBox, QSpinBox, QHBoxLayout,
    QPushButton
)
from PyQt6.QtCore import pyqtSignal, Qt
from core.i18n import I18n


class ControlPanel(QWidget):
    sig_params_changed = pyqtSignal()
    # 2D 画笔：启用 / 清除 信号
    sig_brush_toggled = pyqtSignal(bool)
    sig_brush_cleared = pyqtSignal()


    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # 清理旧布局（供语言切换时重建 UI）
        if self.layout():
            QWidget().setLayout(self.layout())
        self.layout = QVBoxLayout(self)

        # 1. 基础 (DC, T0, Dewow)
        self.add_group_basic()
        # 1.5 ROI（裁剪/静音）
        self.add_group_roi()
        # 2. 空间/去背景
        self.add_group_spatial()
        # 3. 增益
        self.add_group_gain()
        # 4. 一维滤波 (Bandpass + 平滑)
        self.add_group_filter()
        # 5. F-K 滤波
        self.add_group_fk()
        # 6. 显示设置
        self.add_group_display()

        self.layout.addStretch()

    # ----------------- 小工具：SpinBox 工厂 -----------------

    def _create_double_spin(self, val, min_v, max_v, step=0.1, decimals=2):
        spin = QDoubleSpinBox()
        spin.setRange(min_v, max_v)
        spin.setValue(val)
        spin.setSingleStep(step)
        spin.setDecimals(decimals)
        spin.valueChanged.connect(self.sig_params_changed.emit)
        return spin

    def _create_int_spin(self, val, min_v, max_v, step=1):
        spin = QSpinBox()
        spin.setRange(min_v, max_v)
        spin.setValue(val)
        spin.setSingleStep(step)
        spin.valueChanged.connect(self.sig_params_changed.emit)
        return spin

    # ----------------- 1. 基础处理 -----------------

    def add_group_basic(self):
        g = QGroupBox(I18n.tr('group_basic'))
        l = QVBoxLayout()

        # DC 去直流窗口（0=关闭）
        h_dc = QHBoxLayout()
        h_dc.addWidget(QLabel(I18n.tr("lbl_dc_win")))
        self.spin_dc_ns = self._create_double_spin(0.0, 0.0, 20.0, 0.5, 1)
        h_dc.addWidget(self.spin_dc_ns)
        l.addLayout(h_dc)

        # Time-Zero 自动校正
        self.chk_t0 = QCheckBox(I18n.tr('lbl_t0') + " (Auto)")
        self.chk_t0.setChecked(True)
        self.chk_t0.clicked.connect(self.sig_params_changed.emit)
        l.addWidget(self.chk_t0)

        # Dewow
        self.chk_dewow = QCheckBox(I18n.tr('lbl_dewow'))
        self.chk_dewow.clicked.connect(self.sig_params_changed.emit)
        l.addWidget(self.chk_dewow)

        # Dewow 窗口 (ns)
        h_dewow = QHBoxLayout()
        h_dewow.addWidget(QLabel(I18n.tr('lbl_dewow_win')))
        # 默认 6ns，范围 0~50ns，步长 0.5ns，小数 1 位
        self.spin_dewow_win = self._create_double_spin(6.0, 0.0, 50.0, 0.5, 1)
        h_dewow.addWidget(self.spin_dewow_win)
        l.addLayout(h_dewow)

        # 顶部静音窗口 (ns) —— 0 表示关闭
        h_mute = QHBoxLayout()
        h_mute.addWidget(QLabel(I18n.tr('lbl_mute_ns')))
        self.spin_mute_ns = self._create_double_spin(0.0, 0.0, 50.0, 0.5, 1)
        h_mute.addWidget(self.spin_mute_ns)
        l.addLayout(h_mute)
        

        # 背景材料选择
        h_bgmat = QHBoxLayout()
        h_bgmat.addWidget(QLabel(I18n.tr('lbl_bg_material')))
        self.combo_bg_material = QComboBox()
        # 默认先只有“自动/自定义”，真正的材料列表由 MainWindow 在加载 .in 后填充
        self.combo_bg_material.addItem(I18n.tr('lbl_bg_auto'), userData="")
        self.combo_bg_material.currentIndexChanged.connect(self.sig_params_changed.emit)
        h_bgmat.addWidget(self.combo_bg_material)
        l.addLayout(h_bgmat)

        # 介电常数 eps
        l.addWidget(QLabel(I18n.tr('lbl_eps')))
        self.spin_eps = self._create_double_spin(6.0, 1.0, 81.0, 0.1, 1)
        l.addWidget(self.spin_eps)

        g.setLayout(l)
        self.layout.addWidget(g)

    # ----------------- 2. 空间/背景处理 -----------------

    
    def add_group_roi(self):
        """ROI：左右/上下裁剪 + 深度静音带（用于 .out/.npy 等所有输入）"""
        box = QGroupBox(I18n.tr('group_roi'))
        lay = QVBoxLayout(box)

        # --- X 裁剪（按道号/trace，1-based，end 为包含端）---
        self.chk_crop_x = QCheckBox(I18n.tr('lbl_crop_x_on'))
        self.chk_crop_x.stateChanged.connect(self.sig_params_changed)
        lay.addWidget(self.chk_crop_x)

        rowx = QHBoxLayout()
        rowx.addWidget(QLabel(I18n.tr('lbl_crop_x_start')))
        self.spin_crop_x_start = QSpinBox()
        self.spin_crop_x_start.setRange(1, 1)
        self.spin_crop_x_start.setValue(1)
        self.spin_crop_x_start.valueChanged.connect(self.sig_params_changed)
        rowx.addWidget(self.spin_crop_x_start)

        rowx.addWidget(QLabel(I18n.tr('lbl_crop_x_end')))
        self.spin_crop_x_end = QSpinBox()
        self.spin_crop_x_end.setRange(1, 1)
        self.spin_crop_x_end.setValue(1)
        self.spin_crop_x_end.valueChanged.connect(self.sig_params_changed)
        rowx.addWidget(self.spin_crop_x_end)
        lay.addLayout(rowx)

        # --- Y 裁剪（按深度 m）---
        self.chk_crop_y = QCheckBox(I18n.tr('lbl_crop_y_on'))
        self.chk_crop_y.stateChanged.connect(self.sig_params_changed)
        lay.addWidget(self.chk_crop_y)

        rowy = QHBoxLayout()
        rowy.addWidget(QLabel(I18n.tr('lbl_crop_depth_start')))
        self.spin_crop_depth_start = QDoubleSpinBox()
        self.spin_crop_depth_start.setDecimals(3)
        self.spin_crop_depth_start.setSingleStep(0.01)
        self.spin_crop_depth_start.setRange(0.0, 10.0)
        self.spin_crop_depth_start.setValue(0.0)
        self.spin_crop_depth_start.valueChanged.connect(self.sig_params_changed)
        rowy.addWidget(self.spin_crop_depth_start)

        rowy.addWidget(QLabel(I18n.tr('lbl_crop_depth_end')))
        self.spin_crop_depth_end = QDoubleSpinBox()
        self.spin_crop_depth_end.setDecimals(3)
        self.spin_crop_depth_end.setSingleStep(0.01)
        self.spin_crop_depth_end.setRange(0.0, 10.0)
        self.spin_crop_depth_end.setValue(0.0)
        self.spin_crop_depth_end.valueChanged.connect(self.sig_params_changed)
        rowy.addWidget(self.spin_crop_depth_end)
        lay.addLayout(rowy)

        # --- 静音带（按深度 m，覆盖全 X）---
        self.chk_mute_band = QCheckBox(I18n.tr('lbl_mute_band_on'))
        self.chk_mute_band.stateChanged.connect(self.sig_params_changed)
        lay.addWidget(self.chk_mute_band)

        rowm = QHBoxLayout()
        rowm.addWidget(QLabel(I18n.tr('lbl_mute_depth_start')))
        self.spin_mute_depth_start = QDoubleSpinBox()
        self.spin_mute_depth_start.setDecimals(3)
        self.spin_mute_depth_start.setSingleStep(0.01)
        self.spin_mute_depth_start.setRange(0.0, 10.0)
        self.spin_mute_depth_start.setValue(0.0)
        self.spin_mute_depth_start.valueChanged.connect(self.sig_params_changed)
        rowm.addWidget(self.spin_mute_depth_start)

        rowm.addWidget(QLabel(I18n.tr('lbl_mute_depth_end')))
        self.spin_mute_depth_end = QDoubleSpinBox()
        self.spin_mute_depth_end.setDecimals(3)
        self.spin_mute_depth_end.setSingleStep(0.01)
        self.spin_mute_depth_end.setRange(0.0, 10.0)
        self.spin_mute_depth_end.setValue(0.0)
        self.spin_mute_depth_end.valueChanged.connect(self.sig_params_changed)
        rowm.addWidget(self.spin_mute_depth_end)
        lay.addLayout(rowm)

        rowt = QHBoxLayout()
        rowt.addWidget(QLabel(I18n.tr('lbl_mute_taper_m')))
        self.spin_mute_taper_m = QDoubleSpinBox()
        self.spin_mute_taper_m.setDecimals(3)
        self.spin_mute_taper_m.setSingleStep(0.01)
        self.spin_mute_taper_m.setRange(0.0, 2.0)
        self.spin_mute_taper_m.setValue(0.0)
        self.spin_mute_taper_m.valueChanged.connect(self.sig_params_changed)
        rowt.addWidget(self.spin_mute_taper_m)
        lay.addLayout(rowt)

        btn_row = QHBoxLayout()
        self.btn_roi_reset = QPushButton(I18n.tr('btn_roi_reset'))
        self.btn_roi_reset.clicked.connect(self._roi_reset)
        btn_row.addWidget(self.btn_roi_reset)
        lay.addLayout(btn_row)

        self.layout.addWidget(box)

    def _roi_reset(self):
        """重置 ROI 控件到默认（全关）"""
        try:
            self.chk_crop_x.setChecked(False)
            self.chk_crop_y.setChecked(False)
            self.chk_mute_band.setChecked(False)
            self.spin_crop_x_start.setValue(1)
            self.spin_crop_x_end.setValue(max(1, self.spin_crop_x_end.maximum()))
            self.spin_crop_depth_start.setValue(0.0)
            self.spin_crop_depth_end.setValue(0.0)
            self.spin_mute_depth_start.setValue(0.0)
            self.spin_mute_depth_end.setValue(0.0)
            self.spin_mute_taper_m.setValue(0.0)
        finally:
            self.sig_params_changed.emit()

    def set_roi_limits(self, nx: int, max_depth_m: float):
        """由 MainWindow 根据当前数据动态设置 ROI 控件范围"""
        nx = int(max(1, nx))
        max_depth_m = float(max(0.0, max_depth_m))

        if hasattr(self, "spin_crop_x_start"):
            self.spin_crop_x_start.setRange(1, nx)
            self.spin_crop_x_end.setRange(1, nx)
            # 保障 end>=start 的常见体验（但不强制）
            if self.spin_crop_x_end.value() > nx:
                self.spin_crop_x_end.setValue(nx)

        if hasattr(self, "spin_crop_depth_start"):
            self.spin_crop_depth_start.setRange(0.0, max(0.0, max_depth_m))
            self.spin_crop_depth_end.setRange(0.0, max(0.0, max_depth_m))
            self.spin_mute_depth_start.setRange(0.0, max(0.0, max_depth_m))
            self.spin_mute_depth_end.setRange(0.0, max(0.0, max_depth_m))

    def add_group_spatial(self):
        g = QGroupBox(I18n.tr('group_spatial'))
        l = QVBoxLayout()

        l.addWidget(QLabel(I18n.tr('lbl_bg_method')))
        self.combo_bg = QComboBox()
        self.combo_bg.addItem(I18n.tr('opt_none'), 'none')
        self.combo_bg.addItem(I18n.tr('opt_mean'), 'mean')
        self.combo_bg.addItem(I18n.tr('opt_median'), 'median')
        self.combo_bg.addItem(I18n.tr('opt_tophat'), 'tophat')
        self.combo_bg.currentIndexChanged.connect(self.sig_params_changed.emit)
        l.addWidget(self.combo_bg)

        l.addWidget(QLabel(I18n.tr('lbl_bg_win')))
        self.spin_bg_win = self._create_int_spin(61, 3, 500, 2)
        l.addWidget(self.spin_bg_win)

        g.setLayout(l)
        self.layout.addWidget(g)

    # ----------------- 3. 增益 -----------------

    def add_group_gain(self):
        g = QGroupBox(I18n.tr('group_gain'))
        l = QVBoxLayout()

        self.chk_gain = QCheckBox(I18n.tr('lbl_gain_enable'))
        self.chk_gain.clicked.connect(self.sig_params_changed.emit)
        l.addWidget(self.chk_gain)

        # 线性增益 alpha
        h1 = QHBoxLayout()
        h1.addWidget(QLabel(I18n.tr('lbl_alpha')))
        self.spin_alpha = self._create_double_spin(0.00, 0.00, 10.00, 0.05, 2)
        h1.addWidget(self.spin_alpha)
        l.addLayout(h1)

        # 指数增益 beta
        h2 = QHBoxLayout()
        h2.addWidget(QLabel(I18n.tr('lbl_beta')))
        self.spin_beta = self._create_double_spin(0.00, 0.00, 10.00, 0.05, 2)
        h2.addWidget(self.spin_beta)
        l.addLayout(h2)

        # AGC 窗口 ns
        h3 = QHBoxLayout()
        h3.addWidget(QLabel(I18n.tr("lbl_agc_ns")))
        self.spin_agc = self._create_double_spin(0.0, 0.0, 500.0, 1.0, 1)
        h3.addWidget(self.spin_agc)
        l.addLayout(h3)

        g.setLayout(l)
        self.layout.addWidget(g)

    # ----------------- 4. 1D 滤波 -----------------

    def add_group_filter(self):
        g = QGroupBox(I18n.tr('group_filter'))
        l = QVBoxLayout()

        # Bandpass 滤波开关
        self.chk_bp = QCheckBox(I18n.tr("lbl_bandpass"))
        self.chk_bp.clicked.connect(self.sig_params_changed.emit)
        l.addWidget(self.chk_bp)

        # L/H 频率 (MHz)
        h_bp = QHBoxLayout()
        self.spin_bp_low = self._create_double_spin(50.0, 0.0, 2000.0, 10.0, 0)   # MHz
        self.spin_bp_high = self._create_double_spin(900.0, 10.0, 5000.0, 50.0, 0)
        h_bp.addWidget(QLabel("L:"))
        h_bp.addWidget(self.spin_bp_low)
        h_bp.addWidget(QLabel("H:"))
        h_bp.addWidget(self.spin_bp_high)
        l.addLayout(h_bp)

        # 横向平滑窗口 (trace 数)
        h1 = QHBoxLayout()
        h1.addWidget(QLabel(I18n.tr('lbl_smooth')))
        self.spin_smooth = self._create_int_spin(0, 0, 50, 1)
        h1.addWidget(self.spin_smooth)
        l.addLayout(h1)

        g.setLayout(l)
        self.layout.addWidget(g)

    # ----------------- 5. F-K 滤波 -----------------

    def add_group_fk(self):
        # F-K group uses i18n translations
        g = QGroupBox(I18n.tr('group_fk'))
        l = QVBoxLayout()

        # 开关
        self.chk_fk = QCheckBox(I18n.tr('lbl_fk_enable'))
        self.chk_fk.clicked.connect(self.sig_params_changed.emit)
        l.addWidget(self.chk_fk)

        # 波数范围 kmin / kmax (1/m)
        h_k = QHBoxLayout()
        h_k.addWidget(QLabel(I18n.tr('lbl_fk_kmin')))
        self.spin_fk_kmin = self._create_double_spin(0.0, 0.0, 50.0, 0.1, 3)
        h_k.addWidget(self.spin_fk_kmin)

        h_k.addWidget(QLabel(I18n.tr('lbl_fk_kmax')))
        self.spin_fk_kmax = self._create_double_spin(0.0, 0.0, 50.0, 0.1, 3)
        h_k.addWidget(self.spin_fk_kmax)
        l.addLayout(h_k)

        # 频率范围 fmin / fmax (MHz)
        h_f = QHBoxLayout()
        h_f.addWidget(QLabel(I18n.tr('lbl_fk_fmin')))
        self.spin_fk_fmin = self._create_double_spin(0.0, 0.0, 5000.0, 10.0, 1)
        h_f.addWidget(self.spin_fk_fmin)

        h_f.addWidget(QLabel(I18n.tr('lbl_fk_fmax')))
        self.spin_fk_fmax = self._create_double_spin(0.0, 0.0, 5000.0, 10.0, 1)
        h_f.addWidget(self.spin_fk_fmax)
        l.addLayout(h_f)

        g.setLayout(l)
        self.layout.addWidget(g)

    # ----------------- 6. 显示设置 -----------------

    def add_group_display(self):
        g = QGroupBox(I18n.tr('group_display'))
        l = QVBoxLayout()

        # 显示原始 vs 处理后
        self.chk_show_raw = QCheckBox(I18n.tr('lbl_show_raw'))
        self.chk_show_raw.clicked.connect(self.sig_params_changed.emit)
        l.addWidget(self.chk_show_raw)

        # 是否显示 Hilbert 包络
        self.chk_env = QCheckBox(I18n.tr('lbl_env'))
        self.chk_env.clicked.connect(self.sig_params_changed.emit)
        l.addWidget(self.chk_env)

        # Clip 百分位
        h_clip = QHBoxLayout()
        h_clip.addWidget(QLabel(I18n.tr('lbl_clip')))
        self.spin_clip = self._create_double_spin(99.0, 80.0, 100.0, 0.5, 1)
        h_clip.addWidget(self.spin_clip)
        l.addLayout(h_clip)

        # 色卡
        h_cmap = QHBoxLayout()
        h_cmap.addWidget(QLabel(I18n.tr('lbl_cmap')))
        self.combo_cmap = QComboBox()
        self.combo_cmap.addItems(["seismic", "gray", "viridis", "jet"])
        self.combo_cmap.currentIndexChanged.connect(self.sig_params_changed.emit)
        h_cmap.addWidget(self.combo_cmap)
        l.addLayout(h_cmap)


    # === 2D 画笔（对比视图标注） ===
        h_brush = QHBoxLayout()

        self.chk_brush_2d = QCheckBox(I18n.tr("lbl_brush_2d"))   # 例如： "启用画笔"
        self.chk_brush_2d.setToolTip(I18n.tr("tip_brush_2d"))
        self.chk_brush_2d.toggled.connect(self.sig_brush_toggled)
        h_brush.addWidget(self.chk_brush_2d)

        self.btn_clear_brush_2d = QPushButton(I18n.tr("btn_clear_brush_2d"))  # 例如："清除标注"
        self.btn_clear_brush_2d.setToolTip(I18n.tr("tip_clear_brush_2d"))
        self.btn_clear_brush_2d.clicked.connect(self.sig_brush_cleared)
        h_brush.addWidget(self.btn_clear_brush_2d)

        l.addLayout(h_brush)

        g.setLayout(l)
        self.layout.addWidget(g)


    # ----------------- 参数打包 -----------------

    def get_values(self):
        return {
            # Basic
            'dc_ns': self.spin_dc_ns.value(),
            't0_auto': self.chk_t0.isChecked(),
            'dewow': self.chk_dewow.isChecked(),
            'dewow_win_ns': self.spin_dewow_win.value(),   # <<< 新增
            'mute_ns': self.spin_mute_ns.value(),
            'bg_material': (
                self.combo_bg_material.currentData()
                if hasattr(self, 'combo_bg_material') else ""
            ),
            'eps': self.spin_eps.value(),

                        # ROI Crop/Mute
            'crop_x_on': self.chk_crop_x.isChecked() if hasattr(self,'chk_crop_x') else False,
            'crop_x_start': self.spin_crop_x_start.value() if hasattr(self,'spin_crop_x_start') else 1,
            'crop_x_end': self.spin_crop_x_end.value() if hasattr(self,'spin_crop_x_end') else 1,
            'crop_y_on': self.chk_crop_y.isChecked() if hasattr(self,'chk_crop_y') else False,
            'crop_depth_start': self.spin_crop_depth_start.value() if hasattr(self,'spin_crop_depth_start') else 0.0,
            'crop_depth_end': self.spin_crop_depth_end.value() if hasattr(self,'spin_crop_depth_end') else 0.0,
            'mute_band_on': self.chk_mute_band.isChecked() if hasattr(self,'chk_mute_band') else False,
            'mute_depth_start': self.spin_mute_depth_start.value() if hasattr(self,'spin_mute_depth_start') else 0.0,
            'mute_depth_end': self.spin_mute_depth_end.value() if hasattr(self,'spin_mute_depth_end') else 0.0,
            'mute_taper_m': self.spin_mute_taper_m.value() if hasattr(self,'spin_mute_taper_m') else 0.0,

# Spatial
            'bg_method': self.combo_bg.currentData(),
            'bg_win': self.spin_bg_win.value(),

            # Gain
            'gain_on': self.chk_gain.isChecked(),
            'gain_alpha': self.spin_alpha.value(),
            'gain_beta': self.spin_beta.value(),
            'agc_win': self.spin_agc.value(),

            # 1D Filter
            'use_bp': self.chk_bp.isChecked(),
            'bp_low': self.spin_bp_low.value() * 1e6,   # MHz -> Hz
            'bp_high': self.spin_bp_high.value() * 1e6,
            'smooth_x': self.spin_smooth.value(),

            # F-K Filter
            'fk_enabled': self.chk_fk.isChecked(),
            'fk_kmin': self.spin_fk_kmin.value(),
            'fk_kmax': self.spin_fk_kmax.value(),
            'fk_fmin_mhz': self.spin_fk_fmin.value(),
            'fk_fmax_mhz': self.spin_fk_fmax.value(),

            # Display
            'show_raw': self.chk_show_raw.isChecked(),   # 新增
            'show_env': self.chk_env.isChecked(),
            'clip': self.spin_clip.value(),
            'cmap': self.combo_cmap.currentText()
        }

    def set_materials(self, materials: dict, default_name: str | None = None):
        """
        用 .in 中的 materials 列表填充“背景材料”下拉框。

        materials: {name: {'epsr':..., ...}, ...}
        default_name: 期望默认选中的材料名（可为 None）
        """
        if not hasattr(self, "combo_bg_material"):
            return

        self.combo_bg_material.blockSignals(True)
        self.combo_bg_material.clear()

        # 第一项：自动/自定义
        self.combo_bg_material.addItem(I18n.tr('lbl_bg_auto'), userData="")

        # 按名字排序便于选择
        for name, m in sorted(materials.items(), key=lambda kv: kv[0]):
            epsr = None
            if isinstance(m, dict) and "epsr" in m:
                epsr = m["epsr"]
            label = f"{name}"
            if epsr is not None:
                label = f"{name} (εr={epsr:g})"
            self.combo_bg_material.addItem(label, userData=name)

        # 设定默认选中项
        idx = 0
        if default_name:
            for i in range(self.combo_bg_material.count()):
                if self.combo_bg_material.itemData(i) == default_name:
                    idx = i
                    break
        self.combo_bg_material.setCurrentIndex(idx)
        self.combo_bg_material.blockSignals(False)

