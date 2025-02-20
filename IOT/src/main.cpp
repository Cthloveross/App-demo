#include "ECE140_WIFI.h"
#include "ECE140_MQTT.h"
#include <Adafruit_BMP085.h>
#include <ArduinoJson.h>  // JSON formatting

// Initialize WiFi and MQTT objects
ECE140_WIFI wifi;
const char* clientId = "esp32-sensors";
const char* topicPrefix = "Eason/ece140/sensors";
ECE140_MQTT mqtt(clientId, topicPrefix);  // ✅ Correct Initialization

// WiFi credentials
const char* wifiSsid = "UCSD-PROTECTED";
const char* ucsdUsername = "tic001@ucsd.edu";  
const char* ucsdPassword = "Cth770998800";  

// Create BMP085 sensor instance
Adafruit_BMP085 bmp;

void setup() {
    Serial.begin(115200);
    Serial.println("\n===== ESP32 IoT Setup =====");

    // **Connect to WiFi**
    Serial.print("Connecting to UCSD-PROTECTED WiFi...");
    wifi.connectToWPAEnterprise(wifiSsid, ucsdUsername, ucsdPassword);

    // **Connect to MQTT Broker**
    Serial.print("Connecting to MQTT broker...");
    if (mqtt.connectToBroker()) {  // ✅ Corrected function call
        Serial.println(" ✅ Connected to MQTT!");
        mqtt.publishMessage("/status", "ESP32 Connected to MQTT!");  
    } else {
        Serial.println(" ❌ Failed to connect to MQTT!");
        return;
    }

    // **Initialize BMP085 Sensor**
    if (!bmp.begin()) {
        Serial.println("❌ ERROR: BMP085 sensor not found! Check wiring.");
        while (1); // Halt execution
    }
}

void loop() {
    mqtt.loop();  // Keep MQTT client running

    static unsigned long lastPublishTime = 0;
    unsigned long currentTime = millis();

    if (currentTime - lastPublishTime >= 5000) {  // Send data every 5 seconds
        lastPublishTime = currentTime;

        // **Read Sensor Data**
        float temperature = bmp.readTemperature();
        int pressure = bmp.readPressure();

        // **Format JSON Data**
        StaticJsonDocument<200> jsonDoc;
        jsonDoc["temperature"] = temperature;
        jsonDoc["pressure"] = pressure;
        
        String message;
        serializeJson(jsonDoc, message);

        // **Print & Publish Data**
        Serial.println("\n==== Sensor Readings ====");
        Serial.println("Temperature: " + String(temperature) + " °C");
        Serial.println("Pressure: " + String(pressure) + " Pa");

        mqtt.publishMessage("readings", message);
    }
}
