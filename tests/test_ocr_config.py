import os
import sys
import cv2
import pytesseract
import time
import numpy as np

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.vision import VisionEngine

def test_tesseract_configs():
    vision = VisionEngine()
    
    img_dir = os.path.join(os.path.dirname(__file__), 'imgsOcr')
    if not os.path.exists(img_dir):
        print(f"Directory not found: {img_dir}")
        return

    files = [f for f in os.listdir(img_dir) if f.endswith(('.png', '.jpg'))]
    if not files:
        print("No images found.")
        return

    print(f"Found {len(files)} images. Starting Tesseract Benchmark...\n")

    # Define configurations to test
    # (Preprocessing Method, Tesseract Config)
    configs = [
        ("default", r'--oem 3 --psm 7'),
        ("default", r'--oem 3 --psm 6'),
        ("game", r'--oem 3 --psm 7'),
        ("game", r'--oem 3 --psm 6'),
        ("game", r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'),
        ("number", r'--oem 3 --psm 7'),
        ("number", r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'),
        ("adaptive", r'--oem 3 --psm 7'),
        ("adaptive", r'--oem 3 --psm 6'),
        ("adaptive", r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'),
        ("clean", r'--oem 3 --psm 7'),
        ("clean", r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'),
        ("white_text", r'--oem 3 --psm 7'),
        ("white_text", r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'),
        ("raw", r'--oem 3 --psm 7'),
        ("raw", r'--oem 3 --psm 6'),
    ]

    results = {} # (method, config) -> {correct: 0, total: 0, time: 0}

    for method, config in configs:
        key = (method, config)
        results[key] = {'correct': 0, 'total': 0, 'time': 0}
        
        print(f"Testing: Method='{method}', Config='{config}'")
        
        start_time = time.time()
        
        for f in files:
            expected = os.path.splitext(f)[0]
            path = os.path.join(img_dir, f)
            
            img = cv2.imread(path)
            if img is None: continue
            
            # Preprocess
            processed = vision.preprocess_image(img, method=method)
            
            # OCR
            try:
                text = pytesseract.image_to_string(processed, config=config).strip()
                # Remove spaces for number comparison
                text_clean = text.replace(" ", "")
                
                is_correct = (text_clean == expected)
                if is_correct:
                    results[key]['correct'] += 1
                
                print(f"  [{'PASS' if is_correct else 'FAIL'}] Expected: {expected}, Got: {text_clean} (Raw: {text})")
                
            except Exception as e:
                print(f"  Error: {e}")
        
        elapsed = time.time() - start_time
        results[key]['total'] = len(files)
        results[key]['time'] = elapsed
        print(f"  -> Accuracy: {results[key]['correct']}/{len(files)} | Time: {elapsed:.4f}s\n")

    # Summary
    print("-" * 60)
    print(f"{'Method':<10} | {'Config':<40} | {'Accuracy':<10} | {'Time (s)':<10}")
    print("-" * 60)
    
    best_config = None
    best_acc = -1
    
    for (method, config), res in results.items():
        acc = res['correct'] / res['total'] * 100 if res['total'] > 0 else 0
        print(f"{method:<10} | {config[:40]:<40} | {res['correct']}/{res['total']} ({acc:.0f}%) | {res['time']:.4f}")
        
        if acc > best_acc:
            best_acc = acc
            best_config = (method, config)
            
    print("-" * 60)
    print(f"Best Configuration: Method='{best_config[0]}', Config='{best_config[1]}'")

def test_easyocr():
    print("\n" + "="*30)
    print("Testing EasyOCR...")
    print("="*30)
    
    try:
        import easyocr
    except ImportError:
        print("EasyOCR not installed. Skipping.")
        print("To install: pip install easyocr")
        return

    img_dir = os.path.join(os.path.dirname(__file__), 'imgsOcr')
    files = [f for f in os.listdir(img_dir) if f.endswith(('.png', '.jpg'))]
    
    print("Initializing EasyOCR Reader (this may take a moment)...")
    start_init = time.time()
    # gpu=False to test CPU impact as requested (or check if available)
    reader = easyocr.Reader(['en'], gpu=True, verbose=False) 
    print(f"Initialization took: {time.time() - start_init:.4f}s")
    
    correct = 0
    start_time = time.time()
    
    for f in files:
        expected = os.path.splitext(f)[0]
        path = os.path.join(img_dir, f)
        
        # EasyOCR reads directly from file or numpy
        result = reader.readtext(path, detail=0)
        # Result is a list of strings
        text = "".join(result).replace(" ", "")
        
        if text == expected:
            correct += 1
        
        # print(f"  Expected: {expected}, Got: {text}")

    elapsed = time.time() - start_time
    print(f"EasyOCR Results:")
    print(f"Accuracy: {correct}/{len(files)} ({correct/len(files)*100:.0f}%)")
    print(f"Total Time: {elapsed:.4f}s (Avg: {elapsed/len(files):.4f}s/img)")

if __name__ == "__main__":
    test_tesseract_configs()
    test_easyocr()
