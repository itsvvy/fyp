#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
离线检查采集到的棋盘格图像 (全分辨率, 稳健检测)

对 calib_images/ 中的每张图做 findChessboardCorners:
  - 不加 CALIB_CB_FAST_CHECK, 避免"误判没有棋盘"导致的漏检
  - 检测到后再做 cornerSubPix 亚像素细化
  - 把检测成功的图复制到 good/ 目录, 供 calibrate_camera.py 使用

用法:
    python3 check_images.py
"""

import glob
import os
import shutil

import cv2

# ============ 可调参数 ============
PATTERN_SIZE = (9, 6)      # 内角点 (列, 行): 10x7 方格 -> 9x6
IMG_DIR = "calib_images"
GOOD_DIR = "good"
# 稳健检测: 不加 FAST_CHECK (它会在"疑似无棋盘"时快速短路, 容易漏检)
CHESSBOARD_FLAGS = (
    cv2.CALIB_CB_ADAPTIVE_THRESH
    | cv2.CALIB_CB_NORMALIZE_IMAGE
)
# =================================


def main():
    images = sorted(glob.glob(os.path.join(IMG_DIR, "*.jpg")))
    if not images:
        print("错误: %s/ 里没有图像, 请先运行 capture_chessboard.py 采集" % IMG_DIR)
        return

    if not os.path.isdir(GOOD_DIR):
        os.makedirs(GOOD_DIR)

    good = 0
    print("正在检查 %d 张图像..." % len(images))
    for f in images:
        img = cv2.imread(f)
        if img is None:
            print("  SKIP(无法读取)", os.path.basename(f))
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        found, corners = cv2.findChessboardCorners(
            gray, PATTERN_SIZE, None, CHESSBOARD_FLAGS
        )
        if found:
            cv2.cornerSubPix(
                gray, corners, (11, 11), (-1, -1),
                (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001),
            )
            shutil.copy2(f, os.path.join(GOOD_DIR, os.path.basename(f)))
            good += 1
            print("  OK  ", os.path.basename(f))
        else:
            print("  FAIL", os.path.basename(f), "(未检测到完整棋盘格)")

    print("-" * 50)
    print("检测成功 %d / %d 张, 已复制到 %s/" % (good, len(images), GOOD_DIR))
    if good < 10:
        print("提示: 建议至少 10 张通过, 最好 15~30 张; 目前偏少可重拍一些")


if __name__ == "__main__":
    main()
