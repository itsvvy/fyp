#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jetson Nano CSI 相机 - 棋盘格图像采集脚本 (纯采集版)

只负责流畅预览和按 s 保存全尺寸原图, 不做实时角点检测。
棋盘格是否合格留到离线的 check_images.py 去判断, 这样采集阶段负载最低、最流畅。

用法:
    python3 capture_chessboard.py

按键:
    s 或 空格  保存当前帧到 calib_images/
    q 或 ESC   退出
"""

import os

import cv2

# ============ 可调参数 ============
CAPTURE_WIDTH = 1920
CAPTURE_HEIGHT = 1080
FRAMERATE = 30
FLIP_METHOD = 0            # 0/1/2/3 旋转画面, 若图像上下颠倒再改这里
OUT_DIR = "calib_images"
PREVIEW_WIDTH = 960        # 显示窗口降采样宽度
PREVIEW_HEIGHT = 540       # 显示窗口降采样高度
SENSOR_MODE = -1           # -1=自动; 自动协商异常时可设为 2 (1920x1080@30)
# =================================


def gstreamer_pipeline(capture_width=1920, capture_height=1080,
                       display_width=1920, display_height=1080,
                       framerate=30, flip_method=0, sensor_mode=-1):
    """Jetson Nano CSI 相机 GStreamer 管道 (低延迟, 丢旧帧)."""
    src = "nvarguscamerasrc"
    if sensor_mode >= 0:
        src += " sensor-mode=%d" % sensor_mode
    fmt = (
        src + " ! "
        "video/x-raw(memory:NVMM), width=(int){w}, height=(int){h}, "
        "format=(string)NV12, framerate=(fraction){f}/1 ! "
        "nvvidconv flip-method={flip} ! "
        "video/x-raw, width=(int){dw}, height=(int){dh}, format=(string)BGRx ! "
        "videoconvert ! video/x-raw, format=(string)BGR ! "
        "appsink sync=false max-buffers=1 drop=true"
    )
    return fmt.format(
        w=capture_width,
        h=capture_height,
        f=framerate,
        flip=flip_method,
        dw=display_width,
        dh=display_height,
    )


def main():
    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)

    pipeline = gstreamer_pipeline(
        capture_width=CAPTURE_WIDTH,
        capture_height=CAPTURE_HEIGHT,
        display_width=CAPTURE_WIDTH,
        display_height=CAPTURE_HEIGHT,
        framerate=FRAMERATE,
        flip_method=FLIP_METHOD,
        sensor_mode=SENSOR_MODE,
    )
    print("打开相机管道: nvarguscamerasrc @ %dx%d @ %dfps"
          % (CAPTURE_WIDTH, CAPTURE_HEIGHT, FRAMERATE))

    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
    if not cap.isOpened():
        print("错误: 无法打开 CSI 相机, 请检查相机排线/供电, 或运行:")
        print("  gst-inspect-1.0 nvarguscamerasrc")
        return

    count = 0
    print("按键: s/空格=保存, q/ESC=退出")
    print("采集建议: 15~30 张, 棋盘格占画面 1/4~1/2, 不同位置/倾斜/距离, 先对焦清晰")

    while True:
        ok, frame = cap.read()
        if not ok:
            print("读取帧失败")
            break

        # 只降采样用于显示, 保存仍用全尺寸原图
        small = cv2.resize(frame, (PREVIEW_WIDTH, PREVIEW_HEIGHT))
        cv2.putText(small, "saved: %d" % count, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
        cv2.imshow("Capture", small)

        key = cv2.waitKey(30) & 0xFF  # ~30fps 节奏, 避免空转
        if key == ord('s') or key == 32:  # s 或空格
            path = os.path.join(OUT_DIR, "img_%03d.jpg" % count)
            cv2.imwrite(path, frame)
            print("已保存:", path)
            count += 1
        elif key == ord('q') or key == 27:  # q 或 ESC
            break

    cap.release()
    cv2.destroyAllWindows()
    print("采集结束, 共保存 %d 张图像到 %s/" % (count, OUT_DIR))


if __name__ == "__main__":
    main()
