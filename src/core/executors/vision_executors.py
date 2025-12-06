import time
import cv2
from typing import Tuple, Optional
from .action_executor import ActionExecutor
from ..models import ClickImageAction, OCRAction, Point, Region, Size
from ...utils.logger import app_logger


class ClickImageExecutor(ActionExecutor):
    def execute(self, runner, action: ClickImageAction, device_serial: str) -> Tuple[bool, Optional[int]]:
        device = runner.adb.connect_device(device_serial)
        if not device:
            return False, None

        image_path = runner.assets.get_image_path(action.image_name)
        if not image_path:
            app_logger.error(f"Image asset '{action.image_name}' not found!")
            return False, None

        # Load template once
        template = cv2.imread(image_path)
        if template is None:
            app_logger.error(f"Failed to load image file: {image_path}")
            return False, None

        # Retry loop
        max_retries = getattr(action, 'max_retries', 1)
        retry_interval = getattr(action, 'retry_interval_ms', 1000)
        
        for attempt in range(max_retries):
            # Take screenshot
            screen = runner.adb.take_screenshot(device)
            if screen is None:
                app_logger.error("Failed to take screenshot during ClickImageAction")
                return False, None  # Fatal error, don't retry
                
            # Find image
            rect = runner.vision.find_image_rect(screen, template, threshold=action.threshold)
            if rect:
                point = rect.get_random_point() if action.randomize_location else Point(rect.x + rect.width // 2, rect.y + rect.height // 2)
                app_logger.info(f"Image '{action.image_name}' found at {point}")
                runner.adb.tap(device, point, action.duration_ms)
                return True, None
            
            # Image not found - check if we should retry
            if attempt >= max_retries - 1:
                app_logger.warning(f"Image '{action.image_name}' not found after {max_retries} attempts.")
                return False, None
            
            app_logger.info(f"Image '{action.image_name}' not found. Retrying ({attempt + 1}/{max_retries}) in {retry_interval}ms...")
            
            # Wait with stop/pause checking
            if not self._wait_with_checks(runner, retry_interval):
                break  # Stop event was set
                    
        return False, None

    def _wait_with_checks(self, runner, wait_ms: int) -> bool:
        """Wait for specified milliseconds while checking for stop/pause. Returns False if stopped."""
        start_wait = time.time()
        while (time.time() - start_wait) * 1000 < wait_ms:
            if runner._stop_event.is_set():
                return False
            while runner.paused:
                time.sleep(0.1)
                if runner._stop_event.is_set():
                    return False
            time.sleep(0.1)
        return True


class OCRExecutor(ActionExecutor):
    def execute(self, runner, action: OCRAction, device_serial: str) -> Tuple[bool, Optional[int]]:
        device = runner.adb.connect_device(device_serial)
        if not device:
            return False, None

        # 1. Get Region
        regions = runner.assets.load_regions()
        region_data = regions.get(action.region_name)
        
        if not region_data:
            app_logger.error(f"Region '{action.region_name}' not found!")
            return False, None

        # Parse region from data format
        region = self._parse_region(region_data, runner)

        # 2. Take Screenshot
        screen = runner.adb.take_screenshot(device)
        if screen is None:
            app_logger.error("Failed to take screenshot for OCR")
            return False, None

        # 3. Validate region type
        if not isinstance(region, Region):
            app_logger.error("OCR only supports rectangular regions currently")
            return False, None

        # 4. Crop Image with bounds checking
        cropped = self._crop_screen(screen, region)
        if cropped is None:
            app_logger.error(f"Invalid region dimensions for OCR: {region}")
            return False, None

        # 5. Read Text
        whitelist = "0123456789" if action.text_type == "number" else ""
        text = runner.vision.read_text(cropped, lang=action.language, preprocess=action.preprocess_mode, whitelist=whitelist)
        
        # 6. Post-process based on text_type
        if action.text_type == "number":
            text = text.replace(" ", "").strip()
        
        app_logger.info(f"OCR Result ({action.region_name}): '{text}'")
        
        # 7. Save to Variable
        runner.macro.variables[action.variable_name] = text
        if runner.on_variable_update:
            runner.on_variable_update(action.variable_name, text)
        return True, None

    def _parse_region(self, region_data, runner):
        """Parse region from data format, handling dict and direct region formats."""
        if isinstance(region_data, dict):
            region = region_data["region"]
            source_res = region_data.get("source_resolution")
            if source_res:
                source_res_obj = Size(width=source_res["width"], height=source_res["height"])
                return runner.scale_coordinate(region, source_res_obj)
            return region
        return runner.scale_coordinate(region_data)

    def _crop_screen(self, screen, region: Region):
        """Crop screen to region bounds with safety checks. Returns None if invalid."""
        h, w = screen.shape[:2]
        x = max(0, min(region.x, w))
        y = max(0, min(region.y, h))
        width = max(0, min(region.width, w - x))
        height = max(0, min(region.height, h - y))
        
        if width <= 0 or height <= 0:
            return None
        return screen[y:y+height, x:x+width]

