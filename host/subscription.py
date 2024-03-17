from hololinked.server import HTTPServer

H = HTTPServer([], port=8082, host="https://localhost:8081")
H.listen()