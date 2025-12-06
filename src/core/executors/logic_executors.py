import time
from typing import Optional, Tuple

import cv2

from ..comparison_utils import evaluate_comparison
from ..models import (ConditionAction, LoopAction, LoopEndAction,
                      LoopStartAction, VarAction)
from ...utils.logger import app_logger
from .action_executor import ActionExecutor


class VarExecutor(ActionExecutor):
    def execute(self, runner, action: VarAction, device_serial: str) -> Tuple[bool, Optional[int]]:
        current_val = runner.macro.variables.get(action.var_name, 0)
        
        if action.operation == "set":
            runner.macro.variables[action.var_name] = action.value
            if runner.on_variable_update: runner.on_variable_update(action.var_name, action.value)
            app_logger.info(f"Variable '{action.var_name}' set to {action.value}")
        elif action.operation == "increment":
            try:
                runner.macro.variables[action.var_name] = int(current_val) + int(action.value)
                if runner.on_variable_update: runner.on_variable_update(action.var_name, runner.macro.variables[action.var_name])
                app_logger.info(f"Variable '{action.var_name}' incremented to {runner.macro.variables[action.var_name]}")
            except ValueError:
                app_logger.error(f"Cannot increment variable '{action.var_name}' of type {type(current_val)}")
                return False, None
        
        return True, None

class ConditionExecutor(ActionExecutor):
    def execute(self, runner, action: ConditionAction, device_serial: str) -> Tuple[bool, Optional[int]]:
        device = runner.adb.connect_device(device_serial)
        if not device: return False, None

        result = False
        
        if action.condition_type == "variable":
            var_val = runner.macro.variables.get(action.target)
            result = evaluate_comparison(var_val, action.operator, action.value)
            
            # Special handling for existence checks
            if action.operator == "exists":
                result = action.target in runner.macro.variables
                
        elif action.condition_type == "image_found":
            image_path = runner.assets.get_image_path(action.target)
            if image_path:
                screen = runner.adb.take_screenshot(device)
                if screen is not None:
                    template = cv2.imread(image_path)
                    if template is not None:
                        point = runner.vision.find_image(screen, template)
                        result = point is not None
        
        app_logger.info(f"Condition '{action.condition_type}' on '{action.target}': {result}")
        
        actions_to_run = action.then_actions if result else action.else_actions
        for sub_action in actions_to_run:
            if runner._stop_event.is_set(): break
            while runner.paused:
                time.sleep(0.1)
                if runner._stop_event.is_set(): break
            
            # Recursively execute sub-actions using the runner's main execution method
            runner.execute_action(device, sub_action)
            
        return True, None

class LoopExecutor(ActionExecutor):
    def execute(self, runner, action: LoopAction, device_serial: str) -> Tuple[bool, Optional[int]]:
        device = runner.adb.connect_device(device_serial)
        if not device: return False, None

        app_logger.info(f"Starting loop: {action.iterations} iterations")
        for i in range(action.iterations):
            if runner._stop_event.is_set(): break
            
            app_logger.debug(f"Loop iteration {i+1}/{action.iterations}")
            for sub_action in action.loop_actions:
                if runner._stop_event.is_set(): break
                while runner.paused:
                    time.sleep(0.1)
                    if runner._stop_event.is_set(): break
                runner.execute_action(device, sub_action)
                
        return True, None

class LoopStartExecutor(ActionExecutor):
    def execute(self, runner, action: LoopStartAction, device_serial: str) -> Tuple[bool, Optional[int]]:
        current_index = getattr(runner, 'current_index', -1)
        if current_index == -1:
            app_logger.warning("LoopStartAction executed without known index. Ignoring.")
            return False, None

        should_continue = False
        
        if action.loop_type == "infinite":
            should_continue = self._handle_infinite_loop()
        elif action.loop_type == "count":
            should_continue = self._handle_count_loop(runner, action)
        elif action.loop_type == "condition":
             should_continue = self._handle_condition_loop(runner, action)
            
        if should_continue:
            return True, None # Continue to next action (inside loop)
        else:
            # Jump to action AFTER LoopEnd
            end_index = runner.find_loop_end_index(action.loop_id, current_index)
            return True, end_index + 1

    def _handle_infinite_loop(self) -> bool:
        return True

    def _handle_count_loop(self, runner, action: LoopStartAction) -> bool:
        # Initialize if not present
        if action.loop_id not in runner.loop_counters:
            runner.loop_counters[action.loop_id] = 0
        
        current_count = runner.loop_counters[action.loop_id]
        if action.iterations == -1 or current_count < action.iterations:
            runner.loop_counters[action.loop_id] += 1
            app_logger.debug(f"Loop {action.loop_id} iteration {runner.loop_counters[action.loop_id]}/{action.iterations}")
            return True
        else:
            # Reset counter when loop finishes
            del runner.loop_counters[action.loop_id]
            return False

    def _handle_condition_loop(self, runner, action: LoopStartAction) -> bool:
        # Check condition using centralized comparison
        var_val = runner.macro.variables.get(action.condition_var)
        should_continue = evaluate_comparison(var_val, action.condition_op, action.condition_value)
        app_logger.debug(f"Loop Condition: '{action.condition_var}' ({var_val}) {action.condition_op} '{action.condition_value}' -> {should_continue}")
        return should_continue

class LoopEndExecutor(ActionExecutor):
    def execute(self, runner, action: LoopEndAction, device_serial: str) -> Tuple[bool, Optional[int]]:
        current_index = getattr(runner, 'current_index', -1)
        # Jump back to LoopStart
        start_index = runner.find_loop_start_index(action.linked_loop_id, current_index)
        return True, start_index
