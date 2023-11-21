# adopted from IDS imaging python example - see license in license folder
import base64
import threading
import time
from pyueye import ueye
import numpy as np
import cv2
import sys
from enum import Enum

from daqpy.server import RemoteObject, RemoteParameter, post, StateMachine, Event
from daqpy.server.remote_parameters import Integer, String, Selector, Number
from daqpy.server.remote_parameter import Image

from .exceptions import ErrorCodes, UEyeError
from .data import ColorModes, DisplayModes

# Example in development - not complete & may not work

class UEyeCamera(RemoteObject):

    states = Enum('states', 'ON FAULT CONNECTION_ERROR CAPTURE DISCONNECTED ALARM')

    camera_id = Integer(default=0, bounds=(0,255), URL_path='/id')

    sensor_info = RemoteParameter(readonly=True, default=None, allow_None=True, URL_path='/sensor/info')

    camera_info = RemoteParameter(readonly=True, default=None, allow_None=True, URL_path='/info')

    error_codes = RemoteParameter(readonly=True, default=ErrorCodes.json(), URL_path='/error-codes',
                        class_member=True)
    
    status = String(URL_path='/status')

    image = Image(URL_path='/video')

   
    def __init__(self, camera_id : int, **kwargs):
        super().__init__(camera_id=camera_id, **kwargs)
        self._rectAOI = ueye.IS_RECT()
        self._image_memory = ueye.c_mem_p()
        self._mem_id = ueye.INT()
        self._pitch = ueye.INT()
        # self.image_event = Event('image')

    @post('/connect')
    def connect(self):
        self.device = ueye.HIDS(self.camera_id) 
        # Starts the driver and establishes the connection to the camera
        ret = ueye.is_InitCamera(self.device, None)
        if ret != ueye.IS_SUCCESS:
            self.state_machine.current_state = self.states.CONNECTION_ERROR
            raise UEyeError(ret, f"could not connect to camera with camera id {self.camera_id}")

        ret = ueye.is_ResetToDefault(self.device)
        if ret != ueye.IS_SUCCESS:
            raise UEyeError(ret, "could not reset cam to default settings")
        
        self._camera_info = ueye.CAMINFO()
        if ueye.is_GetCameraInfo(self.device, self._camera_info) != ueye.IS_SUCCESS:
            self.state_machine.current_state = self.states.ALARM
            self.status = 'could not fetch camera info'

        self._sensor_info = ueye.SENSORINFO()
        if ueye.is_GetSensorInfo(self.device, self._sensor_info) != ueye.IS_SUCCESS:
            self.state_machine.current_state = self.states.ALARM
            self.status = 'could not fetch sensor info'

        self.logger.debug(f"sensor info {self._sensor_info}")
        self.logger.debug(f"camera info {self._camera_info}")

        self.set_color_mode(1)
        self.set_display_mode(1)
        self.set_area_of_interest()
        self.set_frame_rate(1)
        self.set_exposure(3)
        self.state_machine.current_state = self.states.ON
        
        # MemID = ueye.int() 
        # pitch = ueye.INT()
        # nBitsPerPixel = ueye.INT(24)    #24: bits per pixel for color mode; take 8 bits per pixel for monochrome
        # channels = 3                    #3: channels for color mode(RGB); take 1 channel for monochrome
        # m_nColorMode =		# Y8/RGB16/RGB24/REG32
        # bytes_per_pixel = int(nBitsPerPixel / 8)

    @sensor_info.getter
    def get_sensor_info(self):
        return self._sensor_info
    
    @camera_info.getter
    def get_cam_info(self):
        return self._camera_info
    
    color_mode = Selector(objects=tuple(ColorModes.__members__.values()), default=ColorModes.IS_COLORMODE_MONOCHROME.value,
                        doc="color mode that will used on captured images")

    @color_mode.setter
    def set_color_mode(self, value):
        # Set the right color mode
        ret = ueye.is_SetColorMode(self.device, value)
        if ret != ueye.IS_SUCCESS:
            raise UEyeError(ret, 'could not set color mode')  

        n_bits_per_pixel = ueye.INT(24)
        sensor_color_mode = self._sensor_info.nColorMode.value
        if int.from_bytes(sensor_color_mode, byteorder='big') == ueye.IS_COLORMODE_BAYER:
            # setup the color depth to the current windows setting
            color_mode = ueye.INT()
            ueye.is_GetColorDepth(self.device, n_bits_per_pixel, color_mode)
          
        elif int.from_bytes(sensor_color_mode, byteorder='big') == ueye.IS_COLORMODE_CBYCRY:
            color_mode = ueye.IS_CM_BGRA8_PACKED
            n_bits_per_pixel = ueye.INT(32)
          
        elif int.from_bytes(sensor_color_mode, byteorder='big') == ueye.IS_COLORMODE_MONOCHROME:
            color_mode = ueye.IS_CM_MONO8
            n_bits_per_pixel = ueye.INT(8)
        else:
            # for monochrome camera models use Y8 mode
            color_mode = ueye.IS_CM_MONO8
            n_bits_per_pixel = ueye.INT(8)

        self._n_bits_per_pixel = n_bits_per_pixel
        self._color_mode = color_mode
        self._n_bytes_per_pixel = int(n_bits_per_pixel / 8)
      
        self.logger.info(f"color mode : {ColorModes(value).name}")
        self.logger.info(f"bits per pixel : {n_bits_per_pixel}")
        self.logger.info(f"bytes per pixel : {self._n_bytes_per_pixel}")
    

    bits_per_pixel = Integer(readonly=True, URL_path='/bits-per-pixel')
    @bits_per_pixel.getter
    def get_bits_per_pixel(self):
        return self._n_bits_per_pixel.value

    state_machine = StateMachine(
        states=states,
        initial_state=states.DISCONNECTED,
        CONNECTION_ERROR=[connect], 
        DISCONNECTED=[connect],
    )

    display_mode = Selector(objects=tuple(DisplayModes.__members__.values()), default=DisplayModes.IS_SET_DM_DIB.value,
                        doc="display mode that will set on the captured images")

    @display_mode.setter 
    def set_display_mode(self, value):
        ret = ueye.is_SetDisplayMode(self.device, value)
        if ret != ueye.IS_SUCCESS:
            raise UEyeError(ret, 'could not set color mode')  
        
    # area_of_interest = RemoteParameter()

    # @area_of_interest.setter
    def set_area_of_interest(self):
        ret = ueye.is_AOI(self.device, ueye.IS_AOI_IMAGE_GET_AOI, self._rectAOI, ueye.sizeof(self._rectAOI))
        if ret != ueye.IS_SUCCESS:
            raise UEyeError(ret, "could not set area of interest")

        self._aoi_width = self._rectAOI.s32Width
        self._aoi_height = self._rectAOI.s32Height

        ret = ueye.is_AllocImageMem(self.device, self._aoi_width, self._aoi_height, self._n_bits_per_pixel, 
                                            self._image_memory, self._mem_id)
        
        if ret != ueye.IS_SUCCESS:
            raise UEyeError(ret, "could not allocate image memory")
      
        ret = ueye.is_SetImageMem(self.device, self._image_memory, self._mem_id)
        if ret != ueye.IS_SUCCESS:
            raise UEyeError(ret, "could not set camera captured images to image memory")
     
    @post('/capture/video')
    def start_acquisition(self):
        # Activates the camera's live video mode (free run mode)
        ret = ueye.is_CaptureVideo(self.device, ueye.IS_DONT_WAIT)
        if ret != ueye.IS_SUCCESS:
            raise UEyeError(ret, "could not start camera acquisition")
        ret = ueye.is_InquireImageMem(self.device, self._image_memory, self._mem_id, self._aoi_width, 
                                    self._aoi_height, self._n_bits_per_pixel, self._pitch)
        if ret != ueye.IS_SUCCESS:
            raise UEyeError(ret, "could not enable image queue after acquisition start")
        self._capture = True
        self._acquisition_thread = threading.Thread(target=self.capture_loop)
        self._acquisition_thread.start()

    @post('/capture/video/stop')
    def stop_acquisition(self):
        self._capture = False

    def capture_loop(self):
        self.state_machine.set_state(self.states.CAPTURE)
        while self._capture:
            array = ueye.get_data(self._image_memory, self._aoi_width, self._aoi_height, self._n_bits_per_pixel, 
                                self._pitch, copy=False)
            frame = np.reshape(array, (self._aoi_height.value, self._aoi_width.value, self._n_bytes_per_pixel))
            # frame = cv2.resize(frame, (0,0), fx=0.5, fy=0.5)
            _, buffer = cv2.imencode('.jpg', frame)
            base64_image = base64.b64encode(buffer)
            self.image = base64_image
            self.logger.debug("captured image")
            time.sleep(1)
        self.state_machine.set_state(self.states.ON)

    @post('/capture/image')
    def capture_image(self):
        ret = ueye.is_CaptureVideo(self.device, ueye.IS_DONT_WAIT)
        if ret != ueye.IS_SUCCESS:
            raise UEyeError(ret, "could not start camera acquisition")
        ret = ueye.is_InquireImageMem(self.device, self._image_memory, self._mem_id, self._aoi_width, 
                                    self._aoi_height, self._n_bits_per_pixel, self._pitch)
        if ret != ueye.IS_SUCCESS:
            raise UEyeError(ret, "could not enable image queue after acquisition start")
        self.state_machine.set_state(self.states.CAPTURE)
        array = ueye.get_data(self._image_memory, self._aoi_width, self._aoi_height, self._n_bits_per_pixel, 
                            self._pitch, copy=False)
        frame = np.reshape(array, (self._aoi_height.value, self._aoi_width.value, self._n_bytes_per_pixel))
        # frame = cv2.resize(frame, (0,0), fx=0.5, fy=0.5)
        _, buffer = cv2.imencode('.jpg', frame)
        base64_image = base64.b64encode(buffer)
        self.image = base64_image
        self.state_machine.set_state(self.states.ON)

    frame_rate = Number(default=1, bounds=(0,30), inclusive_bounds=(False, True), URL_path='/frame-rate')

    @frame_rate.setter 
    def set_frame_rate(self, value):
        setFPS = ueye.double()
        ret = ueye.is_SetFrameRate(self.device, value,  setFPS)
        if ret != ueye.IS_SUCCESS:
            raise UEyeError(ret, "could not set frame rate")

    exposure = Number(default=1.0, URL_path='/exposure')
    @exposure.setter 
    def set_exposure(self, value):
        ret = ueye.is_Exposure(self.device, ueye.IS_EXPOSURE_CMD_SET_EXPOSURE, ueye.double(value), 8)
        if ret != ueye.IS_SUCCESS:
            raise UEyeError(ret, "could not set exposure")


    def __del__(self):
        ueye.is_FreeImageMem(self.device, self._image_memory, self._mem_id)
        ueye.is_ExitCamera(self.device)


