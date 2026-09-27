# 项目概览

## 题目
Edge-Based Dual Stereo Sensing System: Fusion of CIS and DVS Cameras for Real-Time Obstacle Detection and Tracking (ASTRI)

## 背景
传统视觉系统在运动模糊、数据吞吐和动态范围方面存在局限；事件相机 DVS 擅长高速运动与稀疏数据，CIS 提供纹理与色彩。本项目在边缘设备上融合双目 CIS 与双目 DVS，做实时障碍检测 / 手势识别 / 深度感知跟踪等，不依赖云端。

## 预期产出
- 边缘感知系统（双目 CIS + 双目 DVS 集成）
- 传感器融合算法（CIS 纹理/深度 + DVS 运动事件）
- 实时应用 Demo
- 性能评估（延迟、功耗、检测精度对比）
- （可选）可视化 / 告警 UI

## 当前阶段
- 已完成：CSI 单目标定、USB 双目标定（内参 / 畸变 / 基线）。
- 进行中：立体校正 + 视差 / 深度验证。
