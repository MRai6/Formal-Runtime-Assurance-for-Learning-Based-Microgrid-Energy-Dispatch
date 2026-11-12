"""Abstract base controller interface for microgrid dispatch policies."""

from abc import ABC, abstractmethod
import numpy as np


class BaseController(ABC):
    """Abstract base class for all rule-based, heuristic, or learned dispatch controllers."""

    @abstractmethod
    def act(self, observation: np.ndarray) -> np.ndarray:
        """Compute the dispatch control action given the current environment observation.

        Args:
            observation: Environment observation vector.

        Returns:
            1-element action vector in [-1.0, 1.0].
        """
        pass

    def reset(self) -> None:
        """Reset internal controller state between episodes (if stateful)."""
        pass
