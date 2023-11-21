import ssl
import logging
from daqpy.server import HTTPServer
from serial_utility import SerialCommunication


def start_http_server():
    ssl_context = ssl.SSLContext(protocol = ssl.PROTOCOL_TLS)
    ssl_context.load_cert_chain('assets\\security\\certificate.pem',
                        keyfile = 'assets\\security\\key.pem')

    H = HTTPServer(consumers=['serial-communication/system-util'], 
                   subscription="http://localhost:8080", port=8081, log_level=logging.DEBUG,  ssl_context=ssl_context)
    H.start()


if __name__ == '__main__':
  
    S = SerialCommunication(instance_name='serial-communication/system-util')
    S.run() 

