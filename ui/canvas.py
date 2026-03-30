# ui/canvas.py
try:
    # Matplotlib >= 3.6 (Qt6/Qt5 compatible)
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
except Exception:
    # Fallback (older Matplotlib)
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg

from matplotlib.figure import Figure
import matplotlib as mpl
from core.i18n import I18n

# ---- Global font settings: Chinese + minus sign ----
mpl.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
mpl.rcParams["axes.unicode_minus"] = False


class GPRCanvas(FigureCanvasQTAgg):
    """Main B-scan canvas."""

    def __init__(self, parent=None):
        self.fig = Figure(figsize=(8, 6), dpi=100, facecolor="#121212")
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor("#101010")

        super().__init__(self.fig)
        self.setParent(parent)

        self.fig.tight_layout(pad=0.2)
        self.show_placeholder()

    def plot(
        self,
        data,
        extent=None,
        title="",
        cmap="gray",
        vmin=None,
        vmax=None,
        xlabel="",
        ylabel="",
        aspect="auto",
    ):
        """Render image."""
        self.ax.clear()
        self.ax.set_facecolor("#101010")

        im = self.ax.imshow(
            data,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            extent=extent,
            aspect=aspect,
            origin="upper",
        )

        self.ax.set_title(title, color="#ECEFF1", fontsize=11)
        self.ax.set_xlabel(xlabel, color="#CFD8DC", fontsize=9)
        self.ax.set_ylabel(ylabel, color="#CFD8DC", fontsize=9)
        self.ax.tick_params(colors="#B0BEC5", labelsize=8)

        self.fig.tight_layout(pad=0.2)
        self.draw()
        return im

    def show_placeholder(self):
        """Placeholder when no data is loaded (language-aware)."""
        self.ax.clear()
        self.ax.set_facecolor("#101010")
        self.ax.set_xticks([])
        self.ax.set_yticks([])

        text = I18n.tr("placeholder_no_data")

        self.ax.text(
            0.5,
            0.5,
            text,
            ha="center",
            va="center",
            color="#B0BEC5",
            fontsize=11,
            linespacing=1.5,
            transform=self.ax.transAxes,
        )

        self.fig.tight_layout(pad=0.2)
        self.draw()

    def clear_canvas(self):
        self.ax.clear()
        self.ax.set_facecolor("#101010")
        self.draw()
