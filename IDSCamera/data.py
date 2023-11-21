from enum import IntEnum
from pyueye import ueye


class ColorModes(IntEnum):
    IS_COLORMODE_INVALID = 0
    IS_COLORMODE_MONOCHROME = 1
    IS_COLORMODE_BAYER = 2
    IS_COLORMODE_CBYCRY = 4
    IS_COLORMODE_JPEG = 8

    def json(self):
        return {name.strip('IS_COLORMODE') : value.value for name, value in vars(self).items() if isinstance(value, self)}
    

class DisplayModes(IntEnum):
    IS_SET_DM_DIB = 1
    IS_SET_DM_DIRECT3D = 4
    IS_SET_DM_OPENGL = 8
    IS_SET_DM_MONO = 0x800
    IS_SET_DM_BAYER = 0x1000
    IS_SET_DM_YCBCR = 0x4000
