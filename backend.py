### Backend for weather sensing stuff
#
#   * Runs a webserver that can be exposed to the Internet via reverse proxy, which
#     accepts POST requests from the ESP32 to report temperature + humidity data
#       * authenticated with some secret, a command-line option to this program perhpas
#         logs all requests, and requests are all nondestructive + time limited, so
#         security breaches are not really a big deal
#       * maybe reject IPs not known to be associated with the Claremont Colleges, but 
#         that could be overkill
#   * Saves temperature+humidity data, with timestamps, to a SQLite database file (commit to Git?)
#   * Generates plots of temperature, humidity, and Heat Index over the last 24 hours
#   * Generates a webpage with aforementioned plots and 24-hour and 168-hour (weekly) maximum/minimum temperature
#       * I'm not sure yet if this should be a separate HTML file, or just part of the web server this serves
#
# I referenced Google/DuckDuckGo, the Python API docs, and GitHub Copilot while writing this
#

import argparse
import time
import sqlite3
from http.server import *

parser = argparse.ArgumentParser(
    prog='backend.py',
    description="Runs webserver to handle backend of Annika and Juha's temp/humidity sensor scheme",
)
parser.add_argument('--secret', help='Secret key for authentication that requests must have. Do not share!', required=True)

args = parser.parse_args()
print(args)

db = sqlite3.connect('weather_data.db')

DB_INITIALIZATION_SQL = '''
-- Database schema
CREATE TABLE IF NOT EXISTS weather_data (
    timestamp INTEGER NOT NULL, -- Unix timestamp from Python time.time()
    humidity INTEGER NOT NULL,  -- Relative humidity as a percentage
    temperature REAL NOT NULL   -- Temperature in degrees Celsius
);
'''

db.cursor().executescript(DB_INITIALIZATION_SQL).close() 
db.commit()

# Our own class extending BaseHTTPRequestHandler to handle POST requests
class Server(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'Weather sensing backend. Go away')
    
    def do_POST(self):
        # Check for secret key in headers
        if self.headers.get('X-Secret-Key') != args.secret :
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b'Forbidden')
            return

        # Read the content length and read the data
        humidity = self.headers.get('X-Humidity')
        temperature = self.headers.get('X-Temperature')
        if humidity is None or temperature is None:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Bad Request: Missing humidity or temperature headers')
            return
        humidity = float(humidity)
        temperature = float(temperature)
        timestamp = time.time()

        cursor = db.cursor()
        cursor.execute('INSERT INTO weather_data (timestamp, temperature, humidity) VALUES (?, ?, ?)', (timestamp, temperature, humidity))
        cursor.close()
        db.commit()

        return self.send_response(200)


# From Python docs
def run(server_class=HTTPServer, handler_class=Server):
    server_address = ('', 8087)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()

run()