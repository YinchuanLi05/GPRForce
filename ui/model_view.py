# ui/model_view.py
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel
from ui.canvas import GPRCanvas
import numpy as np


class ModelViewDialog(QDialog):
    """
    显示几何真值:
    - 左：GT Mask (管道=1)
    - 右：GT εr 分布
    依赖 MainWindow 里提前填好的字段:
        gpr_data.gt_mask : (nz, nx) uint8 / bool
        gpr_data.gt_eps  : (nz, nx) float
        gpr_data.gt_x    : (nx,)
        gpr_data.gt_z    : (nz,)
    """
    def __init__(self, gpr_data, parent=None):
        super().__init__(parent)
        self.gpr = gpr_data
        self.setWindowTitle("模型与几何真值 / Model & Ground Truth")
        self.resize(1000, 600)

        # ---------- 基本布局 ----------
        main_layout = QVBoxLayout(self)

        lbl = QLabel("几何真值视图： 左 = Mask, 右 = εr map")
        main_layout.addWidget(lbl)

        center = QHBoxLayout()
        main_layout.addLayout(center)

        # 左右两个画布
        self.canvas_mask = GPRCanvas(self)
        self.canvas_eps = GPRCanvas(self)

        center.addWidget(self.canvas_mask, stretch=1)
        center.addWidget(self.canvas_eps, stretch=1)

        # 一进来就画图
        self._plot_gt()

    def _plot_gt(self):
        g = self.gpr

        mask = np.asarray(getattr(g, "gt_mask", None))
        eps = np.asarray(getattr(g, "gt_eps", None))
        x = np.asarray(getattr(g, "gt_x", None))
        z = np.asarray(getattr(g, "gt_z", None))

        if mask.ndim != 2 or eps.ndim != 2 or x.ndim != 1 or z.ndim != 1:
            # 简单兜底：什么都没有就不画
            return

        nz, nx = mask.shape
        if eps.shape != (nz, nx):
            # 形状不一致直接放弃，避免崩溃
            return

        # extent: [left, right, bottom, top]
        x0, x1 = float(x[0]), float(x[-1])
        z0, z1 = float(z[0]), float(z[-1])
        extent = [x0, x1, z1, z0]   # 深度向下

        # --- 左：Mask ---
        self.canvas_mask.plot(
            mask,
            extent,
            "GT Mask (pipe=1)",
            cmap="gray",
            vmin=0.0,
            vmax=1.0,
            xlabel="Distance x (m)",
            ylabel="Depth z (m)",
            aspect="equal",              # ⭐ 保证 x/z 物理尺度 1:1
        )

        # --- 右：εr ---
        # 1) 先拿到有效值
        valid = eps[np.isfinite(eps)]
        if valid.size == 0:
            return

        vmin_eps = float(valid.min())
        vmax_eps = float(valid.max())

        # 2) 防止全图 same 值导致 vmin==vmax
        if abs(vmax_eps - vmin_eps) < 1e-6:
            vmin_eps -= 0.5
            vmax_eps += 0.5

        self.canvas_eps.plot(
            eps,
            extent,
            "GT εr map",
            cmap="viridis",
            vmin=vmin_eps,
            vmax=vmax_eps,
            xlabel="Distance x (m)",
            ylabel="Depth z (m)",
            aspect="equal",              # ⭐ 保证 x/z 物理尺度 1:1
        )
