import random
import threading
import time
import traceback
from typing import Callable, Optional, Any

from .adb_manager import AdbManager
from .asset_manager import AssetManager
from .comparison_utils import evaluate_condition as _evaluate_condition
from .executors import (
    ClickExecutor, ClickImageExecutor, ConditionExecutor, LoopEndExecutor,
    LoopExecutor, LoopStartExecutor, MultiExecutor, OCRExecutor, SwipeExecutor,
    VarExecutor, WaitExecutor
)
from .models import (
    Action, ClickAction, ClickImageAction, ConditionAction, LoopAction,
    LoopEndAction, LoopStartAction, Macro, MultiAction, MultiRegion, OCRAction,
    Point, PolygonRegion, Region, SwipeAction, VarAction, WaitAction
)
from .vision import VisionEngine
from ..utils.logger import app_logger


class MacroRunner(threading.Thread):
    def __init__(self, device_serial: str, macro: Macro, adb_manager: AdbManager):
        super().__init__()
        self.device_serial = device_serial
        self.macro = macro
        self.adb = adb_manager
        self.vision = VisionEngine()
        self.assets = AssetManager()
        self.running = False
        self.paused = False
        self._stop_event = threading.Event()
        self.loop_counters = {}
        self.on_variable_update: Optional[Callable[[str, Any], None]] = None
        self.on_status_update: Optional[Callable[[str], None]] = None
        
        # Initialize Executors
        self.executors = {
            "click": ClickExecutor(),
            "wait": WaitExecutor(),
            "swipe": SwipeExecutor(),
            "var": VarExecutor(),
            "condition": ConditionExecutor(),
            "loop": LoopExecutor(),
            "loop_start": LoopStartExecutor(),
            "loop_end": LoopEndExecutor(),
            "click_image": ClickImageExecutor(),
            "ocr": OCRExecutor(),
            "multi": MultiExecutor()
        }

    def run(self):
        self.running = True
        if self.on_status_update: self.on_status_update("Running")
        app_logger.info(f"Starting macro '{self.macro.name}' on device {self.device_serial}")
        self.loop_counters = {}
        
        device = self.adb.connect_device(self.device_serial)
        if not device:
            app_logger.error(f"Device {self.device_serial} not found!")
            self.running = False
            return

        # Validate resolution
        current_res = self.adb.get_screen_resolution(device)
        if not self.macro.validate_resolution(current_res):
            app_logger.error(f"Resolution mismatch! Macro: {self.macro.target_resolution}, Device: {current_res}")
            self.running = False
            return

        try:
            # Store current and target resolutions for scaling
            self.current_resolution = current_res
            self.target_resolution = self.macro.target_resolution
            
            i = 0
            while i < len(self.macro.actions):
                if self._stop_event.is_set():
                    break
                
                while self.paused:
                    time.sleep(0.1)
                    if self._stop_event.is_set():
                        break

                action = self.macro.actions[i]
                if not action.enabled:
                    i += 1
                    continue

                next_idx = self.execute_action(device, action, i)
                
                if next_idx is not None:
                    i = next_idx
                else:
                    i += 1
                
        except Exception as e:
            app_logger.error(f"Error executing macro: {e}")
            app_logger.error(traceback.format_exc())
        finally:
            self.running = False
            if self.on_status_update: self.on_status_update("Finished")
            app_logger.info(f"Macro '{self.macro.name}' finished.")

    def evaluate_condition(self, condition: dict) -> bool:
        """Evaluate a condition dict against macro variables."""
        return _evaluate_condition(condition, self.macro.variables)

    def update_variable(self, update_rule: dict):
        if not update_rule: return
        
        var_name = update_rule.get("var")
        op = update_rule.get("op")
        val = update_rule.get("val")
        
        if op == "set":
            self.macro.variables[var_name] = val
            if self.on_variable_update: self.on_variable_update(var_name, val)
            app_logger.info(f"Variable '{var_name}' set to {val}")
        elif op == "increment":
            try:
                curr = float(self.macro.variables.get(var_name, 0))
                self.macro.variables[var_name] = curr + float(val)
                if self.on_variable_update: self.on_variable_update(var_name, self.macro.variables[var_name])
                app_logger.info(f"Variable '{var_name}' incremented to {self.macro.variables[var_name]}")
            except (ValueError, TypeError):
                app_logger.error(f"Failed to increment variable '{var_name}' (value: {self.macro.variables.get(var_name)})")
        elif op == "decrement":
            try:
                curr = float(self.macro.variables.get(var_name, 0))
                self.macro.variables[var_name] = curr - float(val)
                if self.on_variable_update: self.on_variable_update(var_name, self.macro.variables[var_name])
                app_logger.info(f"Variable '{var_name}' decremented to {self.macro.variables[var_name]}")
            except (ValueError, TypeError):
                app_logger.error(f"Failed to decrement variable '{var_name}' (value: {self.macro.variables.get(var_name)})")

    def execute_action(self, device, action: Action, current_index: int = -1) -> Optional[int]:
        app_logger.debug(f"Executing action: {action.type}")
        
        # Store current index for executors that need it (e.g. LoopStart)
        self.current_index = current_index

        # 1. Check Condition
        conditions = [rule for rule in action.advanced_logic if rule.trigger == "condition" and rule.enabled]
        for rule in conditions:
            if not self.evaluate_condition(rule.data):
                app_logger.debug(f"Action {action.id} skipped (condition not met)")
                if isinstance(action, LoopStartAction):
                    # If LoopStart is skipped, we must jump to the end of the loop
                    return self.find_loop_end_index(action.loop_id, current_index) + 1
                return None

        # 2. On Start
        on_starts = [rule for rule in action.advanced_logic if rule.trigger == "on_start" and rule.enabled]
        for rule in on_starts:
            self.update_variable(rule.data)
            
        # 3. Execute Action Strategy
        executor = self.executors.get(action.type)
        if not executor:
            app_logger.error(f"No executor found for action type: {action.type}")
            return None

        success, next_index = executor.execute(self, action, self.device_serial)
        
        # 4. On Success / Failure
        if success:
            # Special handling for LoopStartAction: Only trigger OnSuccess when loop finishes (jumps to end)
            # If next_index is None, it means the loop is continuing (iteration start), so we skip OnSuccess
            if isinstance(action, LoopStartAction) and next_index is None:
                pass
            else:
                on_successes = [rule for rule in action.advanced_logic if rule.trigger == "on_success" and rule.enabled]
                for rule in on_successes:
                    self.update_variable(rule.data)
        else:
            on_failures = [rule for rule in action.advanced_logic if rule.trigger == "on_failure" and rule.enabled]
            for rule in on_failures:
                self.update_variable(rule.data)
                
        return next_index


    def find_loop_end_index(self, loop_id: str, start_index: int) -> int:
        for i in range(start_index + 1, len(self.macro.actions)):
            act = self.macro.actions[i]
            if isinstance(act, LoopEndAction) and act.linked_loop_id == loop_id:
                return i
        return len(self.macro.actions) # End of script if not found

    def find_loop_start_index(self, loop_id: str, end_index: int) -> int:
        for i in range(end_index - 1, -1, -1):
            act = self.macro.actions[i]
            if isinstance(act, LoopStartAction) and act.loop_id == loop_id:
                return i
        return 0 # Should not happen if structure is correct
    

    def stop(self):
        self._stop_event.set()
        if self.on_status_update: self.on_status_update("Stopping")
    
    def pause(self):
        self.paused = True
        if self.on_status_update: self.on_status_update("Paused")

    def resume(self):
        self.paused = False
        if self.on_status_update: self.on_status_update("Running")
    
    def scale_coordinate(self, coord, source_resolution=None):
        """Scale a coordinate (Point, Region, or PolygonRegion) from source to current resolution"""
        if not hasattr(self, 'current_resolution'):
            return coord
        
        # If no source_resolution provided, don't scale (backward compatibility)
        # Old regions without resolution metadata should work at their native resolution
        if source_resolution is None:
            return coord
        
        # No scaling needed if resolutions match
        if (self.current_resolution.width == source_resolution.width and
            self.current_resolution.height == source_resolution.height):
            return coord
        
        # Scale based on type
        if isinstance(coord, Point):
            scale_x = self.current_resolution.width / source_resolution.width
            scale_y = self.current_resolution.height / source_resolution.height
            return Point(int(coord.x * scale_x), int(coord.y * scale_y))
        elif isinstance(coord, (Region, PolygonRegion, MultiRegion)):
            return coord.scale(source_resolution, self.current_resolution)
        
        return coord
