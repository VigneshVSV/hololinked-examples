from hololinked.server import create_primary_host
from pathlib import Path
import os
from tornado import ioloop
import ssl

ssl_context = ssl.SSLContext(protocol = ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain(
    str(Path(os.path.dirname(__file__)).parent) + '\\assets\\security\\certificate.pem',
    keyfile = str(Path(os.path.dirname(__file__)).parent) + '\\assets\\security\\key.pem')

server = create_primary_host(str(Path(os.path.dirname(__file__)).parent) + "\\assets\\db_config.json", 
                            ssl_context=ssl_context)
server.listen(8080)
event_loop = ioloop.IOLoop.current()
print("starting server")
event_loop.start()