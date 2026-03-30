from pathlib import Path
from ui.ascan_view import AScanViewDialog  # <--- 新增
import numpy as np
import json  # ★ 新增
import platform

try:
    import winsound  # Windows only
except Exception:  # pragma: no cover
    winsound = None
from PyQt6.QtCore import Qt, QTimer,QSize,QPointF,QRectF,QPoint, QEvent, QSignalBlocker

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QFileDialog, QSplitter, QComboBox,
    QLabel, QPlainTextEdit, QMessageBox, QScrollArea,
    QDialog, QCheckBox, QDialogButtonBox, QProgressBar,
    QLineEdit, QGroupBox, QSpinBox, QStackedWidget, 
         QToolButton, QMenu, QStyle

      
 # ⭐ 新增几个
)
from PyQt6.QtGui import QColor, QTextCursor, QFont, QPainter, QPen, QBrush, QPixmap, QIcon, QShortcut, QKeySequence


from ui.dialogs import NpyParamsDialog

from ui.canvas import GPRCanvas
from ui.controls import ControlPanel
from ui.model_view import ModelViewDialog

from io_module.loader import load_out_file, load_npy_file, load_repro_package
from io_module.parse_in import parse_in_file

from io_module import exporter
from core.i18n import I18n

# 处理算法
import algorithms.basic as algo_basic
import algorithms.spatial as algo_spatial
import algorithms.gain as algo_gain
import algorithms.filters as algo_filters
import algorithms.fk as algo_fk
from ui.model3d_pv import Model3DViewPVDialog, DrawingOverlay



from dataclasses import dataclass            # ★ 新增
from typing import Dict, Any, List           # ★ 新增

from PyQt6.QtCore import QThread          # <--- 新增
from core.worker import PipelineWorker    # <--- 新增

class CompareViewWidget(QWidget):
    """包含 4 个 ComparePane，用 QSplitter 实现可调大小"""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.panes: List[ComparePane] = [ComparePane(self) for _ in range(4)]

        vs_left = QSplitter(Qt.Vertical)
        vs_left.addWidget(self.panes[0])   # 左上
        vs_left.addWidget(self.panes[2])   # 左下

        vs_right = QSplitter(Qt.Vertical)
        vs_right.addWidget(self.panes[1])  # 右上
        vs_right.addWidget(self.panes[3])  # 右下

        hs = QSplitter(Qt.Horizontal)
        hs.addWidget(vs_left)
        hs.addWidget(vs_right)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(hs)

        self.splitter_main = hs  # 以后想读写分割比例可以用到

class ComparePane(QWidget):
    """四宫格中的一个小视图：上面是图，下面是参数文字"""

    def __init__(self, parent=None):
        super().__init__(parent)
        from ui.canvas import GPRCanvas  # 避免循环导入






        self.canvas = GPRCanvas(self)
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        font = self.label.font()
        font.setPointSize(9)
        self.label.setFont(font)

        # ⭐ 固定参数文字区域高度，防止某个视图文字太多把图压扁
        self.label.setFixedHeight(50)   # 可以根据显示效果微调，比如 45~70

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        layout.addWidget(self.canvas, stretch=1)
        layout.addWidget(self.label, stretch=0)

class AiAvatarWidget(QWidget):
    """
    AI 小助手头像：使用本地图片渲染（推荐透明背景 PNG）。

    默认路径：ui/assets/ai_robot_icon.png
    - 如果图片找不到，会降级画一个简易占位，不影响主程序运行。
    """
    def __init__(self, parent=None, image_path=None):
        super().__init__(parent)
        self.setObjectName("AiAvatarWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        if image_path is None:
            image_path = str((Path(__file__).resolve().parent / "assets" / "ai_robot_icon.png"))
        self._image_path = image_path
        self._pix = QPixmap(self._image_path) if self._image_path else QPixmap()

        # 小助手占用区域（和 AiAssistantWidget 保持一致）
        self.setFixedSize(96, 72)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        r = self.rect()

        if self._pix is None or self._pix.isNull():
            # 占位：避免因为资源丢失导致“空白”
            painter.setPen(QPen(QColor("#90A4AE"), 1.5))
            painter.setBrush(QBrush(QColor(255, 255, 255, 30)))
            painter.drawRoundedRect(r.adjusted(2, 2, -2, -2), 12, 12)
            painter.setPen(QPen(QColor("#CFD8DC"), 1))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, "AI")
            return

        pix = self._pix.scaled(
            r.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (r.width() - pix.width()) // 2
        y = (r.height() - pix.height()) // 2
        painter.drawPixmap(x, y, pix)


class AiAssistantWidget(QWidget):
    """
    右下角固定的小助手（头像 + 可选气泡）。
    - 默认不抢鼠标事件（避免影响主界面交互）。
    - 通过 set_message() 在头像上方显示一段“气泡文本”，也可设置自动隐藏时间。
    """
    def __init__(self, parent=None, image_path=None):
        super().__init__(parent)
        self.setObjectName("AiAssistantWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # 头像（透明 PNG 推荐）
        self.avatar = AiAvatarWidget(self, image_path=image_path)

        # 小助手本体尺寸（只占角落这一块）
        self.setFixedSize(96, 72)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.avatar, alignment=Qt.AlignmentFlag.AlignCenter)

        # 气泡：挂在父容器上（不改变本体大小），这样小人始终贴角落
        host = parent if parent is not None else self.parentWidget()
        self.bubble = QLabel(host)
        self.bubble.setWordWrap(True)
        self.bubble.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.bubble.setVisible(False)
        self.bubble.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        font = self.bubble.font()
        font.setPointSize(9)
        self.bubble.setFont(font)

        # 气泡最大宽度（超出自动换行）
        self._bubble_max_w = 260
        self.bubble.setMaximumWidth(self._bubble_max_w)

        # 自动隐藏定时器
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.bubble.hide)

        # 不拦截鼠标（防止挡住画布/控制台的点击与滚轮）
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def hideEvent(self, e):
        # 本体隐藏时，气泡也隐藏
        try:
            self.bubble.hide()
        except Exception:
            pass
        return super().hideEvent(e)

    def _bubble_style(self, mood: str) -> str:
        # 轻量、对比度高、和暗色背景搭配
        if mood in ("err", "error"):
            bg = "rgba(239,83,80,0.92)"
            fg = "#FFFFFF"
        elif mood in ("warn", "warning"):
            bg = "rgba(255,183,77,0.92)"
            fg = "#1E1E1E"
        elif mood in ("ok", "success"):
            bg = "rgba(165,214,167,0.92)"
            fg = "#1E1E1E"
        else:
            bg = "rgba(38,50,56,0.92)"
            fg = "#ECEFF1"
        return (
            f"QLabel{{"
            f"background-color:{bg}; color:{fg};"
            f"border: 1px solid rgba(255,255,255,0.18);"
            f"border-radius: 10px;"
            f"padding: 8px 10px;"
            f"}}"
        )

    def update_bubble_pos(self):
        """
        根据当前小人位置，把气泡贴在头像上方（尽量靠右对齐）。
        """
        if not self.bubble.isVisible():
            return
        host = self.bubble.parentWidget()
        if host is None:
            return

        # 让 bubble 尺寸先计算好
        self.bubble.adjustSize()
        w = min(self._bubble_max_w, max(120, self.bubble.sizeHint().width()))
        self.bubble.setFixedWidth(w)
        self.bubble.adjustSize()

        # 右对齐到 avatar 右边缘
        margin = 6
        bx = self.x() + self.width() - self.bubble.width()
        by = self.y() - self.bubble.height() - margin

        # 边界钳制
        bx = max(6, min(bx, host.width() - self.bubble.width() - 6))
        by = max(6, min(by, host.height() - self.bubble.height() - 6))

        self.bubble.move(bx, by)
        self.bubble.raise_()

    def set_message(self, text: str, mood: str = "info", auto_hide_ms: int = 3500):
        """
        在头像上方显示气泡文本。
        - auto_hide_ms=0 表示不自动隐藏
        """
        if self.bubble is None:
            return
        if not text:
            self.bubble.hide()
            return

        self.bubble.setStyleSheet(self._bubble_style(mood))
        self.bubble.setText(text.strip())
        self.bubble.show()
        self.update_bubble_pos()

        if auto_hide_ms and auto_hide_ms > 0:
            self._hide_timer.stop()
            self._hide_timer.start(int(auto_hide_ms))
        else:
            self._hide_timer.stop()

    def hide_bubble(self):
        try:
            self._hide_timer.stop()
            self.bubble.hide()
        except Exception:
            pass

@dataclass
@dataclass
class ViewSlot:
    params: Dict[str, Any] | None = None
    data: np.ndarray | None = None
    extent: tuple | None = None
    title: str = ""
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.gpr_data = None

        # 上一次重处理使用的参数 + 数据缓存
        self._last_heavy_params = None
        self._last_heavy_data = None
    
        # 上一次 AI 建议文本（用于去重）
        self._last_ai_msg = ""

        # 当前绘图的物理范围 (xmin, xmax, zmin, zmax)
        self.current_extent = None

        # 四视图对比槽位（保存每个视图的数据和参数）
        self.view_slots = [ViewSlot() for _ in range(4)]
        # 画笔状态
# 2D 画笔（截图 overlay）相关
        self.brush_enabled = False
        self.overlay_2d: DrawingOverlay | None = None

        self.brush_lines = {}                 # canvas -> [Line2D, ...]
        self.ai_widget = None  # AI 助手面板，会在 init_ui 里真正创建


        self.fitting_mode = False
        self.fit_vertex = None  # 存储 (x_meters, t_ns) 注意存的是时间！
        self.fit_v = 0.1        # 初始速度 m/ns
        self.fit_line = None    # 绘图对象
        self.fit_text = None



        # 交互模式：normal / fit / brush（互斥）
        self.interaction_mode = "normal"
        self._interaction_guard = False
        # 处理定时器（节流）
        self._pipeline_timer = QTimer(self)

        # 交互反馈：音效 + 快捷键
        self.sound_enabled = True
        self._shortcuts = []  # 防止 QShortcut 被 GC
        self._pipeline_timer.setSingleShot(True)
        self._pipeline_timer.setInterval(200)
        self._pipeline_timer.timeout.connect(self._run_pipeline_internal)


    # ★ 新增：底部状态栏
        self._status = self.statusBar()
        self._status.setSizeGripEnabled(False)
        self._status.setStyleSheet("font-size: 10pt;")
        self._status.showMessage(I18n.tr('status_ready'))
        self.resize(1400, 900)
        self.init_ui()
        self.update_texts()

        # 控制台启动提示
        self.console_print(
            self._t("[help] 输入 help 查看可用命令；Ctrl+L 聚焦命令行。",
                    "[help] Type help for commands; Ctrl+L focuses the command line."),
            kind="hint",
        )

    # ---------------- UI 构建 ----------------
    def init_ui(self):
        # ================= 顶部：小图标工具栏 =================
        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(8, 4, 8, 4)
        top_layout.setSpacing(6)

        # ---- 左侧：一排小工具按钮 ----
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(4)

        style = self.style()

        def make_tool_button(icon, text, slot, sound='click'):
            btn = QToolButton()
            btn.setIcon(icon)
            btn.setToolButtonStyle(Qt.ToolButtonIconOnly)
            btn.setToolTip(text)
            btn.setFixedSize(28, 28)
            def _wrapped():
                self.play_ui_sound(sound)
                slot()
            btn.clicked.connect(_wrapped)
            return btn

        # 1) 加载数据
        icon_open = style.standardIcon(QStyle.SP_DialogOpenButton)
        self.btn_open = make_tool_button(icon_open, I18n.tr('load_btn'), self.load_file)
        toolbar_layout.addWidget(self.btn_open)

        # 2) 导出结果
        icon_save = style.standardIcon(QStyle.SP_DialogSaveButton)
        self.btn_export = make_tool_button(icon_save, I18n.tr('export_btn'), self.export_data)
        toolbar_layout.addWidget(self.btn_export)

        # 3) 手动加载 .in
        icon_in = style.standardIcon(QStyle.SP_FileDialogDetailedView)
        self.btn_load_in = make_tool_button(icon_in, I18n.tr('load_in_btn'), self.load_in_file_manual)
        toolbar_layout.addWidget(self.btn_load_in)

        # 4) 模型/真值视图
        icon_model2d = style.standardIcon(QStyle.SP_FileDialogListView)
        self.btn_model2d = make_tool_button(icon_model2d, I18n.tr('show_model_btn'), self.show_model_view)
        toolbar_layout.addWidget(self.btn_model2d)

        # 5) 3D 模型视图
        icon_model3d = style.standardIcon(QStyle.SP_ComputerIcon)
        self.btn_model3d = make_tool_button(icon_model3d, I18n.tr('show_model3d_btn'), self.show_model3d_view)
        toolbar_layout.addWidget(self.btn_model3d)

        # 6) 修改物理参数
        icon_phys = style.standardIcon(QStyle.SP_DriveHDIcon)
        self.btn_phys = make_tool_button(icon_phys, I18n.tr('edit_physical_tip'), self.edit_physical_params)
        toolbar_layout.addWidget(self.btn_phys)

        # 7) 速度拟合工具（开关）
        icon_fit = style.standardIcon(QStyle.SP_ArrowUp)
        self.btn_fit_velocity = QToolButton()
        self.btn_fit_velocity.setIcon(icon_fit)
        self.btn_fit_velocity.setCheckable(True)
        self.btn_fit_velocity.setFixedSize(28, 28)
        self.btn_fit_velocity.setToolTip(I18n.tr('fit_velocity_tip'))
        self.btn_fit_velocity.toggled.connect(lambda checked: (self.play_ui_sound("toggle"), self.toggle_fitting_mode(checked)))
        toolbar_layout.addWidget(self.btn_fit_velocity)

        # 8) 参数预设 && 视图操作：用一个下拉菜单收起来
        self.menu_preset = QMenu(I18n.tr('preset_menu_title'), self)

        # 参数预设动作
        self.act_save_params = self.menu_preset.addAction(I18n.tr('preset_save_params'))
        self.act_save_params.triggered.connect(lambda: (self.play_ui_sound("click"), self.save_params_preset()))
        self.act_load_params = self.menu_preset.addAction(I18n.tr('preset_load_params'))
        self.act_load_params.triggered.connect(lambda: (self.play_ui_sound("click"), self.load_params_preset()))

        self.menu_preset.addSeparator()

        # 保存到视图 1~4
        self.act_save_v1 = self.menu_preset.addAction(I18n.tr('preset_save_v1'))
        self.act_save_v1.triggered.connect(lambda: (self.play_ui_sound("click"), self.save_current_view_to_slot(0)))
        self.act_save_v2 = self.menu_preset.addAction(I18n.tr('preset_save_v2'))
        self.act_save_v2.triggered.connect(lambda: (self.play_ui_sound("click"), self.save_current_view_to_slot(1)))
        self.act_save_v3 = self.menu_preset.addAction(I18n.tr('preset_save_v3'))
        self.act_save_v3.triggered.connect(lambda: (self.play_ui_sound("click"), self.save_current_view_to_slot(2)))
        self.act_save_v4 = self.menu_preset.addAction(I18n.tr('preset_save_v4'))
        self.act_save_v4.triggered.connect(lambda: (self.play_ui_sound("click"), self.save_current_view_to_slot(3)))

        self.menu_preset.addSeparator()

        # 从视图 1~4 载入
        self.act_load_v1 = self.menu_preset.addAction(I18n.tr('preset_load_v1'))
        self.act_load_v1.triggered.connect(lambda: (self.play_ui_sound("click"), self.load_params_from_slot(0)))
        self.act_load_v2 = self.menu_preset.addAction(I18n.tr('preset_load_v2'))
        self.act_load_v2.triggered.connect(lambda: (self.play_ui_sound("click"), self.load_params_from_slot(1)))
        self.act_load_v3 = self.menu_preset.addAction(I18n.tr('preset_load_v3'))
        self.act_load_v3.triggered.connect(lambda: (self.play_ui_sound("click"), self.load_params_from_slot(2)))
        self.act_load_v4 = self.menu_preset.addAction(I18n.tr('preset_load_v4'))
        self.act_load_v4.triggered.connect(lambda: (self.play_ui_sound("click"), self.load_params_from_slot(3)))

        self.btn_preset = QToolButton()
        self.btn_preset.setText(" ")
        self.btn_preset.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_preset.setIcon(style.standardIcon(QStyle.SP_DesktopIcon))
        self.btn_preset.setPopupMode(QToolButton.InstantPopup)
        self.btn_preset.setMenu(self.menu_preset)
        self.btn_preset.setFixedHeight(28)
        toolbar_layout.addWidget(self.btn_preset)

        top_layout.addLayout(toolbar_layout)
        top_layout.addStretch(1)

        # ---- 右侧：视图模式 + 语言 + 进度条 ----
        right_layout = QHBoxLayout()
        right_layout.setSpacing(6)

        # 视图模式
        self.lbl_view_mode = QLabel(I18n.tr("lbl_view_mode"))
        right_layout.addWidget(self.lbl_view_mode)

        self.combo_view_mode = QComboBox()
        self.combo_view_mode.addItem(I18n.tr("view_mode_single"), "single")
        self.combo_view_mode.addItem(I18n.tr("view_mode_compare4"), "compare4")
        self.combo_view_mode.currentIndexChanged.connect(self.on_view_mode_changed)
        self.combo_view_mode.setFixedHeight(24)
        self.combo_view_mode.setFixedWidth(90)
        right_layout.addWidget(self.combo_view_mode)

        # 语言
        self.lbl_lang = QLabel(I18n.tr('lbl_language'))
        right_layout.addWidget(self.lbl_lang)

        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["中文", "English"])
        self.combo_lang.currentIndexChanged.connect(self.change_language)
        self.combo_lang.setFixedHeight(24)
        self.combo_lang.setFixedWidth(80)
        right_layout.addWidget(self.combo_lang)

        # AI 助手开关（优先用自定义机器人图标）
        _ai_icon_path = Path(__file__).resolve().parent / "assets" / "ai_robot_icon.png"
        if _ai_icon_path.exists():
            icon_ai = QIcon(str(_ai_icon_path))
        else:
            icon_ai = style.standardIcon(QStyle.StandardPixmap.SP_DialogHelpButton)
        self.btn_ai_helper = QToolButton()
        self.btn_ai_helper.setIcon(icon_ai)
        self.btn_ai_helper.setCheckable(True)
        self.btn_ai_helper.setToolTip(I18n.tr('ai_helper_tip'))
        self.btn_ai_helper.setFixedSize(28, 28)
        self.btn_ai_helper.toggled.connect(lambda checked: (self.play_ui_sound("toggle"), self.toggle_ai_helper(checked)))
        right_layout.addWidget(self.btn_ai_helper)

        # 声音开关（工具反馈用，不影响处理流水线）
        icon_sound_on = style.standardIcon(getattr(QStyle.StandardPixmap, 'SP_MediaVolume', QStyle.StandardPixmap.SP_FileDialogInfoView))
        icon_sound_off = style.standardIcon(getattr(QStyle.StandardPixmap, 'SP_MediaVolumeMuted', QStyle.StandardPixmap.SP_BrowserStop))
        self._icon_sound_on = icon_sound_on
        self._icon_sound_off = icon_sound_off

        self.btn_sound = QToolButton()
        self.btn_sound.setCheckable(True)
        self.btn_sound.setChecked(True)
        self.btn_sound.setFixedSize(28, 28)
        self.btn_sound.setToolTip('音效反馈：开/关')
        self.btn_sound.toggled.connect(self.toggle_sound)
        self.btn_sound.setIcon(self._icon_sound_on)
        right_layout.addWidget(self.btn_sound)

        # 快捷键帮助（输出到下方控制台，不弹气泡）
        icon_keys = style.standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        btn_keys = make_tool_button(icon_keys, '快捷键/帮助', self.show_shortcuts_help)
        right_layout.addWidget(btn_keys)


        # 进度条（细细一条）
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(10)
        self.progress_bar.setFixedWidth(120)
        self.progress_bar.hide()
        right_layout.addWidget(self.progress_bar)

        top_layout.addLayout(right_layout)

        # ================== 中部：左控制面板 + 右视图区 ==================
        self.splitter = QSplitter()
        self.controls = ControlPanel()
        self.controls.sig_params_changed.connect(self.on_params_changed)

        self.controls_scroll = QScrollArea()
        self.controls_scroll.setWidgetResizable(True)
        self.controls_scroll.setWidget(self.controls)

        # 2D 画笔信号
        self.controls.sig_brush_toggled.connect(self.on_brush_toggled)
        self.controls.sig_brush_cleared.connect(self.clear_brush)

        # 交互音效：只给关键按钮挂声音（避免滚轮调参时乱响）
        try:
            if hasattr(self.controls, 'btn_roi_reset'):
                self.controls.btn_roi_reset.clicked.connect(lambda: self.play_ui_sound('click'))
            if hasattr(self.controls, 'btn_clear_brush_2d'):
                self.controls.btn_clear_brush_2d.clicked.connect(lambda: self.play_ui_sound('click'))
        except Exception:
            pass

        # 主画布（单图）
        self.canvas = GPRCanvas()
        single_view = QWidget()
        sv_layout = QVBoxLayout(single_view)
        sv_layout.setContentsMargins(0, 0, 0, 0)
        sv_layout.addWidget(self.canvas)

        # 四视图对比
        self.compare_view = CompareViewWidget(self)
        self.view_stack = QStackedWidget(self)
        self.view_stack.addWidget(single_view)          # index 0: 单图
        self.view_stack.addWidget(self.compare_view)    # index 1: 四宫格

        # 绑定四视图里的点击事件
        for i, pane in enumerate(self.compare_view.panes):
            pane.canvas.mpl_connect(
                "button_press_event",
                lambda event, idx=i: self.on_compare_canvas_click(idx, event)
            )

        self.splitter.addWidget(self.controls_scroll)
        self.splitter.addWidget(self.view_stack)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([360, 1100])  # 控件窄一点，图像宽一点

        # 右侧视图区上的 2D 画笔 overlay（默认隐藏）
        self.overlay_2d = DrawingOverlay(self.view_stack)
        self.overlay_2d.hide()

        # 主画布点击 -> A-Scan
        self.canvas.mpl_connect("button_press_event", self.on_canvas_click)

        # 滚轮事件：用于“速度拟合”调节开口
        self.canvas.mpl_connect("scroll_event", self.on_fit_scroll)

        # ================== 底部：信息控制台 ==================
        # ================== 底部：信息控制台 ==================
        # ================== 底部：信息控制台 + 命令行 ==================
        self.txt_info = QPlainTextEdit()
        self.txt_info.setReadOnly(True)
        self.txt_info.setStyleSheet(
            "background-color: #263238; color: #ECEFF1; "
            "font-family: Consolas, monospace; font-size: 10pt;"
        )
        # 允许通过 splitter 拖动高度，只给一个下限即可
        self.txt_info.setMinimumHeight(80)

        # 命令行输入框
        self.cmd_line = QLineEdit()
        self.cmd_line.setPlaceholderText(I18n.tr('cmd_placeholder'))
        self.cmd_line.returnPressed.connect(self.on_command_entered)

        # ">>>" 提示 + 输入框
        cmd_bar = QHBoxLayout()
        cmd_bar.setContentsMargins(4, 0, 4, 4)
        cmd_bar.setSpacing(4)
        lbl_prompt = QLabel(">>>")
        lbl_prompt.setStyleSheet("color: #B0BEC5;")
        cmd_bar.addWidget(lbl_prompt)
        cmd_bar.addWidget(self.cmd_line)

        console_widget = QWidget()
        console_layout = QVBoxLayout(console_widget)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(0)

        console_layout.addWidget(self.txt_info)
        console_layout.addLayout(cmd_bar)

        # --- 悬浮 AI 小助手：挂在 console_widget 上，只在下方面板里拖动 ---
        self.console_widget = console_widget

        self.ai_widget = AiAssistantWidget(self.console_widget)
        self.ai_widget.hide()
        self.ai_widget.adjustSize()

        margin = 8
        size = self.ai_widget.sizeHint()
        x = self.console_widget.width() - size.width() - margin
        y = self.console_widget.height() - size.height() - margin
        self.ai_widget.move(max(0, x), max(0, y))

        # 让我们能在 console 大小变化时顺手把小助手重新摆到右下角
        self.console_widget.installEventFilter(self)


        # 垂直 splitter：上面是视图区，下面是控制台+命令行
        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.addWidget(self.splitter)
        main_splitter.addWidget(console_widget)
        main_splitter.setStretchFactor(0, 5)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([800, 140])  # 初始比例，之后你可以拖

        # 顶层布局
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(top_bar)
        layout.addWidget(main_splitter)
        self.setCentralWidget(central)

        # 初始化快捷键（只做 UI 交互，不影响处理逻辑）
        self._init_shortcuts()

        # （已去重）AI 小助手只创建一次：挂在 console_widget 上，并由 eventFilter/显示时自动贴右下角。



    

    # ---------------- 声音与快捷键 ----------------
    def play_ui_sound(self, kind: str = "click"):
        """轻量 UI 音效：只用于按钮/模式切换等交互反馈。"""
        if not getattr(self, "sound_enabled", True):
            return
        try:
            # Windows：用 winsound.Beep 做一个“更像按钮”的短促音
            if platform.system().lower().startswith("win") and winsound is not None:
                if kind == "error":
                    winsound.Beep(220, 120)
                elif kind == "toggle":
                    winsound.Beep(660, 50)
                elif kind == "notify":
                    winsound.Beep(880, 60)
                else:  # click
                    winsound.Beep(990, 30)
            else:
                # 其他平台：Qt 自带 beep
                QApplication.beep()
        except Exception:
            # 极端情况下别让 UI 音效影响主流程
            pass

    def toggle_sound(self, checked: bool):
        """顶部喇叭按钮：开/关 UI 音效反馈。"""
        # 先发一个反馈音（关的时候也能听到）
        if checked:
            self.sound_enabled = True
            self.btn_sound.setIcon(getattr(self, "_icon_sound_on", self.btn_sound.icon()))
            self.console_print(self._t("[UI] 音效反馈：开启", "[UI] Sound feedback: ON"), kind="info")
            self.play_ui_sound("notify")
        else:
            # 如果之前是开的，先给一个低一点的结束音
            if getattr(self, "sound_enabled", True):
                self.play_ui_sound("toggle")
            self.sound_enabled = False
            self.btn_sound.setIcon(getattr(self, "_icon_sound_off", self.btn_sound.icon()))
            self.console_print(self._t("[UI] 音效反馈：关闭", "[UI] Sound feedback: OFF"), kind="info")

    def _init_shortcuts(self):
        """常用快捷键（偏保守，避免和输入框冲突）。"""
        def add(seq: str, fn):
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(fn)
            self._shortcuts.append(sc)

        add("Ctrl+O", lambda: (self.play_ui_sound("click"), self.load_file()))
        add("Ctrl+E", lambda: (self.play_ui_sound("click"), self.export_data()))
        add("Ctrl+I", lambda: (self.play_ui_sound("click"), self.load_in_file_manual()))
        add("Ctrl+1", lambda: (self.play_ui_sound("toggle"), self.combo_view_mode.setCurrentIndex(0)))
        add("Ctrl+2", lambda: (self.play_ui_sound("toggle"), self.combo_view_mode.setCurrentIndex(1)))
        add("Ctrl+L", lambda: self.cmd_line.setFocus())
        add("F1", lambda: (self.play_ui_sound("notify"), self.show_shortcuts_help()))
        add("Ctrl+H", lambda: (self.play_ui_sound("toggle"), self.btn_ai_helper.setChecked(not self.btn_ai_helper.isChecked())))
        add("Ctrl+M", lambda: (self.play_ui_sound("toggle"), self.btn_fit_velocity.setChecked(not self.btn_fit_velocity.isChecked())))
        add("Ctrl+B", lambda: (self.play_ui_sound("toggle"), self.controls.chk_brush_2d.setChecked(not self.controls.chk_brush_2d.isChecked()) if hasattr(self, 'controls') and hasattr(self.controls, 'chk_brush_2d') else None))
        add("F5", lambda: (self.play_ui_sound("click"), self.run_pipeline(force_full=True)))

    def show_shortcuts_help(self):
        """把快捷键清单输出到下方控制台（不弹窗）。"""
        if getattr(I18n, "current_lang", "zh") == "en":
            lines = [
                "[UI] Shortcuts:",
                "  Ctrl+O   Open data file",
                "  Ctrl+E   Export processed outputs",
                "  Ctrl+I   Load .in model manually",
                "  Ctrl+1   Switch to single view",
                "  Ctrl+2   Switch to 4-view compare",
                "  Ctrl+L   Focus command line",
                "  Ctrl+H   Toggle AI helper panel",
                "  Ctrl+M   Toggle velocity-fit mode",
                "  Ctrl+B   Toggle 2D brush",
                "  F5       Force full re-run pipeline",
                "  F1       Show this help",
            ]
        else:
            lines = [
                "[UI] 快捷键：",
                "  Ctrl+O   打开数据文件",
                "  Ctrl+E   导出处理结果",
                "  Ctrl+I   手动加载 .in 模型",
                "  Ctrl+1   切到单图视图",
                "  Ctrl+2   切到四宫格对比",
                "  Ctrl+L   光标定位到命令行输入",
                "  Ctrl+H   切换 AI 小助手面板",
                "  Ctrl+M   切换速度拟合模式",
                "  Ctrl+B   切换 2D 画笔",
                "  F5       强制全流程重算一次",
                "  F1       显示本帮助",
            ]
        for s in lines:
            self.console_print(s, kind="hint")

    # ---------------- 多语言 ----------------
    def change_language(self, index: int):
        lang = "zh" if index == 0 else "en"
        I18n.set_language(lang)
        self.update_texts()

        if self.controls is None:
            return

        # 备份当前参数
        old_vals = self.controls.get_values()

        # 重建控件面板（让文字更新）
        self.controls.setParent(None)
        self.controls.deleteLater()

        self.controls = ControlPanel()
        self.controls.sig_params_changed.connect(self.on_params_changed)
        self.controls_scroll.setWidget(self.controls)

        # 2D 画笔：开关 & 清除
        self.controls.sig_brush_toggled.connect(self.on_brush_toggled)
        self.controls.sig_brush_cleared.connect(self.clear_brush)

        # 恢复参数
        self._restore_controls(old_vals)

        # 参数更新后，跑一次处理（不强制全重算）
        self.run_pipeline(force_full=False)

    def _place_ai_widget(self, do_raise: bool = False):
        """把 AI 小助手贴到 console_widget 右下角。

        注意：
        - raise_() 只在显示/首次摆放时做一次（do_raise=True），
          避免在 eventFilter 里反复 raise_() 导致 Z 序混乱。
        """
        if getattr(self, "console_widget", None) is None or getattr(self, "ai_widget", None) is None:
            return
        if not self.ai_widget.isVisible():
            return

        margin = 8
        size = self.ai_widget.sizeHint()
        x = self.console_widget.width() - size.width() - margin
        y = self.console_widget.height() - size.height() - margin
        self.ai_widget.move(max(0, x), max(0, y))
        # 若气泡可见，跟随更新位置
        if hasattr(self.ai_widget, 'update_bubble_pos'):
            self.ai_widget.update_bubble_pos()

        if do_raise:
            # 用 singleShot(0) 确保在布局/绘制之后再提到最上层
            QTimer.singleShot(0, self.ai_widget.raise_)


    def eventFilter(self, obj, event):
        # 当下方面板大小变化时，把小助手重新放在右下角
        if obj is getattr(self, "console_widget", None) and event.type() == QEvent.Type.Resize:
            if getattr(self, "ai_widget", None) is not None and self.ai_widget.isVisible():
                self._place_ai_widget(do_raise=False)
        return super().eventFilter(obj, event)

    def _refresh_placeholders(self):
        """Refresh placeholder text on canvases after language/view changes."""
        # Main canvas
        try:
            if getattr(self, "gpr_data", None) is None:
                self.canvas.show_placeholder()
        except Exception:
            pass

        # Compare panes: refresh empty slots
        try:
            if hasattr(self, "compare_view") and hasattr(self.compare_view, "panes"):
                for i, pane in enumerate(self.compare_view.panes):
                    slot_data = None
                    if hasattr(self, "view_slots") and self.view_slots and i < len(self.view_slots):
                        slot_data = getattr(self.view_slots[i], "data", None)
                    if slot_data is None:
                        pane.canvas.show_placeholder()
                        try:
                            pane.label.setText("")
                        except Exception:
                            pass
        except Exception:
            pass






    def update_texts(self):
        """根据当前语言刷新界面文字"""
        # 窗口标题
        self.setWindowTitle(I18n.tr('window_title'))

        # ---- Tooltips / menus (re-translate) ----
        if hasattr(self, "btn_open"):
            self.btn_open.setToolTip(I18n.tr('load_btn'))
        if hasattr(self, "btn_export"):
            self.btn_export.setToolTip(I18n.tr('export_btn'))
        if hasattr(self, "btn_load_in"):
            self.btn_load_in.setToolTip(I18n.tr('load_in_btn'))
        if hasattr(self, "btn_model2d"):
            self.btn_model2d.setToolTip(I18n.tr('show_model_btn'))
        if hasattr(self, "btn_model3d"):
            self.btn_model3d.setToolTip(I18n.tr('show_model3d_btn'))
        if hasattr(self, "btn_phys"):
            self.btn_phys.setToolTip(I18n.tr('edit_physical_tip'))
        if hasattr(self, "btn_fit_velocity"):
            self.btn_fit_velocity.setToolTip(I18n.tr('fit_velocity_tip'))
        if hasattr(self, "btn_ai_helper"):
            self.btn_ai_helper.setToolTip(I18n.tr('ai_helper_tip'))
        if hasattr(self, "btn_sound"):
            # sound tooltip depends on state
            tip = I18n.tr('sound_tip_on') if getattr(self, "_sound_enabled", True) else I18n.tr('sound_tip_off')
            self.btn_sound.setToolTip(tip)

        # Preset menu
        if hasattr(self, "menu_preset"):
            self.menu_preset.setTitle(I18n.tr('preset_menu_title'))
        for n in (1, 2, 3, 4):
            if hasattr(self, f"act_save_v{n}"):
                getattr(self, f"act_save_v{n}").setText(I18n.tr(f"preset_save_v{n}"))
            if hasattr(self, f"act_load_v{n}"):
                getattr(self, f"act_load_v{n}").setText(I18n.tr(f"preset_load_v{n}"))
        if hasattr(self, "act_save_params"):
            self.act_save_params.setText(I18n.tr('preset_save_params'))
        if hasattr(self, "act_load_params"):
            self.act_load_params.setText(I18n.tr('preset_load_params'))

        # Status bar
        if hasattr(self, "_status"):
            self._status.showMessage(I18n.tr('status_ready'))

        # 顶部图标按钮目前是 icon-only，只用 tooltip 就够了
        # 如果以后想做中英文 tooltip，可以在 init_ui 里把这些按钮存成 self.xxx，
        # 然后在这里用 setToolTip 更新；现在先不强求。
        # 例如：
        # if hasattr(self, "btn_open"):
        #     self.btn_open.setToolTip(I18n.tr('load_btn'))
        # if hasattr(self, "btn_export"):
        #     self.btn_export.setToolTip(I18n.tr('export_btn'))

        # 视图模式下拉框
        self.lbl_view_mode.setText(I18n.tr('lbl_view_mode'))

        current_mode = self.combo_view_mode.currentData()
        self.combo_view_mode.blockSignals(True)
        self.combo_view_mode.clear()
        self.combo_view_mode.addItem(I18n.tr('view_mode_single'), "single")
        self.combo_view_mode.addItem(I18n.tr('view_mode_compare4'), "compare4")
        if current_mode == "compare4":
            self.combo_view_mode.setCurrentIndex(1)
        else:
            self.combo_view_mode.setCurrentIndex(0)
        self.combo_view_mode.blockSignals(False)

        # 语言标签
        self.lbl_lang.setText(I18n.tr('lbl_language'))

        # 命令行输入提示
        if hasattr(self, 'cmd_line') and self.cmd_line is not None:
            self.cmd_line.setPlaceholderText(I18n.tr('cmd_placeholder'))

        # Refresh canvas placeholder texts after language switch
        self._refresh_placeholders()

    def _t(self, zh: str, en: str) -> str:
        """Tiny bilingual helper: choose text based on current language."""
        return en if getattr(I18n, 'current_lang', 'zh') == 'en' else zh


    def on_command_entered(self):
        """命令行回车时触发"""
        cmd = self.cmd_line.text().strip()
        if not cmd:
            return

        # 回显命令
        self.console_print(f">>> {cmd}", kind="cmd")
        self.cmd_line.clear()

        parts = cmd.split()
        name = parts[0].lower()
        args = parts[1:]

        # --------- 帮助 / 信息类 ---------
        if name in ("help", "h", "?"):
            topic = args[0] if args else ""
            self.show_help_topic(topic)

        elif name in ("clear", "cls"):
            self.txt_info.clear()

        elif name in ("info", "summary"):
            # 显示当前数据基本信息（你已有方法）
            self.update_info_display()

        # --------- 视图模式切换 ---------
        elif name == "view":
            if not args:
                self.console_print(self._t("[view] 用法：view single | view 4", "[view] Usage: view single | view 4"), kind="hint")
                return
            mode = args[0].lower()
            if mode in ("single", "1", "singleview"):
                # 单图
                self.combo_view_mode.setCurrentIndex(0)
                self.console_print(self._t("[view] 切换到：单图模式", "[view] Switched to: single view"), kind="info")
            elif mode in ("4", "compare", "compare4", "multi"):
                # 对比 4 图
                self.combo_view_mode.setCurrentIndex(1)
                self.console_print(self._t("[view] 切换到：对比4图模式", "[view] Switched to: 4-view compare"), kind="info")
            else:
                self.console_print(self._t(f"[view] 未知模式：{mode}", f"[view] Unknown mode: {mode}"), kind="warn")

        # --------- 界面语言切换 ---------
        elif name == "lang":
            if not args:
                self.console_print(self._t("[lang] 当前语言：", "[lang] Current language: ") + f"{self.combo_lang.currentText()}", kind="info")
                self.console_print(self._t("  用法：lang zh | lang en", "  Usage: lang zh | lang en"), kind="hint")
                return
            lang = args[0].lower()
            if lang in ("zh", "cn", "zh-cn", "chs", "ch"):
                self.combo_lang.setCurrentIndex(0)
                self.console_print(self._t("[lang] 切换语言：中文", "[lang] Switched: Chinese"), kind="info")
            elif lang in ("en", "eng", "english"):
                self.combo_lang.setCurrentIndex(1)
                self.console_print(self._t("[lang] 切换语言：English", "[lang] Switched: English"), kind="info")
            else:
                self.console_print(self._t(f"[lang] 未知语言：{lang}", f"[lang] Unknown language: {lang}"), kind="warn")

        # --------- 参数预设 / 视图槽位 ---------
        elif name == "preset":
            if len(args) < 2:
                self.console_print(
                    self._t(
                        "[preset] 用法：\n"
                        "  preset save 1..4   保存当前参数到视图1~4\n"
                        "  preset load 1..4   从视图1~4载入参数",
                        "[preset] Usage:\n"
                        "  preset save 1..4   save current params to view 1~4\n"
                        "  preset load 1..4   load params from view 1~4",
                    ),
                    kind="hint",
                )
                return

            sub = args[0].lower()
            slot_str = args[1]

            try:
                slot = int(slot_str) - 1
            except ValueError:
                self.console_print(self._t(f"[preset] 非法槽位：{slot_str}", f"[preset] Invalid slot: {slot_str}"), kind="warn")
                return

            if slot < 0 or slot > 3:
                self.console_print(self._t("[preset] 槽位必须是 1..4", "[preset] Slot must be 1..4"), kind="hint")
                return

            if sub in ("save", "s"):
                self.save_current_view_to_slot(slot)
                self.console_print(self._t(f"[preset] 已保存到视图{slot + 1}", f"[preset] Saved to view {slot + 1}"), kind="ok")
            elif sub in ("load", "l"):
                self.load_params_from_slot(slot)
                self.console_print(self._t(f"[preset] 已从视图{slot + 1}载入参数", f"[preset] Loaded from view {slot + 1}"), kind="ok")
            else:
                self.console_print(self._t(f"[preset] 未知子命令：{sub}", f"[preset] Unknown subcommand: {sub}"), kind="warn")

        # --------- 速度拟合工具开关 ---------
        elif name in ("fit", "vel"):
            if not args or args[0].lower() in ("toggle", "t"):
                # 切换当前状态
                self.btn_fit_velocity.setChecked(
                    not self.btn_fit_velocity.isChecked()
                )
                state = self._t("开启", "ON") if self.btn_fit_velocity.isChecked() else self._t("关闭", "OFF")
                self.console_print(self._t(f"[fit] 已{state}速度拟合模式", f"[fit] Velocity fitting: {state}"), kind="info")
            else:
                sw = args[0].lower()
                if sw in ("on", "1", "true", "yes"):
                    self.btn_fit_velocity.setChecked(True)
                    self.console_print(self._t("[fit] 已开启速度拟合模式", "[fit] Velocity fitting enabled"), kind="info")
                elif sw in ("off", "0", "false", "no"):
                    self.btn_fit_velocity.setChecked(False)
                    self.console_print(self._t("[fit] 已关闭速度拟合模式", "[fit] Velocity fitting disabled"), kind="info")
                else:
                    self.console_print(
                        self._t(
                            "[fit] 用法：\n"
                            "  fit on / fit off\n"
                            "  fit        (在开/关之间切换)",
                            "[fit] Usage:\n"
                            "  fit on / fit off\n"
                            "  fit        (toggle on/off)",
                        ),
                        kind="hint",
                    )

        # --------- 模型视图调用 ---------
        elif name == "model":
            sub = args[0].lower() if args else "2d"
            if sub in ("2d", "model", "geo"):
                self.show_model_view()
                self.console_print("[model] 打开二维模型/真值视图", kind="warn")
            elif sub in ("3d", "vol"):
                self.show_model3d_view()
                self.console_print("[model] 打开 3D 模型视图", kind="warn")
            else:
                self.console_print(
                    "[model] 用法：model 2d | model 3d", kind="warn"
                )
        elif name == "ai":
            # 命令行 AI 小助手：ai suggest / ai gain / ai basic / ai bg / ai off
            sub = args[0].lower() if args else "suggest"

            # 确保面板显示
            if hasattr(self, "btn_ai_helper"):
                self.btn_ai_helper.setChecked(True)

            if sub in ("suggest", "s"):
                text = self.ai_build_suggestion()
                if hasattr(self, "ai_widget") and self.ai_widget is not None:
                    self.ai_widget.set_message(text, mood="info")
                for line in text.splitlines():
                    self.console_print(f"[AI] {line}", kind="ai")

            elif sub in ("gain", "explain_gain"):
                text = self.ai_explain_gain()
                if hasattr(self, "ai_widget") and self.ai_widget is not None:
                    self.ai_widget.set_message(text, mood="info")
                for line in text.splitlines():
                    self.console_print(f"[AI] {line}", kind="ai")

            elif sub in ("basic", "explain_basic"):
                text = self.ai_explain_basic()
                if hasattr(self, "ai_widget") and self.ai_widget is not None:
                    self.ai_widget.set_message(text, mood="info")
                for line in text.splitlines():
                    self.console_print(f"[AI] {line}", kind="ai")

            elif sub in ("bg", "background"):
                text = self.ai_explain_bg()
                if hasattr(self, "ai_widget") and self.ai_widget is not None:
                    self.ai_widget.set_message(text, mood="info")
                for line in text.splitlines():
                    self.console_print(f"[AI] {line}", kind="ai")

            elif sub in ("off", "hide"):
                if hasattr(self, "btn_ai_helper"):
                    self.btn_ai_helper.setChecked(False)
            else:
                self.console_print(self._t("[ai] 用法：", "[ai] Usage:"), kind="hint")
                self.console_print(self._t("  ai suggest        - 综合看一眼当前参数是否合理", "  ai suggest        - overall parameter suggestions"), kind="hint")
                self.console_print(self._t("  ai gain           - 专门解释增益相关设置", "  ai gain           - explain gain settings"), kind="hint")
                self.console_print(self._t("  ai basic          - 解释基础处理设置", "  ai basic          - explain basic processing"), kind="hint")
                self.console_print(self._t("  ai bg             - 解释空间/背景处理设置", "  ai bg             - explain background removal"), kind="hint")
                self.console_print(self._t("  ai off            - 隐藏小助手面板", "  ai off            - hide AI panel"), kind="hint")

        # --------- 未知命令 ---------
        else:
            self.console_print(self._t(f"[help] 未知命令：{name}", f"[help] Unknown command: {name}"), kind="warn")
            self.console_print(self._t("  输入 help 查看可用命令。", "  Type help to list commands."), kind="hint")

    def console_print(self, text: str, kind: str = "out"):
        """
        在控制台输出一行文字，并根据 kind 设置颜色/样式。
        kind:
          - "cmd"   : 用户输入的命令 (>>> ...)
          - "info"  : 提示信息 / 正常输出
          - "warn"  : 警告
          - "err"   : 错误
          - 其他    : 默认样式
        """
        cursor = self.txt_info.textCursor()
        cursor.movePosition(QTextCursor.End)

        fmt = self.txt_info.currentCharFormat()

        if kind == "cmd":
            # 用户输入命令：淡橙色
            fmt.setForeground(QColor("#FFCC80"))
            fmt.setFontWeight(QFont.Bold)

        elif kind in ("ai",):
            # AI 输出：浅蓝
            fmt.setForeground(QColor("#81D4FA"))
            fmt.setFontWeight(QFont.Normal)

        elif kind in ("hint",):
            # 引导/说明：青色
            fmt.setForeground(QColor("#80DEEA"))
            fmt.setFontWeight(QFont.Bold)

        elif kind in ("ok",):
            # 成功：浅绿
            fmt.setForeground(QColor("#A5D6A7"))
            fmt.setFontWeight(QFont.Bold)

        elif kind == "info":
            # 普通信息：浅灰白
            fmt.setForeground(QColor("#ECEFF1"))
            fmt.setFontWeight(QFont.Normal)

        elif kind == "warn":
            # 警告：橙色
            fmt.setForeground(QColor("#FFB74D"))
            fmt.setFontWeight(QFont.Bold)

        elif kind == "err":
            # 错误：红色
            fmt.setForeground(QColor("#EF5350"))
            fmt.setFontWeight(QFont.Bold)

        else:
            fmt.setForeground(QColor("#ECEFF1"))
            fmt.setFontWeight(QFont.Normal)
        cursor.setCharFormat(fmt)
        cursor.insertText(text + "\n")
        self.txt_info.setTextCursor(cursor)
        self.txt_info.ensureCursorVisible()


    def show_help_topic(self, topic: str = ""):
        """在控制台输出帮助信息（中英双语）。"""
        topic = (topic or "").lower().strip()
        lang = getattr(I18n, "current_lang", "zh")

        help_zh = {
            "": """
[help] GPR Studio 控制台命令总览

基础命令：
  help / help <topic>      查看帮助（topic: basic / gain / bg / ai）
  clear / cls              清空控制台
  info                     输出当前数据摘要

视图与语言：
  view single | view 4     切换视图模式
  lang zh | lang en        切换界面语言

工具与功能：
  fit on/off               速度拟合工具（也可 Ctrl+M）
  model 2d / model 3d      打开二维/三维模型/真值视图
  ai suggest/gain/basic/bg AI 参数解释（输出到下方控制台）
""",
            "basic": """
[basic] 基础处理相关

- T0 校正（Auto）：自动 time-zero，对齐直达波/界面
- 去低频（Dewow）：去除低频漂移（窗口越大越平滑）
- 顶部静音：把浅层直达波/耦合噪声衰减掉（慎用）
""",
            "gain": """
[gain] 增益与显示相关

- Linear Gain (alpha)：随深度线性放大
- Exp Gain (beta)：随深度指数放大（容易炸噪）
- AGC：自动增益控制（窗口 ns）
- Contrast Clip：按百分位裁剪对比度（如 99.0~99.8）
""",
            "bg": """
[bg] 空间/背景处理

- Mean / Median 背景去除：按列/滑窗估计背景并相减
- 背景窗（trace）：窗口越大越“稳”，越小越“灵”
""",
            "ai": """
[ai] AI 小助手

- ai suggest：综合给出调参建议
- ai gain：解释增益相关
- ai basic：解释基础处理
- ai bg：解释背景处理
（所有输出只写到下方控制台，不弹气泡）
""",
        }

        help_en = {
            "": """
[help] GPR Studio console commands

Basics:
  help / help <topic>      Help (topic: basic / gain / bg / ai)
  clear / cls              Clear console
  info                     Print current data summary

View & language:
  view single | view 4     Switch view mode
  lang zh | lang en        Switch UI language

Tools:
  fit on/off               Velocity fitting tool (or Ctrl+M)
  model 2d / model 3d      Open 2D / 3D model & truth view
  ai suggest/gain/basic/bg AI parameter explanations (to console)
""",
            "basic": """
[basic] Basic processing

- T0 correction (Auto): time-zero alignment (direct wave / interface)
- Dewow: remove low-frequency drift (larger window = smoother)
- Top mute: attenuate shallow direct-wave/coupling (use carefully)
""",
            "gain": """
[gain] Gain & display

- Linear Gain (alpha): depth-linear amplification
- Exp Gain (beta): depth-exponential amplification (can amplify noise)
- AGC: automatic gain control (window in ns)
- Contrast Clip: percentile clipping for contrast (e.g., 99.0~99.8)
""",
            "bg": """
[bg] Spatial / background removal

- Mean / Median background: estimate background and subtract
- Background window (traces): larger = steadier, smaller = more sensitive
""",
            "ai": """
[ai] AI helper

- ai suggest: overall parameter suggestions
- ai gain: explain gain settings
- ai basic: explain basic processing
- ai bg: explain background processing
(All outputs go to the console only; no speech bubbles.)
""",
        }

        bundle = help_en if lang == "en" else help_zh

        text = bundle.get(topic)
        if text is None:
            self.console_print(
                self._t(f"[help] 未知主题：{topic}", f"[help] Unknown topic: {topic}"),
                kind="warn",
            )
            self.console_print(
                self._t("  输入 help 查看可用命令。", "  Type help to list commands."),
                kind="hint",
            )
            return

        for line in text.strip("\n").splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith(("[help]", "[basic]", "[gain]", "[bg]", "[ai]")):
                self.console_print(line, kind="hint")
            else:
                self.console_print(line, kind="info")


    def toggle_ai_helper(self, checked: bool):
        """
        顶部按钮控制：显示 / 隐藏 AI 小助手面板。
        """
        if not hasattr(self, "ai_widget") or self.ai_widget is None:
            return

        if checked:
            self.ai_widget.show()
            self._place_ai_widget(do_raise=True)
            msg = self._t("已启动调参小助手，可以在命令行输入：ai suggest / ai gain 等。",
                            "AI helper enabled. Try commands: ai suggest / ai gain, etc.")
            self.ai_widget.set_message(msg, mood="info")
            self.console_print(self._t("[AI] 调参小助手已开启。", "[AI] AI helper enabled."), kind="info")
        else:
            self.ai_widget.hide()
            if hasattr(self.ai_widget, 'hide_bubble'):
                self.ai_widget.hide_bubble()
            self.console_print(self._t("[AI] 调参小助手已关闭。", "[AI] AI helper disabled."), kind="info")
    # ---------------- AI 助手：规则 + 建议 ----------------

    def ai_build_suggestion(self) -> str:
        """
        读取当前参数 + 数据，给出一小段文字建议。
        不接 LLM，完全是规则+模板。
        """
        p = self.controls.get_values()
        g = self.gpr_data

        lines: list[str] = []

        # 1) 基本信息
        if g is None or g.raw_data is None:
            eps_ui = float(p.get("eps", 6.0))
            lines.append(f"目前还没有加载数据，我只能根据面板参数给点建议。")
            lines.append(f"背景介质 εr≈{eps_ui:.2f}，Dewow 窗={p.get('dewow_win_ns', 6.0)} ns，"
                         f"背景方法={p.get('bg_method','none')}。")
        else:
            eps = float(getattr(g, "eps_bg", p.get("eps", 6.0)))
            dt = float(getattr(g, "dt", 1e-10))
            nt, nx = g.raw_data.shape
            c = 0.299792458
            v = c / np.sqrt(max(eps, 1e-6))
            max_depth = nt * dt * 1e9 * v / 2.0  # m

            lines.append(f"当前数据：{nt}×{nx} 道，dt≈{dt*1e9:.3f} ns，dx≈{getattr(g,'dx',0.0):.3f} m，"
                         f"背景 εr≈{eps:.2f}，最大理论探测深度≈{max_depth:.2f} m。")

            if max_depth < 0.5:
                lines.append("最大深度不到 0.5 m，偏浅，如果你关注 0.8 m 目标，采样时间窗可能偏短。")
            elif max_depth > 3.0:
                lines.append("时间窗对应深度已经很深了，浅层目标只占很少部分，可以配合顶部静音压掉无效深度。")

        # 2) Dewow / 背景
        if p.get("dewow", False):
            win = float(p.get("dewow_win_ns", 6.0))
            if win < 2.0:
                lines.append(f"Dewow 窗口仅 {win:.1f} ns，会比较激进，通常 3~8 ns 会更稳妥一些。")
        else:
            lines.append("当前关闭 Dewow，如果低频漂移明显，可以考虑勾选 Dewow 再看一眼波形。")

        bg_method = p.get("bg_method", "none")
        bg_win = int(p.get("bg_win", 0))
        if bg_method == "none":
            lines.append("没有做空间背景去除，如果画面有强烈的水平条带，可以尝试 Mean / Median 背景。")
        else:
            if bg_win < 10:
                lines.append(f"空间背景窗口只有 {bg_win} 道，可能会把目标也一并减掉，可以试试加大到 30~80。")

        # 3) 增益 / AGC
        if not p.get("gain_on", False) and p.get("agc_win", 0) <= 0:
            lines.append("时间增益和 AGC 都是关闭的，深部反射会比较暗。")
        else:
            alpha = float(p.get("gain_alpha", 0.0))
            beta = float(p.get("gain_beta", 0.0))
            agc = float(p.get("agc_win", 0.0))
            if p.get("gain_on", False):
                lines.append(f"已启用时间增益：线性 α={alpha:.3g}，指数 β={beta:.3g}。")
            if agc > 0:
                lines.append(f"AGC 窗口={agc:.1f} ns，注意窗口过大会让强弱反射对比变小。")

        # 4) 带通 / 平滑
        if p.get("use_bp", False):
            low = float(p.get("bp_low", 0.0))
            high = float(p.get("bp_high", 0.0))
            if high > 0 and low > 0 and high / max(low, 1e-6) < 1.3:
                lines.append(f"带通频带 [{low:.1f},{high:.1f}] MHz 很窄，可能会把波形拉得过于平滑。")
        else:
            lines.append("当前没有带通滤波，如果原始数据高频噪声比较多，可以考虑开一个宽带通。")

        if int(p.get("smooth_x", 0)) > 0:
            lines.append(f"横向平滑窗口={p.get('smooth_x')}，注意过大会模糊目标边缘。")

        # 5) 简单看一下深浅层能量对比
        if g is not None and getattr(g, "processed_data", None) is not None:
            arr = np.abs(g.processed_data.astype(float))
            nt, nx = arr.shape
            n_seg = max(10, nt // 6)
            top_mean = float(arr[:n_seg, :].mean())
            bottom_mean = float(arr[-n_seg:, :].mean())
            if top_mean > 0:
                ratio = bottom_mean / top_mean
                if ratio < 0.2 and not p.get("gain_on", False):
                    lines.append("从当前处理结果看，深部反射能量只有浅部的约 "
                                 f"{ratio*100:.0f}% ，可以适当开启增益或调大 AGC。")

        if not lines:
            lines.append("当前参数看起来比较正常，可以先看几组不同背景/增益组合再微调。")

        return "\n".join(lines)
    def ai_explain_gain(self) -> str:
        p = self.controls.get_values()
        on = p.get("gain_on", False)
        alpha = float(p.get("gain_alpha", 0.0))
        beta = float(p.get("gain_beta", 0.0))
        agc = float(p.get("agc_win", 0.0))

        lines = []
        lines.append("增益模块当前设置：")
        lines.append(f"  • Enable Gain : {'开启' if on else '关闭'}")
        lines.append(f"  • 线性增益 α : {alpha:.3g}")
        lines.append(f"  • 指数增益 β : {beta:.3g}")
        lines.append(f"  • AGC 窗口   : {agc:.1f} ns")
        lines.append("")
        lines.append("经验小贴士：")
        lines.append("  - 通常只需要一种“强”增益：要么指数 β，要么 AGC，不必全都拉很大；")
        lines.append("  - β 太大时深部会被放得很亮，但噪声也会被一起放大；")
        lines.append("  - AGC 窗口越大，对比度越平均，极强/极弱反射的差异会被削弱。")
        return "\n".join(lines)

    def ai_explain_basic(self) -> str:
        p = self.controls.get_values()
        dc = float(p.get("dc_ns", 0.0))
        dewow_on = p.get("dewow", False)
        dewow_win = float(p.get("dewow_win_ns", 6.0))
        mute_ns = float(p.get("mute_ns", 0.0))

        lines = []
        lines.append("基础处理当前设置：")
        lines.append(f"  • DC Win       : {dc:.1f} ns")
        lines.append(f"  • Time-zero    : {'自动对齐已开启' if p.get('t0_auto', False) else '关闭'}")
        lines.append(f"  • Dewow        : {'开启' if dewow_on else '关闭'} (窗={dewow_win:.1f} ns)")
        lines.append(f"  • 顶部静音窗   : {mute_ns:.1f} ns")
        lines.append("")
        lines.append("建议：")
        if dc == 0:
            lines.append("  - DC Win=0 表示不做直流校正，如果每道开头有偏移，可以试着给 5~15 ns；")
        if not dewow_on:
            lines.append("  - 没有 Dewow 时，超慢变化的漂移会保留下来，容易导致色条/背景倾斜；")
        else:
            if dewow_win < 2:
                lines.append("  - Dewow 窗低于 2 ns，可能过于激进；一般 3~8 ns 比较常用。")
        if mute_ns > 0:
            lines.append("  - 你启用了顶部静音，可以用来压掉空气层/直达波的强反射。")
        else:
            lines.append("  - 如需压掉直达波，可适当设置顶部静音窗口。")
        return "\n".join(lines)

    def ai_explain_bg(self) -> str:
        p = self.controls.get_values()
        method = p.get("bg_method", "none")
        win = int(p.get("bg_win", 0))

        lines = []
        lines.append("空间/背景处理当前设置：")
        lines.append(f"  • 方法   : {method}")
        lines.append(f"  • 窗口   : {win} 道")
        lines.append("")
        if method == "none":
            lines.append("你目前没有做空间背景去除，如果画面里有大面积的水平条纹，可以尝试 'Mean' 或 'Median'。")
        else:
            lines.append("一般经验：")
            lines.append("  - 'Mean' 对连续背景有效，但容易受极强反射影响；")
            lines.append("  - 'Median' 更抗孤立强反射；")
            lines.append("  - 窗口太小会把目标也减掉，太大会导致大尺度趋势被抹平。")
        return "\n".join(lines)


    def _restore_controls(self, vals: dict):
        if not vals:
            return
        p = vals

        # Basic
        self.controls.spin_dc_ns.setValue(p.get("dc_ns", self.controls.spin_dc_ns.value()))
        self.controls.chk_t0.setChecked(p.get("t0_auto", self.controls.chk_t0.isChecked()))
        self.controls.chk_dewow.setChecked(p.get("dewow", self.controls.chk_dewow.isChecked()))
        self.controls.spin_dewow_win.setValue(
                      p.get("dewow_win_ns", self.controls.spin_dewow_win.value())
          )  # 新增
        self.controls.spin_mute_ns.setValue(p.get("mute_ns", self.controls.spin_mute_ns.value()))
        self.controls.spin_eps.setValue(p.get("eps", self.controls.spin_eps.value()))

        # Spatial
        if "bg_method" in p:
            target = p["bg_method"]
            idx = 0
            for i in range(self.controls.combo_bg.count()):
                if self.controls.combo_bg.itemData(i) == target:
                    idx = i
                    break
            self.controls.combo_bg.setCurrentIndex(idx)
        self.controls.spin_bg_win.setValue(p.get("bg_win", self.controls.spin_bg_win.value()))

        # Gain
        self.controls.chk_gain.setChecked(p.get("gain_on", self.controls.chk_gain.isChecked()))
        self.controls.spin_alpha.setValue(p.get("gain_alpha", self.controls.spin_alpha.value()))
        self.controls.spin_beta.setValue(p.get("gain_beta", self.controls.spin_beta.value()))
        self.controls.spin_agc.setValue(p.get("agc_win", self.controls.spin_agc.value()))

        # Filter
        self.controls.chk_bp.setChecked(p.get("use_bp", self.controls.chk_bp.isChecked()))
        self.controls.spin_bp_low.setValue(p.get("bp_low", self.controls.spin_bp_low.value()) / 1e6)
        self.controls.spin_bp_high.setValue(p.get("bp_high", self.controls.spin_bp_high.value()) / 1e6)
        self.controls.spin_smooth.setValue(p.get("smooth_x", self.controls.spin_smooth.value()))

        # F-K
        self.controls.chk_fk.setChecked(p.get("fk_enabled", self.controls.chk_fk.isChecked()))
        self.controls.spin_fk_kmin.setValue(p.get("fk_kmin", self.controls.spin_fk_kmin.value()))
        self.controls.spin_fk_kmax.setValue(p.get("fk_kmax", self.controls.spin_fk_kmax.value()))
        self.controls.spin_fk_fmin.setValue(p.get("fk_fmin_mhz", self.controls.spin_fk_fmin.value()))
        self.controls.spin_fk_fmax.setValue(p.get("fk_fmax_mhz", self.controls.spin_fk_fmax.value()))

        # Display
        self.controls.chk_show_raw.setChecked(p.get("show_raw", self.controls.chk_show_raw.isChecked()))
        self.controls.chk_env.setChecked(p.get("show_env", self.controls.chk_env.isChecked()))
        self.controls.spin_clip.setValue(p.get("clip", self.controls.spin_clip.value()))
        if "cmap" in p:
            idx = self.controls.combo_cmap.findText(p["cmap"])
            if idx >= 0:
                self.controls.combo_cmap.setCurrentIndex(idx)

    # ---------------- 信息栏 ----------------
    def update_info_display(self):
        if self.gpr_data is None:
            self.txt_info.clear()
            self.update_status_bar()
            return

        g = self.gpr_data
        lines = []

        if g.filename:
            lines.append(f"File: {Path(g.filename).name}")

        if getattr(g, "dx", None) is not None:
            lines.append(f"dx (trace step): {g.dx:.4f} m")
        if getattr(g, "eps_bg", None) is not None:
            lines.append(f"Background er: {g.eps_bg:.3f}")
        if getattr(g, "fc", None) is not None:
            lines.append(f"fc: {g.fc/1e6:.1f} MHz")
        if getattr(g, "dt", None) is not None:
            lines.append(f"dt: {g.dt*1e9:.3f} ns")
        if getattr(g, "domain", None) is not None:
            X, Y, Z = g.domain
            lines.append(f"Domain: X={X:.2f} m, Y={Y:.2f} m, Z={Z:.2f} m")
        if getattr(g, "grid_dims", None) is not None:
            dx, dy, dz = g.grid_dims
            lines.append(f"Grid: dx={dx*1e3:.1f} mm, dy={dy*1e3:.1f} mm, dz={dz*1e3:.1f} mm")

        if g.raw_data is not None:
            nt, nx = g.raw_data.shape
            lines.append(f"Data shape: Nt={nt}, Nx={nx}")
        if getattr(g, "eps_bg", None) is not None:
            self.controls.spin_eps.setValue(float(g.eps_bg))

        if getattr(g, "fc", None):
            fc_mhz = g.fc / 1e6
            low_mhz = 0.4 * fc_mhz
            high_mhz = 1.6 * fc_mhz
            self.controls.spin_bp_low.setValue(low_mhz)
            self.controls.spin_bp_high.setValue(high_mhz)
        
        self.update_bg_material_combo()
        self.txt_info.setPlainText("\n".join(lines))
        self.update_status_bar()
    def update_status_bar(self, extra: str = ""):
        if not hasattr(self, "_status"):
            return

        parts = []

        g = self.gpr_data
        if g is not None:
        # 不要用 "or" 链接 numpy 数组，会触发 ValueError
            arr = getattr(g, "raw_data", None)
            if arr is None:
               arr = getattr(g, "processed_data", None)

            if arr is not None:
                try:
                  nt, nx = arr.shape[:2]
                  parts.append(f"{nt}×{nx}")
                except Exception:
                    pass

            dt = getattr(g, "dt", None)
            dx = getattr(g, "dx", None)
            eps = getattr(g, "eps_bg", None)

            if dt is not None:
                parts.append(f"dt={dt * 1e9:.3f} ns")
            if dx is not None:
                parts.append(f"dx={dx:.3f} m")
            if eps is not None:
                parts.append(f"εr={float(eps):.2f}")

            filename = getattr(g, "filename", None)
            if filename:
                parts.insert(0, Path(filename).name)

        if extra:
            parts.append(extra)
   
        msg = "   |   ".join(parts) if parts else (extra or "Ready")
        self._status.showMessage(msg)
 
    def update_bg_material_combo(self):
        """根据当前 in_info 填充背景材料下拉框，并选择一个合理的默认值。"""
        if self.gpr_data is None or self.gpr_data.in_info is None:
            # 没有 in 信息，就只保留“自动/自定义”
            if hasattr(self.controls, "set_materials"):
                self.controls.set_materials({}, None)
            return

        info = self.gpr_data.in_info
        materials = info.get("materials", {}) or {}

        # 尝试根据 eps_bg 找到一个匹配的材料名
        default_name = None
        eps_bg = getattr(self.gpr_data, "eps_bg", None)
        if eps_bg is not None and materials:
            for name, m in materials.items():
                if isinstance(m, dict) and "epsr" in m:
                    if abs(float(m["epsr"]) - float(eps_bg)) < 1e-6:
                        default_name = name
                        break

        if hasattr(self.controls, "set_materials"):
            self.controls.set_materials(materials, default_name)


    # ---------------- 文件加载 ----------------
    def load_file(self):
        # 1. 过滤器配置
        filters = I18n.tr("load_filters")
        path, _ = QFileDialog.getOpenFileName(
            self, "加载 GPR 数据", "", filters
        )
        if not path:
            return

        try:
            p = Path(path)
            
            # --- 分支 A0: 处理 .zip 可复现包 ---
            if p.suffix.lower() == '.zip':
                g = load_repro_package(p)

            # --- 分支 A: 处理 .npy 文件 ---
            elif p.suffix.lower() == '.npy':
                # 1. 先用 loader 尝试加载
                g = load_npy_file(p)
                
                # 2. 检查是否缺失关键物理参数 (in_info 为空说明是纯数据，非 GPR_Studio 导出)
                #    且 dt 为默认极小值 1e-10 (loader 里的兜底值)
                is_pure_data = (g.in_info is None)
                
                if is_pure_data:
                    # 3. 弹出参数设置对话框
                    # g.raw_data.shape 应该是 (950, 226)
                    dlg = NpyParamsDialog(g.raw_data.shape, self)
                    
                    # 可以在这里预设一些值，如果知道文件名规律 (比如包含 '0.025')
                    # dlg.spin_dx.setValue(0.025) 
                    
                    if dlg.exec() == QDialog.DialogCode.Accepted:
                        vals = dlg.get_values()
                        g.dx = vals['dx']
                        g.dt = vals['dt']
                        g.eps_bg = vals['eps_bg']
                        
                        # 重要：更新 metadata 方便导出
                        self.console_print(f"已手动应用参数: dx={g.dx:.3f}m, dt={g.dt*1e9:.3f}ns", kind="warn")
                    else:
                        # 用户取消，终止加载
                        return

            # --- 分支 B: 处理 .out 文件 (标准流程) ---
            else:
                g = load_out_file(p)
                
        except Exception as e:
            QMessageBox.critical(self, self._t("加载失败","Load Failed"), str(e))
            return

        # --- 通用后处理 ---
# [修改这里]：加载成功后的处理
        self.gpr_data = g
        self._last_heavy_params = None
        self._last_heavy_data = None
        
        # ★★★ 关键修复：强制清除旧的绘图范围缓存 ★★★
        self.current_extent = None 
        
        # ★★★ 关键修复：彻底清空画布，防止旧图残留 ★★★
        self.canvas.ax.clear()
        self.canvas.draw()

        self.update_info_display()
        
        # 强制运行全流程，这会触发 update_plot 重新画图
        self.run_pipeline(force_full=True)

    def load_in_file_manual(self):
        if self.gpr_data is None:
            QMessageBox.warning(self, self._t("提示","Warning"), "请先加载 .out 主数据文件")
            return

        in_path, _ = QFileDialog.getOpenFileName(
            self, "Load .in Model", "", "Input File (*.in)"
        )
        if not in_path:
            return

        try:
            info = parse_in_file(Path(in_path))
            g = self.gpr_data

            if "eps_bg" in info:
                g.eps_bg = info["eps_bg"]
            if "trace_step" in info:
                g.dx = info["trace_step"]
            if "waveform" in info and "fc" in info["waveform"]:
                g.fc = info["waveform"]["fc"]
            if "domain" in info:
                g.domain = info["domain"]
            g.in_info = info

            g.in_path = info.get("in_path", str(in_path))  # ★ 新增

            self._last_heavy_params = None
            self._last_heavy_data = None
            self.current_extent = None

            self.update_info_display()
            self.run_pipeline(force_full=False)
            QMessageBox.information(self, "成功", "已用 .in 文件更新物理参数")
        except Exception as e:
            QMessageBox.critical(self, self._t("解析错误","Parse Error"), str(e))

# ---------------- 数据导出 ----------------
    def export_data(self):


        # 若当前是对比模式，则导出多视图
        try:
            mode = self.combo_view_mode.currentData()
        except Exception:
            mode = "single"

        if mode == "compare4":
            self.export_compare_views()
            return
        if self.gpr_data is None or self.gpr_data.processed_data is None:
            QMessageBox.warning(self, I18n.tr("export_warn_title"), I18n.tr("export_warn_nodata"))
            return

        # 弹出保存对话框
        filters = I18n.tr("export_filters_single")
        path, selected_filter = QFileDialog.getSaveFileName(
            self, I18n.tr("export_dialog_title"), "result", filters
        )
        if not path:
            return

        try:
            if "Image" in selected_filter:
                # 导出图片：直接利用 canvas 绘图结果
                exporter.export_image(self.canvas, path)
            elif "MATLAB" in selected_filter:
                exporter.export_to_mat(self.gpr_data, path)
            elif "zip" in selected_filter.lower():
                # 可复现包：包含 raw/heavy/processed + params/meta + preview
                params = self.controls.get_values() if self.controls is not None else {}
                raw = getattr(self.gpr_data, "raw_data", None)
                heavy = getattr(self, "_last_heavy_data", None)
                extra = {
                    "view_mode": str(self.combo_view_mode.currentData()) if hasattr(self, "combo_view_mode") else "single",
                    "current_extent": list(self.current_extent) if getattr(self, "current_extent", None) is not None else None,
                }
                exporter.export_reproducible_package(
                    self.gpr_data,
                    path,
                    params=params,
                    raw_data=raw,
                    heavy_data=heavy,
                    canvas=self.canvas,
                    extra_meta=extra,
                )
            else:
                # 默认 npy
                exporter.export_to_npy(self.gpr_data, path)
            
            QMessageBox.information(self, I18n.tr("export_success_title"), f"{I18n.tr('export_success_title')}\n\n{path}")
        except Exception as e:
            QMessageBox.critical(self, I18n.tr("export_fail_title"), str(e))
    
# [ui/main_window.py] -> MainWindow 类内部

    # ... (放在其他方法附近，比如 export_data 后面)

    def edit_physical_params(self):
        """
        弹出对话框，允许用户重新修改 dt, dx, eps_bg 等物理参数。
        """
        if self.gpr_data is None or self.gpr_data.raw_data is None:
            QMessageBox.warning(self, self._t("提示","Warning"), "请先加载数据")
            return

        # 1. 创建对话框，传入当前数据的形状
        nt, nx = self.gpr_data.raw_data.shape
        # 确保已导入 NpyParamsDialog
        from ui.dialogs import NpyParamsDialog 
        dlg = NpyParamsDialog((nt, nx), self)
        
        # 2. 【关键】将当前的参数值预填到对话框中 (反向回填)
        # 注意：dt 要从秒转回纳秒 (ns)
        current_dt_ns = getattr(self.gpr_data, "dt", 1e-10) * 1e9
        current_dx = getattr(self.gpr_data, "dx", 0.025)
        current_eps = getattr(self.gpr_data, "eps_bg", 6.0)
        
        dlg.spin_dt.setValue(current_dt_ns)
        dlg.spin_dx.setValue(current_dx)
        dlg.spin_eps.setValue(current_eps)
        
        # 3. 运行对话框
        if dlg.exec() == QDialog.DialogCode.Accepted:
            vals = dlg.get_values()
            
            # 4. 更新数据模型
            self.gpr_data.dx = vals['dx']
            self.gpr_data.dt = vals['dt']
            self.gpr_data.eps_bg = vals['eps_bg']
            
            # 5. 强制刷新界面
            self.console_print(
                f"== 参数已更新 ==\n"
                f"dx: {self.gpr_data.dx:.4f} m\n"
                f"dt: {self.gpr_data.dt*1e9:.4f} ns\n"
                f"εr: {self.gpr_data.eps_bg:.2f}", kind="warn"
            )
            
            # 清除当前的绘图范围缓存，强制重新计算坐标轴
            self.current_extent = None 
            self.update_info_display()
            self.run_pipeline(force_full=True)

    def export_compare_views(self):
        """在对比 4 图模式下导出选中的视图（图片 + 参数 JSON）"""

        # 哪些视图槽里有数据
        available = [i for i, slot in enumerate(self.view_slots) if slot.data is not None]
        if not available:
            zh = (I18n.current_lang == "zh")
            QMessageBox.warning(
                self,
                "提示" if zh else "Notice",
                "还没有保存到任何视图，请先点击“保存到视图1~4”按钮。" if zh
                else "No compare views saved yet."
            )
            return

        zh = (I18n.current_lang == "zh")

        # === 1) 选择要导出的视图 ===
        dlg = QDialog(self)
        dlg.setWindowTitle("导出对比视图" if zh else "Export Compare Views")
        vbox = QVBoxLayout(dlg)

        label = QLabel("请选择要导出的视图：" if zh else "Select views to export:")
        vbox.addWidget(label)

        checkboxes = []
        for i in range(4):
            text = f"视图 {i+1}" if zh else f"View {i+1}"
            cb = QCheckBox(text)
            if i in available:
                cb.setChecked(True)
            else:
                cb.setChecked(False)
                cb.setEnabled(False)
            vbox.addWidget(cb)
            checkboxes.append(cb)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        vbox.addWidget(btn_box)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        selected = [i for i, cb in enumerate(checkboxes) if cb.isChecked()]
        if not selected:
            return

        # === 2) 选择输出文件夹 ===
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择导出文件夹" if zh else "Select output folder",
            ""
        )
        if not folder:
            return

        out_dir = Path(folder)

        # === 3) 逐个视图导出图片 + 参数 JSON ===
        exported_count = 0

        for i in selected:
            slot = self.view_slots[i]
            if slot.data is None:
                continue

            # 图片文件
            img_name = f"View{i+1}.png"
            img_path = out_dir / img_name

            canvas = self.compare_view.panes[i].canvas
            try:
                exporter.export_image(canvas, img_path)
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "导出失败" if zh else "Export Failed",
                    f"视图 {i+1} 图片导出失败:\n{e}" if zh else f"Failed to export view {i+1} image:\n{e}",
                )
                continue

            # 参数 JSON
            params = slot.params or {}
            meta = {}
            if self.gpr_data is not None:
                meta = {
                    "dt": getattr(self.gpr_data, "dt", None),
                    "dx": getattr(self.gpr_data, "dx", None),
                    "eps_bg": getattr(self.gpr_data, "eps_bg", None),
                    "fc": getattr(self.gpr_data, "fc", None),
                    "source_file": str(getattr(self.gpr_data, "filename", "")),
                }

            payload = {"params": params, "meta": meta}
            json_path = out_dir / f"View{i+1}_params.json"
            try:
                with json_path.open("w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "导出失败" if zh else "Export Failed",
                    f"视图 {i+1} 参数导出失败:\n{e}" if zh else f"Failed to export view {i+1} params:\n{e}",
                )
                continue

            exported_count += 1

        # === 4) 完成提示 ===
        if exported_count > 0:
            QMessageBox.information(
                self,
                "导出完成" if zh else "Export Finished",
                f"已导出 {exported_count} 个视图到:\n{out_dir}" if zh
                else f"Exported {exported_count} views to:\n{out_dir}",
            )


    # ---------------- 参数变动 & 定时器 ----------------
    def on_params_changed(self):
        if self.gpr_data is None:
            return
        self.update_status_bar("等待重绘…")
        self._pipeline_timer.start()

    def _run_pipeline_internal(self):
        self.run_pipeline(force_full=False)

    # ---------------- 处理流水线 ----------------
    def run_pipeline(self, force_full: bool = False):
        if self.gpr_data is None:
            return
        self.update_status_bar("Processing…")
        p = self.controls.get_values()
        dt = float(self.gpr_data.dt)

        # --- 背景介电常数选择逻辑 ---
        bg_mat_name = p.get("bg_material") if p.get("bg_material") else None
        eps_from_mat = None

        if bg_mat_name and self.gpr_data.in_info:
            mats = self.gpr_data.in_info.get("materials", {})
            m = mats.get(bg_mat_name)
            if isinstance(m, dict) and "epsr" in m:
                eps_from_mat = float(m["epsr"])

        if eps_from_mat is not None:
            # 以材料的 εr 为准，并同步到 eps 控件（避免反复触发信号）
            self.gpr_data.eps_bg = eps_from_mat
            if abs(self.controls.spin_eps.value() - eps_from_mat) > 1e-6:
                old_block = self.controls.spin_eps.blockSignals(True)
                self.controls.spin_eps.setValue(eps_from_mat)
                self.controls.spin_eps.blockSignals(old_block)
        else:
            # 没选材料时，直接用 eps 控件的值
            self.gpr_data.eps_bg = float(p["eps"])


        # 判断是否需要重新做“重处理”
        heavy_keys = [
            "dc_ns", "t0_auto", "dewow", "dewow_win_ns", "mute_ns",
            "bg_material",
            "bg_method", "bg_win",
            "gain_on", "gain_alpha", "gain_beta", "agc_win",
            "use_bp", "bp_low", "bp_high",
            "smooth_x",
            "fk_enabled", "fk_kmin", "fk_kmax", "fk_fmin_mhz", "fk_fmax_mhz",
        ]


        heavy_params = {k: p.get(k) for k in heavy_keys}

        need_heavy = (
            force_full or
            self._last_heavy_params is None or
            self._last_heavy_data is None or
            self._last_heavy_params != heavy_params
        )

        if need_heavy:
            data = self.gpr_data.raw_data.astype(np.float64).copy()

            # DC 去直流
            if p["dc_ns"] > 0:
                n_head = int(p["dc_ns"] * 1e-9 / dt)
                if n_head > 0:
                    data = algo_basic.dc_shift_remove(data, n_head)

            # Time-zero
            if p["t0_auto"]:
                try:
                    t0_idx = algo_basic.estimate_common_t0(data, dt)
                    data = algo_basic.apply_t0_shift(data, t0_idx)
                except Exception as e:
                    QMessageBox.warning(self, "Time-zero 失败", f"自动估计 t0 出错：{e}")

            # Dewow
            # Dewow
            if p["dewow"]:
                win_ns = float(p.get("dewow_win_ns", 6.0))
                if win_ns > 0:
                    data = algo_basic.dewow(data, dt, win_ns)


            # 顶部静音
            if p.get("mute_ns", 0.0) > 0:
                data = algo_basic.mute_top_window(data, dt, p["mute_ns"])

            # 空间/背景
            if p["bg_method"] != "none" and p["bg_win"] > 0:
                try:
                    data = algo_spatial.remove_background(
                        data,
                        method=p["bg_method"],
                        win_traces=p["bg_win"],
                    )
                except Exception as e:
                    QMessageBox.warning(self, "背景去除失败", f"背景去除时出错：{e}")

            # 时间增益
            if p["gain_on"]:
                try:
                    tvec = np.arange(data.shape[0]) * dt
                    data = algo_gain.time_gain(
                        data,
                        tvec,
                        p["gain_alpha"],
                        p["gain_beta"],
                    )
                except Exception as e:
                    QMessageBox.warning(self, "增益失败", f"Time gain 处理出错：{e}")

            # AGC
            if p["agc_win"] > 0:
                try:
                    data = algo_gain.agc(data, dt, p["agc_win"])
                except Exception as e:
                    QMessageBox.warning(self, "AGC 失败", f"AGC 处理出错：{e}")

            # 带通滤波
            if p["use_bp"]:
                low = p["bp_low"]
                high = p["bp_high"]
                try:
                    data = algo_filters.bandpass_filter(data, dt, low, high)
                except Exception as e:
                    QMessageBox.warning(self, "带通滤波失败", f"带通滤波出错：{e}")

            # F-K 滤波
            if p.get("fk_enabled", False) and getattr(self.gpr_data, "dx", 0) > 0:
                fmin = p.get("fk_fmin_mhz", 0.0) * 1e6
                fmax = p.get("fk_fmax_mhz", 0.0) * 1e6
                kmin = p.get("fk_kmin", 0.0)
                kmax = p.get("fk_kmax", 0.0)

                fnyq = 0.5 / dt
                if fmin <= 0:
                    fmin = None
                elif fmin >= fnyq:
                    fmin = None

                if fmax <= 0:
                    fmax = None
                elif fmax > fnyq:
                    fmax = fnyq

                if (fmin is not None and fmax is not None and fmin >= fmax) or \
                   (kmin and kmax and kmin >= kmax):
                    QMessageBox.warning(self, "F-K 参数无效", "F-K 滤波参数设置不合理，已跳过 F-K 滤波。")
                else:
                    try:
                        data = algo_fk.fk_filter_basic(
                            data,
                            dt,
                            self.gpr_data.dx,
                            fmin=fmin,
                            fmax=fmax,
                            kmin=kmin if kmin > 0 else None,
                            kmax=kmax if kmax > 0 else None,
                        )
                    except Exception as e:
                        QMessageBox.warning(self, "F-K 滤波失败", f"F-K 滤波出错：{e}")

            # 横向 SavGol 平滑
            if p["smooth_x"] > 0:
                try:
                    data = algo_filters.savgol_smooth_x(data, p["smooth_x"])
                except Exception as e:
                    QMessageBox.warning(self, "横向平滑失败", f"Savitzky-Golay 平滑出错：{e}")

            self._last_heavy_params = heavy_params
            self._last_heavy_data = data
        else:
            data = self._last_heavy_data.copy()

        # -------- 显示阶段：原始 vs 处理 + ROI（裁剪/静音） + 包络 --------
        if p.get("show_raw", False):
            base = self.gpr_data.raw_data.astype(np.float64)
        else:
            base = data

        # ROI 控件范围（随数据更新）
        try:
            eps_tmp = float(getattr(self.gpr_data, "eps_bg", 6.0))
            if eps_tmp <= 0:
                eps_tmp = 6.0
            nt_full, nx_full = base.shape
            max_depth_full = algo_basic.sample_to_depth(nt_full - 1, dt, eps_tmp) if nt_full > 1 else 0.0
            if hasattr(self.controls, "set_roi_limits"):
                self.controls.set_roi_limits(nx=nx_full, max_depth_m=max_depth_full)
        except Exception:
            pass

        # --- ROI 参数解析 ---
        roi = {
            'crop_x_on': bool(p.get('crop_x_on', False)),
            'crop_x_start': int(p.get('crop_x_start', 1)),
            'crop_x_end': int(p.get('crop_x_end', 1)),
            'crop_y_on': bool(p.get('crop_y_on', False)),
            'crop_depth_start': float(p.get('crop_depth_start', 0.0)),
            'crop_depth_end': float(p.get('crop_depth_end', 0.0)),
            'mute_band_on': bool(p.get('mute_band_on', False)),
            'mute_depth_start': float(p.get('mute_depth_start', 0.0)),
            'mute_depth_end': float(p.get('mute_depth_end', 0.0)),
            'mute_taper_m': float(p.get('mute_taper_m', 0.0)),
        }

        eps_bg = float(getattr(self.gpr_data, 'eps_bg', 6.0))
        if eps_bg <= 0:
            eps_bg = 6.0

        # X 裁剪：按 A-scan 范围（1-based，end 为包含端）
        x0 = 0
        x1 = base.shape[1]
        if roi['crop_x_on'] and base.shape[1] > 0:
            xs = max(1, roi['crop_x_start'])
            xe = max(1, roi['crop_x_end'])
            if xe < xs:
                xs, xe = xe, xs
            x0 = max(0, min(base.shape[1] - 1, xs - 1))
            x1 = max(x0 + 1, min(base.shape[1], xe))

        # Y 裁剪：按深度范围（m）
        t0 = 0
        t1 = base.shape[0]
        if roi['crop_y_on'] and base.shape[0] > 0:
            t0 = algo_basic.depth_to_sample(roi['crop_depth_start'], dt, eps_bg)
            t1 = algo_basic.depth_to_sample(roi['crop_depth_end'], dt, eps_bg)
            if t1 < t0:
                t0, t1 = t1, t0
            t0 = max(0, min(base.shape[0] - 1, t0))
            t1 = max(t0 + 1, min(base.shape[0], t1))

        # 静音带：先按全幅索引置零，再裁剪（避免索引偏移问题）
        i0 = i1 = 0
        taper_samp = 0
        base_roi = base
        if roi['mute_band_on'] and base.shape[0] > 0:
            i0 = algo_basic.depth_to_sample(roi['mute_depth_start'], dt, eps_bg)
            i1 = algo_basic.depth_to_sample(roi['mute_depth_end'], dt, eps_bg)
            if i1 < i0:
                i0, i1 = i1, i0
            taper_samp = algo_basic.depth_to_sample(roi['mute_taper_m'], dt, eps_bg) if roi['mute_taper_m'] > 0 else 0
            base_roi = algo_basic.mute_band_by_index(base_roi, i0, i1, taper=taper_samp)

        # 应用裁剪
        if roi['crop_x_on'] or roi['crop_y_on']:
            base_roi = algo_basic.crop_by_index(base_roi, t0=t0, t1=t1, x0=x0, x1=x1)

        # 包络
        if p.get('show_env', False):
            data_display = algo_basic.envelope_detection(base_roi, axis=0)
        else:
            data_display = base_roi

        # 保存 ROI 元信息（导出/复现用）
        try:
            self.gpr_data.roi_info = {
                'crop_x_on': roi['crop_x_on'],
                'crop_x_start': roi['crop_x_start'],
                'crop_x_end': roi['crop_x_end'],
                'x0': int(x0),
                'x1_excl': int(x1),
                'crop_y_on': roi['crop_y_on'],
                'crop_depth_start': roi['crop_depth_start'],
                'crop_depth_end': roi['crop_depth_end'],
                't0': int(t0),
                't1_excl': int(t1),
                'mute_band_on': roi['mute_band_on'],
                'mute_depth_start': roi['mute_depth_start'],
                'mute_depth_end': roi['mute_depth_end'],
                'mute_taper_m': roi['mute_taper_m'],
                'mute_i0': int(i0),
                'mute_i1': int(i1),
                'mute_taper_samp': int(taper_samp),
            }
        except Exception:
            pass

        self.gpr_data.processed_data = data_display

        # -------- 坐标 / extent --------
        start_x = 0.0
        info = getattr(self.gpr_data, "in_info", {})
        if isinstance(info, dict):
            if "rx_pos" in info and info["rx_pos"]:
                start_x = float(info["rx_pos"][0])
            elif "src_pos" in info and info["src_pos"]:
                start_x = float(info["src_pos"][0])

        dx = getattr(self.gpr_data, "dx", 0.02)
        if dx <= 0:
            dx = 0.02
        nx = data_display.shape[1]
        # X 裁剪后：start_x 需要平移
        try:
            if bool(p.get('crop_x_on', False)):
                start_x = start_x + dx * int(x0)
        except Exception:
            pass
        end_x = start_x + dx * (nx - 1) if nx > 0 else start_x

        eps = float(getattr(self.gpr_data, "eps_bg", 6.0))
        if eps <= 0:
            eps = 6.0

        # 深度范围：对齐到“原始样点索引”（t0 可能来自深度裁剪）
        nt = data_display.shape[0]
        try:
            idx0_abs = int(t0)
        except Exception:
            idx0_abs = 0
        idx1_abs = idx0_abs + max(0, nt - 1)
        start_depth = algo_basic.sample_to_depth(idx0_abs, dt, eps)
        max_depth = algo_basic.sample_to_depth(idx1_abs, dt, eps)

        self.current_extent = (start_x, end_x, start_depth, max_depth)
        plot_extent = [start_x, end_x, max_depth, start_depth]

        xlabel = f"Distance (m) [dx={dx:.3f}]"
        ylabel = f"Depth (m) [εr={eps:.2f}]"

        limit = np.percentile(np.abs(data_display), p.get('clip', 99.0))
        vmin = 0.0 if p.get('show_env', False) else -limit
        vmax = limit

        self.canvas.plot(
            data_display, plot_extent, "Processed GPR",
            p.get('cmap', 'seismic'), vmin, vmax, xlabel, ylabel
        )

        # --- ROI 叠加线条（红：X裁剪；绿：静音带）---
        try:
            ax = self.canvas.ax
            if bool(p.get('crop_x_on', False)):
                ax.axvline(start_x, color='red', linewidth=1.2)
                ax.axvline(end_x, color='red', linewidth=1.2)
            if bool(p.get('mute_band_on', False)):
                y0m = float(p.get('mute_depth_start', 0.0))
                y1m = float(p.get('mute_depth_end', 0.0))
                if y1m < y0m:
                    y0m, y1m = y1m, y0m
                ax.axhline(y0m, color='lime', linewidth=1.0)
                ax.axhline(y1m, color='lime', linewidth=1.0)
                ax.axhspan(y0m, y1m, color='lime', alpha=0.12)
            self.canvas.draw()
        except Exception:
            pass

        # --- 如果启用了 AI 小助手，则在每次处理完成后自动给一条建议 ---
        try:
            if getattr(self, "btn_ai_helper", None) is not None \
               and self.btn_ai_helper.isChecked() \
               and getattr(self, "ai_widget", None) is not None:
                text = self.ai_build_suggestion()
                # 文本有变化时才更新，避免每次刷新都重复刷同一句
                if text and text != getattr(self, "_last_ai_msg", ""):
                    self._last_ai_msg = text
                    # 自动模式只在小人气泡里说，不往控制台刷一大堆
                    self.ai_widget.set_message(text, mood="info")
        except Exception as e:
            # 任何 AI 相关错误都不影响正常绘图
            try:
                self.console_print(f"[AI] 自动建议失败：{e}", kind="warn")
            except Exception:
                pass

        self.update_status_bar("Processed")


    def _format_params_for_label(self, p: Dict[str, Any]) -> str:
        """把参数字典压缩成几行描述，显示在四宫格下方"""
        lines = []

        if p.get("dewow", False):
            lines.append(f"Dewow: {p.get('dewow_win_ns', 0)} ns")
        if p.get("bg_method", "none") != "none":
            lines.append(f"BG: {p.get('bg_method')} (win={p.get('bg_win', 0)})")

        if p.get("gain_on", False):
            lines.append(f"Gain: α={p.get('gain_alpha')}, β={p.get('gain_beta')}")
        if p.get("agc_win", 0) > 0:
            lines.append(f"AGC: {p.get('agc_win')} ns")

        if p.get("use_bp", False):
            lines.append(f"BP: {p.get('bp_low')}–{p.get('bp_high')} MHz")
        if p.get("smooth_x", 0) > 0:
            lines.append(f"SavGol X: {p.get('smooth_x')}")
        if p.get("fk_enabled", False):
            lines.append(
                f"FK: f=[{p.get('fk_fmin_mhz')}, {p.get('fk_fmax_mhz')}] MHz, "
                f"k=[{p.get('fk_kmin')}, {p.get('fk_kmax')}]"
            )

        return "\n".join(lines)

    def save_current_view_to_slot(self, slot_idx: int):
        """把当前 B 扫处理结果和参数保存到第 slot_idx 个对比视图"""
        if self.gpr_data is None or self.gpr_data.processed_data is None:
            zh = (I18n.current_lang == "zh")
            QMessageBox.warning(
                self,
                "提示" if zh else "Notice",
                "请先加载数据并完成处理。" if zh else "Please load and process data first.",
            )
            return

        if self.current_extent is None:
            return

        data = self.gpr_data.processed_data
        p = self.controls.get_values()
        extent = self.current_extent

        # 计算颜色范围，与 run_pipeline 中逻辑保持一致
        clip = float(p.get("clip", 95.0))
        if data.size > 0:
            limit = np.percentile(np.abs(data), clip)
            if limit <= 0:
                limit = float(np.max(np.abs(data)) or 1.0)
        else:
            limit = 1.0

        if p.get("show_env", False):
            vmin, vmax = 0.0, limit
        else:
            vmin, vmax = -limit, limit

        cmap_name = p.get("cmap", "seismic")
        title = f"View #{slot_idx + 1}"

        # 更新数据槽
        self.view_slots[slot_idx] = ViewSlot(
            params=p,
            data=data.copy(),
            extent=extent,
            title=title,
        )

        # 更新对应的 pane
        pane = self.compare_view.panes[slot_idx]
        pane.canvas.plot(
            data,
            extent=extent,
            title=title,
            cmap=cmap_name,
            vmin=vmin,
            vmax=vmax,
            xlabel=f"Distance (m) [dx={getattr(self.gpr_data, 'dx', 0.0):.3f}]",
            ylabel=f"Depth (m) [εr={float(getattr(self.gpr_data, 'eps_bg', 6.0)):.2f}]",
        )
        pane.label.setText(self._format_params_for_label(p))

    def load_params_from_slot(self, slot_idx: int):
        """从某个视图槽位读取参数，应用到当前控件并回到单图模式"""

        # 基本检查
        if slot_idx < 0 or slot_idx >= len(self.view_slots):
            return

        slot = self.view_slots[slot_idx]
        if slot.params is None:
            zh = (I18n.current_lang == "zh")
            QMessageBox.warning(
                self,
                "提示" if zh else "Notice",
                f"视图 {slot_idx+1} 尚未保存任何参数。" if zh
                else f"View {slot_idx+1} has no saved params.",
            )
            return

        # 1) 把参数写回控件
        self._restore_controls(slot.params)

        # 2) 切回单图模式
        try:
            # 如果你有视图模式下拉框，就这样切回 index 0
            self.combo_view_mode.setCurrentIndex(0)
        except Exception:
            pass

        # 3) 若已有数据，则用这套参数重新处理
        if self.gpr_data is not None and self.gpr_data.raw_data is not None:
            self.run_pipeline(force_full=True)



    # ---------------- 几何真值视图 ----------------
    def show_model_view(self):
        if self.gpr_data is None:
            QMessageBox.warning(self, self._t("提示","Warning"), "请先加载 .out 主数据文件")
            return

        g = self.gpr_data

        info = getattr(g, "in_info", None)
        in_path = getattr(g, "in_path", None)

        if not info:
            # 没有缓存 info，则根据 in_path 或 .out 名推断
            if in_path is None:
                if not g.filename:
                    QMessageBox.warning(self, self._t("提示","Warning"), "当前数据缺少文件路径，无法自动匹配 .in")
                    return
                in_path = Path(g.filename).with_suffix(".in")
            else:
                in_path = Path(in_path)

            if not in_path.exists():
                QMessageBox.warning(self, self._t("提示","Warning"), f"未找到 .in 文件：{in_path}")
                return

            try:
                info = parse_in_file(in_path)
                g.in_info = info
                g.in_path = info.get("in_path", str(in_path))
            except Exception as e:
                QMessageBox.critical(self, self._t("解析错误","Parse Error"), f".in 文件解析失败：{e}")
                return


        if self.current_extent is None:
            self.run_pipeline(force_full=False)
            if self.current_extent is None:
                QMessageBox.warning(self, self._t("提示","Warning"), "当前还没有处理后的数据，无法计算几何切片。")
                return

        extent = self.current_extent

        if g.processed_data is None:
            QMessageBox.warning(self, self._t("提示","Warning"), "当前没有可用的处理数据")
            return

        nz, nx = g.processed_data.shape

        from algorithms.model_gt import build_gt_slice_from_in_info

        mask_gt, eps_gt, extra = build_gt_slice_from_in_info(
            info,
            plane="xz",
            n1=nx,
            n2=nz,
            extent=extent,
        )

        g.gt_mask = mask_gt
        g.gt_eps = eps_gt

        x0, x1, z0, z1 = extent
        g.gt_x = np.linspace(x0, x1, nx)
        g.gt_z = np.linspace(z0, z1, nz)

        dlg = ModelViewDialog(g, self)
        dlg.exec()

    def show_model3d_view(self):
        """弹出 3D 几何模型视图"""
        if self.gpr_data is None:
            QMessageBox.warning(self, self._t("提示","Warning"), "请先加载 .out 主数据文件")
            return

        from pathlib import Path
        g = self.gpr_data

        # 确保有 in_info，逻辑和 show_model_view 类似
        info = getattr(g, "in_info", None)
        in_path = getattr(g, "in_path", None)

        if info is None:
            if in_path is None:
                if not getattr(g, "filename", None):
                    QMessageBox.warning(self, self._t("提示","Warning"), "当前数据缺少文件路径，无法自动匹配 .in")
                    return
                in_path = Path(g.filename).with_suffix(".in")
            else:
                in_path = Path(in_path)

            if not in_path.exists():
                QMessageBox.warning(self, self._t("提示","Warning"), f"未找到 .in 文件：{in_path}")
                return

            try:
                info = parse_in_file(in_path)
                g.in_info = info
                g.in_path = str(in_path)
            except Exception as e:
                QMessageBox.critical(self, self._t("解析错误","Parse Error"), f".in 文件解析失败：{e}")
                return

        # 直接把 gpr_data 传给 3D 对话框
        dlg = Model3DViewPVDialog(g, self)
        dlg.exec()
# ---------------- A-Scan 交互逻辑 ----------------
    
    # 注意：请确保在 init_ui 中添加了这行代码：
    # self.canvas.mpl_connect('button_press_event', self.on_canvas_click)
    # (为了不破坏您现有的 init_ui，我在下面提供一个 setup_click_event 方法，您需要在 init_ui 结尾调用它)


    def on_compare_canvas_click(self, slot_idx: int, event):
        """在对比模式的某个视图里点击，弹出对应的 A-Scan"""
        if getattr(self, "interaction_mode", "normal") != "normal":
            return


        # 只响应左键
        if event.button != 1:
            return

        # 防止越界
        if slot_idx < 0 or slot_idx >= len(self.view_slots):
            return

        # 找到对应的 pane & axes，确保点击的是这个视图
        pane = self.compare_view.panes[slot_idx]
        if event.inaxes is not pane.canvas.ax:
            return

        slot = self.view_slots[slot_idx]
        if slot.data is None or slot.extent is None:
            # 这个视图还没有保存数据
            return

        if event.xdata is None:
            return

        x_click = event.xdata
        x0, x1, z0, z1 = slot.extent
        if x1 == x0:
            return

        data = slot.data
        nt, nx = data.shape

        # 把 x 坐标映射到道号：线性映射 [x0,x1] -> [0, nx-1]
        t = (x_click - x0) / (x1 - x0)
        idx = int(round(t * (nx - 1)))
        idx = max(0, min(nx - 1, idx))   # 防止越界

        trace = data[:, idx]

        if self.gpr_data is None or self.gpr_data.dt is None:
            return
        dt = self.gpr_data.dt

        # 弹出 A-Scan 窗口
        dlg = AScanViewDialog(trace, dt, idx, self)
        dlg.exec()

    def save_params_preset(self):
        """保存当前参数到 JSON 文件"""
        params = self.controls.get_values()

        # 附带一些元数据（可选）
        meta = {}
        if self.gpr_data is not None:
            meta = {
                "dt": self.gpr_data.dt,
                "dx": getattr(self.gpr_data, "dx", None),
                "eps_bg": getattr(self.gpr_data, "eps_bg", None),
                "fc": getattr(self.gpr_data, "fc", None),
                "source_file": str(getattr(self.gpr_data, "filename", "")),
            }

        # 选择保存路径
        zh = (I18n.current_lang == "zh")
        title = "保存参数预设" if zh else "Save Parameter Preset"
        filt = "参数预设 (*.json)" if zh else "Parameter Preset (*.json)"
        path_str, _ = QFileDialog.getSaveFileName(self, title, "", filt)
        if not path_str:
            return

        path = Path(path_str)
        if path.suffix.lower() != ".json":
            path = path.with_suffix(".json")

        payload = {"params": params, "meta": meta}

        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(
                self,
                "保存失败" if zh else "Save Failed",
                str(e),
            )
            return

        QMessageBox.information(
            self,
            "已保存" if zh else "Saved",
            f"参数预设已保存到:\n{path}",
        )


    # ---------- 画笔控制 ----------

    # ---------- 2D 画笔（基于截图的 Overlay） ----------
    # ---------- 交互模式管理（拟合 / 画笔 / A-Scan 点击互斥） ----------

    def _set_fit_button_checked(self, checked: bool):
        if hasattr(self, "btn_fit_velocity") and self.btn_fit_velocity is not None:
            blocker = QSignalBlocker(self.btn_fit_velocity)
            try:
                self.btn_fit_velocity.setChecked(checked)
            finally:
                del blocker

    def _set_brush_checkbox_checked(self, checked: bool):
        if hasattr(self, "controls") and self.controls is not None and hasattr(self.controls, "chk_brush_2d"):
            blocker = QSignalBlocker(self.controls.chk_brush_2d)
            try:
                self.controls.chk_brush_2d.setChecked(checked)
            finally:
                del blocker

    def _enter_fit_mode(self):
        self.fitting_mode = True
        self.console_print(self._t(">> 进入速度拟合模式", ">> Enter velocity fitting mode"), kind="hint")
        self.console_print(self._t("   1. [左键] 点击双曲线顶点", "   1. [Left click] pick hyperbola apex"), kind="hint")
        self.console_print(self._t("   2. [滚轮] 调整开口大小 (改变速度)", "   2. [Wheel] adjust opening (change velocity)"), kind="hint")
        self.console_print(self._t("   3. [右键] 退出拟合模式", "   3. [Right click] exit fitting mode"), kind="hint")

    def _exit_fit_mode(self):
        self.fitting_mode = False
        self.fit_vertex = None

        # 清理拟合线与文本
        if getattr(self, "fit_line", None) is not None:
            try:
                self.fit_line.remove()
            except Exception:
                pass
            self.fit_line = None

        if getattr(self, "fit_text", None) is not None:
            try:
                self.fit_text.remove()
            except Exception:
                pass
            self.fit_text = None

        # 重画以清除痕迹
        if hasattr(self, "canvas") and self.canvas is not None:
            self.canvas.draw()

        self.console_print(self._t("<< 退出拟合模式", "<< Exit fitting mode"), kind="hint")

    def _enter_brush_mode(self) -> bool:
        """进入 2D 画笔模式：截图 -> overlay。成功返回 True，否则 False（并负责回滚 UI）。"""
        self.brush_enabled = True

        # 没有数据就不开画笔
        if self.gpr_data is None or getattr(self.gpr_data, "processed_data", None) is None:
            QMessageBox.warning(self, self._t("提示","Warning"), "请先加载数据并完成一次处理，再使用画笔。")
            self.brush_enabled = False
            self._set_brush_checkbox_checked(False)
            return False

        # 对右侧视图区截图（无论当前是单图还是四视图）
        try:
            pix = self.view_stack.grab()
        except Exception:
            pix = None

        if pix is None or pix.isNull():
            QMessageBox.warning(self, self._t("提示","Warning"), "当前视图截图失败，画笔模式不可用。")
            self.brush_enabled = False
            self._set_brush_checkbox_checked(False)
            return False

        if self.overlay_2d is None:
            self.overlay_2d = DrawingOverlay(self.view_stack)

        self.overlay_2d.setGeometry(self.view_stack.rect())
        self.overlay_2d.set_background(pix)
        self.overlay_2d.show()
        self.overlay_2d.raise_()
        return True

    def _exit_brush_mode(self):
        self.brush_enabled = False
        if self.overlay_2d is not None:
            self.overlay_2d.hide()
            self.overlay_2d.clear_paths()

    def set_interaction_mode(self, mode: str):
        """
        统一管理交互模式（互斥）：
        - normal：A-Scan 点击可用
        - fit：速度拟合（屏蔽 A-Scan / 画笔）
        - brush：2D 画笔（屏蔽 A-Scan / 拟合）
        """
        mode = (mode or "normal").lower()
        if mode not in ("normal", "fit", "brush"):
            mode = "normal"

        if getattr(self, "_interaction_guard", False):
            return

        if getattr(self, "interaction_mode", "normal") == mode:
            return

        self._interaction_guard = True
        try:
            prev = getattr(self, "interaction_mode", "normal")

            # ---- 退出旧模式 ----
            if prev == "fit" and getattr(self, "fitting_mode", False):
                self._exit_fit_mode()
                self._set_fit_button_checked(False)
            elif prev == "brush" and getattr(self, "brush_enabled", False):
                self._exit_brush_mode()
                self._set_brush_checkbox_checked(False)

            # ---- 进入新模式 ----
            self.interaction_mode = mode

            if mode == "fit":
                # 进入拟合前：强制关闭画笔
                if getattr(self, "brush_enabled", False):
                    self._exit_brush_mode()
                    self._set_brush_checkbox_checked(False)
                self._set_fit_button_checked(True)
                self._enter_fit_mode()

            elif mode == "brush":
                # 进入画笔前：强制退出拟合（清理红线）
                if getattr(self, "fitting_mode", False):
                    self._exit_fit_mode()
                    self._set_fit_button_checked(False)
                self._set_brush_checkbox_checked(True)
                ok = self._enter_brush_mode()
                if not ok:
                    # 失败则回到 normal
                    self.interaction_mode = "normal"

            else:
                # normal：两种工具都要关闭
                if getattr(self, "fitting_mode", False):
                    self._exit_fit_mode()
                if getattr(self, "brush_enabled", False):
                    self._exit_brush_mode()
                self._set_fit_button_checked(False)
                self._set_brush_checkbox_checked(False)

        finally:
            self._interaction_guard = False



    def on_brush_toggled(self, checked: bool):
        """左侧面板勾选/取消“启用画笔”：交由统一的交互模式管理。"""
        self.play_ui_sound('toggle')
        self.set_interaction_mode("brush" if checked else "normal")

    def clear_brush(self):
        self.play_ui_sound("click")
        """
        清除 2D 画笔的标注轨迹，但保持当前画笔模式状态（勾选框不变）。
        """
        if self.overlay_2d is not None:
            self.overlay_2d.clear_paths()
            self.overlay_2d.update()


    def load_params_preset(self):
        """从 JSON 文件加载参数预设并应用到控件"""
        zh = (I18n.current_lang == "zh")
        title = "加载参数预设" if zh else "Load Parameter Preset"
        filt = "参数预设 (*.json)" if zh else "Parameter Preset (*.json)"
        path_str, _ = QFileDialog.getOpenFileName(self, title, "", filt)
        if not path_str:
            return

        path = Path(path_str)
        try:
            with path.open("r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            QMessageBox.critical(
                self,
                "加载失败" if zh else "Load Failed",
                str(e),
            )
            return

        # 兼容两种格式：{params: {...}} 或直接就是 params
        params = payload.get("params") if isinstance(payload, dict) else None
        if params is None:
            params = payload

        if not isinstance(params, dict):
            QMessageBox.warning(
                self,
                "格式错误" if zh else "Format Error",
                "文件格式不正确，未找到参数字段" if zh else "Invalid preset file.",
            )
            return

        # 应用到控件
        self._restore_controls(params)

        # 如果已经加载了数据，则立即重新处理
        if self.gpr_data is not None and self.gpr_data.raw_data is not None:
            self.run_pipeline(force_full=True)

    def on_view_mode_changed(self, index: int):
        mode = self.combo_view_mode.currentData()
        if mode == "compare4":
            self.view_stack.setCurrentIndex(1)
        else:
            self.view_stack.setCurrentIndex(0)


    def on_canvas_click(self, event):
        """
        画布点击响应：统一使用当前控件参数作为坐标转换基准
        """
        if event.inaxes != self.canvas.ax: return

        # 画笔模式下，画布点击全部忽略（避免 A-Scan/拟合互相踩踏）
        if getattr(self, "interaction_mode", "normal") == "brush":
            return
        
        # --- 模式 A: 速度拟合模式 ---
        if self.fitting_mode:
            if event.button == 1: # 左键：定点
                # 1. 记录点击的屏幕坐标
                x_click_m = event.xdata
                y_click_display = event.ydata 
                
                # 2. 【核心修正】获取“当前屏幕渲染所用的”介电常数
                # 不要读 self.gpr_data.eps_bg，因为那个可能没更新，或者和当前画面不一致
                # 我们必须相信界面上显示的数字，因为画面是根据它画出来的
                current_eps = self.controls.spin_eps.value()
                
                # 3. 计算当前画面的光速
                c = 0.299792458
                v_current = c / np.sqrt(current_eps)
                
                # 4. 反算绝对时间 (Time = Depth * 2 / v)
                # 这个 t_click_ns 是双曲线的物理核心，永远不变
                t_click_ns = (y_click_display * 2.0) / v_current
                
                self.fit_vertex = (x_click_m, t_click_ns)
                
                # 立即绘制
                self.draw_hyperbola()
                
            elif event.button == 3: # 右键：应用
                if self.fit_vertex:
                    c = 0.299792458
                    eps_new = (c / self.fit_v) ** 2
                    
                    self.console_print(f">> 拟合应用: v={self.fit_v:.3f}, εr={eps_new:.2f}", kind="warn")
                    
                    # 1. 修改控件，这会触发 run_pipeline，重绘背景图
                    self.controls.spin_eps.setValue(eps_new)
                    
                    # 2. 退出拟合模式 (清理红线)
                    # 因为背景图即将重绘，坐标轴会变，旧红线必须清除
                    self.toggle_fitting_mode(False)
                    self.btn_fit_velocity.setChecked(False) 
            return

        # --- 模式 B: A-Scan (保持原样) ---
        if hasattr(self, "current_extent") and self.current_extent is not None:
            start_x, end_x, _, _ = self.current_extent
            dx = getattr(self.gpr_data, "dx", 0.02)
            if dx <= 0: dx = 0.02
            idx = int(round((event.xdata - start_x) / dx))
            data = self.gpr_data.processed_data
            if data is not None and 0 <= idx < data.shape[1]:
                trace = data[:, idx]
                dt = self.gpr_data.dt
                from ui.ascan_view import AScanViewDialog
                dlg = AScanViewDialog(trace, dt, idx, self)
                dlg.exec()

    def draw_hyperbola(self):
        """
        绘制拟合曲线
        【逻辑修正】：
        1. 形状由 fit_v 决定 (滚轮)
        2. 屏幕位置由 spin_eps 决定 (当前背景)
        3. 强制锁定视图范围，防止 Matplotlib 自动缩放导致图像跳变
        """
        if not self.fit_vertex or not self.current_extent:
            return
            
        # 1. 获取当前视图的显示范围 (锁定视图的关键)
        # 不要只依赖 self.current_extent，要看当前用户缩放到哪里了
        cur_xlim = self.canvas.ax.get_xlim()
        cur_ylim = self.canvas.ax.get_ylim()
        
        # 2. 准备数据
        x0_m, t0_ns = self.fit_vertex 
        x_min, x_max = cur_xlim # 只画视野内的线，提高性能
        
        # 3. 生成 x 轴 (增加点数保证平滑)
        x_plot = np.linspace(x_min, x_max, 400)
        
        # 4. 计算时间域形状 (Time Domain)
        # 公式: t = sqrt(t0^2 + 4*(x-x0)^2 / v_fit^2)
        delta_x = x_plot - x0_m
        t_sq = t0_ns**2 + (4 * (delta_x**2)) / (self.fit_v**2)
        t_plot_ns = np.sqrt(t_sq)
        
        # 5. 【核心修正】坐标映射 Time -> Depth
        # 必须使用界面上当前的 eps 来转换，这样红线才能和背景图贴合
        current_eps = self.controls.spin_eps.value()
        c = 0.299792458
        v_current_display = c / np.sqrt(current_eps)
        
        y_plot_display = t_plot_ns * v_current_display / 2.0
        y0_display = t0_ns * v_current_display / 2.0

        # 6. 绘图
        if self.fit_line is None:
            self.fit_line, = self.canvas.ax.plot(
                x_plot, y_plot_display, 
                color='red', linewidth=2.5, linestyle='--', alpha=0.9
            )
            self.fit_text = self.canvas.ax.text(
                x0_m, y0_display, "", 
                color='yellow', fontweight='bold', fontsize=11,
                verticalalignment='bottom',
                bbox=dict(facecolor='black', alpha=0.6, edgecolor='none')
            )
        else:
            self.fit_line.set_data(x_plot, y_plot_display)
            self.fit_text.set_position((x0_m, y0_display))
            
        # 更新文字
        eps_fit = (c / self.fit_v) ** 2
        self.fit_text.set_text(f"v={self.fit_v:.3f}\nεr={eps_fit:.2f}")
        
        # 7. 【关键步骤】强制恢复坐标轴范围
        # Matplotlib 画了新线后可能会自动撑大坐标轴，这里给它按回去
        self.canvas.ax.set_xlim(cur_xlim)
        self.canvas.ax.set_ylim(cur_ylim) 
        
        self.canvas.draw()

        # ... (后续保留原有的 A-Scan 弹出逻辑) ...

    def on_fit_scroll(self, event):
        """滚轮调整开口（改变拟合速度 v）"""
        if not self.fitting_mode or not self.fit_vertex:
            return

        # 速度步进（根据当前速度动态调整，体验更好）
        step_v = 0.001 if self.fit_v < 0.1 else 0.005

        # Matplotlib 不同版本：可能提供 event.step(+/-) 或 event.button('up'/'down')
        direction = None
        if hasattr(event, "step") and event.step is not None:
            try:
                direction = 1 if float(event.step) > 0 else -1
            except Exception:
                direction = None
        if direction is None:
            btn = getattr(event, "button", None)
            if btn in ("up", "u", 1):
                direction = 1
            elif btn in ("down", "d", -1):
                direction = -1
            else:
                # 保底：当作向下
                direction = -1

        self.fit_v += direction * step_v

        # 限制范围（光速上限）
        self.fit_v = max(0.01, min(0.299, float(self.fit_v)))

        self.draw_hyperbola()


# ---------------------------------------------------------
    #  补全缺失的方法：速度拟合工具相关逻辑
    # ---------------------------------------------------------

    def toggle_fitting_mode(self, checked):
        """顶部按钮切换速度拟合工具：交由统一的交互模式管理。"""
        self.set_interaction_mode("fit" if checked else "normal")

