# GPRForce

**GPRForce** is an end-to-end desktop platform for ground-penetrating radar (GPR) data, built around a closed-loop workflow of **import, metadata completion, processing, visualization, comparison, and export**. It supports **linked inspection of simulation models (gprMax `.in`) and echo data (`.out` / `.npy`)**, while turning commonly used preprocessing and filtering pipelines into **parameterized and reproducible workflows** for both research and engineering delivery.

> **Name meaning:** GPR stands for *Ground Penetrating Radar*. The word *Force* reflects the software’s intended role as a driving force for GPR workflows—transforming scattered empirical know-how into an operational, comparable, and reproducible engineering process.

## Key Features

- **Data Import**
  - Supports importing **gprMax `.out` (HDF5)** files and **array-based `.npy`** data
  - Provides a **metadata completion mechanism** for data lacking essential information, such as `.npy` files, including parameters like **dt / dx / εr / fc**

- **Model–Data Linking (Core Capability)**
  - Parses gprMax **`.in`** files to extract **domain size, grid settings, material definitions, and geometric object information**
  - Supports **2D ground-truth / material distribution visualization** and **3D geometry preview**, enabling linked cross-reference between the simulation model and radar data

- **Configurable Processing Pipeline**
  - Typical operations include **DC removal, time-zero correction, dewow, top mute windowing, background removal, gain control, AGC, band-pass filtering, F-K filtering, and envelope display**
  - All steps are **switchable, parameterized, and reproducible**, making experimental workflows easier to control and repeat

- **Visualization and Interaction**
  - Supports **B-scan axis calibration** in time/depth coordinates, with depth converted based on **relative permittivity (εr)**
  - Provides **contrast clipping, ROI overlay, and A-scan point selection/inspection**

- **Comparison and Reproducibility**
  - Supports **single-view and four-panel comparison slots** for side-by-side evaluation of multiple processing schemes
  - Enables **preset saving/loading in JSON format** for one-click reproduction of parameter configurations

- **Export and Delivery**
  - Data export: **`.npy` / `.mat`**
  - Figure export: **`.png` / `.jpg` / `.pdf`**
  - Parameter preset export: **`.json`**

## Runtime Environment

- **OS:** Windows 10 / Windows 11 (64-bit)
- **Python:** **Python 3.10 or above is recommended**  
  (the project has been verified to run successfully in a Python 3.10 environment)
- **Main dependencies:** PyQt6, NumPy, SciPy, Matplotlib, h5py, PyVista / pyvistaqt (for 3D visualization), etc.

## Installation and Launch (Recommended via Conda)

```bash
conda create -n gprforce310 python=3.10 -y
conda activate gprforce310
cd F:\GPRForce
pip install -r requirements.txt
python main.py
```
