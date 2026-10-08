#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jetson Nano 标定结果可视化脚本

A. 角点叠加图: 对 good/ 中的每张图重检角点并画彩色连线, 存到 visualized/corners/
B. 去畸变对比图: 用 calibration.yaml 对样本图做去畸变, 原图与结果并排一张并标注, 存到 visualized/undistort/

全部离线、只写文件、不弹窗口 (避免 Jetson 上 imshow 卡顿)。

用法:
    python3 visualize.py
"""

import glob
import os

import cv2

# ============ 可调参数 ============
PATTERN_SIZE = (9, 6)      # 内角点 (列, 行): 10x7 方格 -> 9x6
IMG_DIR = "good"           # 输入: 已通过检查的棋盘格图像
CORNERS_DIR = "visualized/corners"     # 输出 A: 角点叠加图
UNDIST_DIR = "visualized/undistort"    # 输出 B: 去畸变对比图
CALIB_FILE = "calibration.yaml"        # 由 calibrate_camera.py 生成
SAMPLE_COUNT = 2           # 去畸变对比用几张样本
CHESSBOARD_FLAGS = (
    cv2.CALIB_CB_ADAPTIVE_THRESH
    | cv2.CALIB_CB_NORMALIZE_IMAGE
)
# =================================


def ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def draw_label(img, text, org):
    """在图上画一个带白底红字的标签 (ASCII 文字, OpenCV 字体不支持中文)."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 1.3
    thickness = 2
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    cv2.rectangle(img, (org[0], org[1] - th - 10),
                  (org[0] + tw + 12, org[1] + 8), (255, 255, 255), -1)
    cv2.putText(img, text, (org[0] + 6, org[1] - 2),
                font, scale, (0, 0, 255), thickness)


def do_corners(images):
    ensure_dir(CORNERS_DIR)
    ok = 0
    for f in images:
        img = cv2.imread(f)
        if img is None:
            print("  SKIP(无法读取)", os.path.basename(f))
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        found, corners = cv2.findChessboardCorners(
            gray, PATTERN_SIZE, None, CHESSBOARD_FLAGS
        )
        if not found:
            print("  FAIL", os.path.basename(f), "(未检测到棋盘格)")
            continue
        cv2.cornerSubPix(
            gray, corners, (11, 11), (-1, -1),
            (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001),
        )
        vis = img.copy()
        cv2.drawChessboardCorners(vis, PATTERN_SIZE, corners, True)
        out = os.path.join(CORNERS_DIR, os.path.basename(f))
        cv2.imwrite(out, vis)
        ok += 1
        print("  已存:", out)
    print("A. 角点叠加图完成: %d 张 -> %s/" % (ok, CORNERS_DIR))


def do_undistort(images):
    fs = cv2.FileStorage(CALIB_FILE, cv2.FILE_STORAGE_READ)
    if not fs.isOpened():
        print("跳过 B: 找不到 %s, 请先运行 calibrate_camera.py" % CALIB_FILE)
        return
    mtx = fs.getNode("camera_matrix").mat()
    dist = fs.getNode("dist_coeffs").mat()
    fs.release()

    ensure_dir(UNDIST_DIR)
    done = 0
    for f in images[:SAMPLE_COUNT]:
        img = cv2.imread(f)
        if img is None:
            continue
        h, w = img.shape[:2]
        new_mtx, _ = cv2.getOptimalNewCameraMatrix(mtx, dist, (w, h), 1, (w, h))
        undist = cv2.undistort(img, mtx, dist, None, new_mtx)

        side = cv2.hconcat([img, undist])
        draw_label(side, "Original", (20, 50))
        draw_label(side, "Undistorted", (w + 20, 50))

        out = os.path.join(
            UNDIST_DIR, os.path.basename(f).replace(".jpg", "_compare.jpg")
        )
        cv2.imwrite(out, side)
        done += 1
        print("  已存:", out)
    print("B. 去畸变对比图完成: %d 张 -> %s/" % (done, UNDIST_DIR))


def main():
    images = sorted(glob.glob(os.path.join(IMG_DIR, "*.jpg")))
    if not images:
        print("错误: %s/ 里没有图像, 请先运行 capture_chessboard.py 和 check_images.py"
              % IMG_DIR)
        return

    print("A. 生成角点叠加图...")
    do_corners(images)
    print()
    print("B. 生成去畸变对比图...")
    do_undistort(images)


if __name__ == "__main__":
    main()
