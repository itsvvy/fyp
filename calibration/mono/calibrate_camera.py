#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jetson Nano 单目相机标定脚本 (读取 good/ 中已通过检查的棋盘格图像)

适用: NVIDIA Jetson Nano, JetPack 4.x (OpenCV 4.1.1 / Python 3.6+)

棋盘格: 10x7 方格 -> 内角点 9x6, 方格边长 25mm = 0.025 m

用法:
    python3 calibrate_camera.py

输出:
    calibration.npz   (numpy 格式: mtx, dist, rms, image_size)
    calibration.yaml  (OpenCV FileStorage 格式, 便于后续项目读取)
"""

import glob
import os

import cv2
import numpy as np

# ============ 可调参数 ============
PATTERN_SIZE = (9, 6)      # 内角点 (列, 行): 10x7 方格 -> 9x6
SQUARE_SIZE = 0.025        # 方格边长 25mm = 0.025 米 (务必用尺子实测打印尺寸)
IMG_DIR = "good"
# 稳健检测: 不加 FAST_CHECK (它会在"疑似无棋盘"时快速短路, 容易漏检)
CHESSBOARD_FLAGS = (
    cv2.CALIB_CB_ADAPTIVE_THRESH
    | cv2.CALIB_CB_NORMALIZE_IMAGE
)
# =================================


def main():
    images = sorted(glob.glob(os.path.join(IMG_DIR, "*.jpg")))
    if len(images) < 3:
        print("错误: 至少需要 3 张含完整棋盘格的图像, 当前找到 %d 张" % len(images))
        print("请先运行 capture_chessboard.py 采集, 再用 check_images.py 挑出合格图")
        return

    # 世界坐标: 所有内角点位于 z=0 平面, 间距为 SQUARE_SIZE
    objp = np.zeros((PATTERN_SIZE[0] * PATTERN_SIZE[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:PATTERN_SIZE[0], 0:PATTERN_SIZE[1]].T.reshape(-1, 2)
    objp *= SQUARE_SIZE

    objpoints = []   # 3D 世界坐标
    imgpoints = []   # 2D 像素坐标
    image_size = None
    used = []

    print("正在处理 %d 张图像..." % len(images))
    for f in images:
        img = cv2.imread(f)
        if img is None:
            print("跳过(无法读取):", f)
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if image_size is None:
            image_size = (gray.shape[1], gray.shape[0])

        found, corners = cv2.findChessboardCorners(
            gray, PATTERN_SIZE, None, CHESSBOARD_FLAGS
        )
        if found:
            corners_refined = cv2.cornerSubPix(
                gray, corners, (11, 11), (-1, -1),
                (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001),
            )
            objpoints.append(objp)
            imgpoints.append(corners_refined)
            used.append(f)
            print("  OK  ", os.path.basename(f))
        else:
            print("  SKIP", os.path.basename(f), "(未检测到棋盘格)")

    print("检测到 %d / %d 张有效棋盘格" % (len(objpoints), len(images)))
    if len(objpoints) < 3:
        print("有效图像不足, 无法标定, 请重新采集")
        return

    rms, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
        objpoints, imgpoints, image_size, None, None
    )

    print("-" * 50)
    print("图像尺寸: %dx%d" % (image_size[0], image_size[1]))
    print("RMS 重投影误差: %.4f 像素" % rms)
    print("相机内参矩阵 K (像素):")
    print(mtx)
    print("畸变系数 [k1 k2 p1 p2 k3]:")
    print(dist.ravel())

    # 逐张重投影误差
    mean_err = 0.0
    for i in range(len(objpoints)):
        imgp2, _ = cv2.projectPoints(objpoints[i], rvecs[i], tvecs[i], mtx, dist)
        err = cv2.norm(imgpoints[i], imgp2, cv2.NORM_L2) / len(imgp2)
        mean_err += err
    mean_err /= len(objpoints)
    print("平均重投影误差: %.4f 像素" % mean_err)

    # 保存结果
    np.savez(
        "calibration.npz",
        mtx=mtx,
        dist=dist,
        rms=np.array(rms),
        image_size=np.array(image_size),
    )
    fs = cv2.FileStorage("calibration.yaml", cv2.FILE_STORAGE_WRITE)
    fs.write("camera_matrix", mtx)
    fs.write("dist_coeffs", dist)
    fs.write("image_width", image_size[0])
    fs.write("image_height", image_size[1])
    fs.release()

    print("-" * 50)
    print("已保存: calibration.npz 和 calibration.yaml")
    print("质量参考: RMS < 0.5 像素为佳; 0.5~1.0 尚可; >1.0 建议重新采集")


if __name__ == "__main__":
    main()
