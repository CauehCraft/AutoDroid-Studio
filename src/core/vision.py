import cv2
import numpy as np
import pytesseract
from typing import Optional, Tuple, List
from .models import Region, Point

class VisionEngine:
    def __init__(self):
        # Try to find tesseract in common paths if not in PATH
        self._configure_tesseract()

    def _configure_tesseract(self):
        
        # Check if tesseract is already in PATH
        if shutil.which("tesseract"):
            return

        # Common installation paths on Windows
        common_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.join(os.getenv('LOCALAPPDATA', ''), r"Tesseract-OCR\tesseract.exe")
        ]

        for path in common_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                print(f"Found Tesseract at: {path}")
                return
        
        print("Warning: Tesseract not found in PATH or common locations.")

    def find_image(self, screen: np.ndarray, template: np.ndarray, threshold: float = 0.8) -> Optional[Point]:
        """
        Finds a template image within the screen image.
        Returns the center Point of the match if found, else None.
        """
        rect = self.find_image_rect(screen, template, threshold)
        if rect:
            return Point(rect.x + rect.width // 2, rect.y + rect.height // 2)
        return None

    def find_image_rect(self, screen: np.ndarray, template: np.ndarray, threshold: float = 0.8) -> Optional[Region]:
        """
        Finds a template image within the screen image.
        Returns the bounding Region of the match if found, else None.
        """
        if screen is None or template is None:
            return None

        # Ensure images are same type (grayscale or color)
        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        w, h = template_gray.shape[::-1]

        res = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        if max_val >= threshold:
            return Region(max_loc[0], max_loc[1], w, h)
        
        return None

    def find_all_images(self, screen: np.ndarray, template: np.ndarray, threshold: float = 0.8) -> List[Point]:
        """
        Finds all occurrences of a template image.
        """
        if screen is None or template is None:
            return []

        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        w, h = template_gray.shape[::-1]

        res = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        loc = np.where(res >= threshold)
        
        points = []
        for pt in zip(*loc[::-1]):
            center_x = pt[0] + w // 2
            center_y = pt[1] + h // 2
            points.append(Point(center_x, center_y))
            
        # TODO: Filter close points (non-max suppression) if needed
        return points

    def preprocess_image(self, image: np.ndarray, method: str = "default") -> np.ndarray:
        """
        Preprocesses the image for better OCR accuracy.
        """
        if image is None: return None
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        if method == "game":
            # Robust pipeline for game text (usually light text on dark/complex bg)
            # 1. Upscale significantly (3x) to help with small fonts
            gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            
            # 2. Apply Otsu's thresholding with Inversion
            # THRESH_BINARY_INV: If pixel > threshold (light text), set to 0 (black). Else 255 (white).
            # This creates Black Text on White Background, which Tesseract loves.
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            return thresh
            
        elif method == "number":
            # Similar to game but maybe less aggressive scaling
            gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            return thresh
            
        elif method == "adaptive":
            # Old 'game' mode: Upscale + Invert + Adaptive Threshold
            gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            gray = cv2.bitwise_not(gray)
            gray = cv2.medianBlur(gray, 3)
            thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                         cv2.THRESH_BINARY, 11, 2)
            return thresh

        elif method == "clean":
            # Adaptive + Morphological cleaning
            gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            gray = cv2.bitwise_not(gray)
            gray = cv2.medianBlur(gray, 3)
            thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                         cv2.THRESH_BINARY, 11, 2)
            # Remove small noise
            kernel = np.ones((2,2), np.uint8)
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
            return thresh

        elif method == "white_text":
            # Specific for white text on any background
            # Use HSV to filter only "pure" white (Low Saturation, High Value)
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # Define range for white
            # S: 0-50 (Low saturation, allows for slight color cast but mostly white/gray)
            # V: 200-255 (High brightness)
            lower_white = np.array([0, 0, 200])
            upper_white = np.array([180, 50, 255])
            
            mask = cv2.inRange(hsv, lower_white, upper_white)
            
            # Upscale
            mask = cv2.resize(mask, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            
            # Remove small noise (speckles)
            kernel = np.ones((2,2), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            
            # Invert to get Black Text on White Background (Tesseract standard)
            # Mask is White(255) for text. Invert -> Black(0) for text.
            thresh = cv2.bitwise_not(mask)
            return thresh

        elif method == "raw":
            # Just grayscale, no thresholding
            return gray
            
        else: # default
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return thresh

    def read_text(self, screen: np.ndarray, region: Optional[Region] = None, preprocess: str = "game", lang: str = "eng", whitelist: str = "") -> str:
        """
        Reads text from the screen or a specific region using OCR.
        preprocess: 'default', 'game', 'number', 'white_text', 'adaptive', 'clean'
        whitelist: Optional string of allowed characters (e.g. "0123456789")
        """
        if screen is None:
            return ""

        img_to_process = screen
        if region:
            # Crop the image: y:y+h, x:x+w
            img_to_process = screen[region.y : region.y + region.height, region.x : region.x + region.width]

        # Preprocess
        processed_img = self.preprocess_image(img_to_process, method=preprocess)
        
        # Save debug image
        try:
            cv2.imwrite("ocr_debug.png", processed_img)
        except: pass

        try:
            # Configure tesseract
            # --psm 7: Treat the image as a single text line.
            # --psm 6: Assume a single uniform block of text.
            # Try psm 7 for single line counters.
            config = r'--oem 3 --psm 7'
            
            if whitelist:
                config += f' -c tessedit_char_whitelist={whitelist}'
            
            text = pytesseract.image_to_string(processed_img, lang=lang, config=config)
            return text.strip()
        except pytesseract.TesseractNotFoundError:
            print("Error: Tesseract OCR not found. Please ensure Tesseract is installed and in your PATH.")
            return "Error: OCR Not Installed"
        except Exception as e:
            print(f"OCR Error: {e}")
            return ""
