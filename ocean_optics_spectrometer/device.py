import threading
import datetime
import numpy
from enum import Enum
from seabreeze.spectrometers import Spectrometer

from hololinked.server import RemoteObject, StateMachine, put, post, get, Event, patch, remote_method
from hololinked.server.remote_parameters import (String, Integer, Number, Selector, ClassSelector, Integer, 
                        Boolean, TypedList, Selector)

from data import Intensity



class OceanOpticsSpectrometer(RemoteObject):
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
    
    integration_time_microsec = Integer(default=1000000, bounds=(1, None), crop_to_bounds=True, 
                            URL_path='/integration-time/micro-seconds', 
                            doc="integration time of measurement in microseconds")
    
    trigger_mode = Selector(objects=[0,1,2,3,4], default=0, 
                        URL_path='/trigger-mode', 
                        doc="""0 = normal/free running, 1 = Software trigger, 2 = Ext. Trigger Level,
                         3 = Ext. Trigger Synchro/ Shutter mode, 4 = Ext. Trigger Edge""")
    
    background_correction = Selector(objects=['AUTO', 'CUSTOM', None], default=None, allow_None=True, 
                        URL_path='/background-correction',
                        doc="set True for Seabreeze internal black level correction")
    
    nonlinearity_correction = Boolean(default=False, URL_path='/nonlinearity-correction')
    
    custom_background_intensity = TypedList(item_type=(float, int), 
                        URL_path='/background-correction/user-defined-intensity')

    
    def __init__(self, serial_number = None, **kwargs):
        super().__init__(serial_number=serial_number, **kwargs)
        if serial_number is not None:
            self.connect()
        self._acquisition_thread = None 
        self._running = False
        self.data_measured_event = Event(name='intensity-measurement-event', URL_path='/intensity/measurement-event')
        self.logger.debug(f"opened device with serial number {self.serial_number} with model {self.model}")
    
    @post('/connect')
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
       
    @post('/disconnect')
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
    def apply_integration_time_ms(self, value):
        self.device.integration_time_micros(int(value*1000))
        self._integration_time_ms = int(value) 
        self._integration_time_us = int(value)*1000

    @integration_time_millisec.getter 
    def get_integration_time_ms(self):
        try:
            return self._integration_time_ms
        except:
            return self.parameters["integration_time_millisec"].default 
    
    @integration_time_microsec.setter
    def apply_integration_time_us(self, value):
        self.device.integration_time_micros(value)
        self._integration_time_ms = value/1000
        self._integration_time_us = value

    @integration_time_microsec.getter
    def get_integration_time_us(self):
        try:
            return self._integration_time_us
        except:
            return self.parameters["integration_time_microsec"].default 
        
    @patch('/integration-time/bounds')
    def set_intregation_time_bounds(self, value):
        if not isinstance(value, list) and len(value) == 2:
            raise TypeError("Specify integration time bounds as a list of two values [lower bound, higher bound]")
        if not isinstance(value[0], (type(None), (int, float))):
            raise TypeError("lower bound of integration type not a number or None")
        if not isinstance(value[1], (type(None), (int, float))):
            raise TypeError("higher bound of integration type not a number or None")                                          
        self.parameters["integration_time"].bounds = value 

    @get('/acquisition/settings')
    def _get_acquisition_settings(self):
        return {
            'integration_time_milliseconds' : self.integration_time_millisec,
            'trigger_mode' : self.trigger_mode,
            'background_correction' : self.background_correction,
            'non_linearity_correction' : self.nonlinearity_correction
        }

    @remote_method('/acquisition/settings', http_method=['POST', 'PATCH'])
    def _set_acquisition_settings(self, **settings):
        assert settings.keys() in ['integration_time_millisec', 'integration_time_microsec',
                            'background_correction', 'nonlinearity_correction'], "not all supplied values are acquisition settings"
        for key, value in settings.items():
            setattr(self, key, value)
    
    @post('/acquisition/start')
    def start_acquisition(self):
        self.stop_acquisition() # Just a shield 
        self._acquisition_thread = threading.Thread(target=self.measure) 
        self._acquisition_thread.start()

    @post('/acquisition/stop')
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
                            self.data_measured_event.push(self.last_intensity)
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

    @post('/acquisition/single/start')
    def start_acquisition_single(self):
        self.stop_acquisition() # Just a shield 
        self._acquisition_thread = threading.Thread(target=self.measure, args=(1,)) 
        self._acquisition_thread.start()
        self.logger.info("data event will be pushed once acquisition is complete.")

    @post('/fault/reset')
    def reset_fault(self):
        self.state_machine.set_state(self.states.ON)
      
    state_machine = StateMachine(
        states=states,
        initial_state=states.DISCONNECTED,
        DISCONNECTED=[connect],
        ON=[start_acquisition, integration_time_millisec, integration_time_microsec, trigger_mode, 
            background_correction, nonlinearity_correction, disconnect],
        MEASURING=[stop_acquisition],
        FAULT=[stop_acquisition]
    )

    logger_remote_access = True

