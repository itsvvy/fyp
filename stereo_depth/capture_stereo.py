#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双目深度 demo — 采集脚本 (弹窗画面 + 键盘保存)

在 Jetson Nano 上运行, 弹出左右并排的预览窗口:
    s 或 空格 = 保存一对 (左目->stereo_left/, 右目->stereo_right/)
    q 或 ESC  = 退出

!! 重要 !!  FLIP_LR / MIRROR 必须和标定(calibrate_stereo)时采集用的设置一致。
"""

import os

import cv2

# ============ 可调参数 ============
DEVICE = "/dev/video1"      # Nano: video0=IMX219(CSI), video1=PayCam(USB)
WIDTH = 2560
HEIGHT = 960                # 每目 1280x960
FPS = 30
LEFT_DIR = "stereo_left"
RIGHT_DIR = "stereo_right"
FLIP_LR = True             # !! 与标定采集时保持一致 !!
MIRROR = False              # !! 与标定采集时保持一致 !!
PREVIEW_SCALE = 0.5         # 预览缩放
# =================================


def main():
    if not os.path.isdir(LEFT_DIR):
        os.makedirs(LEFT_DIR)
    if not os.path.isdir(RIGHT_DIR):
        os.makedirs(RIGHT_DIR)

    cap = cv2.VideoCapture(DEVICE, cv2.CAP_V4L2)
    if not cap.isOpened():
        print("错误: 无法打开相机 %s。请确认相机已插到 Nano 的 USB 口, 且 DEVICE 路径正确" % DEVICE)
        return

    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS)

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print("实际分辨率: %dx%d -> 每目 %dx%d" % (w, h, w // 2, h))

    count = 0
    print("按键: s/空格=保存一对, q/ESC=退出")
    print("采集建议: 物体覆盖不同距离和位置, 保证左右目都清晰")

    while True:
        ok, frame = cap.read()
        if not ok:
            print("读取失败")
            break

        half = frame.shape[1] // 2
        left = frame[:, :half]
        right = frame[:, half:]

        if FLIP_LR:
            left, right = right, left
        if MIRROR:
            left = cv2.flip(left, 1)
            right = cv2.flip(right, 1)

        # 预览 = 处理后的左右目重新并排 (所见即所存)
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
