import json
import os
import shutil
import cv2
from typing import Dict, List, Union, Optional
from .models import Region, PolygonRegion, Point, MultiRegion

class AssetManager:
    def __init__(self, base_path="assets"):
        self.base_path = base_path
        self.regions_file = os.path.join(base_path, "regions.json")
        self.images_dir = os.path.join(base_path, "images")
        
        os.makedirs(self.images_dir, exist_ok=True)
        self.regions = self.load_regions()

    def load_regions(self) -> Dict[str, Union[Region, PolygonRegion, MultiRegion]]:
        if not os.path.exists(self.regions_file):
            return {}
            
        try:
            with open(self.regions_file, 'r') as f:
                data = json.load(f)
                
            loaded = {}
            for name, props in data.items():
                source_res = props.get("source_resolution")  # May be None for old regions
                
                if props["type"] == "region":
                    region = Region(props["x"], props["y"], props["width"], props["height"])
                elif props["type"] == "polygon":
                    points = [Point(p["x"], p["y"]) for p in props["points"]]
                    region = PolygonRegion(points)
                elif props["type"] == "multi":
                    sub_regions = []
                    for sub in props["regions"]:
                        if sub["type"] == "region":
                            sub_regions.append(Region(sub["x"], sub["y"], sub["width"], sub["height"]))
                        elif sub["type"] == "polygon":
                            points = [Point(p["x"], p["y"]) for p in sub["points"]]
                            sub_regions.append(PolygonRegion(points))
                    region = MultiRegion(sub_regions)
                else:
                    continue
                
                # Store with metadata
                loaded[name] = {"region": region, "source_resolution": source_res}
            
            return loaded
        except Exception as e:
            print(f"Error loading regions: {e}")
            return {}

    def save_region(self, name: str, region: Union[Region, PolygonRegion, MultiRegion], source_resolution: Optional[Dict[str, int]] = None):
        """Save a region with optional source resolution metadata"""
        self.regions[name] = {"region": region, "source_resolution": source_resolution}
        self._persist_regions()

    def _persist_regions(self):
        data = {}
        for name, region_data in self.regions.items():
            # Handle both old format (direct Region) and new format (dict with metadata)
            if isinstance(region_data, dict):
                region = region_data["region"]
                source_res = region_data.get("source_resolution")
            else:
                # Backward compatibility: old format
                region = region_data
                source_res = None
            
            if isinstance(region, Region):
                data[name] = {
                    "type": "region",
                    "x": region.x, "y": region.y, 
                    "width": region.width, "height": region.height
                }
            elif isinstance(region, PolygonRegion):
                points = [{"x": p.x, "y": p.y} for p in region.points]
                data[name] = {
                    "type": "polygon",
                    "points": points
                }
            elif isinstance(region, MultiRegion):
                sub_regions_data = []
                for sub in region.regions:
                    if isinstance(sub, Region):
                        sub_regions_data.append({
                            "type": "region",
                            "x": sub.x, "y": sub.y,
                            "width": sub.width, "height": sub.height
                        })
                    elif isinstance(sub, PolygonRegion):
                        points = [{"x": p.x, "y": p.y} for p in sub.points]
                        sub_regions_data.append({
                            "type": "polygon",
                            "points": points
                        })
                data[name] = {
                    "type": "multi",
                    "regions": sub_regions_data
                }
            
            # Add source resolution if available
            if source_res:
                data[name]["source_resolution"] = source_res
        
        with open(self.regions_file, 'w') as f:
            json.dump(data, f, indent=2)

    def save_image(self, name: str, image_path: str):
        # Copy image to assets folder
        ext = os.path.splitext(image_path)[1]
        target_path = os.path.join(self.images_dir, f"{name}{ext}")
        shutil.copy2(image_path, target_path)
        return target_path

    def get_image_path(self, name: str) -> str:
        # Find image with any extension
        for ext in ['.png', '.jpg', '.jpeg']:
            path = os.path.join(self.images_dir, f"{name}{ext}")
            if os.path.exists(path):
                return path
        return None

    def save_image_asset(self, name: str, image_data):
        filename = f"{name}.png"
        path = os.path.join(self.images_dir, filename)
        cv2.imwrite(path, image_data)
        return path
