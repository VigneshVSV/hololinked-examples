import numpy
from dataclasses import dataclass



@dataclass 
class Intensity:
    value : numpy.ndarray
    timestamp : str  

    def json(self):
        return {
            'value' : self.value.tolist(),
            'timestamp' : self.timestamp
        }

    @property
    def not_completely_black(self):
        if any(self.value[i] > 0 for i in range(len(self.value))):  
            return True 
        return False
    