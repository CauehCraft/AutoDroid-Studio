import io
import os
import random
import shutil
import struct
import subprocess
import time
from typing import List, Optional

import cv2
import numpy as np
from PIL import Image
from ppadb.client import Client as AdbClient
from ppadb.device import Device

from ..utils.logger import app_logger
from .models import Point, Size, SwipeAction
from .scrcpy_client import ScrcpyClient


class AdbManager:
    def __init__(self, host="127.0.0.1", port=5037):
        self.client = AdbClient(host=host, port=port)
        self.connected_devices = {}
        self.scrcpy_clients = {}
        self._tracking_id_counter = 0

    def get_devices(self) -> List[Device]:
        try:
            return self.client.devices()
        except Exception as e:
            print(f"Error getting devices: {e}")
            return []

    def connect_device(self, serial: str) -> Optional[Device]:
        device = self.client.device(serial)
        if device:
            self.connected_devices[serial] = device
        return device

    def get_scrcpy_client(self, serial: str) -> Optional[ScrcpyClient]:
        if serial not in self.scrcpy_clients:
            client = ScrcpyClient(serial, self)
            if client.start():
                self.scrcpy_clients[serial] = client
            else:
                return None
        
        if not self.scrcpy_clients[serial].connected:
            if not self.scrcpy_clients[serial].start():
                return None
                
        return self.scrcpy_clients[serial]

    def get_screen_resolution(self, device: Device) -> Size:
        output = device.shell("wm size")
        if output:
            resolution_str = output.strip().split(":")[-1].strip()
            # wm size returns "Physical size: 1080x1920"
            width, height = map(int, resolution_str.split("x"))
            return Size(width, height)
        return Size(0, 0)
    
    def get_resolution(self, device: Device) -> Size:
        """Alias for get_screen_resolution"""
        return self.get_screen_resolution(device)

    def take_screenshot(self, device: Device) -> np.ndarray:
        try:
            image_bytes = device.screencap()
            image = Image.open(io.BytesIO(image_bytes))
            # Convert to numpy array (OpenCV format BGR)
            img_np = np.array(image)
            img_cv2 = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            return img_cv2
        except Exception as e:
            print(f"Error taking screenshot: {e}")
            return None

    def tap(self, device: Device, point: Point, duration_ms: int = 100):
        client = self.get_scrcpy_client(device.serial)
        if client:
            client.touch(int(point.x), int(point.y), 0)
            if duration_ms > 0:
                time.sleep(duration_ms / 1000.0)
            client.touch(int(point.x), int(point.y), 1)
            return

        print(f"Error: Scrcpy client not available for device {device.serial}")

    def swipe(self, device: Device, start: Point, end: Point, duration_ms: int = 300, duration_variance_ms: int = 0):
        client = self.get_scrcpy_client(device.serial)
        if client:
            actual_duration = self._calculate_variance(duration_ms, duration_variance_ms, min_val=10)
            client.swipe(int(start.x), int(start.y), int(end.x), int(end.y), actual_duration)
            return

        print(f"Error: Scrcpy client not available for device {device.serial}")
    
    def swipe_with_holds(self, device: Device, start: Point, end: Point, duration_ms: int = 300, 
                         hold_start_ms: int = 0, hold_end_ms: int = 0,
                         duration_variance_ms: int = 0, hold_start_variance_ms: int = 0, hold_end_variance_ms: int = 0):
        """
        Perform swipe with hold delays at start and end.
        """
        client = self.get_scrcpy_client(device.serial)
        if client:
            actual_duration = self._calculate_variance(duration_ms, duration_variance_ms, min_val=10)
            actual_hold_start = self._calculate_variance(hold_start_ms, hold_start_variance_ms, min_val=0)
            actual_hold_end = self._calculate_variance(hold_end_ms, hold_end_variance_ms, min_val=0)

            client.swipe(int(start.x), int(start.y), int(end.x), int(end.y), actual_duration, actual_hold_start, actual_hold_end)
            return

        print(f"Error: Scrcpy client not available for device {device.serial}")

    def input_text(self, device: Device, text: str):
        escaped_text = text.replace(" ", "%s") 
        device.shell(f"input text {escaped_text}")
    
    def key_event(self, device: Device, key_code: int):
        device.shell(f"input keyevent {key_code}")
    
    def _get_adb_path(self):
        adb_path = shutil.which("adb")
        if adb_path:
            return adb_path
            
        common_paths = [
            r"scrcpy-win64\adb.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                return path
                
        return "adb"

    def _get_touch_device(self, device: Device) -> Optional[tuple]:
        """Find the input device that supports touchscreen events."""
        try:
            output = device.shell("getevent -p")
            current_device = None
            current_max_x = 0
            current_max_y = 0
            supports_x = False
            supports_y = False
            
            for line in output.splitlines():
                line = line.strip()
                if line.startswith("add device"):
                    current_device = line.split(":")[-1].strip()
                    supports_x = False
                    supports_y = False
                    current_max_x = 0
                    current_max_y = 0
                elif line.startswith("0035"): # ABS_MT_POSITION_X
                    parts = line.split(",")
                    for part in parts:
                        if "max" in part:
                            try:
                                current_max_x = int(part.split()[1])
                                supports_x = True
                            except: pass
                elif line.startswith("0036"): # ABS_MT_POSITION_Y
                    parts = line.split(",")
                    for part in parts:
                        if "max" in part:
                            try:
                                current_max_y = int(part.split()[1])
                                supports_y = True
                            except: pass
                
                if current_device and supports_x and supports_y:
                    return (current_device, current_max_x, current_max_y)
                    
            return None
        except Exception as e:
            print(f"Error finding touch device: {e}")
            return None

    def get_rotation(self, device: Device) -> int:
        try:
            output = device.shell("dumpsys input | grep 'SurfaceOrientation'")
            if output:
                return int(output.split(":")[-1].strip())
        except: pass
        
        try:
            output = device.shell("settings get system user_rotation")
            if output:
                return int(output.strip())
        except: pass
        
        return 0

    def _calculate_variance(self, base_value: int, variance: int, min_val: int = 0) -> int:
        """Helper to apply random variance to a value."""
        if variance > 0:
            val = base_value + random.randint(-variance, variance)
            return max(min_val, val)
        return base_value

    def execute_multitouch_actions(self, device: Device, actions: list, recursion_depth: int = 0):
        """
        Execute multiple touch actions simultaneously using binary event injection.
        """
        scrcpy_client = self.get_scrcpy_client(device.serial)
        if scrcpy_client:
            app_logger.info(f"Executing {len(actions)} actions via Scrcpy")
            
            active_actions = self._prepare_multitouch_actions(actions, scrcpy_client)
            num_actions = len(active_actions)
            
            safe_events_per_sec = 60.0
            calculated_interval = num_actions / safe_events_per_sec
            interval = max(0.016, calculated_interval)
            
            app_logger.info(f"MultiAction: {num_actions} actions, Interval: {interval:.4f}s ({1/interval:.1f} Hz)")
            
            return self._run_multitouch_loop(scrcpy_client, active_actions, interval)

        app_logger.warning("Scrcpy client unavailable, cannot execute actions.")
        return False

    def _prepare_multitouch_actions(self, actions: list, scrcpy_client: ScrcpyClient) -> list:
        active_actions = []
        for i, action in enumerate(actions):
            if i > 9: break
            
            base_duration = getattr(action, 'duration_ms', 100)
            variance = getattr(action, 'duration_variance_ms', getattr(action, 'random_duration_variance', 0))
            actual_duration = self._calculate_variance(base_duration, variance, min_val=10)
            
            hold_start = 0
            hold_end = 0
            start_pt = Point(0,0)
            end_pt = Point(0,0)
            action_type = 'click'
            
            if isinstance(action, SwipeAction):
                action_type = 'swipe'
                start_pt = action.start_point if isinstance(action.start_point, Point) else Point(0, 0)
                end_pt = action.end_point if isinstance(action.end_point, Point) else Point(0, 0)
                
                hold_start = self._calculate_variance(getattr(action, 'hold_start_ms', 0), getattr(action, 'hold_start_variance_ms', 0))
                hold_end = self._calculate_variance(getattr(action, 'hold_end_ms', 0), getattr(action, 'hold_end_variance_ms', 0))
                
                total_time = hold_start + actual_duration + hold_end
            else:
                start_pt = action.target if isinstance(action.target, Point) else Point(0, 0)
                end_pt = start_pt
                total_time = actual_duration

            active_actions.append({
                'index': i,
                'action': action,
                'start': start_pt,
                'end': end_pt,
                'duration': actual_duration,
                'total_time': total_time,
                'hold_start': hold_start,
                'hold_end': hold_end,
                'active': True,
                'type': action_type
            })
            
            scrcpy_client.touch(int(start_pt.x), int(start_pt.y), 0, pointer_id=i)
            app_logger.info(f"ClickDown: Action {i+1} ({action_type}) at ({int(start_pt.x)}, {int(start_pt.y)})")
            
        return active_actions

    def _run_multitouch_loop(self, scrcpy_client: ScrcpyClient, active_actions: list, interval: float) -> bool:
        start_time = time.perf_counter()
        
        while any(item['active'] for item in active_actions):
            loop_start = time.perf_counter()
            current_time_ms = (loop_start - start_time) * 1000
            
            scrcpy_client.begin_batch()
            
            for item in active_actions:
                if not item['active']: continue
                
                if current_time_ms >= item['total_time']:
                    # UP
                    end_x = int(item['end'].x)
                    end_y = int(item['end'].y)
                    scrcpy_client.touch(end_x, end_y, 1, pointer_id=item['index'])
                    item['active'] = False
                    
                    app_logger.info(f"ClickUp: Action {item['index']+1} ({item['type']}) - Duration: {int(current_time_ms)}ms")
                    continue
                    
                # Move
                if item['type'] == 'swipe':
                    if current_time_ms < item['hold_start']:
                        continue
                    if current_time_ms > (item['hold_start'] + item['duration']):
                        # Hold end, ensure at end
                        scrcpy_client.touch(int(item['end'].x), int(item['end'].y), 2, pointer_id=item['index'])
                        continue
                        
                    # Moving
                    time_in_movement = current_time_ms - item['hold_start']
                    t = time_in_movement / item['duration']
                    if t > 1.0: t = 1.0
                    
                    curr_x = int(item['start'].x + (item['end'].x - item['start'].x) * t)
                    curr_y = int(item['start'].y + (item['end'].y - item['start'].y) * t)
                    
                    scrcpy_client.touch(curr_x, curr_y, 2, pointer_id=item['index'])
                else:
                    # Click (hold) - keep position
                    pass
                    
            scrcpy_client.end_batch()
            
            elapsed = time.perf_counter() - loop_start
            remaining = interval - elapsed
            if remaining > 0:
                time.sleep(remaining)
            
        return True
