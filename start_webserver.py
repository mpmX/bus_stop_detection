import os
import SimpleHTTPServer
import SocketServer

PORT = 8000
os.chdir('map')
handler = SimpleHTTPServer.SimpleHTTPRequestHandler
httpd = SocketServer.TCPServer(("", PORT), handler)
print "serving at port", PORT
httpd.serve_forever()