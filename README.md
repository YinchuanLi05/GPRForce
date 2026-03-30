# GPRForce

**GPRForce** 是一套面向探地雷达（GPR）数据的 **“导入—补参—处理—展示—对比—导出”** 端到端闭环桌面平台。它支持将 **仿真模型（gprMax `.in`）与回波数据（`.out/.npy`）联动对照**，并将常用预处理/滤波链路参数化、可复现化，便于科研与工程交付。

> 名称含义：GPR = Ground Penetrating Radar；Force 表示本软件希望成为 GPR 工作流的“驱动力”——把分散经验固化为可操作、可对比、可复现的工程流程。

## 主要特性

- **数据导入**
  - 支持导入 **gprMax `.out`（HDF5）** 与 **数组 `.npy`**
  - 对 `.npy` 等缺失元信息的数据提供 **补参机制**（dt / dx / εr / fc 等）
- **模型联动（特色能力）**
  - 可解析 gprMax **`.in`**：提取 domain、网格、材料与几何体信息
  - 支持 **2D 真值/材料分布** 与 **3D 几何预览**，实现模型与数据联动对照
- **可配置处理流水线**
  - 典型步骤：去直流、t0 校正、dewow、顶部静音窗、背景去除、增益、AGC、带通、F-K、包络显示等
  - 支持参数化开关与调参复现
- **可视化与交互**
  - B-scan 坐标标定（时间/深度，深度基于 εr 换算）
  - 对比度裁剪、ROI 叠加、A-scan 点选查看
- **对比与复现**
  - 单图 / 四宫格对比槽（多方案并列评估）
  - Preset（json）保存/加载，一键复现参数方案
- **导出交付**
  - 数据：npy / mat
  - 图像：png / jpg / pdf
  - 参数预设：json

## 运行环境

- OS：Windows 10 / Windows 11（64-bit）
- Python：**建议 Python >= 3.10（本项目已在 3.10 环境验证跑通）**
- 主要依赖：PyQt6、NumPy、SciPy、Matplotlib、h5py、PyVista/pyvistaqt（用于 3D）等

## 安装与启动（推荐 Conda）

```bash
conda create -n gprforce310 python=3.10 -y
conda activate gprforce310
cd F:\GPRForce
pip install -r requirements.txt
python main.py