#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
在 Nano 上运行, 把双目相机预览通过 HTTP 传到本机浏览器, 并可在浏览器里保存左右目。

运行后, 在 Windows 浏览器打开:
    http://<nano的IP>:8000
    (或用 VSCode 端口转发后打开 http://localhost:8000)

页面里点 "Save pair" 会保存一对:
    左目 -> stereo_left/pair_XXX_L.jpg
    右目 -> stereo_right/pair_XXX_R.jpg

注意: 不要和 capture_stereo_usb.py 同时运行 (同一个 USB 相机不能同时被两个进程占用)。
"""

import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

import cv2

# ============ 可调参数 ============
DEVICE = "/dev/video1"      # Nano: video0=IMX219(CSI), video1=PayCam(USB)
WIDTH = 2560
HEIGHT = 960                # 每目 1280x960
FPS = 30
LEFT_DIR = "stereo_left"
RIGHT_DIR = "stereo_right"
FLIP_LR = False             # 左右两半对调 (若物理左目出现在画面右半, 改成 True)
MIRROR = False              # 每只眼水平镜像
PORT = 8000
STREAM_SCALE = 0.5          # 传给浏览器的预览缩放 (降低带宽)
JPEG_QUALITY = 70
# =================================

_lock = threading.Lock()
_state = {"preview": None, "left": None, "right": None, "count": 0}


def capture_loop():
    if not os.path.isdir(LEFT_DIR):
        os.makedirs(LEFT_DIR)
    if not os.path.isdir(RIGHT_DIR):
        os.makedirs(RIGHT_DIR)

    cap = cv2.VideoCapture(DEVICE, cv2.CAP_V4L2)
    if not cap.isOpened():
        print("无法打开相机 %s, 请确认 usb 连接和 DEVICE 路径" % DEVICE)
        return
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS)
    print("相机已打开, 请在浏览器访问 http://<nano-ip>:%d" % PORT)

    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.05)
            continue

        half = frame.shape[1] // 2
        left = frame[:, :half]
        right = frame[:, half:]
        if FLIP_LR:
            left, right = right, left
        if MIRROR:
            left = cv2.flip(left, 1)
            right = cv2.flip(right, 1)

        preview = cv2.hconcat([left, right])
        cv2.line(preview, (half, 0), (half, preview.shape[0]), (0, 255, 0), 2)
        cv2.putText(preview, "L", (20, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 255, 0), 2)
        cv2.putText(preview, "R", (half + 20, 45), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 255, 0), 2)

        small = cv2.resize(preview, None, fx=STREAM_SCALE, fy=STREAM_SCALE)
        ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        if not ok:
            continue
        with _lock:
            _state["preview"] = buf.tobytes()
            _state["left"] = left
            _state["right"] = right


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while True:
                    with _lock:
                        jpg = _state["preview"]
                    if jpg is None:
                        time.sleep(0.05)
                        continue
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n\r\n")
                    self.wfile.write(jpg)
                    self.wfile.write(b"\r\n")
                    time.sleep(0.03)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        if self.path == "/save":
            with _lock:
                left = _state["left"]
                right = _state["right"]
                n = _state["count"]
            if left is not None:
                base = "pair_%03d" % n
                cv2.imwrite(os.path.join(LEFT_DIR, base + "_L.jpg"), left)
                cv2.imwrite(os.path.join(RIGHT_DIR, base + "_R.jpg"), right)
                n += 1
                with _lock:
                    _state["count"] = n
                body = ("saved %d" % n).encode("utf-8")
            else:
                body = b"no frame yet"
            self._send(200, "text/plain; charset=utf-8", body)
            return

        if self.path == "/count":
            with _lock:
                n = _state["count"]
            self._send(200, "text/plain", str(n).encode("utf-8"))
            return

        html = """<!doctype html><html><head><meta charset="utf-8"><title>Stereo Capture</title></head>
<body style="font-family:sans-serif">
<h3>USB stereo (L | R) &nbsp; saved: <span id="n">0</span></h3>
<img src="/stream" style="max-width:100%">
<br><br>
<button style="font-size:20px;padding:10px 20px" onclick="save()">Save pair</button>
<script>
function save(){fetch('/save').then(r=>r.text()).then(t=>{document.getElementById('n').textContent=t.split(' ').pop()})}
setInterval(function(){fetch('/count').then(r=>r.text()).then(t=>{document.getElementById('n').textContent=t})},1000);
</script>
</body></html>"""
        self._send(200, "text/html; charset=utf-8", html.encode("utf-8"))


def main():
    t = threading.Thread(target=capture_loop, daemon=True)
    t.start()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("HTTP 服务已启动: http://<nano-ip>:%d" % PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
