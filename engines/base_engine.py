from abc import ABC, abstractmethod

class BaseEngine(ABC):
    @abstractmethod
    def process(self, frame):
        # Must return a dict: {'x_midi': int, 'y_midi': int} or None
        pass

    @abstractmethod
    def release(self):
        pass