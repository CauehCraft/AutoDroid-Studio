import threading
from typing import Optional, Tuple

import cv2

from ...utils.logger import app_logger
from ..models import (ClickAction, ClickImageAction, MultiAction, MultiRegion,
                      Point, PolygonRegion, Region, SwipeAction)
from .action_executor import ActionExecutor


class MultiExecutor(ActionExecutor):
    def execute(self, runner, action: MultiAction, device_serial: str) -> Tuple[bool, Optional[int]]:
        device = runner.adb.connect_device(device_serial)
        if not device: return False, None

        # Check if all actions are touch/click actions
        all_touch_actions = all(
            isinstance(sub, (ClickAction, SwipeAction, ClickImageAction)) 
            for sub in action.actions
        )
        
        if all_touch_actions and len(action.actions) > 1:
            return self._execute_multitouch_batch(runner, device, action)
        
        # Fallback to threaded execution for mixed action types
        return self._execute_threaded(runner, device, action)

    def _execute_multitouch_batch(self, runner, device, action: MultiAction) -> Tuple[bool, Optional[int]]:
        scaled_actions = []
        valid_original_actions = [] 
        
        for sub_action in action.actions:
            # 1. Check Condition
            if not self._check_condition(runner, sub_action):
                app_logger.debug(f"MultiAction sub-action {sub_action.id} skipped (condition not met)")
                continue
            
            # 2. On Start
            self._trigger_logic(runner, sub_action, "on_start")
            
            valid_original_actions.append(sub_action)

            scaled_action = self._prepare_action(runner, device, sub_action, action.strict_mode)
            
            if scaled_action:
                scaled_actions.append(scaled_action)
            elif action.strict_mode:
                 app_logger.warning(f"Action '{sub_action.description}' failed preparation in Strict Mode. Aborting MultiAction.")
                 return False, None
            # If not strict mode and scaled_action is None (e.g. image not found), we just skip it but keep it in valid_original_actions? 
            # Actually if image not found, we shouldn't trigger success for it.
            if not scaled_action:
                 if sub_action in valid_original_actions:
                     valid_original_actions.remove(sub_action)

        if scaled_actions:
            success = runner.adb.execute_multitouch_actions(device, scaled_actions)
            if success:
                app_logger.info(f"Executed {len(scaled_actions)} simultaneous touch actions")
                # 3. On Success
                for sub_action in valid_original_actions:
                    self._trigger_logic(runner, sub_action, "on_success")
                return True, None
            else:
                # 4. On Failure
                for sub_action in valid_original_actions:
                    self._trigger_logic(runner, sub_action, "on_failure")
                return False, None
        else:
            app_logger.warning("MultiAction aborted due to missing targets or preparation failure.")
            return False, None

    def _execute_threaded(self, runner, device, action: MultiAction) -> Tuple[bool, Optional[int]]:
        app_logger.info(f"Using threaded execution for {len(action.actions)} actions")
        threads = []
        for sub_action in action.actions:
            t = threading.Thread(target=runner.execute_action, args=(device, sub_action))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
            
        return True, None

    def _check_condition(self, runner, action) -> bool:
        conditions = [rule for rule in action.advanced_logic if rule.trigger == "condition" and rule.enabled]
        for rule in conditions:
            if not runner.evaluate_condition(rule.data):
                return False
        return True

    def _trigger_logic(self, runner, action, trigger_type):
        rules = [rule for rule in action.advanced_logic if rule.trigger == trigger_type and rule.enabled]
        for rule in rules:
            runner.update_variable(rule.data)

    def _prepare_action(self, runner, device, sub_action, strict_mode: bool):
        if isinstance(sub_action, ClickAction):
            return self._prepare_click_action(runner, sub_action)
        elif isinstance(sub_action, SwipeAction):
            return self._prepare_swipe_action(runner, sub_action)
        elif isinstance(sub_action, ClickImageAction):
            return self._prepare_image_click_action(runner, device, sub_action, strict_mode)
        return None

    def _prepare_click_action(self, runner, sub_action: ClickAction):
        scaled_target = runner.scale_coordinate(sub_action.target, None)
        return ClickAction(
            id=sub_action.id,
            type=sub_action.type,
            description=sub_action.description,
            target=scaled_target if isinstance(scaled_target, Point) else scaled_target.get_random_point(),
            duration_ms=sub_action.duration_ms,
            random_duration_variance=sub_action.random_duration_variance
        )

    def _prepare_swipe_action(self, runner, sub_action: SwipeAction):
        scaled_start = runner.scale_coordinate(sub_action.start_point, None)
        scaled_end = runner.scale_coordinate(sub_action.end_point, None)
        
        if isinstance(scaled_start, (Region, PolygonRegion, MultiRegion)):
            scaled_start = scaled_start.get_random_point()
        if isinstance(scaled_end, (Region, PolygonRegion, MultiRegion)):
            scaled_end = scaled_end.get_random_point()
            
        return SwipeAction(
            id=sub_action.id,
            type=sub_action.type,
            description=sub_action.description,
            start_point=scaled_start,
            end_point=scaled_end,
            duration_ms=sub_action.duration_ms,
            duration_variance_ms=sub_action.duration_variance_ms,
            hold_start_ms=sub_action.hold_start_ms,
            hold_start_variance_ms=sub_action.hold_start_variance_ms,
            hold_end_ms=sub_action.hold_end_ms,
            hold_end_variance_ms=sub_action.hold_end_variance_ms
        )

    def _prepare_image_click_action(self, runner, device, sub_action: ClickImageAction, strict_mode: bool):
        image_path = runner.assets.get_image_path(sub_action.image_name)
        if not image_path:
            app_logger.error(f"Image asset '{sub_action.image_name}' not found!")
            return None

        screen = runner.adb.take_screenshot(device)
        if screen is None:
            return None

        template = cv2.imread(image_path)
        if template is None:
            app_logger.error(f"Failed to load image file: {image_path}")
            return None

        rect = runner.vision.find_image_rect(screen, template, threshold=sub_action.threshold)
        if rect:
            point = rect.get_random_point() if sub_action.randomize_location else Point(rect.x + rect.width // 2, rect.y + rect.height // 2)
            app_logger.info(f"Image '{sub_action.image_name}' found at {point} for MultiAction")
            
            return ClickAction(
                id=sub_action.id,
                type="click",
                description=f"Click Image: {sub_action.image_name}",
                target=point,
                duration_ms=sub_action.duration_ms,
                random_duration_variance=0 
            )
        else:
            app_logger.warning(f"Image '{sub_action.image_name}' not found.")
            return None
