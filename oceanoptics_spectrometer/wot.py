import datetime
from enum import Enum
import threading
from seabreeze.spectrometers import Spectrometer 

from hololinked.wot import Thing
from hololinked.wot.actions import action
from hololinked.wot.properties import String, ClassSelector, Integer, Number, Selector

from .data import Intensity


class OceanOpticsSpectrometer(Thing):
    """
    Connect to OceanOptics spectrometers using seabreeze library by specifying serial number. 
    For supported spectrometers visit : <a href="https://python-seabreeze.readthedocs.io/en/latest/">Seabreeze Pypi</a>.
    Using start_acquisition() method along with spectrum parameter to view live graph. Using start_acquisition_once()
    to measure spectrum once. 
    """

    states = Enum('states', 'DISCONNECTED ON FAULT MEASURING ALARM')

    serial_number = String(default=None, allow_None=True, URL_path='/serial-number', 
                            doc="serial number of the spectrometer to connect/or connected")

    model = String(default=None, URL_path='/model', allow_None=True, 
                            doc="model of the connected spectrometer")
    
    wavelengths = ClassSelector(default=None, allow_None=True, class_=(list,), 
            URL_path='/supported-wavelengths', doc="wavelength bins of measurement")

    pixel_count = Integer(default=None, allow_None=True, URL_path='/pixel-count', 
                doc="number of points in wavelength")
    
    last_intensity = ClassSelector(default=None, allow_None=True, class_=Intensity, 
            URL_path='/intensity', doc="last measurement intensity (in arbitrary units)") # type: ignore
    
    integration_time_millisec = Number(default=1000, bounds=(0.001, None), crop_to_bounds=True, 
                            URL_path='/integration-time/milli-seconds', 
                            doc="integration time of measurement in milliseconds")
     
    trigger_mode = Selector(objects=[0,1,2,3,4], default=0, 
                        URL_path='/trigger-mode', 
                        doc="""0 = normal/free running, 1 = Software trigger, 2 = Ext. Trigger Level,
                         3 = Ext. Trigger Synchro/ Shutter mode, 4 = Ext. Trigger Edge""")
    
    def __init__(self, serial_number = None, **kwargs):
        super().__init__(serial_number=serial_number, **kwargs)
        if serial_number is not None:
            self.connect()
        self._acquisition_thread = None 
        self._running = False
        self.intensity_measurement_event = Event(name='intensity-measurement-event', URL_path='/intensity/measurement-event')
     
    @action(URL_path='/connect')
    def connect(self, trigger_mode = None, integration_time = None):
        self.device = Spectrometer.from_first_available()# from_serial_number(self.serial_number) 
        self.state_machine.current_state = self.states.ON
        self.wavelengths = self.device.wavelengths().tolist()
        self.model = self.device.model
        self.pixel_count = self.device.pixels
        if trigger_mode is not None:
            self.trigger_mode = trigger_mode
        else:
            self.trigger_mode = self.trigger_mode
            # Will set default value of parameter
        if integration_time is not None:
            self.integration_time = integration_time
        else:
            self.integration_time = self.integration_time_millisec
            # Will set default value of parameter
        self.logger.debug(f"opened device with serial number {self.serial_number} with model {self.model}")
       
    @action(URL_path='/disconnect')
    def disconnect(self):
        self.device.close()
        self.state_machine.current_state = self.states.DISCONNECTED
        
    @trigger_mode.setter 
    def apply_trigger_mode(self, value):
        self.device.trigger_mode(value)
        self._trigger_mode = value 
        
    @trigger_mode.getter 
    def get_trigger_mode(self):
        try:
            return self._trigger_mode
        except:
            return self.parameters["trigger_mode"].default 
        
    @integration_time_millisec.setter 
    def apply_integration_time(self, value):
        self.device.integration_time_micros(int(value*1000))
        self._integration_time_ms = int(value) 
        self._integration_time_us = int(value)*1000

    @integration_time_millisec.getter 
    def get_integration_time(self):
        try:
            return self._integration_time_ms
        except:
            return self.parameters["integration_time_millisec"].default 

    @action(URL_path='/integration-time', http_method='PATCH')
    def set_intregation_time_bounds(self, value):
        if not isinstance(value, list) and len(value) == 2:
            raise TypeError("Specify integration time bounds as a list of two values [lower bound, higher bound]")
        if not isinstance(value[0], (type(None), (int, float))):
            raise TypeError("lower bound of integration type not a number or None")
        if not isinstance(value[1], (type(None), (int, float))):
            raise TypeError("higher bound of integration type not a number or None")                                          
        self.parameters["integration_time"].bounds = value

    @action(URL_path='/acquisition/start', http_method='POST')
    def start_acquisition(self):
        self.stop_acquisition() # Just a shield 
        self._acquisition_thread = threading.Thread(target=self.measure) 
        self._acquisition_thread.start()

    @action(URL_path='/acquisition/stop', http_method='POST')
    def stop_acquisition(self):
        if self._acquisition_thread is not None:
            self.logger.debug(f"stopping acquisition thread with thread-ID {self._acquisition_thread.ident}")
            self._running = False # break infinite loop
            # Reduce the measurement that will proceed in new trigger mode to 1ms
            self.device.integration_time_micros(1000)       
            # Change Trigger Mode if anything else other than 0, which will cause for the measurement loop to block permanently 
            self.device.trigger_mode(0)                    
            self._acquisition_thread.join()
            self._acquisition_thread = None 
            # re-apply old values
            self.trigger_mode = self.trigger_mode
            self.integration_time_millisec = self.integration_time_millisec 
        
    def measure(self, max_count = None):
        try:
            self._running = True
            self.state_machine.current_state = self.states.MEASURING
            self.logger.info(f'starting continuous acquisition loop with trigger mode {self.trigger_mode} & integration time {self.integration_time_millisec} in thread with ID {threading.get_ident()}')
            loop = 0
            while self._running:
                if max_count is not None and loop >= max_count:
                    break 
                try:
                    # Following is a blocking command - self.spec.intensities
                    self.logger.debug(f'starting measurement count {loop+1}')
                    if self.background_correction == 'AUTO':
                        _current_intensity = self.device.intensities(
                                                            correct_dark_counts=True,
                                                            correct_nonlinearity=self.nonlinearity_correction
                                                        )
                    else:
                        _current_intensity = self.device.intensities(
                                                            correct_dark_counts=False,
                                                            correct_nonlinearity=self.nonlinearity_correction 
                                                        )
                        
                    if self.background_correction == 'CUSTOM':
                        if self.custom_background_intensity is None:
                            self.logger.warn('no background correction possible')
                            self.state_machine.set_state(self.states.ALARM)
                        else:
                            _current_intensity = _current_intensity - self.custom_background_intensity

                    timestamp = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
                    self.logger.debug(f'measurement taken at {timestamp} - measurement count {loop+1}')

                    if self._running:
                        # To stop the acquisition in hardware trigger mode, we set running to False in stop_acquisition() 
                        # and then change the trigger mode for self.spec.intensities to unblock. This exits this 
                        # infintie loop. Therefore, to know, whether self.spec.intensities finished, whether due to trigger 
                        # mode or due to actual completion of measurement, we check again if self._running is True. 
                        if any(_current_intensity[i] > 0 for i in range(len(_current_intensity))):   
                            self.last_intensity = Intensity(
                                value=_current_intensity, 
                                timestamp=timestamp
                            )
                            self.intensity_measurement_event.push(self.last_intensity)
                            self.state_machine.current_state = self.states.MEASURING
                        else:
                            self.logger.warn('trigger delayed or no trigger or erroneous data - completely black')
                            self.state_machine.current_state = self.states.ALARM
                    loop += 1
                except Exception as ex:
                    self.logger.error(f'error during acquisition : {str(ex)}')
                    self.state_machine.current_state = self.states.FAULT
            
            if self.state_machine.current_state not in [self.states.FAULT, self.states.ALARM]:        
                self.state_machine.current_state = self.states.ON
            self.logger.info("ending continuous acquisition") 
            self._running = False 
        except Exception as ex:
            self.logger.error(f"error while starting acquisition {str(ex)}")
            self.state_machine.current_state = self.states.FAULT


if __name__ == '__main__':
    PropertyDes