/// Code to run on ESP32C3 microcontroller to read temperature and humidity from a DHT11 sensor and send it to a backend server.
//
// Connects via Wi-Fi to internet to make POST request to https://weather.worldbrightening.net/
// (or other backend server) with temperature and humidity data as headers.
//
// Meant to run on a Xiao ESP32C3 from Seeed Studio.
//
// Assumes the DHT11 is connected to pin 2.


#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT11.h>

#define DHT11_PIN 2
DHT11 dht(2);

// Change these to your Wi-Fi credentials!
// (And don't leak them if there is really a password.)
//
// TODO: check if this works to connect to passwordless network
const char* SSID = "Claremont-Guest"; 
const char* PASSWORD = "";
const char* BACKEND_URL = "https://weather.worldbrightening.net/";

// Connects to Wi-Fi, reads sensor, and reports data.
void report_cycle() {

    WiFi.begin(SSID, PASSWORD);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("Connected to Wi-Fi!");

    float temperature = dht.readTemperature();
    float humidity = dht.readHumidity();

    // POST data
    // see https://randomnerdtutorials.com/esp32-http-get-post-arduino/#http-post
    WiFiClient client;
    HTTPClient http;
    http.begin(client, BACKEND_URL);
    http.addHeader("Authorization", "YOUR_SECRET_KEY"); // Replace with your actual secret key
    http.addHeader("X-Temperature", String(temperature));
    http.addHeader("X-Humidity", String(humidity));
    int httpResponseCode = http.POST("");

    if (httpResponseCode > 0) {
        String response = http.getString();
        Serial.println(httpResponseCode);
        Serial.println(response);
    } else {
        Serial.print("Error on sending POST: ");
        Serial.println(httpResponseCode);
    }
    http.end();
}

// Setup runs again after waking from sleep, so we odn't need to use loop()
void setup() {
    Serial.begin(9600);

    report_cycle(); 

    // Go to sleep for 5 minutes 
    esp_sleep_enable_timer_wakeup(5 * 60 * 1000000); // microseconds
    esp_deep_sleep_start();
}

void loop() {
    
}
