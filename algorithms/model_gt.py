# algorithms/model_gt.py
from __future__ import annotations

from typing import Dict, Any, Tuple, List
import numpy as np


# ==========================================
# 1. 简易几何判定函数（与 gprMax 物理含义保持一致）
# ==========================================

def is_in_box(X: np.ndarray, Y: np.ndarray, Z: np.ndarray,
              p1: Tuple[float, float, float],
              p2: Tuple[float, float, float]) -> np.ndarray:
    """
    判断 (X,Y,Z) 网格点是否在 box 内。
    p1, p2 为对角点，顺序不限。
    """
    x_min, x_max = sorted((p1[0], p2[0]))
    y_min, y_max = sorted((p1[1], p2[1]))
    z_min, z_max = sorted((p1[2], p2[2]))
    eps = 1e-6
    return (
        (X >= x_min - eps) & (X <= x_max + eps) &
        (Y >= y_min - eps) & (Y <= y_max + eps) &
        (Z >= z_min - eps) & (Z <= z_max + eps)
    )


def is_in_cylinder(X: np.ndarray, Y: np.ndarray, Z: np.ndarray,
                   p1: Tuple[float, float, float],
                   p2: Tuple[float, float, float],
                   r: float) -> np.ndarray:
    """
    判断 (X,Y,Z) 网格点是否在 cylinder 内，支持任意方向的圆柱。
    p1, p2 为两端面中心坐标。
    """
    p1 = np.asarray(p1, dtype=float)
    p2 = np.asarray(p2, dtype=float)
    axis_vec = p2 - p1
    length_sq = float(np.dot(axis_vec, axis_vec))

    # 退化为球（两端重合）
    if length_sq < 1e-12:
        return (X - p1[0])**2 + (Y - p1[1])**2 + (Z - p1[2])**2 <= r**2

    # 所有点坐标
    P = np.stack((X, Y, Z), axis=-1)         # (..., 3)
    v = P - p1                               # (..., 3)

    t = np.sum(v * axis_vec, axis=-1) / length_sq
    t_clamped = np.clip(t, 0.0, 1.0)
    Q = p1 + t_clamped[..., None] * axis_vec  # 最近点

    dist_sq = np.sum((P - Q)**2, axis=-1)
    return dist_sq <= r**2


def is_in_sphere(X: np.ndarray, Y: np.ndarray, Z: np.ndarray,
                 c: Tuple[float, float, float], r: float) -> np.ndarray:
    """判断 (X,Y,Z) 网格点是否在 sphere 内。"""
    return ((X - c[0])**2 + (Y - c[1])**2 + (Z - c[2])**2) <= r**2


def is_in_cylindrical_sector(
    X: np.ndarray,
    Y: np.ndarray,
    Z: np.ndarray,
    axis: str,
    center: Tuple[float, float],
    axis_range: Tuple[float, float],
    r: float,
    start_deg: float,
    sweep_deg: float,
) -> np.ndarray:
    """
    判断 (X,Y,Z) 网格点是否在 cylindrical_sector 内。

    语法对应 gprMax 文档:
    #cylindrical_sector: c1 f1 f2 f3 f4 f5 f6 f7 str1 [c1]

    - axis = c1: 'x' / 'y' / 'z'
    - center = (f1, f2): 平面内圆心坐标
    - axis_range = (f3, f4): 沿圆柱轴方向的 [low, high]
    - r = f5: 半径
    - start_deg = f6: 起始角 (deg)
    - sweep_deg = f7: 扫掠角 (deg, 逆时针)
    """
    axis = axis.lower()
    cx, cy = center
    a_min, a_max = sorted(axis_range)
    eps = 1e-9

    if axis == "z":
        # 扇形在 x-y 平面，轴向是 z
        dx = X - cx
        dy = Y - cy
        axis_coord = Z
    elif axis == "y":
        # 扇形在 x-z 平面，轴向是 y
        dx = X - cx
        dy = Z - cy
        axis_coord = Y
    elif axis == "x":
        # 扇形在 y-z 平面，轴向是 x
        dx = Y - cx
        dy = Z - cy
        axis_coord = X
    else:
        return np.zeros_like(X, dtype=bool)

    # 半径约束
    rho = np.sqrt(dx * dx + dy * dy)
    inside_r = rho <= r + eps

    # 角度约束（0° 沿平面第一坐标正方向，逆时针为正）
    theta = np.degrees(np.arctan2(dy, dx))
    theta = np.mod(theta, 360.0)

    start = np.mod(start_deg, 360.0)
    sweep = sweep_deg

    if sweep >= 0:
        delta = (theta - start) % 360.0
        inside_ang = delta <= sweep + eps
    else:
        # 负 sweep：从 start 反向扫 |sweep|
        delta = (start - theta) % 360.0
        inside_ang = delta <= -sweep + eps

    # 轴向厚度约束
    inside_axis = (axis_coord >= a_min - eps) & (axis_coord <= a_max + eps)

    return inside_r & inside_ang & inside_axis


# ==========================================
# 2. 从 parse_in 得到的 info 构建几何真值切片
# ==========================================

def _collect_objects_from_info(info: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Tuple[float, float, float]]:
    """
    从 parse_in_file 解析得到的 info 中，收集材料和体积几何对象。
    目前使用的对象类型：
    - box
    - cylinder
    - sphere

    返回:
        materials : dict, name -> material dict 或 epsr
        objects   : list[{type, params..., mat}]
        domain    : (X, Y, Z)
    """
    materials = info.get("materials", {}) or {}
    domain = tuple(info.get("domain", (1.0, 1.0, 1.0)))

    objects: List[Dict[str, Any]] = []

    # 注意：这里仍然假设 box 先于 cylinder/sphere，和典型 gprMax 模型一致。
    # 如果将来需要完全按照行顺序，可以在 parse_in.py 中直接维护一个 "objects" 列表。
    for b in info.get("boxes", []):
        objects.append({
            "type": "box",
            "p1": tuple(b["p1"]),
            "p2": tuple(b["p2"]),
            "mat": b["material"],
        })

    for c in info.get("cylinders", []):
        objects.append({
            "type": "cylinder",
            "p1": tuple(c["p1"]),
            "p2": tuple(c["p2"]),
            "r": float(c["radius"]),
            "mat": c["material"],
        })

    for s in info.get("spheres", []):
        objects.append({
            "type": "sphere",
            "c": tuple(s["center"]),
            "r": float(s["radius"]),
            "mat": s["material"],
        })
    # cylindrical_sector （扇形圆柱）
    for cs in info.get("cylindrical_sectors", []):
        objects.append({
            "type": "cylindrical_sector",
            "axis": cs.get("axis", "z"),
            "center": tuple(cs.get("center", (0.0, 0.0))),
            "axis_range": tuple(cs.get("axis_range", (0.0, 0.0))),
            "r": float(cs.get("radius", 0.0)),
            "start": float(cs.get("start_angle", 0.0)),
            "sweep": float(cs.get("sweep_angle", 0.0)),
            "mat": cs["material"],
        })


    return materials, objects, domain


def build_gt_slice_from_in_info(
    info_fallback: Dict[str, Any],
    plane: str = "xz",
    coord: float | None = None,
    n1: int = 256,
    n2: int = 256,
    extent: Tuple[float, float, float, float] | None = None,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    根据 .in 解析结果构建一个几何真值切片（目前只支持 XZ 平面）。

    参数
    ----
    info_fallback : dict
        io_module.parse_in.parse_in_file 返回的 info。
    plane : str
        截面平面，目前支持 "xz"（水平 x，竖直为深度）。
    coord : float
        对于 XZ 平面，为切片所在的 y 坐标；若为 None，则使用 rx_pos.y 或 domain 中点。
    n1, n2 : int
        横向 / 深度方向上的采样点数。
    extent : (x_min, x_max, d_min, d_max)
        与 B 扫显示一致的物理范围，d 为“深度”坐标（m，向下为正）。

    返回
    ----
    mask_map : (n2, n1) int
        目标掩膜（目前 cylinder / sphere 标记为 1，其它为 0）。
    eps_map : (n2, n1) float
        相对介电常数分布。
    extra : dict
        额外信息，如 {'u': x_coords, 'v': depth_coords, 'bg_top_z': z_surface}
    """
    if info_fallback is None:
        return np.zeros((n2, n1), dtype=int), np.ones((n2, n1), dtype=float), {}

    materials, objects, domain = _collect_objects_from_info(info_fallback)

    if not objects:
        # 没有几何对象，就返回均匀背景
        eps_bg = float(info_fallback.get("eps_bg", 6.0))
        mask = np.zeros((n2, n1), dtype=int)
        eps_map = np.full((n2, n1), eps_bg, dtype=float)
        # 构建简单坐标
        if extent is None:
            extent = (0.0, domain[0], 0.0, domain[2])
        x_min, x_max, d_min, d_max = extent
        u = np.linspace(x_min, x_max, n1)
        v = np.linspace(d_min, d_max, n2)
        return mask, eps_map, {"u": u, "v": v, "bg_top_z": d_min}

    # ---- 步骤 1：确定坐标范围与地表高度 ----
    if extent is None:
        extent = (0.0, domain[0], 0.0, domain[2])

    x_min, x_max, d_min, d_max = extent

    # 估计地表高度：取所有 box/cylinder/sphere 的最高 z，
    # 且不把 domain 顶当作地表。
    bg_top_z = 0.0
    domain_z = float(domain[2])

    for obj in objects:
        z_high = None
        if obj["type"] == "box":
            z_high = max(obj["p1"][2], obj["p2"][2])
        elif obj["type"] == "cylinder":
            z_high = max(obj["p1"][2], obj["p2"][2]) + obj.get("r", 0.0)
        elif obj["type"] == "sphere":
            z_high = obj["c"][2] + obj["r"]
        elif obj["type"] == "cylindrical_sector":
            axis = obj.get("axis", "z").lower()
            if axis == "z":
                # 轴向为 z，厚度范围就是 [f3, f4]
                z_high = max(obj["axis_range"])
            elif axis in ("x", "y"):
                # 轴向为 x / y，扇形在 y-z / x-z 平面，z 范围≈中心 z ± r
                # center 对 y/z 或 x/z 的第二个分量是 z
                z_center = obj["center"][1]
                z_high = z_center + obj["r"]


        if z_high is not None and z_high < domain_z - 1e-3:
            bg_top_z = max(bg_top_z, z_high)

    if bg_top_z <= 0.0:
        # 兜底：若没有找到明显的地表，就用域高度的一半
        bg_top_z = 0.5 * domain_z

    # ---- 步骤 2：生成 XZ 网格 ----
    if plane.lower() != "xz":
        # 当前只支持 x-z 截面
        return np.zeros((n2, n1), dtype=int), np.ones((n2, n1), dtype=float), {}

    # y 坐标：优先用 rx_pos.y，其次用 domain 中点
    if coord is None:
        ry = None
        if "rx_pos" in info_fallback:
            try:
                ry = float(info_fallback["rx_pos"][1])
            except Exception:
                ry = None
        if ry is None:
            ry = float(domain[1]) / 2.0
        coord = ry

    # u: x 轴; v: depth 轴（与 B 扫保持一致）
    u = np.linspace(x_min, x_max, n1)
    v = np.linspace(d_min, d_max, n2)

    X, D = np.meshgrid(u, v)          # D 为“深度”(向下为正)
    Z = bg_top_z - D                  # 转换到 gprMax 的物理 z 坐标
    Y = np.full_like(X, coord)       # 常数切片

    # ---- 步骤 3：画家算法绘制 epsr & mask ----
    eps_bg = float(info_fallback.get("eps_bg", 6.0))
    eps_map = np.full_like(X, eps_bg, dtype=float)
    mask_map = np.zeros_like(X, dtype=int)

    for obj in objects:
        mat_name = str(obj["mat"]).lower()
        mat_info = materials.get(mat_name)

        if isinstance(mat_info, dict):
            epsr = float(mat_info.get("epsr", eps_bg))
        elif isinstance(mat_info, (float, int)):
            epsr = float(mat_info)
        else:
            # 内置材料：简单兜底
            if mat_name in ("pec", "metal"):
                epsr = 1e6
            elif mat_name in ("free_space", "air", "vacuum"):
                epsr = 1.0
            else:
                epsr = eps_bg

        mask = None
        if obj["type"] == "box":
            mask = is_in_box(X, Y, Z, obj["p1"], obj["p2"])
        elif obj["type"] == "cylinder":
            mask = is_in_cylinder(X, Y, Z, obj["p1"], obj["p2"], obj["r"])
        elif obj["type"] == "sphere":
            mask = is_in_sphere(X, Y, Z, obj["c"], obj["r"])
        elif obj["type"] == "cylindrical_sector":
            mask = is_in_cylindrical_sector(
                X, Y, Z,
                axis=obj["axis"],
                center=obj["center"],
                axis_range=obj["axis_range"],
                r=obj["r"],
                start_deg=obj["start"],
                sweep_deg=obj["sweep"],
            )


        if mask is not None and np.any(mask):
            eps_map[mask] = epsr
            if obj["type"] in ("cylinder", "sphere", "cylindrical_sector"):
                mask_map[mask] = 1


    # ---- 步骤 4：底部无限延拓 ----
    underground = (Z < 0.0)
    eps_map[underground & (eps_map == eps_bg)] = eps_bg

    extra = {
        "u": u,
        "v": v,
        "bg_top_z": bg_top_z,
    }
    return mask_map, eps_map, extra
