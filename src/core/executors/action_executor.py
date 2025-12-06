from typing import Tuple, Optional
from abc import ABC, abstractmethod
from ..models import Action
from ..adb_manager import AdbManager

class ActionExecutor(ABC):
    @abstractmethod
    def execute(self, runner, action: Action, device_serial: str) -> Tuple[bool, Optional[int]]:
        """
        Execute the given action.
        :param runner: The MacroRunner instance (context).
        :param action: The action to execute.
        :param device_serial: The serial number of the device.
        :return: A tuple (success, next_index). 
                 success: True if action succeeded, False otherwise.
                 next_index: The index of the next action to execute, or None to continue sequentially.
        """
        pass
