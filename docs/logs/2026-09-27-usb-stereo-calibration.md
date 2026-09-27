# 2026-09-27 USB 双目相机标定

## 目标
对 USB 双目相机（PayCam C4008，side-by-side 输出）做左右单目 + 双目标定，得到左右内参 / 畸变和双目 R / T / 基线。

## 环境
- 设备: NVIDIA Jetson Nano (B01, 4GB) + PayCam C4008 (USB, SBS)
- 系统: JetPack 4.x / Python 3.6.9 / OpenCV 4.1.1
- 设备节点: /dev/video1（Nano 上 video0=IMX219, video1=PayCam）
- 格式: MJPG 2560×960 @ 30fps（每目 1280×960）
- 棋盘格: 10×7 方格 → 内角点 9×6，方格边长 25 mm

## 过程记录（b版）

### 1. 相机识别（Windows）
- 在 Windows 上用 Get-PnpDevice 识别到 PayCam C4008（VID_2404 / PID_1689），只暴露一个 Camera 接口（MI_00）。
- 初始判断它像单目，但实际是“双路合一路”的 SBS 输出。

### 2. WSL2 检查
- 通过 usbipd attach 挂到 WSL2 Ubuntu，`v4l2-ctl -d /dev/video0 --info` 显示：
  - /dev/video0：Video Capture（真正的视频流）
  - /dev/video1：Metadata Capture（UVC 元数据节点，不是第二只眼）
- 驱动为 uvcvideo。

### 3. 发现 SBS
- 相机 App 画面是左右并排一张图，一边左目、一边右目 → 确认是 side-by-side 双目输出。

### 4. 格式确认
- `v4l2-ctl --list-formats-ext` 列出：
  - MJPG：2560×960 / 1600×600 / 1280×480 / 2560×720 / 3040×1520，均 @30fps
  - YUYV：同分辨率但只有 1~5fps
- 结论：用 MJPG @30fps。

### 5. 环境选择
- 决定在 Jetson Nano 上做（ASTRI 目标边缘设备、原生 USB/V4L2、无需 usbipd）。

### 6. Nano 设备确认
- `v4l2-ctl --list-devices`：video0=IMX219(CSI)，video1=PayCam(USB)。
- 结论：采集脚本 DEVICE 用 /dev/video1。

### 7. 写脚本
- capture_stereo_usb.py：V4L2 + MJPG + 从中间切开成左右目，按 s 成对保存。
- calibrate_stereo.py：左右各做单目标定 → stereoCalibrate（固定内参，算 R/T/E/F）→ stereoRectify（R1/R2/P1/P2/Q）→ 存 stereo_calibration.npz。

### 8. 左右目颠倒与 FLIP_LR
- 现象：感觉 L/R 标注颠倒。
- 判断：挡镜头测试（挡物理左目，看画面哪半边黑）。
- 修复：加 FLIP_LR 开关；并修复 FLIP_LR 不影响预览窗口的 bug——预览改为 hconcat(处理后的 left, right)，所见即所存。

### 9. 屏幕小 → HTTP 预览
- Nano 屏幕太小，写 stream_stereo.py：HTTP MJPEG 流 + 浏览器“Save pair”按钮，在本机浏览器采集。

### 10. 采集与标定
- 采集 28 对，calibrate_stereo.py：27/28 有效（pair_013 失败）。

## 关键结果
| 项 | 值 |
|---|---|
| 每目分辨率 | 1280x960 |
| 左目 RMS | 0.5464 px |
| 右目 RMS | 0.5017 px |
| 双目 RMS | 0.6867 px |
| 基线 |T| | 0.0536 m（5.36 cm） |
| 平移 T | [-0.0532, 0.0009, 0.0064] m |
| 旋转 R | ≈ 单位阵（roll ≈ 1°） |
| 结果文件 | stereo_calibration.npz |

## 遗留问题 / 决策
- 标定可用，可进入立体校正 + 视差 / 深度阶段。

## 下一步
- [ ] 立体校正 + 视差 / 深度可视化验证
