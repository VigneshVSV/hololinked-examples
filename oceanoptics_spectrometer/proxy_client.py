from hololinked.client import ObjectProxy
from device import OceanOpticsSpectrometer

spectrometer = ObjectProxy('spectrometer/ocean-optics/USB2000-plus', 
                serializer='pickle', protocol='IPC') # type: OceanOpticsSpectrometer
spectrometer.log_to_console(data="Something")
spectrometer.integration_time_millisec = 100
print(spectrometer.integration_time_millisec)
spectrometer.integration_time_millisec = 2000
print(spectrometer.integration_time_millisec)


