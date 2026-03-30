# io_module/parse_in.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List


def parse_in_text(text: str) -> Dict[str, Any]:
    """
    解析 gprMax .in 文本，抽取物理与几何参数。

    支持的命令（常用部分）：
    - #title
    - #domain, #dx_dy_dz, #time_window, #pml_cells
    - #material
    - #box
    - #cylinder / #cylinder_new
    - #sphere
    - #cylindrical_sector   （先解析，不参与当前真值构造）
    - #plate                （先解析，不参与当前真值构造）
    - #triangle             （先解析，不参与当前真值构造）
    - #edge                 （先解析，不参与当前真值构造）
    - #waveform
    - #hertzian_dipole
    - #rx
    - #src_steps, #rx_steps

    返回 info 字典中，至少包含（视输入而定）：
    - 'materials' : {name: {'epsr', 'sigma', 'mur', 'kappa'}}
    - 'boxes' / 'cylinders' / 'spheres' / ... : 几何对象列表
    - 'domain' : (X, Y, Z)
    - 'dx_dy_dz' : (dx, dy, dz)
    - 'time_window' : float
    - 'waveform' : {'type', 'amp', 'fc', ...}
    - 'src_pos', 'rx_pos', 'src_steps', 'rx_steps'
    - 'eps_bg' : 推断的背景介电常数
    - 'trace_step' : B-scan 道间距（优先用 rx_steps.x，否则 src_steps.x）
    """
    info: Dict[str, Any] = {}
    materials: Dict[str, Any] = {}
    boxes: List[Dict[str, Any]] = []
    cylinders: List[Dict[str, Any]] = []
    spheres: List[Dict[str, Any]] = []
    cylindrical_sectors: List[Dict[str, Any]] = []
    plates: List[Dict[str, Any]] = []
    triangles: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    in_python_block = False

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        # 跳过 python 脚本块（#python ... #end_python）
        lstripped = raw.lstrip()
        if lstripped.startswith("#python"):
            in_python_block = True
            continue
        if in_python_block:
            if lstripped.startswith("#end_python") or lstripped.startswith("#python_end"):
                in_python_block = False
            continue

        if not line.startswith("#"):
            continue

        # 去掉 '#' 开头
        line = line[1:]

        # 去掉行尾注释（再次出现的 #）
        if "#" in line:
            line, _ = line.split("#", 1)
        line = line.strip()
        if not line:
            continue

        if ":" not in line:
            continue

        cmd, rest = line.split(":", 1)
        cmd = cmd.strip().lower()
        rest = rest.strip()
        parts = rest.split() if rest else []
        if not parts and cmd != "title":
            continue

        # ------------ 基本参数 ------------
        if cmd == "title":
            info["title"] = rest
            continue

        if cmd == "domain" and len(parts) >= 3:
            try:
                info["domain"] = tuple(float(p) for p in parts[:3])
            except ValueError:
                pass
            continue

        if cmd == "dx_dy_dz" and len(parts) >= 3:
            try:
                info["dx_dy_dz"] = tuple(float(p) for p in parts[:3])
            except ValueError:
                pass
            continue

        if cmd == "time_window" and len(parts) >= 1:
            try:
                info["time_window"] = float(parts[0])
            except ValueError:
                pass
            continue

        if cmd == "pml_cells" and len(parts) >= 6:
            try:
                info["pml_cells"] = tuple(int(float(p)) for p in parts[:6])
            except ValueError:
                pass
            continue

        # ------------ 材料 ------------
        if cmd == "material" and len(parts) >= 5:
            try:
                epsr, sigma, mur, kappa = (float(x) for x in parts[:4])
            except ValueError:
                continue
            name = parts[4].lower()
            materials[name] = {
                "epsr": epsr,
                "sigma": sigma,
                "mur": mur,
                "kappa": kappa,
            }
            continue

        # ------------ 体积几何 ------------
        if cmd == "box" and len(parts) >= 7:
            try:
                coords = [float(p) for p in parts[:6]]
            except ValueError:
                continue
            mat_name = parts[6].lower()
            boxes.append(
                {
                    "p1": tuple(coords[:3]),
                    "p2": tuple(coords[3:]),
                    "material": mat_name,
                }
            )
            continue

        if cmd in ("cylinder", "cylinder_new") and len(parts) >= 8:
            try:
                vals = [float(p) for p in parts[:7]]
            except ValueError:
                continue
            mat_name = parts[7].lower()
            cylinders.append(
                {
                    "p1": tuple(vals[:3]),
                    "p2": tuple(vals[3:6]),
                    "radius": vals[6],
                    "material": mat_name,
                }
            )
            continue

        if cmd == "sphere" and len(parts) >= 5:
            try:
                cx, cy, cz, r = (float(p) for p in parts[:4])
            except ValueError:
                continue
            mat_name = parts[4].lower()
            spheres.append(
                {
                    "center": (cx, cy, cz),
                    "radius": r,
                    "material": mat_name,
                }
            )
            continue

        if cmd == "cylindrical_sector" and len(parts) >= 9:
            # #cylindrical_sector: axis f1 f2 f3 f4 f5 f6 f7 mat [c1]
            axis = parts[0].lower()
            try:
                fvals = [float(p) for p in parts[1:8]]
            except ValueError:
                continue
            mat_name = parts[8].lower()
            cylindrical_sectors.append(
                {
                    "axis": axis,                 # 'x' / 'y' / 'z'
                    "center": (fvals[0], fvals[1]),
                    "axis_range": (fvals[2], fvals[3]),
                    "radius": fvals[4],
                    "start_angle": fvals[5],      # deg
                    "sweep_angle": fvals[6],      # deg
                    "material": mat_name,
                }
            )
            continue

        # ------------ 表面 / 线几何（先解析，不参与当前真值） ------------
        if cmd == "plate" and len(parts) >= 7:
            try:
                vals = [float(p) for p in parts[:6]]
            except ValueError:
                continue
            mat_name = parts[6].lower()
            plates.append(
                {
                    "p1": tuple(vals[:3]),
                    "p2": tuple(vals[3:]),
                    "material": mat_name,
                }
            )
            continue

        if cmd == "triangle" and len(parts) >= 11:
            try:
                fvals = [float(p) for p in parts[:10]]
            except ValueError:
                continue
            mat_name = parts[10].lower()
            triangles.append(
                {
                    "v1": tuple(fvals[0:3]),
                    "v2": tuple(fvals[3:6]),
                    "v3": tuple(fvals[6:9]),
                    "thickness": fvals[9],
                    "material": mat_name,
                }
            )
            continue

        if cmd == "edge" and len(parts) >= 7:
            try:
                vals = [float(p) for p in parts[:6]]
            except ValueError:
                continue
            mat_name = parts[6].lower()
            edges.append(
                {
                    "p1": tuple(vals[:3]),
                    "p2": tuple(vals[3:]),
                    "material": mat_name,
                }
            )
            continue

        # ------------ 波形 / 源 / 接收 ------------
        if cmd == "waveform" and len(parts) >= 3:
            # 示例：#waveform: ricker 1 700000000 srcp
            wtype = parts[0].lower()
            try:
                amp = float(parts[1])
                fc = float(parts[2])
            except ValueError:
                continue
            wf = {"type": wtype, "amp": amp, "fc": fc}
            # 若后续还有参数（相位、延时），可以按需扩展
            info["waveform"] = wf
            continue

        if cmd == "hertzian_dipole" and len(parts) >= 5:
            # #hertzian_dipole: pol x y z srcp
            pol = parts[0]
            try:
                x, y, z = (float(p) for p in parts[1:4])
            except ValueError:
                continue
            info["src_pol"] = pol
            info["src_pos"] = (x, y, z)
            continue

        if cmd == "rx" and len(parts) >= 3:
            try:
                x, y, z = (float(p) for p in parts[:3])
            except ValueError:
                continue
            rx_list = info.setdefault("rx_pos_list", [])
            rx_list.append((x, y, z))
            # 为兼容旧代码，保留第一个 rx 作为 rx_pos
            if "rx_pos" not in info:
                info["rx_pos"] = (x, y, z)
            continue

        if cmd == "src_steps" and len(parts) >= 3:
            try:
                info["src_steps"] = tuple(float(p) for p in parts[:3])
            except ValueError:
                pass
            continue

        if cmd == "rx_steps" and len(parts) >= 3:
            try:
                info["rx_steps"] = tuple(float(p) for p in parts[:3])
            except ValueError:
                pass
            continue

        # 其它命令先忽略（snapshot / geometry_view 等）

    # ------------ 汇总结果 ------------
    info["materials"] = materials
    if boxes:
        info["boxes"] = boxes
    if cylinders:
        info["cylinders"] = cylinders
    if spheres:
        info["spheres"] = spheres
    if cylindrical_sectors:
        info["cylindrical_sectors"] = cylindrical_sectors
    if plates:
        info["plates"] = plates
    if triangles:
        info["triangles"] = triangles
    if edges:
        info["edges"] = edges

    # 背景 eps 粗略推断：优先找名字像 background/sand/soil/half_space 的材料
    bg_eps = None
    if materials:
        preferred = ("background", "sand", "soil", "half_space")
        for name in preferred:
            if name in materials:
                bg_eps = float(materials[name]["epsr"])
                break
        if bg_eps is None:
            # 否则就取第一个材料的 epsr
            first = next(iter(materials.values()))
            bg_eps = float(first["epsr"])
    if bg_eps is not None:
        info["eps_bg"] = bg_eps

    # B-Scan 道间距（trace_step）：优先用 rx_steps.x，其次 src_steps.x
    trace_step = None
    if "rx_steps" in info:
        trace_step = float(info["rx_steps"][0])
    elif "src_steps" in info:
        trace_step = float(info["src_steps"][0])
    info["trace_step"] = trace_step

    return info


def parse_in_file(path: Path | str) -> Dict[str, Any]:
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="ignore")
    info = parse_in_text(text)
    # 方便后面使用原始路径
    info["in_path"] = str(path)
    return info
