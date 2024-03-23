import ssl 
import logging
from multiprocessing import Process
from hololinked.server import HTTPServer
from device import OceanOpticsSpectrometer

def start_http_server():
    ssl_context = ssl.SSLContext(protocol = ssl.PROTOCOL_TLS)
    ssl_context.load_cert_chain('assets\\security\\certificate.pem',
                        keyfile = 'assets\\security\\key.pem')

    H = HTTPServer(['spectrometer/ocean-optics/USB2000-plus'], port=8083, ssl_context=ssl_context, 
                      log_level=logging.DEBUG)  
    H.listen()


if __name__ == "__main__":
    # You need to create a certificate on your own 
    P = Process(target=start_http_server)
    P.start()

    O = OceanOpticsSpectrometer(
        instance_name='spectrometer/ocean-optics/USB2000-plus',
        serial_number='USB2+H15897',
        log_level=logging.DEBUG,
        rpc_serializer='pickle',
        # trigger_mode=0
    )
    O.run()