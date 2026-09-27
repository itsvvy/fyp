#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
USB 双目相机标定 (读取 stereo_left/ 与 stereo_right/ 的成对图像)

流程:
  1) 分别对左目、右目做单目标定 (calibrateCamera)
  2) 双目标定 (stereoCalibrate) 得到两相机之间的旋转 R、平移 T, 以及 E/F 矩阵
  3) 立体校正 (stereoRectify) 得到校正矩阵 R1/R2、投影矩阵 P1/P2、视差转深度矩阵 Q
  4) 保存到 stereo_calibration.npz

棋盘格: 10x7 方格 -> 内角点 9x6, 方格边长 25mm = 0.025 m

用法:
    python3 calibrate_stereo.py
"""

import glob
import os

import cv2
import numpy as np

# ============ 可调参数 ============
PATTERN_SIZE = (9, 6)      # 内角点 (列, 行): 10x7 方格 -> 9x6
SQUARE_SIZE = 0.025        # 方格边长 25mm = 0.025 米
LEFT_DIR = "stereo_left"
RIGHT_DIR = "stereo_right"
CHESSBOARD_FLAGS = (
    cv2.CALIB_CB_ADAPTIVE_THRESH
    | cv2.CALIB_CB_NORMALIZE_IMAGE
)
# =================================


def detect_corners(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    found, corners = cv2.findChessboardCorners(
        gray, PATTERN_SIZE, None, CHESSBOARD_FLAGS
    )
    if not found:
        return None
    cv2.cornerSubPix(
        gray, corners, (11, 11), (-1, -1),
        (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001),
    )
    return corners


def main():
    lefts = sorted(glob.glob(os.path.join(LEFT_DIR, "*.jpg")))
    rights = sorted(glob.glob(os.path.join(RIGHT_DIR, "*.jpg")))

    # 按文件名配对 (pair_xxx_L.jpg <-> pair_xxx_R.jpg)
    pairs = []
    for l in lefts:
        base = os.path.basename(l).replace("_L.jpg", "")
        r = os.path.join(RIGHT_DIR, base + "_R.jpg")
        if os.path.exists(r):
            pairs.append((l, r))
    if len(pairs) < 3:
        print("错误: 成对图像不足 (%d), 请先运行 capture_stereo_usb.py" % len(pairs))
        return

    # 世界坐标 (z=0 平面, 间距 SQUARE_SIZE)
    objp = np.zeros((PATTERN_SIZE[0] * PATTERN_SIZE[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:PATTERN_SIZE[0], 0:PATTERN_SIZE[1]].T.reshape(-1, 2)
    objp *= SQUARE_SIZE

    objpoints = []
    imgpoints_l = []
    imgpoints_r = []
    image_size = None

    print("正在处理 %d 对图像..." % len(pairs))
    for l, r in pairs:
        im_l = cv2.imread(l)
        im_r = cv2.imread(r)
        if im_l is None or im_r is None:
            print("  SKIP(无法读取)", os.path.basename(l))
            continue
        if image_size is None:
            image_size = (im_l.shape[1], im_l.shape[0])

        c_l = detect_corners(im_l)
        c_r = detect_corners(im_r)
        if c_l is None or c_r is None:
            print("  FAIL", os.path.basename(l), "(左右至少一只眼未检测到棋盘格)")
            continue
        objpoints.append(objp)
        imgpoints_l.append(c_l)
        imgpoints_r.append(c_r)
        print("  OK  ", os.path.basename(l))

    print("有效配对: %d / %d" % (len(objpoints), len(pairs)))
    if len(objpoints) < 3:
        print("有效配对不足, 无法标定")
        return

    # 1) 单目标定 (左右各一次, 作为双目初值)
    rms_l, mtx_l, dist_l, _, _ = cv2.calibrateCamera(
        objpoints, imgpoints_l, image_size, None, None
    )
    rms_r, mtx_r, dist_r, _, _ = cv2.calibrateCamera(
        objpoints, imgpoints_r, image_size, None, None
    )
    print("左目 RMS: %.4f px   右目 RMS: %.4f px" % (rms_l, rms_r))

    # 2) 双目标定 (固定内参, 只优化 R/T)
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-5)
    ret, mtx_l, dist_l, mtx_r, dist_r, R, T, E, F = cv2.stereoCalibrate(
        objpoints, imgpoints_l, imgpoints_r,
        mtx_l, dist_l, mtx_r, dist_r, image_size,
        criteria=criteria,
        flags=cv2.CALIB_FIX_INTRINSIC,
    )
    print("双目标定 RMS: %.4f px" % ret)

    # 3) 立体校正
    R1, R2, P1, P2, Q, _, _ = cv2.stereoRectify(
        mtx_l, dist_l, mtx_r, dist_r, image_size, R, T
    )

    # 4) 保存
    np.savez(
        "stereo_calibration.npz",
        mtxL=mtx_l, distL=dist_l, mtxR=mtx_r, distR=dist_r,
        R=R, T=T, E=E, F=F,
        R1=R1, R2=R2, P1=P1, P2=P2, Q=Q,
        image_size=np.array(image_size),
    )

    baseline = float(np.linalg.norm(T))
    print("-" * 50)
    print("左目内参 K_L:\n", mtx_l)
    print("右目内参 K_R:\n", mtx_r)
    print("两相机旋转矩阵 R:\n", R)
    print("两相机平移向量 T (米):\n", T.ravel())
    print("基线长度 |T| = %.4f 米" % baseline)
    print("-" * 50)
    print("已保存: stereo_calibration.npz")


if __name__ == "__main__":
    main()
