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
import datetime 
import base64

from http.server import *
from matplotlib import pyplot as plt

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

def heat_index(temperature_C, RH):
    # COmpute heat index in degrees Celsius from temperature in degrees Celsius and relative humidity in percent
    # Formula from USA National Weather Service: https://www.weather.gov/ama/heatindex
    T = temperature_C * 9/5 + 32
    hi_F = -42.379 + (2.04901523*T) + (10.14333127*RH) - (.22475541*T*RH) - (.00683783*T*T) - (.05481717*RH*RH) + (.00122874*T*T*RH) + (.00085282*T*RH*RH) - (.00000199*T*T*RH*RH)
    return (hi_F - 32) * (5/9)

HIGH = -274
HIGHHI = -274
LOW = -274
LOWHI = -274

LAST_TIMESTAMP = 0

MIN_INTERVAL = 60 # no more than one POST request every 60 seconds

def update_plots():
    global HIGH, LOW, HIGHHI, LOWHI
    # Regenerates the plots of temperature, humidity, and heat index over the last 24 hours
    cursor = db.cursor()
    # Get the last 24 hours of data
    cursor.execute('SELECT timestamp, temperature, humidity FROM weather_data WHERE timestamp >= ?', (time.time() - 24*60*60,))
    data = cursor.fetchall()
    cursor.close()

    times = [datetime.date.fromtimestamp(float(x[0])) for x in data]
    temperatures = [float(x[1]) for x in data]
    humidities = [float(x[2]) for x in data]
    heat_indices = [heat_index(t, h) for t, h in zip(temperatures, humidities)]

    HIGH = max(temperatures) if temperatures else None
    LOW = min(temperatures) if temperatures else None
    HIGHHI = max(heat_indices) if heat_indices else None
    LOWHI = min(heat_indices) if heat_indices else None

    fig, ax = plt.subplots()
    ax.plot(times, temperatures, label='Temperature (C)')
    ax.plot(times, heat_indices, label='Heat Index (C)')
    ax.set_xlabel('Time')
    ax.set_ylabel('degrees Celsius')
    # ax.set_xlim(datetime.date.fromtimestamp(time.time() - 24*60*60), datetime.date.fromtimestamp(time.time()))
    ax.legend()
    print(times, temperatures, humidities, heat_indices)
    plt.savefig('plots/temp_last_24_hours.png')

    # Plot humidity
    fig, ax = plt.subplots()
    ax.plot(times, humidities, label='Humidity (%)')
    ax.set_xlabel('Time')
    ax.set_ylabel('Relative Humidity (%)')
    ax.legend()
    plt.savefig('plots/humidity_last_24_hours.png')
    print(data)

update_plots()

DEFAULT_HTML = """
<!DOCTYPE html>
<html>
<body>
    Today's High: $HIGH$&#176;C / $HIGHF$&#176;F<br>
    Today's High Heat Index: $HIGHHI$&#176;C / $HIGHHIF$&#176;F<br>
    Today's Low: $LOW$&#176;C / $LOWF$&#176;F<br>
    Today's Low Heat Index: $LOWHI$&#176;C / $LOWHIF$&#176;F<br>
    <img src="data:image/png;base64,$B64TEMP$" alt="Temperature (C)">
    <img src="data:image/png;base64,$B64HUM$" alt="Humidity (%)">
</body>
</html>
"""

def c_to_f(c):
    return c * 9/5 + 32
def f_to_c(f):
    return (f - 32) * 5/9
def fmt_decimal(d):
    return str(round(d, 1))

# Our own class extending BaseHTTPRequestHandler to handle POST requests
class Server(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        # open humidity/temp PNGs and encode them as base64 to embed in HTML
        temp_png = open('plots/temp_last_24_hours.png', 'rb').read()
        hum_png = open('plots/humidity_last_24_hours.png', 'rb').read()
        b64temp = base64.b64encode(temp_png).decode('utf-8')
        b64hum = base64.b64encode(hum_png).decode('utf-8')

        html = DEFAULT_HTML.replace('$B64TEMP$', b64temp).replace('$B64HUM$', b64hum)
        html = html.replace('$HIGH$', fmt_decimal(HIGH)).replace('$LOW$', fmt_decimal(LOW)).replace('$HIGHHI$', fmt_decimal(HIGHHI)).replace('$LOWHI$', fmt_decimal(LOWHI))
        html = html.replace('$HIGHF$', fmt_decimal(c_to_f(HIGH))).replace('$LOWF$', fmt_decimal(c_to_f(LOW))).replace('$HIGHHIF$', fmt_decimal(c_to_f(HIGHHI))).replace('$LOWHIF$', fmt_decimal(c_to_f(LOWHI)))
        self.wfile.write(html.encode('utf-8'))
    def do_POST(self):
        global LAST_TIMESTAMP
        
        timestamp = time.time()

        if (timestamp - LAST_TIMESTAMP) < MIN_INTERVAL:
            self.send_response(429)
            self.end_headers()
            self.wfile.write(b'Too Many Requests')
            return

        # Check for secret key in headers
        if self.headers.get('Authorization') != args.secret :
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

        cursor = db.cursor()
        cursor.execute('INSERT INTO weather_data (timestamp, temperature, humidity) VALUES (?, ?, ?)', (timestamp, temperature, humidity))
        cursor.close()
        db.commit()

        update_plots()

        return self.send_response(200)


# From Python docs
def run(server_class=HTTPServer, handler_class=Server):
    server_address = ('', 8087)
    httpd = server_class(server_address, handler_class)
    httpd.serve_forever()

run()
