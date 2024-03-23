import logging
import serial as PS
from enum import StrEnum
from threading import RLock

from hololinked.server import StateMachine, HTTPServer
from hololinked.wot import Thing 
from hololinked.wot.actions import action
from hololinked.wot.properties import Number, Selector, String, Selector, Boolean



class SerialCommunication(Thing):

    read_timeout = Number(default=0.1, bounds=(0,1000), allow_None=True, 
                        doc="maximum time to wait until read is complete, set None(null) for indefinite, unit - seconds.", 
                        db_persist=True, URL_path='/read-timeout')
    write_timeout = Number(default=100, bounds=(0,1000), allow_None=True,
                        doc="maximum time to wait until write is complete, set None(null) for indefinite, unit - seconds.", 
                        db_persist=True, URL_path='/write-timeout')
    baud_rate = Selector(objects=[9600, 14400, 19200, 38400, 57600, 115200,
                            128000, 256000, 230400, 460800, 500000, 576000, 921600, 1000000, 1152000, 
                            1500000, 2000000, 2500000, 3000000, 3500000, 4000000], default=9600, 
                    doc="allowed values are 9600, 14400, 19200, 38400, 57600, 115200, 128000, 256000...until 4000000",  
                    db_persist=True, URL_path='/baud-rate')
    comport = String(doc="depending on operating system. e.g. /dev/ttyUSB0 on GNU/Linux or COM3 on Windows",
                    default='COM', db_persist=True, URL_path='/comport')
    byte_size = Selector(default=PS.EIGHTBITS, objects=[PS.EIGHTBITS, PS.SEVENBITS, PS.SIXBITS, PS.FIVEBITS], 
                        doc="Number of data bits. Possible values: FIVEBITS, SIXBITS, SEVENBITS, EIGHTBITS", 
                        db_persist=True, URL_path='/byte-size')
    parity = Selector(default=PS.PARITY_NONE, objects=[PS.PARITY_NONE, PS.PARITY_EVEN, PS.PARITY_ODD, PS.PARITY_MARK,
                PS.PARITY_SPACE], 
                doc=f"""partiy, Possible values are none(int value {PS.PARITY_NONE}), even({PS.PARITY_EVEN}), odd({PS.PARITY_ODD}), 
                    mark({PS.PARITY_MARK})""", db_persist=True, URL_path='/parity')
    stopbits = Selector(default=PS.STOPBITS_ONE, objects=[PS.STOPBITS_ONE, PS.STOPBITS_TWO, PS.STOPBITS_ONE_POINT_FIVE],
                    doc="stopbits", db_persist=True, URL_path='/connection/stopbits')
    xonxoff = Boolean( default=False, doc="xonoff", db_persist=True, URL_path='/xonxoff')

    def __init__(self, COMPORT = "COM100", read_timeout=0.1, write_timeout=0.1, baud_rate=9600, byte_size=PS.EIGHTBITS, 
                parity=PS.PARITY_NONE, stopbits=PS.STOPBITS_ONE, xonxoff=False, **kwargs):
        super().__init__(
            comport=COMPORT,
            read_timeout=read_timeout,
            write_timeout=write_timeout, 
            baud_rate=baud_rate, 
            byte_size=byte_size,
            parity=parity,
            stopbits=stopbits,
            xonxoff=xonxoff      
        )
        self._r_lock = RLock()

    @comport.getter # remote parameter with getter and setter
    def _get_comport(self): # type: ignore
        """
        fget of comport
        """
        return self._comport 

    @comport.setter
    def _set_comport(self, value):
        """
        fset of comport
        """
        assert isinstance(value, str) and value.startswith("COM"), "not a valid COMPORT"
        self._comport = value   
    
    @action(URL_path='/connect', http_method='POST') # RPC style HTTP endpoint, usually takes method name by default when unspecified 
    def connect(self):
        """
        connects to the serial port with given (defined) parameters.
        Returns None upon opening COM port, otherwise raises SerialException.
        """     
        self.logger.debug("Connecting to {} with baudrate : {}, read timeout : {}, bytesize : {}, stopbits : {}, xonxoff = {}, write timeout : {}".format( 
             self.comport, self.baud_rate, self.read_timeout, self.byte_size, self.stopbits, self.xonxoff, self.write_timeout))    
        self._device = PS.Serial(port=self.comport, baudrate=self.baud_rate, timeout=self.read_timeout, 
                bytesize=self.byte_size, stopbits=self.stopbits, xonxoff=self.xonxoff, 
                write_timeout=self.write_timeout)
        if self._device.is_open:      
            self.state_machine.set_state(self.states.ON)                      
           
    @action(URL_path='/disconnect', http_method='POST') # decorate with HTTP verb  
    def disconnect(self):
        """
        disconnects from port. 
        """           
        self._device.close()
        self.state_machine.set_state(self.states.DISCONNECTED)       
                
    @action(URL_path="/execute", http_method='POST')
    def execute_instruction(self, command : str, return_data_size : int = 0):
        """
        executes instruction given by the ASCII string parameter 'command'.
        If return data size is greater than 0, it reads the response and returns the response. 
        Return Data Size - in bytes - 1 ASCII character = 1 Byte.		
        """
        try:
            bytes_data = None
            command = command.encode(encoding='ascii', errors='strict') # type: ignore
            self.logger.debug("Issuing command {} to {}".format(command, self.comport)) 
            self._r_lock.acquire()
            self.state_machine.set_state(self.states.COMMUNICATING)
            self._device.reset_input_buffer()
            self._device.reset_output_buffer()
            self.logger.debug("number of bytes written : {}".format(self._device.write(command)))# type: ignore
            if(return_data_size > 0):
                bytes_data = self._device.read(return_data_size)            
                self._device.reset_input_buffer()
                self._device.reset_output_buffer()
                bytes_data = bytes_data.decode("ascii")
                self.logger.debug("received reply {} from {}".format(bytes_data, self.comport))
            self.state_machine.set_state(self.states.ON)    
            self._r_lock.release()
            return bytes_data # type: ignore
        except:
            raise 
        finally:
            try:
                if self._device.is_open:
                    self.state_machine.set_state(self.states.ON)    
                else:
                    self.state_machine.set_state(self.states.DISCONNECTED)
                self._r_lock.release()
            except:
                pass
      
    class states(StrEnum):
        DISCONNECTED = "DISCONNECTED"
        ON = "ON"
        COMMUNICATING = "COMMUNICATING"
        
    state_machine = StateMachine(
        states=states,
        initial_state=states.DISCONNECTED,
        ON=[execute_instruction, disconnect], 
        DISCONNECTED=[connect, read_timeout, write_timeout, xonxoff, byte_size, 
                    baud_rate, comport, parity, stopbits],
    )
   
        

def local_device_example():
    dev = SerialCommunication(instance_name='system-serial-utility', 
            log_level=logging.DEBUG, COMPORT='COM9', read_timeout=0.1, 
            write_timeout=0.1, xonxoff=False, baud_rate=115200)
    dev.connect()
    print(dev.execute_instruction("*VER", 100))
    dev.disconnect()


def remote_device_example():
    http_server = HTTPServer(consumers='system-serial-utitlity')
    http_server.start()

    dev = SerialCommunication(instance_name='system-serial-utility', 
                            COMPORT="COM6", read_timeout=0.1, write_timeout=0.1, 
                            baud_rate=115200), 
    dev.run()


if __name__ == "__main__":
    remote_device_example()
  