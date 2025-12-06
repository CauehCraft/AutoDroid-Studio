from typing import Tuple, Optional
import time

import cv2

from .action_executor import ActionExecutor
from ..models import ClickAction, WaitAction, SwipeAction, Point, Region, PolygonRegion, MultiRegion, Size
from ...utils.logger import app_logger

class ClickExecutor(ActionExecutor):
    def execute(self, runner, action: ClickAction, device_serial: str) -> Tuple[bool, Optional[int]]:
        device = runner.adb.connect_device(device_serial)
        if not device:
            return False, None

        # Get source resolution from action metadata if available
        source_resolution = self._get_source_resolution(action)
        
        # Scale the target and get random point
        target_point = self._resolve_target_point(runner, action.target, source_resolution)
        
        if not target_point:
            return False, None
        
        # Create a temporary action with the resolved point for execution
        temp_action = ClickAction(
            id=action.id,
            type=action.type,
            description=action.description,
            target=target_point,
            duration_ms=action.duration_ms,
            random_duration_variance=action.random_duration_variance
        )
        
        app_logger.info(f"Clicking at ({target_point.x}, {target_point.y}) [source_res: {source_resolution}]")
        runner.adb.execute_multitouch_actions(device, [temp_action])
        return True, None

    def _get_source_resolution(self, action: ClickAction) -> Optional[Size]:
        """Extract source resolution from action metadata."""
        if hasattr(action, 'source_resolution') and action.source_resolution:
            return Size(
                width=action.source_resolution['width'],
                height=action.source_resolution['height']
            )
        return None

    def _resolve_target_point(self, runner, target, source_resolution) -> Optional[Point]:
        """Scale target and resolve to a Point."""
        scaled_target = runner.scale_coordinate(target, source_resolution)
        
        if isinstance(scaled_target, Point):
            return scaled_target
        elif isinstance(scaled_target, (Region, PolygonRegion, MultiRegion)):
            return scaled_target.get_random_point()
        return None


class WaitExecutor(ActionExecutor):
    def execute(self, runner, action: WaitAction, device_serial: str) -> Tuple[bool, Optional[int]]:
        device = runner.adb.connect_device(device_serial)
        if not device:
            return False, None

        # Image-based wait
        if action.wait_type == "image" and action.image_name:
            return self._wait_for_image(runner, action, device)

        # Default time-based wait
        wait_time = action.get_wait_time()
        app_logger.info(f"Waiting for {wait_time}s...")
        time.sleep(wait_time)
        return True, None

    def _wait_for_image(self, runner, action: WaitAction, device) -> Tuple[bool, Optional[int]]:
        """Wait for an image to appear on screen."""
        app_logger.info(f"Waiting for image '{action.image_name}'...")
        
        image_path = runner.assets.get_image_path(action.image_name)
        if not image_path:
            app_logger.error(f"Image asset '{action.image_name}' not found!")
            return False, None

        template = cv2.imread(image_path)
        if template is None:
            app_logger.error(f"Failed to load image file: {image_path}")
            return False, None

        start_time = time.time()
        
        while True:
            # Check for stop event
            if runner._stop_event.is_set():
                return False, None
            
            # Check for timeout if duration_ms > 0
            if action.duration_ms > 0:
                elapsed = (time.time() - start_time) * 1000
                if elapsed > action.duration_ms:
                    app_logger.warning(f"Wait for image '{action.image_name}' timed out after {action.duration_ms}ms")
                    return False, None

            # Check for pause
            while runner.paused:
                time.sleep(0.1)
                if runner._stop_event.is_set():
                    return False, None
            
            # Take screenshot and search
            screen = runner.adb.take_screenshot(device)
            if screen is not None:
                point = runner.vision.find_image(screen, template)
                if point:
                    app_logger.info(f"Image '{action.image_name}' found. Continuing...")
                    return True, None
            
            time.sleep(action.check_interval_ms / 1000.0)

class SwipeExecutor(ActionExecutor):
    def execute(self, runner, action: SwipeAction, device_serial: str) -> Tuple[bool, Optional[int]]:
        device = runner.adb.connect_device(device_serial)
        if not device: return False, None

        # Scale start and end points
        start_point = runner.scale_coordinate(action.start_point)
        if isinstance(start_point, (Region, PolygonRegion, MultiRegion)):
            start_point = start_point.get_random_point()
        
        end_point = runner.scale_coordinate(action.end_point)
        if isinstance(end_point, (Region, PolygonRegion, MultiRegion)):
            end_point = end_point.get_random_point()
        
        app_logger.info(f"Swiping from ({start_point.x}, {start_point.y}) to ({end_point.x}, {end_point.y})")
        app_logger.info(f"Hold start: {action.hold_start_ms}ms, Swipe duration: {action.duration_ms}ms, Hold end: {action.hold_end_ms}ms")
        
        temp_action = SwipeAction(
            id=action.id,
            type=action.type,
            description=action.description,
            start_point=start_point,
            end_point=end_point,
            duration_ms=action.duration_ms,
            duration_variance_ms=action.duration_variance_ms,
            hold_start_ms=action.hold_start_ms,
            hold_start_variance_ms=action.hold_start_variance_ms,
            hold_end_ms=action.hold_end_ms,
            hold_end_variance_ms=action.hold_end_variance_ms
        )
        
        runner.adb.execute_multitouch_actions(device, [temp_action])
        return True, None
