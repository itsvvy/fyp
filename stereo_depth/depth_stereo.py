#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双目深度 demo — 深度脚本 (离线, 批量处理左右目图像)

依赖: 同目录下的 stereo_calibration.npz (从标定项目 calibrationDurl 拷过来一份)

用法:
    python3 depth_stereo.py            # 处理 stereo_left/ 里所有配对
    python3 depth_stereo.py pair_001   # 只处理指定一对

每组结果放在独立子文件夹 depth_output/<pair>/ 下:
    rectified.jpg   校正后左右并排 (看是否行对齐)
    disparity.jpg   视差图 (越亮越近)
    depth.jpg       深度图 (暖色越近, 单位米)
    depth.npy       原始深度矩阵 (米, 无效处 0)
"""

import glob
import os
import sys

import cv2
import numpy as np

# ============ 可调参数 ============
CALIB = "stereo_calibration.npz"   # 标定结果, 需放在同目录
LEFT_DIR = "stereo_left"
RIGHT_DIR = "stereo_right"
OUT_DIR = "depth_output"
METHOD = "sgbm"             # "sgbm" 质量好(慢) / "bm" 快(粗糙)
MAX_DEPTH = 5.0             # 只显示 5 米内
# =================================


def make_stereo_matcher(method):
    if method == "sgbm":
        win = 5
        return cv2.StereoSGBM_create(
            minDisparity=0,
            numDisparities=192,
            blockSize=win,
            P1=8 * 3 * win * win,
            P2=32 * 3 * win * win,
            disp12MaxDiff=1,
            uniquenessRatio=10,
            speckleWindowSize=100,
            speckleRange=32,
            preFilterCap=63,
            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY,
        )
    return cv2.StereoBM_create(numDisparities=192, blockSize=15)


def load_calib():
    if not os.path.exists(CALIB):
        print("错误: 找不到 %s, 请把标定项目里的该文件拷贝到当前目录" % CALIB)
        return None
    data = np.load(CALIB)
    return {
        "mtxL": data["mtxL"], "distL": data["distL"],
        "mtxR": data["mtxR"], "distR": data["distR"],
        "R1": data["R1"], "R2": data["R2"],
        "P1": data["P1"], "P2": data["P2"], "Q": data["Q"],
    }


def list_pairs():
    bases = []
    for l in sorted(glob.glob(os.path.join(LEFT_DIR, "*_L.jpg"))):
        base = os.path.basename(l).replace("_L.jpg", "")
        r = os.path.join(RIGHT_DIR, base + "_R.jpg")
        if os.path.exists(r):
            bases.append(base)
    return bases


def process_pair(base, calib):
    l_path = os.path.join(LEFT_DIR, base + "_L.jpg")
    r_path = os.path.join(RIGHT_DIR, base + "_R.jpg")
    imgL = cv2.imread(l_path)
    imgR = cv2.imread(r_path)
    if imgL is None or imgR is None:
        print("[%s] 读取失败" % base)
        return
    h, w = imgL.shape[:2]

    # 1) 立体校正
    mapLx, mapLy = cv2.initUndistortRectifyMap(
        calib["mtxL"], calib["distL"], calib["R1"], calib["P1"], (w, h), cv2.CV_32FC1)
    mapRx, mapRy = cv2.initUndistortRectifyMap(
        calib["mtxR"], calib["distR"], calib["R2"], calib["P2"], (w, h), cv2.CV_32FC1)
    rectL = cv2.remap(imgL, mapLx, mapLy, cv2.INTER_LINEAR)
    rectR = cv2.remap(imgR, mapRx, mapRy, cv2.INTER_LINEAR)

    # 2) 视差
    grayL = cv2.cvtColor(rectL, cv2.COLOR_BGR2GRAY)
    grayR = cv2.cvtColor(rectR, cv2.COLOR_BGR2GRAY)
    stereo = make_stereo_matcher(METHOD)
    disparity = stereo.compute(grayL, grayR).astype(np.float32) / 16.0

    # 3) 视差 -> 3D -> 深度 (米)
    disp = disparity.copy()
    disp[disp <= 0] = 0
    points3d = cv2.reprojectImageTo3D(disp, calib["Q"])
    depth = points3d[:, :, 2].copy()
    depth[depth < 0] = 0
    depth[depth > MAX_DEPTH] = 0

    # 每组结果放到独立子文件夹
    pair_dir = os.path.join(OUT_DIR, base)
    if not os.path.isdir(pair_dir):
        os.makedirs(pair_dir)
    cv2.imwrite(os.path.join(pair_dir, "rectified.jpg"), cv2.hconcat([rectL, rectR]))
    disp_vis = cv2.normalize(disp, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)
    cv2.imwrite(os.path.join(pair_dir, "disparity.jpg"), cv2.applyColorMap(disp_vis, cv2.COLORMAP_JET))
    # 深度图可视化: 暖色(红)=近, 冷色(蓝)=远, 无效=黑
    depth_vis = depth.copy()
    valid = depth_vis > 0
    d_vis = np.zeros(depth_vis.shape, dtype=np.uint8)
    if valid.any():
        vmin = float(depth_vis[valid].min())
        vmax = float(depth_vis[valid].max())
        if vmax > vmin:
            scaled = (vmax - depth_vis) / (vmax - vmin) * 255.0
            d_vis = np.clip(scaled, 0, 255).astype(np.uint8)
    depth_color = cv2.applyColorMap(d_vis, cv2.COLORMAP_JET)
    depth_color[~valid] = (0, 0, 0)
    cv2.imwrite(os.path.join(pair_dir, "depth.jpg"), depth_color)
    np.save(os.path.join(pair_dir, "depth.npy"), depth)

    print("[%s] 完成, 焦距 f=%.1f px, 中心采样深度(米):" % (base, calib["P1"][0, 0]))
    for ry in range(5):
        row = []
        for rx in range(5):
            y = int(h * (0.3 + 0.4 * ry / 4))
            x = int(w * (0.3 + 0.4 * rx / 4))
            d = depth[y, x]
            row.append("%.2f" % d if d > 0 else "----")
        print("  " + "  ".join(row))


def main():
    calib = load_calib()
    if calib is None:
        return

    if len(sys.argv) > 1:
        bases = [sys.argv[1].replace("_L.jpg", "").replace("_R.jpg", "")]
    else:
        bases = list_pairs()
        if not bases:
            print("错误: 没有找到成对图像, 请先运行 capture_stereo.py")
            return

    print("将处理 %d 对图像..." % len(bases))
    for base in bases:
        process_pair(base, calib)
    print("全部完成, 结果在 %s/" % OUT_DIR)


if __name__ == "__main__":
    main()
