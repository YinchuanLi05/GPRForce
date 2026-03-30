# ui/model3d_pv.py
from __future__ import annotations

import os
from typing import Dict, Any, List

from PyQt6.QtGui import (
    QPixmap, QPainter, QPen, QImage, QColor
)

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QInputDialog, QWidget, QColorDialog
)


import numpy as np
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QInputDialog, QWidget
)
from PyQt6.QtGui import (
    QPixmap, QPainter, QPen, QImage, QColor
)
from PyQt6.QtCore import Qt, QPoint

# 告诉 qtpy 使用 PyQt6
os.environ.setdefault("QT_API", "pyqt6")

import pyvista as pv
from pyvistaqt import QtInteractor


def _color_for_material(mat_name: str) -> str:
    """为不同材料分配颜色."""
    palette = [
        "#1f77b4",  # blue
        "#ff7f0e",  # orange
        "#2ca02c",  # green
        "#d62728",  # red
        "#9467bd",  # purple
        "#8c564b",  # brown
        "#e377c2",  # pink
        "#7f7f7f",  # gray
        "#bcbd22",  # lime
        "#17becf",  # cyan
    ]
    if not mat_name:
        return "#999999"
    idx = abs(hash(mat_name)) % len(palette)
    return palette[idx]


def _make_box_mesh(p1, p2) -> pv.PolyData:
    x0, y0, z0 = p1
    x1, y1, z1 = p2
    bounds = (x0, x1, y0, y1, z0, z1)
    return pv.Box(bounds=bounds)


def _make_sphere_mesh(center, r) -> pv.PolyData:
    return pv.Sphere(
        radius=float(r),
        center=center,
        theta_resolution=40,
        phi_resolution=28,
    )


def _make_cylinder_mesh(p1, p2, r) -> pv.PolyData:
    """构造任意方向圆柱体."""
    p1 = np.asarray(p1, dtype=float)
    p2 = np.asarray(p2, dtype=float)
    axis_vec = p2 - p1
    height = float(np.linalg.norm(axis_vec))
    if height < 1e-9:
        return _make_sphere_mesh(p1, r)

    direction = axis_vec / height
    center = (p1 + p2) / 2.0

    cyl = pv.Cylinder(
        center=center,
        direction=direction,
        radius=float(r),
        height=height,
        resolution=64,
    )
    return cyl


class DrawingOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._background = QPixmap()
        self._paths: List[List[QPoint]] = []
        self._current_path: List[QPoint] | None = None

        # 画笔属性
        self.pen_color = QColor(0, 0, 0)  # 默认黑色
        self.pen_width = 3

        # 不透明背景，用截图铺满
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMouseTracking(True)

    def set_pen_color(self, color: QColor):
        """修改画笔颜色，并重绘。"""
        self.pen_color = color
        self.update()


    def set_background(self, pixmap: QPixmap):
        """设置背景截图，并清空已有涂鸦。"""
        self._background = pixmap
        self._paths.clear()
        self._current_path = None
        self.update()

    def clear_paths(self):
        """清空当前所有画笔轨迹。"""
        self._paths.clear()
        self._current_path = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 画背景截图
        if not self._background.isNull():
            painter.drawPixmap(self.rect(), self._background)

        # 配置画笔
        pen = QPen(self.pen_color)
        pen.setWidth(self.pen_width)
        painter.setPen(pen)


        # 画历史路径
        for path in self._paths:
            if len(path) > 1:
                for i in range(len(path) - 1):
                    painter.drawLine(path[i], path[i + 1])

        # 画当前路径
        if self._current_path and len(self._current_path) > 1:
            for i in range(len(self._current_path) - 1):
                painter.drawLine(self._current_path[i], self._current_path[i + 1])

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._current_path = [event.position().toPoint()]
            event.accept()
        else:
            event.ignore()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self._current_path is not None:
            self._current_path.append(event.position().toPoint())
            self.update()
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._current_path is not None:
            self._paths.append(self._current_path)
            self._current_path = None
            self.update()
            event.accept()
        else:
            event.ignore()


class Model3DViewPVDialog(QDialog):
    """
    使用 PyVista + pyvistaqt 展示 .in 几何的 3D 视图
    （实体 + 交互视角 + 文字标注 + 截图画笔）

    依赖:
        gpr_data.in_info : parse_in_file 返回的 info
        gpr_data.domain  : (X, Y, Z)，否则尝试 info['domain']
    """

    def choose_pen_color(self):
        """弹出颜色选择器，改变画笔颜色。"""
        # 当前颜色作为默认值
        current = self.overlay.pen_color if hasattr(self.overlay, "pen_color") else QColor(0, 0, 0)
        color = QColorDialog.getColor(current, self, "选择画笔颜色")
        if not color.isValid():
            return

        # 修改 overlay 的画笔颜色
        self.overlay.set_pen_color(color)

        # 按钮也用这个颜色做背景，文字颜色根据亮度调一下
        light = color.lightness()
        text_color = "#000000" if light > 128 else "#ffffff"
        self.btn_pen_color.setStyleSheet(
            f"background-color: {color.name()}; color: {text_color};"
        )

    def __init__(self, gpr_data, parent=None):
        super().__init__(parent)

        self.gpr_data = gpr_data

        # 文字标注状态
        self.annotate_mode = False
        self._annotation_actors: List[Any] = []

        # 截图画笔状态
        self.pen_mode = False
        self._screenshot_bytes: bytes | None = None  # 保持截图原始数据的引用

        self.setWindowTitle("3D 模型视图 (PyVista)")
        self.resize(1000, 750)

        layout = QVBoxLayout(self)

        self.label_info = QLabel("基于 .in 文件的几何模型（x→, y→, z↑）")
        layout.addWidget(self.label_info)

        # PyVista Qt 交互器
        self.plotter = QtInteractor(self)
        layout.addWidget(self.plotter.interactor, stretch=1)

        # 叠加的 2D 画笔画布（默认隐藏）
        self.overlay = DrawingOverlay(self.plotter.interactor)
        self.overlay.hide()

        # 底部按钮条：视角 + 标注 + 画笔 + 清除 + 重置 + 关闭
        btn_layout = QHBoxLayout()

        # 视角
        self.btn_view_xy = QPushButton("XY 俯视")
        self.btn_view_xz = QPushButton("XZ 视角")
        self.btn_view_yz = QPushButton("YZ 视角")
        self.btn_view_xy.clicked.connect(self.view_xy)
        self.btn_view_xz.clicked.connect(self.view_xz)
        self.btn_view_yz.clicked.connect(self.view_yz)

        # 标注
        self.btn_annotate = QPushButton("标注模式")
        self.btn_annotate.setCheckable(True)
        self.btn_annotate.clicked.connect(self.on_annotate_clicked)

        # 截图画笔
        self.btn_pen = QPushButton("画笔")
        self.btn_pen.setCheckable(True)
        self.btn_pen.clicked.connect(self.toggle_pen_mode)

        # 画笔颜色
        self.btn_pen_color = QPushButton("颜色")
        self.btn_pen_color.clicked.connect(self.choose_pen_color)
        # 清除
        self.btn_clear_ann = QPushButton("清除标注")
        self.btn_clear_ann.clicked.connect(self.clear_annotations)

        # 视图
        self.btn_reset = QPushButton("重置视角")
        self.btn_close = QPushButton("关闭")
        self.btn_reset.clicked.connect(self.reset_view)
        self.btn_close.clicked.connect(self.close)

        btn_layout.addWidget(self.btn_view_xy)
        btn_layout.addWidget(self.btn_view_xz)
        btn_layout.addWidget(self.btn_view_yz)
        btn_layout.addSpacing(15)
        btn_layout.addWidget(self.btn_annotate)
        btn_layout.addWidget(self.btn_pen)
        btn_layout.addWidget(self.btn_pen_color)
        btn_layout.addWidget(self.btn_clear_ann)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

        self._setup_theme()
        self.plot_model()
        self.reset_view()

    # ---------------- 外观主题 & 比例 ----------------
    def _setup_theme(self):
        """调整 PyVista 主题外观，让比例更协调。"""
        theme = self.plotter.theme

        theme.background = "white"
        if hasattr(theme, "font"):
            theme.font.size = 10
            theme.font.title_size = 16
            theme.font.label_size = 12
        theme.show_edges = False
        theme.edge_color = "black"

        # 关闭巨大 X/Y/Z 文字
        if hasattr(theme, "axes"):
            theme.axes.show = False

        self.plotter.theme = theme

        # 右下角小坐标轴
        self.plotter.show_axes()

    # ---------------- 构建 3D 场景 ----------------
    def plot_model(self):
        self.plotter.clear()
        self._annotation_actors.clear()

        info: Dict[str, Any] = getattr(self.gpr_data, "in_info", None) or {}
        if not info:
            self.plotter.add_text("No .in information", position="upper_left", font_size=14)
            self.plotter.reset_camera()
            return

        # ---- 计算域 ----
        domain = tuple(info.get("domain", getattr(self.gpr_data, "domain", (1.0, 1.0, 1.0))))
        X, Y, Z = domain
        max_len = max(X, Y, Z)

        # 计算域边框（线框）
        domain_box = pv.Box(bounds=(0.0, X, 0.0, Y, 0.0, Z))
        self.plotter.add_mesh(
            domain_box,
            color="#bbbbbb",
            style="wireframe",
            line_width=1.0,
            opacity=0.7,
        )

        # z=0 平面参考网格
        ground_plane = pv.Plane(
            center=(X / 2, Y / 2, 0.0),
            direction=(0, 0, 1),
            i_size=X,
            j_size=Y,
            i_resolution=10,
            j_resolution=10,
        )
        self.plotter.add_mesh(
            ground_plane,
            color="#f0f0f0",
            opacity=0.6,
            style="wireframe",
            line_width=0.5,
        )

        boxes_info = info.get("boxes", [])

        # ---- 空气层：灰色半透明，从地表到域顶 ----
        ground_top_z = 0.0
        for b in boxes_info:
            z0 = float(b["p1"][2])
            z1 = float(b["p2"][2])
            z_hi = max(z0, z1)
            if z_hi < Z - 1e-3:
                ground_top_z = max(ground_top_z, z_hi)

        if 0.0 < ground_top_z < Z:
            air_box = pv.Box(bounds=(0.0, X, 0.0, Y, ground_top_z, Z))
            self.plotter.add_mesh(
                air_box,
                color="#dddddd",
                opacity=0.20,
                show_edges=False,
            )

        # ---- 材料几何 ----
        legend_used = set()

        def add_with_label(mesh: pv.DataSet, mat_name: str, color: str, opacity: float):
            label = mat_name or "unknown"
            self.plotter.add_mesh(
                mesh,
                color=color,
                opacity=opacity,
                show_edges=False,
                smooth_shading=True,
                label=label,
            )
            legend_used.add(label)

        # box
        for b in boxes_info:
            mat = str(b.get("material", "")).lower()
            color = _color_for_material(mat)
            box_mesh = _make_box_mesh(b["p1"], b["p2"])
            add_with_label(box_mesh, mat, color, opacity=0.25)

        # cylinder
        for c in info.get("cylinders", []):
            mat = str(c.get("material", "")).lower()
            color = _color_for_material(mat)
            cyl_mesh = _make_cylinder_mesh(c["p1"], c["p2"], c["radius"])
            add_with_label(cyl_mesh, mat, color, opacity=0.6)

        # sphere
        for s in info.get("spheres", []):
            mat = str(s.get("material", "")).lower()
            color = _color_for_material(mat)
            sph_mesh = _make_sphere_mesh(s["center"], s["radius"])
            add_with_label(sph_mesh, mat, color, opacity=0.7)

        # ---- Tx / Rx 轨迹 ----
        src_pos = info.get("src_pos", None)
        if src_pos is not None:
            sx, sy, sz = src_pos
            src_r = 0.02 * max_len
            self.plotter.add_mesh(
                pv.Sphere(radius=src_r, center=(sx, sy, sz)),
                color="red",
                opacity=1.0,
                label="Tx",
            )
            legend_used.add("Tx")

        rx_list = info.get("rx_pos_list", None)
        if rx_list:
            rx_pts = np.array(rx_list, dtype=float)

            # 轨迹线（有 Spline 时用一条平滑线）
            if rx_pts.shape[0] >= 2 and hasattr(pv, "Spline"):
                try:
                    line = pv.Spline(rx_pts, n_points=rx_pts.shape[0] * 10)
                    self.plotter.add_mesh(
                        line,
                        color="blue",
                        line_width=2.0,
                        label="Rx path",
                    )
                    legend_used.add("Rx path")
                except Exception:
                    pass

            # 点
            self.plotter.add_points(
                rx_pts,
                color="blue",
                render_points_as_spheres=True,
                point_size=10,
            )

        # 坐标轴范围 & 视角
        self.plotter.set_scale(1.0, 1.0, 1.0)
        self.plotter.set_focus((X / 2, Y / 2, Z / 2))
        self.plotter.set_viewup((0, 0, 1))

        # 带刻度网格（使用 xtitle/ytitle/ztitle，避免 DeprecationWarning）
        self.plotter.show_grid(
            xtitle="x (m)",
            ytitle="y (m)",
            ztitle="z (m)",
            color="#888888",
        )

        # 图例
        if legend_used:
            self.plotter.add_legend(
                bcolor="white",
                border=True,
                size=(0.18, 0.22),
            )

    # ---------------- 视角控制 ----------------
    def reset_view(self):
        if hasattr(self.plotter, "view_isometric"):
            self.plotter.view_isometric()
        else:
            self.plotter.camera_position = "iso"
        self.plotter.reset_camera()

    def view_xy(self):
        if hasattr(self.plotter, "view_xy"):
            self.plotter.view_xy()
        else:
            self.plotter.view_vector((0, 0, 1))
        self.plotter.reset_camera()

    def view_xz(self):
        if hasattr(self.plotter, "view_xz"):
            self.plotter.view_xz()
        else:
            self.plotter.view_vector((0, 1, 0))
        self.plotter.reset_camera()

    def view_yz(self):
        if hasattr(self.plotter, "view_yz"):
            self.plotter.view_yz()
        else:
            self.plotter.view_vector((1, 0, 0))
        self.plotter.reset_camera()

    # ---------------- 文字标注模式 ----------------
    def on_annotate_clicked(self, checked: bool):
        # 开启文字标注时，关闭画笔
        self.annotate_mode = checked
        if checked and self.pen_mode:
            self.pen_mode = False
            self.btn_pen.setChecked(False)
            self.btn_pen.setStyleSheet("")
            self.overlay.hide()
            self.overlay.clear_paths()
        self._update_picking()

    def _update_picking(self):
        """根据当前模式启用/关闭点选（用于文字标注），避免重复 enable 报错。"""
        # 先尽量关掉旧的 picking
        if hasattr(self.plotter, "disable_picking"):
            try:
                self.plotter.disable_picking()
            except Exception:
                pass

        # 文字标注模式
        if self.annotate_mode:
            ok = False
            try:
                if hasattr(self.plotter, "enable_surface_point_picking"):
                    self.plotter.enable_surface_point_picking(
                        callback=self._on_pick_point,
                        left_clicking=True,
                        show_message=False,
                    )
                    ok = True
            except TypeError:
                # 某些老版本不支持 left_clicking / show_message
                try:
                    self.plotter.enable_surface_point_picking(self._on_pick_point)
                    ok = True
                except Exception:
                    ok = False

            if not ok:
                try:
                    self.plotter.enable_point_picking(
                        callback=self._on_pick_point,
                        left_clicking=True,
                        show_message=False,
                    )
                    ok = True
                except TypeError:
                    try:
                        self.plotter.enable_point_picking(self._on_pick_point)
                        ok = True
                    except Exception:
                        ok = False

            self.label_info.setText(
                "标注模式：左键点击模型添加箭头+文字（再次点击“标注模式”关闭）"
            )
            self.btn_annotate.setStyleSheet("background-color: #ffe0b0;")
        else:
            self.btn_annotate.setStyleSheet("")
            if not self.pen_mode:
                self.label_info.setText("基于 .in 文件的几何模型（x→, y→, z↑）")

    # ---- point picking 回调 ----
    def _decode_point_from_args(self, *args):
        """兼容不同 PyVista 版本的点选回调."""
        if not args:
            return None
        # 新版: callback(point)
        if len(args) == 1:
            a0 = args[0]
            if isinstance(a0, (tuple, list, np.ndarray)) and len(a0) == 3:
                return np.array(a0, dtype=float)
            if hasattr(a0, "pick_position"):
                return np.array(a0.pick_position, dtype=float)
        # 某些版本: callback(picker, point)
        if len(args) >= 2:
            a1 = args[1]
            if isinstance(a1, (tuple, list, np.ndarray)) and len(a1) == 3:
                return np.array(a1, dtype=float)
            if hasattr(a1, "pick_position"):
                return np.array(a1.pick_position, dtype=float)
        return None

    def _on_pick_point(self, *args):
        if not self.annotate_mode:
            return

        point = self._decode_point_from_args(*args)
        if point is None:
            return

        self._add_text_annotation(point)

    # ---- 添加箭头 + 文字 ----
    def _add_text_annotation(self, point: np.ndarray):
        text, ok = QInputDialog.getText(
            self,
            "添加标注",
            f"选中点坐标：({point[0]:.3f}, {point[1]:.3f}, {point[2]:.3f})\n输入标注文字：",
        )
        if not ok:
            return
        label = text.strip()
        if not label:
            return

        # 箭头起点稍微偏离一下，避免文字压在目标上
        offset = np.array([0.05, 0.05, 0.05])
        start = point + offset
        direction = point - start

        arrow = pv.Arrow(
            start=start,
            direction=direction,
            tip_length=0.25,
            tip_radius=0.01,
            shaft_radius=0.005,
        )
        actor_arrow = self.plotter.add_mesh(
            arrow,
            color="black",
            opacity=0.9,
        )

        pts = np.array([[start[0], start[1], start[2]]])
        actor_label = self.plotter.add_point_labels(
            pts,
            [label],
            text_color="black",
            point_color="yellow",
            point_size=12,
            shape="round",
            font_size=14,      # 文字稍微大一点
            always_visible=True,
        )

        self._annotation_actors.append(actor_arrow)
        self._annotation_actors.append(actor_label)
        self.plotter.render()

    # ---------------- 截图画笔 ----------------
    def toggle_pen_mode(self, checked: bool):
        """切换截图画笔模式（与文字标注互斥）"""
        self.pen_mode = checked

        if self.pen_mode:
            # 关闭文字标注
            if self.annotate_mode:
                self.annotate_mode = False
                self.btn_annotate.setChecked(False)
                self.btn_annotate.setStyleSheet("")
                # 关闭 picking
                if hasattr(self.plotter, "disable_picking"):
                    try:
                        self.plotter.disable_picking()
                    except Exception:
                        pass

            # 截取当前 3D 视图为背景
            try:
                img = self.plotter.screenshot(return_img=True)
            except Exception:
                img = None

            if img is None:
                # 截图失败，退出画笔模式
                self.pen_mode = False
                self.btn_pen.setChecked(False)
                self.label_info.setText("画笔模式不可用（截图失败）")
                return

            # 转成 QPixmap
            # 转成 QPixmap（注意：QImage 需要 bytes，而不是 memoryview）
            h, w, c = img.shape

            # 确保数据是 uint8 连续内存
            img_u8 = np.require(img, dtype=np.uint8, requirements=["C"])

            # 把数据转成 bytes，并保存在成员里，防止被 GC 掉
            self._screenshot_bytes = img_u8.tobytes()

            if c == 3:
                bytes_per_line = 3 * w
                qimg = QImage(
                    self._screenshot_bytes,
                    w,
                    h,
                    bytes_per_line,
                    QImage.Format.Format_RGB888,
                )
            else:
                bytes_per_line = 4 * w
                qimg = QImage(
                    self._screenshot_bytes,
                    w,
                    h,
                    bytes_per_line,
                    QImage.Format.Format_RGBA8888,
                )

            pixmap = QPixmap.fromImage(qimg)


            # 覆盖到 PyVista 画布上
            self.overlay.setGeometry(self.plotter.interactor.rect())
            self.overlay.set_background(pixmap)
            self.overlay.show()
            self.overlay.raise_()

            self.btn_pen.setStyleSheet("background-color: #e0ffe0;")
            self.label_info.setText(
                "画笔模式：在图上按住左键拖动绘制（再次点击“画笔”退出，清除用“清除标注”）"
            )
        else:
            # 退出画笔模式：隐藏画布
            self.overlay.hide()
            self.btn_pen.setStyleSheet("")
            if not self.annotate_mode:
                self.label_info.setText("基于 .in 文件的几何模型（x→, y→, z↑）")

    # ---------------- 清除标注（文字 + 画笔） ----------------
    def clear_annotations(self):
        # 清文字/箭头
        for actor in self._annotation_actors:
            try:
                self.plotter.remove_actor(actor)
            except Exception:
                pass
        self._annotation_actors.clear()

        # 清画笔轨迹（overlay 上）
        self.overlay.clear_paths()

        self.plotter.render()
