import ssl 
import logging
from daqpy.server import HTTPServer
from ocean_optics_spectrometer import OceanOpticsSpectrometer

if __name__ == "__main__":
    # You need to create a certificate on your own 
    ssl_context = ssl.SSLContext(protocol = ssl.PROTOCOL_TLS)
    ssl_context.load_cert_chain('assets\\security\\certificate.pem',
                        keyfile = 'assets\\security\\key.pem')

    H = HTTPServer(consumers=['spectrometer/ocean-optics/USB2000-plus'], port=8083, ssl_context=ssl_context, 
                      log_level=logging.DEBUG)  
    H.start(block=False)

    O = OceanOpticsSpectrometer(
        instance_name='spectrometer/ocean-optics/USB2000-plus',
        serial_number='USB2+H15897',
        log_level=logging.DEBUG,
        trigger_mode=0
    )
    O.run()