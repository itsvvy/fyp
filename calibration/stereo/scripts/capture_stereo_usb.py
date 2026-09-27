#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
USB 双目相机 (SBS 并排输出) 采集脚本 — 适用于 Jetson Nano / Linux (V4L2)

相机 PayCam C4008 输出一张左右并排的整帧 (side-by-side), 本脚本:
  - 打开 /dev/video1 (Nano 上: video0=IMX219, video1=PayCam)
  - 用 MJPG @ 30fps 取图
  - 从中间切成左目/右目, 按需左右对调 / 水平镜像, 按 s 成对保存
  - 预览窗口 = 实际保存的左右目重新并排, 所见即所存 (FLIP_LR / MIRROR 会立刻反映)

用法:
    python3 capture_stereo_usb.py
按键:
    s 或 空格  保存一对 (左+右)
    q 或 ESC   退出
"""

import os

import cv2

# ============ 可调参数 ============
DEVICE = "/dev/video1"      # Nano: video0=IMX219(CSI), video1=PayCam(USB); 用 v4l2-ctl --list-devices 确认
WIDTH = 2560                # SBS 整帧宽
HEIGHT = 960                # SBS 整帧高 (两目各 1280x960)
FPS = 30
LEFT_DIR = "stereo_left"
RIGHT_DIR = "stereo_right"
FLIP_LR = False             # 左右两半对调: 若"物理左目"出现在画面右半, 改成 True
MIRROR = False              # 每只眼水平镜像: 若单只眼画面像照镜子一样左右反了, 改成 True
PREVIEW_SCALE = 0.5         # 预览缩放
# =================================


def main():
    if not os.path.isdir(LEFT_DIR):
        os.makedirs(LEFT_DIR)
    if not os.path.isdir(RIGHT_DIR):
        os.makedirs(RIGHT_DIR)

    cap = cv2.VideoCapture(DEVICE, cv2.CAP_V4L2)
    if not cap.isOpened():
        print("错误: 无法打开相机 %s。请确认:" % DEVICE)
        print("  1) 相机已插到 Nano 的 USB 口")
        print("  2) v4l2-ctl --list-devices 里 PayCam 对应的 /dev/videoX 与本脚本 DEVICE 一致")
        return

    # 用 MJPG 才能到 30fps; YUYV 只有 1~5fps
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS)

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print("实际分辨率: %dx%d -> 每目 %dx%d" % (w, h, w // 2, h))

    count = 0
    print("按键: s/空格=保存一对, q/ESC=退出")
    print("采集建议: 15~30 对, 棋盘格占每目画面 1/4~1/2, 不同位置/倾斜/距离")

    while True:
        ok, frame = cap.read()
        if not ok:
            print("读取失败")
            break

        half = frame.shape[1] // 2
        left = frame[:, :half]
        right = frame[:, half:]

        # 先左右对调, 再每只眼水平镜像
        if FLIP_LR:
            left, right = right, left
        if MIRROR:
            left = cv2.flip(left, 1)
            right = cv2.flip(right, 1)

        # 预览 = 处理后的 left/right 重新并排, 所见即所存
        preview = cv2.hconcat([left, right])
        cv2.line(preview, (half, 0), (half, preview.shape[0]), (0, 255, 0), 2)
        cv2.putText(preview, "L", (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 255, 0), 2)
        cv2.putText(preview, "R", (half + 20, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 255, 0), 2)
        small = cv2.resize(
            preview,
            (int(preview.shape[1] * PREVIEW_SCALE), int(preview.shape[0] * PREVIEW_SCALE)),
        )
        cv2.imshow("stereo SBS (L | R)", small)

        key = cv2.waitKey(30) & 0xFF
        if key == ord("s") or key == 32:
            base = "pair_%03d" % count
            cv2.imwrite(os.path.join(LEFT_DIR, base + "_L.jpg"), left)
            cv2.imwrite(os.path.join(RIGHT_DIR, base + "_R.jpg"), right)
            count += 1
            print("已保存第 %d 对" % count)
        elif key == ord("q") or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    print("共保存 %d 对 -> %s/ 和 %s/" % (count, LEFT_DIR, RIGHT_DIR))


if __name__ == "__main__":
    main()
