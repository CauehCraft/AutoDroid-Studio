from dataclasses import dataclass, field, asdict
from typing import List, Union, Any, Optional, Dict
import random
import time
import logging
from shapely.geometry import Polygon, Point as ShapelyPoint


@dataclass
class Point:
    x: int
    y: int

@dataclass
class Size:
    width: int
    height: int

@dataclass
class Region:
    x: int
    y: int
    width: int
    height: int

    def get_random_point(self) -> Point:
        return Point(
            random.randint(self.x, self.x + self.width),
            random.randint(self.y, self.y + self.height)
        )
    
    def scale(self, from_resolution: Size, to_resolution: Size) -> 'Region':
        """Scale region coordinates from one resolution to another"""
        scale_x = to_resolution.width / from_resolution.width
        scale_y = to_resolution.height / from_resolution.height
        
        return Region(
            x=int(self.x * scale_x),
            y=int(self.y * scale_y),
            width=int(self.width * scale_x),
            height=int(self.height * scale_y)
        )

def serialize_target(target) -> dict:
    """Serialize Point, Region, PolygonRegion, or MultiRegion to dict format.
    
    This is a helper function used by action classes to serialize their targets
    for JSON storage. Centralizes the serialization logic to avoid duplication.
    """
    if isinstance(target, Point):
        return {"type": "point", "x": target.x, "y": target.y}
    elif isinstance(target, Region):
        return {"type": "region", "x": target.x, "y": target.y, 
                "width": target.width, "height": target.height}
    elif isinstance(target, PolygonRegion):
        return {"type": "polygon", 
                "points": [{"x": p.x, "y": p.y} for p in target.points]}
    elif isinstance(target, MultiRegion):
        regions_data = []
        for r in target.regions:
            if isinstance(r, Region):
                regions_data.append({"type": "region", "x": r.x, "y": r.y, 
                                     "width": r.width, "height": r.height})
            elif isinstance(r, PolygonRegion):
                regions_data.append({"type": "polygon", 
                                     "points": [{"x": p.x, "y": p.y} for p in r.points]})
        return {"type": "multi", "regions": regions_data}
    return {"type": "point", "x": 0, "y": 0}


@dataclass
class PolygonRegion:
    points: List[Point]  # List of (x, y) tuples or Point objects

    def get_random_point(self) -> Point:
        if not self.points or len(self.points) < 3:
            raise ValueError("Polygon must have at least 3 points")
        
        poly = Polygon([(p.x, p.y) for p in self.points])
        min_x, min_y, max_x, max_y = poly.bounds
        
        while True:
            p = ShapelyPoint(random.uniform(min_x, max_x), random.uniform(min_y, max_y))
            if poly.contains(p):
                return Point(int(p.x), int(p.y))
    
    def scale(self, from_resolution: Size, to_resolution: Size) -> 'PolygonRegion':
        """Scale polygon points from one resolution to another"""
        scale_x = to_resolution.width / from_resolution.width
        scale_y = to_resolution.height / from_resolution.height
        
        scaled_points = [
            Point(int(p.x * scale_x), int(p.y * scale_y))
            for p in self.points
        ]
        return PolygonRegion(scaled_points)

@dataclass
class MultiRegion:
    regions: List[Union[Region, PolygonRegion]]

    def get_random_point(self) -> Point:
        if not self.regions:
            raise ValueError("MultiRegion must have at least one region")
        # Pick a random region
        region = random.choice(self.regions)
        return region.get_random_point()

    def scale(self, from_resolution: Size, to_resolution: Size) -> 'MultiRegion':
        scaled_regions = [r.scale(from_resolution, to_resolution) for r in self.regions]
        return MultiRegion(scaled_regions)

@dataclass
class Variable:
    name: str
    value: Union[str, int, float, bool]
    type: str = "string"

@dataclass
class LogicRule:
    trigger: str  # "condition", "on_start", "on_success", "on_failure"
    data: Dict[str, Any] # The logic definition (var, op, val)
    enabled: bool = True
    
    def to_dict(self):
        return {
            "trigger": self.trigger,
            "data": self.data,
            "enabled": self.enabled
        }

    @staticmethod
    def from_dict(data):
        return LogicRule(
            trigger=data.get("trigger", ""),
            data=data.get("data", {}),
            enabled=data.get("enabled", True)
        )

@dataclass
class Action:
    id: str
    type: str
    description: str = ""
    enabled: bool = True
    # New Advanced Logic System
    advanced_logic: List[LogicRule] = field(default_factory=list)
    
    # Deprecated fields (kept for backward compatibility during init)
    condition: Optional[Dict[str, Any]] = None 
    on_start: Optional[Dict[str, Any]] = None 
    on_success: Optional[Dict[str, Any]] = None 
    on_failure: Optional[Dict[str, Any]] = None 
    
    def __post_init__(self):
        # Migrate legacy fields to advanced_logic if present
        if self.condition:
            self.advanced_logic.append(LogicRule(trigger="condition", data=self.condition))
            self.condition = None
        if self.on_start:
            self.advanced_logic.append(LogicRule(trigger="on_start", data=self.on_start))
            self.on_start = None
        if self.on_success:
            self.advanced_logic.append(LogicRule(trigger="on_success", data=self.on_success))
            self.on_success = None
        if self.on_failure:
            self.advanced_logic.append(LogicRule(trigger="on_failure", data=self.on_failure))
            self.on_failure = None
        
        # Ensure advanced_logic items are LogicRule objects (if loaded from dict)
        if self.advanced_logic and isinstance(self.advanced_logic[0], dict):
            self.advanced_logic = [LogicRule.from_dict(item) for item in self.advanced_logic]

    def execute(self, context):
        raise NotImplementedError

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "description": self.description,
            "enabled": self.enabled,
            "advanced_logic": [l.to_dict() for l in self.advanced_logic]
        }

    @staticmethod
    def from_dict(data):
        # Factory method to be implemented or handled by a manager
        pass

@dataclass
class ClickAction(Action):
    target: Union[Point, Region, PolygonRegion, MultiRegion, str] = None  # str for region name
    duration_ms: int = 100
    random_duration_variance: int = 0
    source_resolution: Optional[Dict[str, int]] = None  # Resolution where region was created
    
    def execute(self, context):
        # Implementation will be in the engine, but here we define data
        pass

    def to_dict(self):
        data = super().to_dict()
        data["target"] = serialize_target(self.target)
        data["duration_ms"] = self.duration_ms
        data["random_duration_variance"] = self.random_duration_variance
        return data

@dataclass
class WaitAction(Action):
    duration_ms: int = 0
    random_variance_ms: int = 0
    wait_type: str = "time"  # "time" or "image"
    image_name: Optional[str] = None
    check_interval_ms: int = 1000
    
    def get_wait_time(self) -> float:
        if self.random_variance_ms > 0:
            variance = random.randint(-self.random_variance_ms, self.random_variance_ms)
            return max(0, (self.duration_ms + variance) / 1000.0)
        return self.duration_ms / 1000.0

    def to_dict(self):
        data = super().to_dict()
        data["duration_ms"] = self.duration_ms
        data["random_variance_ms"] = self.random_variance_ms
        data["wait_type"] = self.wait_type
        data["image_name"] = self.image_name
        data["check_interval_ms"] = self.check_interval_ms
        return data

@dataclass
class ClickImageAction(Action):
    image_name: str = ""
    threshold: float = 0.8
    duration_ms: int = 100
    randomize_location: bool = False # If true, clicks a random point within the found image
    random_duration_variance: int = 0
    max_retries: int = 1
    retry_interval_ms: int = 1000
    
    def to_dict(self):
        data = super().to_dict()
        data["image_name"] = self.image_name
        data["threshold"] = self.threshold
        data["duration_ms"] = self.duration_ms
        data["randomize_location"] = self.randomize_location
        data["random_duration_variance"] = self.random_duration_variance
        data["max_retries"] = self.max_retries
        data["retry_interval_ms"] = self.retry_interval_ms
        return data

@dataclass
class OCRAction(Action):
    region_name: str = ""
    variable_name: str = ""
    language: str = "eng"
    preprocess_mode: str = "game" # default, game, white_text, etc.
    text_type: str = "text" # text, number
    
    def to_dict(self):
        data = super().to_dict()
        data["region_name"] = self.region_name
        data["variable_name"] = self.variable_name
        data["language"] = self.language
        data["preprocess_mode"] = self.preprocess_mode
        data["text_type"] = self.text_type
        return data

@dataclass
class VarAction(Action):
    var_name: str = ""
    operation: str = ""  # "set", "increment", "decrement"
    value: Any = None

    def to_dict(self):
        data = super().to_dict()
        data["var_name"] = self.var_name
        data["operation"] = self.operation
        data["value"] = self.value
        return data

@dataclass
class ConditionAction(Action):
    condition_type: str = ""  # "variable", "image_found", "text_found"
    target: str = ""  # Variable name or Image/Text asset name
    operator: str = ""  # "==", "!=", ">", "<", "exists", "not_exists"
    value: Any = None # Value to compare against (for variables)
    then_actions: List[Action] = field(default_factory=list)
    else_actions: List[Action] = field(default_factory=list)

    def to_dict(self):
        data = super().to_dict()
        data["condition_type"] = self.condition_type
        data["target"] = self.target
        data["operator"] = self.operator
        data["value"] = self.value
        data["then_actions"] = [a.to_dict() for a in self.then_actions]
        data["else_actions"] = [a.to_dict() for a in self.else_actions]
        return data

@dataclass
class LoopAction(Action):
    iterations: int = 1
    loop_actions: List[Action] = field(default_factory=list)

    def to_dict(self):
        data = super().to_dict()
        data["iterations"] = self.iterations
        data["loop_actions"] = [a.to_dict() for a in self.loop_actions]
        return data

@dataclass
class SwipeAction(Action):
    start_point: Union[Point, Region, PolygonRegion] = None
    end_point: Union[Point, Region, PolygonRegion] = None
    duration_ms: int = 300
    duration_variance_ms: int = 0
    hold_start_ms: int = 0  # Delay after pressing at start point
    hold_start_variance_ms: int = 0
    hold_end_ms: int = 0    # Delay before releasing at end point
    hold_end_variance_ms: int = 0
    
    def to_dict(self):
        data = super().to_dict()
        data["start_point"] = serialize_target(self.start_point)
        data["end_point"] = serialize_target(self.end_point)
        data["duration_ms"] = self.duration_ms
        data["duration_variance_ms"] = self.duration_variance_ms
        data["hold_start_ms"] = self.hold_start_ms
        data["hold_start_variance_ms"] = self.hold_start_variance_ms
        data["hold_end_ms"] = self.hold_end_ms
        data["hold_end_variance_ms"] = self.hold_end_variance_ms
        return data

@dataclass
class MultiAction(Action):
    actions: List[Action] = field(default_factory=list) # Actions to run simultaneously
    strict_mode: bool = False # If True, aborts if any sub-action fails (e.g. image not found)
    
    def to_dict(self):
        data = super().to_dict()
        data["actions"] = [a.to_dict() for a in self.actions]
        data["strict_mode"] = self.strict_mode
        return data

@dataclass
class Macro:
    name: str
    target_resolution: Size
    actions: List[Action] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict) # Global variables for the macro
    created_at: float = field(default_factory=time.time)
    
    def validate_resolution(self, device_resolution: Size) -> bool:
        """Validate resolution - now just logs a warning if different"""
        if (self.target_resolution.width != device_resolution.width or 
            self.target_resolution.height != device_resolution.height):
            # Log warning but allow execution - scaling will be applied
            logging.warning(f"Resolution mismatch: Macro expects {self.target_resolution}, device has {device_resolution}. Auto-scaling will be applied.")
        return True  # Always return True, rely on scaling

    def to_dict(self):
        return {
            "name": self.name,
            "target_resolution": {"width": self.target_resolution.width, "height": self.target_resolution.height},
            "actions": [a.to_dict() for a in self.actions],
            "variables": self.variables,
            "created_at": self.created_at
        }


@dataclass
class LoopStartAction(Action):
    loop_id: str = ""
    loop_type: str = "count" # "count", "infinite", "condition"
    iterations: int = 1 # -1 for infinite
    condition_var: str = ""
    condition_op: str = "=="
    condition_value: str = ""

    def to_dict(self):
        data = super().to_dict()
        data["loop_id"] = self.loop_id
        data["loop_type"] = self.loop_type
        data["iterations"] = self.iterations
        data["condition_var"] = self.condition_var
        data["condition_op"] = self.condition_op
        data["condition_value"] = self.condition_value
        return data

@dataclass
class LoopEndAction(Action):
    linked_loop_id: str = ""

    def to_dict(self):
        data = super().to_dict()
        data["linked_loop_id"] = self.linked_loop_id
        return data
