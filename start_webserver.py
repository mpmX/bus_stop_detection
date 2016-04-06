import SimpleHTTPServer
import SocketServer

PORT = 8000
handler = SimpleHTTPServer.SimpleHTTPRequestHandler
httpd = SocketServer.TCPServer(("", PORT), handler)
print "serving at port", PORT
httpd.serve_forever()