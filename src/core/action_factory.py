import time

from .models import (
    Action, ClickAction, ClickImageAction, ConditionAction, LogicRule,
    LoopAction, LoopEndAction, LoopStartAction, MultiAction, MultiRegion,
    OCRAction, Point, PolygonRegion, Region, SwipeAction, VarAction, WaitAction,
    ScreenshotAction
)


class ActionFactory:
    @staticmethod
    def _parse_target(target_data: dict):
        """Parse a target dict into Point, Region, PolygonRegion, or MultiRegion.
        
        This helper centralizes deserialization logic for action targets,
        avoiding code duplication between click and swipe action parsing.
        """
        if not target_data:
            return Point(0, 0)
            
        target_type = target_data.get("type")
        
        if target_type == "point":
            return Point(target_data.get("x", 0), target_data.get("y", 0))
        elif target_type == "region":
            return Region(
                x=target_data.get("x", 0),
                y=target_data.get("y", 0),
                width=target_data.get("width", 0),
                height=target_data.get("height", 0)
            )
        elif target_type == "polygon":
            points = [Point(p["x"], p["y"]) for p in target_data.get("points", [])]
            return PolygonRegion(points)
        elif target_type == "multi":
            regions = []
            for r_data in target_data.get("regions", []):
                if r_data.get("type") == "region":
                    regions.append(Region(r_data["x"], r_data["y"], r_data["width"], r_data["height"]))
                elif r_data.get("type") == "polygon":
                    regions.append(PolygonRegion([Point(p["x"], p["y"]) for p in r_data.get("points", [])]))
            return MultiRegion(regions)
        
        return Point(0, 0)

    @staticmethod
    def create_action(data: dict) -> Action:
        type = data.get("type")
        id = data.get("id", str(time.time()))
        desc = data.get("description", "")
        enabled = data.get("enabled", True)
        
        # Load advanced_logic if present
        advanced_logic = []
        if data.get("advanced_logic"):
            advanced_logic = [LogicRule.from_dict(item) for item in data.get("advanced_logic")]

        common_kwargs = {
            "id": id,
            "type": type,
            "description": desc,
            "enabled": enabled,
            "advanced_logic": advanced_logic
        }
        
        if type == "click":
            target = ActionFactory._parse_target(data.get("target", {}))
            
            return ClickAction(
                **common_kwargs,
                target=target,
                duration_ms=data.get("duration_ms", 100),
                random_duration_variance=data.get("random_duration_variance", 0),
                source_resolution=data.get("source_resolution")
            )
                               
        elif type == "wait":
            return WaitAction(
                **common_kwargs,
                duration_ms=data.get("duration_ms", 1000),
                random_variance_ms=data.get("random_variance_ms", 0),
                wait_type=data.get("wait_type", "time"),
                image_name=data.get("image_name"),
                check_interval_ms=data.get("check_interval_ms", 1000)
            )
                               
        elif type == "click_image":
            return ClickImageAction(
                **common_kwargs,
                image_name=data.get("image_name", ""),
                threshold=data.get("threshold", 0.8),
                duration_ms=data.get("duration_ms", 100),
                randomize_location=data.get("randomize_location", False),
                random_duration_variance=data.get("random_duration_variance", 0),
                max_retries=data.get("max_retries", 1),
                retry_interval_ms=data.get("retry_interval_ms", 1000)
            )
            
        elif type == "ocr":
            # Migration for legacy 'preprocess' bool
            preprocess_mode = data.get("preprocess_mode")
            if preprocess_mode is None:
                # Legacy fallback
                if data.get("preprocess", True):
                    preprocess_mode = "game"
                else:
                    preprocess_mode = "raw"

            return OCRAction(
                **common_kwargs,
                region_name=data.get("region_name", ""),
                variable_name=data.get("variable_name", ""),
                language=data.get("language", "eng"),
                preprocess_mode=preprocess_mode,
                text_type=data.get("text_type", "text")
            )
                                    
        elif type == "variable":
            return VarAction(
                **common_kwargs,
                var_name=data.get("var_name", ""),
                operation=data.get("operation", "set"),
                value=data.get("value", 0)
            )
                             
        elif type == "condition":
            action = ConditionAction(
                **common_kwargs,
                condition_type=data.get("condition_type", "variable"),
                target=data.get("target", ""),
                operator=data.get("operator", "=="),
                value=data.get("value", 0)
            )
            for sub in data.get("then_actions", []):
                sub_action = ActionFactory.create_action(sub)
                if sub_action: action.then_actions.append(sub_action)
            for sub in data.get("else_actions", []):
                sub_action = ActionFactory.create_action(sub)
                if sub_action: action.else_actions.append(sub_action)
            return action
            
        elif type == "loop":
            action = LoopAction(
                **common_kwargs,
                iterations=data.get("iterations", 1)
            )
            for sub in data.get("loop_actions", []):
                sub_action = ActionFactory.create_action(sub)
                if sub_action: action.loop_actions.append(sub_action)
            return action
            
        elif type == "swipe":
            start = ActionFactory._parse_target(data.get("start_point", {"type": "point", "x": 0, "y": 0}))
            end = ActionFactory._parse_target(data.get("end_point", {"type": "point", "x": 0, "y": 0}))
            
            return SwipeAction(
                **common_kwargs,
                start_point=start,
                end_point=end,
                duration_ms=data.get("duration_ms", 300),
                duration_variance_ms=data.get("duration_variance_ms", 0),
                hold_start_ms=data.get("hold_start_ms", 0),
                hold_start_variance_ms=data.get("hold_start_variance_ms", 0),
                hold_end_ms=data.get("hold_end_ms", 0),
                hold_end_variance_ms=data.get("hold_end_variance_ms", 0)
            )
                               
        elif type == "multi":
            action = MultiAction(**common_kwargs)
            for sub in data.get("actions", []):
                sub_action = ActionFactory.create_action(sub)
                if sub_action: action.actions.append(sub_action)
            return action
            
        elif type == "loop_start":
            return LoopStartAction(
                **common_kwargs,
                loop_id=data.get("loop_id", ""),
                loop_type=data.get("loop_type", "count"),
                iterations=data.get("iterations", 1),
                condition_var=data.get("condition_var", ""),
                condition_op=data.get("condition_op", "=="),
                condition_value=data.get("condition_value", "")
            )
        
        elif type == "loop_end":
            return LoopEndAction(
                **common_kwargs,
                linked_loop_id=data.get("linked_loop_id", "")
            )
            
        elif type == "screenshot":
            return ScreenshotAction(
                **common_kwargs,
                filename_pattern=data.get("filename_pattern", "screenshot_{timestamp}.png"),
                save_path=data.get("save_path", "screenshots")
            )
            
        return None
