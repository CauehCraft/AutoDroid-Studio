import http.server
import socketserver
import os

PORT = 8013
DIRECTORY = "debug_site"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

if __name__ == "__main__":
    # Ensure directory exists
    if not os.path.exists(DIRECTORY):
        os.makedirs(DIRECTORY)
        
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving at port {PORT}")
        print(f"Open http://localhost:{PORT} on your device (after adb reverse)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
