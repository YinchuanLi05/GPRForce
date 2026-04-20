# GPRForce

**GPRForce** is an end-to-end desktop platform for ground-penetrating radar (GPR) data, built around a closed-loop workflow of **import, metadata completion, processing, visualization, comparison, 和 export**. It supports **linked inspection of simulation models (gprMax `.in`) and echo data (`.out` / `.npy`)**, while turning commonly used preprocessing and filtering pipelines into **parameterized and reproducible workflows** for both research and engineering delivery.

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

## Citation

If you use **GPRForce** in your research, publications, datasets, figures, engineering reports, or technical projects, please **cite the software and acknowledge its use** in the relevant manuscript, thesis, report, or documentation. Proper citation helps ensure academic credit, methodological traceability, and workflow reproducibility.

If an accompanying paper is available, we recommend citing **both**:
1. the **software itself**, especially for version-specific reproducibility; and
2. the **associated publication**, if it provides the detailed methodology, experiments, or validation results.

A recommended citation format is:

> Authors. **GPRForce: An End-to-End Closed-Loop Desktop Platform for Ground-Penetrating Radar Data**. Version x.x.x, Year. URL/DOI.

### Example BibTeX

> Please replace the placeholder fields below with the actual author list, version number, year, repository URL, or DOI before public release.

```bibtex
@software{gprforce2026,
  author  = {<Author 1> and <Author 2> and <Author 3>},
  title   = {GPRForce: An End-to-End Closed-Loop Desktop Platform for Ground-Penetrating Radar Data},
  year    = {2026},
  version = {<version>},
  url     = {<repository-or-release-url>},
  note    = {Open-source software}
}
```

### Suggested acknowledgement sentence

If you prefer a short statement in a paper, report, project document, or presentation, you may use:

> Part of the GPR data preparation, processing, visualization, and comparison workflow in this work was conducted using the open-source software **GPRForce**.

## Feedback, Issues, 和 Contact

We welcome bug reports, reproducibility issues, feature requests, optimization suggestions, 和 collaboration inquiries related to **GPRForce**.

If you encounter any problems while using the software, identify unexpected behavior, or have ideas for improvement, please feel free to contact us. Feedback from users is valuable for improving software robustness, usability, documentation quality, and engineering reproducibility.

You may reach us through one or more of the following channels:

- **GitHub Issues:** `<repository-issues-url>`
- **Email:** `<contact-email>`
- **Project homepage / lab page:** `<project-or-lab-url>`

When reporting an issue, we recommend including the following information whenever possible:

- operating system and Python version
- input data type (`.out` / `.npy`)
- the processing steps or parameter preset used
- error messages, screenshots, or minimal reproducible examples
- expected behavior versus observed behavior

We also welcome suggestions on the following aspects:

- preprocessing pipeline optimization
- visualization and interaction improvements
- support for additional GPR data formats
- performance acceleration and deployment refinement
- documentation, examples, and reproducibility enhancement

## Runtime Environment

- **OS:** Windows 10 / Windows 11 (64-bit)
- **Python:** **Python 3.9 or above is recommended**  
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
