# FYP — Edge-Based Dual Stereo Sensing System (ASTRI)

融合 CIS（CMOS Image Sensor）与 DVS（Dynamic Vision Sensor）的双目边缘感知系统，用于实时障碍检测与跟踪。目标是在 NVIDIA Jetson Nano 等边缘设备上端到端运行，不依赖云端。

## 硬件
- NVIDIA Jetson Nano (B01, 4GB)
- CSI 单镜头相机 (IMX219)
- USB 双目相机 (PayCam C4008，side-by-side 输出)
- 棋盘格：10×7 方格（内角点 9×6），方格边长 25 mm

## 目录结构
```
fyp/
├── README.md
├── .gitignore
├── docs/
│   ├── project-overview.md
│   └── logs/                      # 工作日志（一日期一文件）
├── calibration/
│   ├── mono/                      # CSI 单目相机标定
│   │   ├── scripts/
│   │   └── results/
│   └── stereo/                    # USB 双目相机标定
│       ├── scripts/
│       └── results/
└── assets/
    └── chessboard9x6.pdf
```

## 标定结果速览
- 单目（CSI IMX219，1920×1080）：RMS 1.06 px，fx≈2722。详见 `calibration/mono/results/`。
- 双目（PayCam C4008，每目 1280×960）：基线 5.36 cm，左右 RMS 0.55 / 0.50 px，双目 RMS 0.69 px。详见 `calibration/stereo/results/`。

## 复现
见各 `calibration/*/results/README.md` 与对应日志。
