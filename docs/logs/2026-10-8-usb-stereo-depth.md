# 2026-10-11 USB 双目深度图（视差法）

## 目标

基于已完成的 USB 双目标定结果，用视差法离线计算双目深度图，做成一个独立于标定的“双目深度”demo。

## 环境

- 设备: NVIDIA Jetson Nano (B01, 4GB) + PayCam C4008 (USB, side-by-side 输出)
- 系统: JetPack 4.x / Python 3.6.9 / OpenCV 4.1.1
- 设备节点: /dev/video1（Nano 上 video0=IMX219, video1=PayCam）
- 采集格式: MJPG 2560×960 @ 30fps（切开后每目 1280×960）
- 依赖输入: stereo_calibration.npz（来自 2026-09-27-usb-stereo-calibration）
- 目录: 独立于标定，新建 ~/dev/stereo_depth/

## 过程记录

### 1. 方案确认

- 确认用视差法（stereo disparity）：立体校正 → 视差 → 深度。
- 深度公式 Z = f·b / d；焦距 f 和基线 b 已封装在 Q 矩阵里，无需手工量取。
- 确认离线处理：直接读已拍好的左右目图片计算，不依赖实时相机。

### 2. 目录与脚本规划

- 深度任务与标定解耦，只保留两个核心脚本 + 一个标定结果文件。
- capture_stereo.py：采集左右目。
- depth_stereo.py：算视差与深度。
- stereo_calibration.npz：唯一的外部输入，从 calibrationDurl 拷一份。

### 3. 采集脚本

- 先按“本机屏幕太小”做了 HTTP 浏览器推流版；后按用户要求改回 imshow 弹窗 + 键盘 s/q 保存。
- capture_stereo.py：V4L2 + MJPG + 从中间切开左右目 + FLIP_LR/MIRROR 校正方向 + 弹窗预览。
- 关键约束：FLIP_LR/MIRROR 必须与标定采集时一致，否则左右目约定变化会导致深度反/错。

### 4. 深度脚本

- depth_stereo.py 流程：
  - initUndistortRectifyMap(mtxL/distL/R1/P1) + remap 校正左目；右目同理用 R2/P2；
  - StereoSGBM（或 StereoBM）求视差；
  - reprojectImageTo3D(disparity, Q) 转深度（米）。
- 输出：rectified.jpg / disparity.jpg / depth.jpg / depth.npy。

### 5. 首次运行与结果

- f = 1343.8 px（stereoRectify 给左右取的共同焦距，介于左右 fx≈1338/1373 之间，合理）。
- 中心区域采样深度 0.45 ~ 0.96 m，存在无效点（----）。
- 诊断无效点来源：纹理少 / 遮挡 / 过近（numDisparities=192 对应最近约 f·b/192 ≈ 0.37 m）。

### 6. 关键概念澄清

- stereo_calibration.npz 不“自动生效”：由 depth_stereo.py 显式 np.load 读取后喂给 OpenCV；采集脚本不读它。
- 基线 |T| = 5.36 cm 是 stereoCalibrate 从棋盘格图像算出的，不是写死数据；唯一手工物理量是棋盘格 25 mm。

### 7. 批量处理与目录结构

- 现象：拍了 3 组图像，结果只有 1 组。
- 原因：脚本默认只处理第一对，且输出文件名固定会互相覆盖。
- 修复：改为遍历所有配对，每组结果放独立子文件夹 depth_output/<pair>/。

### 8. depth.jpg 颜色方向修正

- 现象：怀疑 depth.jpg 的“暖色=近 / 冷色=远”反了。
- 诊断：原代码 depth_vis[depth_vis<=0]=MAX_DEPTH 后 normalize，把近（小值）映射成蓝、远/无效（5.0）映射成红，确实反了；disparity.jpg 方向正确（大视差=近=红）。
- 修复：只对有效深度范围归一化并取反，近=红/远=蓝，无效单独置黑。

### 9. 更高精度方法调研

- SGBM 之上可选项：
  - ① 调 SGBM 参数（零成本，先做）；
  - ② SGBM + WLS 滤波（需 opencv_contrib/ximgproc，Nano 默认未编 contrib）；
  - ③ 深度学习（RAFT-Stereo / CREStereo，需 GPU + TensorRT，工程量大）；
  - ④ 换硬件（RealSense / ZED，若精度为硬需求）。
- 决策：先在 Nano 上走调参路线。

## 关键结果

项 | 值
---|---
方法 | 视差法（StereoSGBM）
校正后焦距 f | 1343.8 px
基线 | 5.36 cm
采样深度范围 | 0.45 ~ 0.96 m（近距离场景）
结果文件 | depth_output/<pair>/ 下 rectified.jpg / disparity.jpg / depth.jpg / depth.npy

## 遗留问题 / 决策

- 目前为离线单帧 / 批量处理，未做实时深度流（Nano 上 SGBM 帧率有限）。
- 深度精度受 SGBM 参数影响，尚未系统调参。

## 下一步

- SGBM 参数调优（或做参数扫描）
- 检查 cv2.ximgproc 是否可用，评估 WLS 滤波
- （可选）实时深度流 demo
