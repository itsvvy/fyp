# 2026-09-27 CSI 单目相机标定

## 目标
对 Jetson Nano 的 CSI 单目相机（IMX219）做内参 + 畸变标定，为后续去畸变 / 立体视觉打基础。

## 环境
- 设备: NVIDIA Jetson Nano (B01, 4GB) + CSI 单镜头相机 (IMX219)
- 系统: JetPack 4.x / Python 3.6.9 / OpenCV 4.1.1
- 访问方式: VSCode remote-ssh + Jetson 本地键盘 / 显示器
- 棋盘格: 10×7 方格 → 内角点 9×6，方格边长 25 mm（chessboard9x6.pdf）
- 采集分辨率: 1920×1080 @ 30fps（GStreamer nvarguscamerasrc）

## 过程记录（b版）

### 1. 环境检查
- 目标：确认 Nano 默认环境能否直接跑采集与标定。
- 执行并观察：
  - `python3 --version` → `Python 3.6.9`
  - `python3 -c "import cv2, numpy; print(cv2.__version__)"` → `OpenCV 4.1.1`
  - `gst-inspect-1.0 nvarguscamerasrc` → 元素存在，caps 含 `video/x-raw(memory:NVMM)`、`format: NV12`
- 结论：三项通过，无需额外安装。

### 2. 参考代码评估
- 读了官方 cameraCalibration.py / calibration_utils.py / README.md。
- 发现：
  - `from __future__ import annotations`、`Sequence[str] | None` 等语法 → 需要 Python 3.10+；
  - requirements.txt 要求 opencv-python>=4.8；
  - `CHECKERBOARD=(6,9)`、方格按 1 个单位（与我们的板子不符）；
  - 只读仓库自带 images/*.jpg，不包含相机采集。
- 结论：官方代码不能直接跑、也不负责采集；改为自写 Python 3.6 / OpenCV 4.1.1 兼容脚本。

### 3. 采集脚本第一版（720p）与性能问题
- 做法：capture_chessboard.py 请求 1280x720@30fps，每帧做 findChessboardCorners + cornerSubPix。
- 现象：运行后“帧率很低、延迟很大、Jetson 发热”。
- 检查日志：
  - 相机被协商成 `Camera mode = 5`、`Frame Rate = 120.000005`；
  - 可用 sensor 模式里 1280x720 只有 60/120fps（无 30fps 档）；
  - 另有 `Cannot query video position`、`canberra-gtk-module` 两条提示，判断无害。
- 诊断：720p 无 30fps 档 → 自动选中 120fps；叠加每帧角点检测 → CPU 打满 → 显示帧率低、缓冲堆积延迟、发热。
- 修复：改 1920x1080@30（sensor mode 2）；appsink 加 `sync=false max-buffers=1 drop=true` 丢旧帧；`waitKey(30)` 节流；`cv2.setNumThreads(2)`。

### 4. 采集脚本第二版（1080p）与检测慢
- 现象：“卡顿缓解但勉强，棋盘格检测概率极低”，连按 s 多次都“未保存”。
- 检查日志：`Camera mode = 2`、`Frame Rate = 29.999999`（120fps 已解决）；Ctrl+C 的 traceback 停在 findChessboardCorners 那一行。
- 诊断：findChessboardCorners 在 1920x1080、检测不到棋盘时最慢（单次数百 ms~数秒）；每 5 帧调一次 → 周期性卡顿；显示与真实画面不同步 → 难以对准 → 检测一直失败。
- 修复：检测改到 960x540 降采样图上；频率降到每 10 帧；实时循环去掉 cornerSubPix；保存时才重检一次。

### 5. 棋盘格尺寸修正
- 现象：连官方 pattern.png 都检测不到，(8,5) 疑似错误，实测 `PATTERN_SIZE=(9,6)` 可行。
- 检查：重新分析 chessboard9x6.pdf，连通域显示棋盘格本体约 1477x1036px，按每格约 148px 推得 10 列 x 7 行方格 → 内角点 9x6。
- 结论：此前把“9x6 方格”误当成“8x5 内角点”。
- 修复：PATTERN_SIZE 由 (8,5) 改为 (9,6)。

### 6. 工作流调整（先拍后查）
- 决策：把实时检测从采集循环彻底移出；采集只负责流畅保存；新增 check_images.py 离线逐张检查（全分辨率、去掉 FAST_CHECK 避免漏检），通过者复制到 good/。
- 结果：check_images.py 处理 25 张，23 张通过。

### 7. findChessboardCorners 参数顺序 bug
- 现象：calibrate_camera.py 报 `TypeError: Expected Ptr<cv::UMat> for argument '%s'`，定位在 findChessboardCorners 调用处。
- 诊断：`findChessboardCorners(gray, pattern, flags)` 把 flags 当成第三个位置参数 corners。
- 修复：改为 `findChessboardCorners(gray, pattern, None, flags)`，check_images.py 同步修正。

### 8. 标定与物理校验
- 结果：23/23 张检测成功，图像 1920x1080；RMS = 1.0617px。
- 校验：fx≈2722，与 IMX219 物理预期（焦距约 3.04mm / 像元 1.12µm ≈ 2714px）基本一致 → 标定物理上合理。
- 附带：脚本里“平均重投影误差 0.14px”是计算公式错误（误导值），已修正为正确的逐点平均误差。

### 9. 可视化
- 新增 visualize.py：对 good/ 每张图重检角点并画线 → visualized/corners/；对 2 张样本做去畸变，原图与结果并排标注 Original/Undistorted → visualized/undistort/。
- 说明：去畸变对比图默认只取前 2 张（SAMPLE_COUNT=2），可按需调大。

## 关键结果
| 项 | 值 |
|---|---|
| 图像尺寸 | 1920x1080 |
| RMS 重投影误差 | 1.0617 px |
| 相机内参 K | [[2721.9, 0, 1050.4], [0, 2727.9, 480.1], [0, 0, 1]] |
| 畸变系数 [k1 k2 p1 p2 k3] | [0.0305, 0.7391, -0.0054, 0.0168, -1.6144] |
| 结果文件 | calibration.npz / calibration.yaml |

## 遗留问题 / 决策
- RMS 1.06px 略高于 0.5px 理想值，属“可用但偏粗糙”；后续做精确测距 / 深度需重拍优化。

## 下一步
- [ ] USB 双目标定
- [ ] （可选）补拍更多姿态、重新标定降低 RMS
