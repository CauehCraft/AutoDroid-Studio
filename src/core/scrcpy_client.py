import os
import queue
import random
import socket
import struct
import subprocess
import threading
import time
from typing import Optional, Tuple

from ..utils.logger import app_logger
from .models import Point

# Touch action codes (Android MotionEvent)
ACTION_DOWN = 0
ACTION_UP = 1
ACTION_MOVE = 2

# Scrcpy control message types
MSG_TYPE_INJECT_TOUCH_EVENT = 2

# Default timing values
DEFAULT_SWIPE_INTERVAL_SEC = 0.016  # 60Hz
FULL_PRESSURE = 0xFFFF
NO_PRESSURE = 0


class ScrcpyClient:
    def __init__(self, device_serial: str, adb_manager):
        self.device_serial = device_serial
        self.adb_manager = adb_manager
        self.server_process = None
        self.socket = None
        self.connected = False
        self.width = 0
        self.height = 0
        self.max_size = 0 # 0 means no limit
        self._stop_event = threading.Event()
        self._batching = False
        self._batch_buffer = bytearray()
        
        # Path to scrcpy-server
        self.server_path = self._find_server_path()
        
    def _find_server_path(self):
        # Check common locations
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        paths = [
            os.path.join(base_dir, "scrcpy-win64", "scrcpy-server"),
            os.path.join(base_dir, "scrcpy-win64", "scrcpy-server.jar"),
            os.path.join(base_dir, "scrcpy-server"),
            os.path.join(base_dir, "scrcpy-server.jar"),
        ]
        
        for path in paths:
            if os.path.exists(path):
                return path
        return None

    def start(self):
        if not self.server_path:
            app_logger.error("scrcpy-server not found!")
            return False
            
        if self.connected:
            return True
            
        try:
            app_logger.info(f"Pushing scrcpy-server to device {self.device_serial}...")
            self.adb_manager.client.device(self.device_serial).push(self.server_path, "/data/local/tmp/scrcpy-server.jar")
            
            local_port = random.randint(20000, 30000)
            socket_name = "scrcpy_%08x" % random.randint(0, 0x7FFFFFFF)
            
            app_logger.info(f"Forwarding tcp:{local_port} -> localabstract:{socket_name}")
            
            adb_path = self.adb_manager._get_adb_path()
            subprocess.run([adb_path, "-s", self.device_serial, "forward", f"tcp:{local_port}", f"localabstract:{socket_name}"], check=True)
            
            scid_val = random.randint(0, 0x7FFFFFFF)
            scid_hex = f"{scid_val:08x}"
            socket_name = "scrcpy_%s" % scid_hex
            
            subprocess.run([adb_path, "-s", self.device_serial, "forward", f"tcp:{local_port}", f"localabstract:{socket_name}"], check=True)
            
            cmd = [
                adb_path, "-s", self.device_serial, "shell",
                "CLASSPATH=/data/local/tmp/scrcpy-server.jar",
                "app_process", "/", "com.genymobile.scrcpy.Server",
                "3.3.3",
                f"scid={scid_hex}", # Pass as hex string
                "log_level=info",
                "video=false",
                "audio=false",
                "control=true",
                "tunnel_forward=true", # Server listens (required for adb forward)
                "cleanup=true"
            ]
            
            app_logger.info(f"Starting scrcpy-server: {' '.join(cmd)}")
            self.server_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            time.sleep(1.0)
            
            if self.server_process.poll() is not None:
                stdout, stderr = self.server_process.communicate()
                app_logger.error(f"Scrcpy server exited early: {stdout.decode('utf-8', 'ignore')} {stderr.decode('utf-8', 'ignore')}")
                return False

            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.socket.connect(("127.0.0.1", local_port))
            
            try:
                device_name = self.socket.recv(64)
                if not device_name:
                    raise ConnectionError("Socket closed during handshake (device name)")
                app_logger.info(f"Connected to scrcpy-server on {device_name.decode('utf-8', 'ignore').strip()}")
                
                dummy = self.socket.recv(1)
                if not dummy:
                    raise ConnectionError("Socket closed during handshake (dummy byte)")
            except Exception as e:
                stdout, stderr = "", ""
                if self.server_process:
                    try:
                        stdout = self.server_process.stdout.read1().decode('utf-8', 'ignore')
                        stderr = self.server_process.stderr.read1().decode('utf-8', 'ignore')
                    except: pass
                app_logger.error(f"Handshake failed: {e}. Server Output: {stdout} {stderr}")
                raise e
                
            self.connected = True
            app_logger.info("Scrcpy Client Ready")
            return True
            
        except Exception as e:
            app_logger.error(f"Failed to start scrcpy client: {e}")
            self.stop()
            return False

    def stop(self):
        self.connected = False
        if self.socket:
            try: self.socket.close()
            except: pass
            self.socket = None
            
        if self.server_process:
            try: self.server_process.terminate()
            except: pass
            self.server_process = None

    def begin_batch(self):
        self._batching = True
        self._batch_buffer = bytearray()
        
    def end_batch(self):
        self._batching = False
        if self._batch_buffer:
            try:
                self.socket.sendall(self._batch_buffer)
                self._batch_buffer = bytearray()
                return True
            except Exception as e:
                app_logger.error(f"Error sending batch: {e}")
                self.connected = False
                return False
        return True

    def send_control_message(self, msg_type, data):
        if not self.connected or not self.socket:
            return False
        try:
            packet = struct.pack(">B", msg_type) + data
            
            if self._batching:
                self._batch_buffer.extend(packet)
                return True
            else:
                self.socket.sendall(packet)
                return True
        except Exception as e:
            app_logger.error(f"Error sending control message: {e}")
            self.connected = False
            return False

    def touch(self, x: int, y: int, action: int, pointer_id: int = -1):
        """
        action: 0=down, 1=up, 2=move
        """
        if not self.connected:
            return False
        
        if self.width == 0 or self.height == 0:
            res = self.adb_manager.get_screen_resolution(self.adb_manager.connect_device(self.device_serial))
            self.width = res.width
            self.height = res.height
        
        pressure = FULL_PRESSURE if action in [ACTION_DOWN, ACTION_MOVE] else NO_PRESSURE
        
        data = struct.pack(">BqiiHHHII", 
            action, 
            pointer_id, 
            x, y, self.width, self.height, 
            pressure, 
            0,
            0
        )
        return self.send_control_message(MSG_TYPE_INJECT_TOUCH_EVENT, data)

    def swipe(self, start_x, start_y, end_x, end_y, duration_ms, hold_start_ms=0, hold_end_ms=0):
        self.touch(start_x, start_y, ACTION_DOWN)
        
        if hold_start_ms > 0:
            time.sleep(hold_start_ms / 1000.0)
        
        interval = DEFAULT_SWIPE_INTERVAL_SEC
        steps = max(1, int(duration_ms / (interval * 1000)))
        
        start_time = time.perf_counter()
        
        for i in range(steps):
            target_time = (i + 1) * interval
            t = (i + 1) / steps
            cx = int(start_x + (end_x - start_x) * t)
            cy = int(start_y + (end_y - start_y) * t)
            self.touch(cx, cy, ACTION_MOVE)
            
            elapsed = time.perf_counter() - start_time
            remaining = target_time - elapsed
            if remaining > 0:
                time.sleep(remaining)
        
        self.touch(end_x, end_y, ACTION_MOVE)
        
        if hold_end_ms > 0:
            time.sleep(hold_end_ms / 1000.0)
        
        self.touch(end_x, end_y, ACTION_UP)
