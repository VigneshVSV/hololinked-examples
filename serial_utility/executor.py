import logging
from daqpy.server import HTTPServer
from serial_utility import SerialCommunication

if __name__ == '__main__':
    H = HTTPServer(consumers = ['serial-communication/system-util', 'system-serial-util-loop'], 
                   subscription = "http://localhost:8080", port = 8081, log_level = logging.DEBUG) # ssl_context = ssl_context)
    H.start()

    S = SerialCommunication(instance_name='serial-communication/system-util')
    S.run() 

