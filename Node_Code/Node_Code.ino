#include <ESP8266WiFi.h>
#include <PubSubClient.h>

// WiFi Configuration
const char* ssid = "Hashem's Phone";
const char* password = "had207@2";

// MQTT Configuration
const char* mqtt_server = "broker.emqx.io";
const char* topic_data = "hash/waterstatus";
const char* topic_command = "hash/pumpcontrol";

// Pin Definitions
const int trigPin = 5;   // D1 (Ultrasonic Trig)
const int echoPin = 4;   // D2 (Ultrasonic Echo)
const int ledPin = 2;    // D4 (WiFi Status LED, Active LOW)
const int flowPin = 14;  // D5 (Flow Sensor Pulse Input)
const int relayPin = 12; // D6 (Pump Control Relay)

// Flow Sensor Variables
volatile unsigned long pulseCount = 0;
float flowRate = 0.0;
const float calibrationFactor = 5.5; 

// Network Clients
WiFiClient espClient;
PubSubClient client(espClient);

// Timing Variables
unsigned long previousMillis = 0;
const long interval = 1000; 

unsigned long previousLedMillis = 0;
const long ledInterval = 300; 

unsigned long lastReconnectAttempt = 0; // For non-blocking MQTT reconnect

// Hardware Interrupt for Flow Sensor
void ICACHE_RAM_ATTR pulseCounter() {
  pulseCount++;
}

// MQTT Callback (Optimized: Zero dynamic memory / No String objects)
void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Command received on: ");
  Serial.println(topic);
  
  // Verify the payload directly from the byte array for maximum speed and memory safety
  if (length >= 2 && payload[0] == 'O' && payload[1] == 'N') {
    digitalWrite(relayPin, HIGH); // Adjust HIGH/LOW based on your Relay module logic
    Serial.println("Action: Pump turned ON");
  } 
  else if (length >= 3 && payload[0] == 'O' && payload[1] == 'F' && payload[2] == 'F') {
    digitalWrite(relayPin, LOW);
    Serial.println("Action: Pump turned OFF");
  }
}

void setup_wifi() {
  Serial.print("Connecting to WiFi");
  WiFi.begin(ssid, password);
  
  // Delay here is safe because it only runs once during boot (Blocking is acceptable in setup)
  while (WiFi.status() != WL_CONNECTED) {
    digitalWrite(ledPin, !digitalRead(ledPin)); 
    delay(500);
    Serial.print(".");
  }
  digitalWrite(ledPin, LOW); 
  Serial.println("\nWiFi connected");
}

// Non-blocking MQTT reconnect function
boolean reconnect() {
  // Generate a random Client ID using char array (No String)
  char clientId[20];
  snprintf(clientId, sizeof(clientId), "ESP8266-%04X", random(0xffff));
  
  if (client.connect(clientId)) {
    Serial.println("MQTT reconnected");
    client.subscribe(topic_command); // Resubscribe to pump commands
    return true;
  }
  return false;
}

void setup() {
  Serial.begin(9300); 
  
  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  pinMode(ledPin, OUTPUT);
  
  pinMode(relayPin, OUTPUT);
  digitalWrite(relayPin, LOW); // Ensure pump is OFF on boot
  
  pinMode(flowPin, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(flowPin), pulseCounter, FALLING);
  
  setup_wifi();
  
  client.setServer(mqtt_server, 1883);
  client.setCallback(callback);
}

void loop() {
  unsigned long currentMillis = millis();

  // 1. Non-blocking WiFi status LED
  if (WiFi.status() != WL_CONNECTED) {
    if (currentMillis - previousLedMillis >= ledInterval) {
      previousLedMillis = currentMillis;
      digitalWrite(ledPin, !digitalRead(ledPin));
    }
  } else {
    digitalWrite(ledPin, LOW); 
  }

  // 2. Non-blocking MQTT Reconnect mechanism
  if (!client.connected()) {
    if (currentMillis - lastReconnectAttempt > 5000) {
      lastReconnectAttempt = currentMillis;
      if (reconnect()) {
        lastReconnectAttempt = 0; // Reset on success
      }
    }
  } else {
    client.loop(); // Process incoming messages only if connected
  }

  // 3. Sensor Reading & Publishing (Runs independently of connection status)
  if (currentMillis - previousMillis >= interval) {
    float elapsedTime = (currentMillis - previousMillis) / 1000.0;
    previousMillis = currentMillis; 
    
    // Read Flow Rate safely
    detachInterrupt(digitalPinToInterrupt(flowPin));
    float pulseFreq = pulseCount / elapsedTime;
    flowRate = pulseFreq / calibrationFactor; 
    pulseCount = 0;
    attachInterrupt(digitalPinToInterrupt(flowPin), pulseCounter, FALLING);

    // Read Ultrasonic Distance
    digitalWrite(trigPin, LOW);
    delayMicroseconds(2);
    digitalWrite(trigPin, HIGH);
    delayMicroseconds(10);
    digitalWrite(trigPin, LOW);

    long duration = pulseIn(echoPin, HIGH, 30000);
    float distance = 0.0;
    if (duration > 0) {
      distance = duration * 0.034 / 2;
    }

    // Construct JSON using char array (Prevents Heap Fragmentation)
    char jsonPayload[64];
    snprintf(jsonPayload, sizeof(jsonPayload), "{\"distance\":%.2f, \"flowRate\":%.2f}", distance, flowRate);

    Serial.print("Publishing: ");
    Serial.println(jsonPayload);

    // Publish if connected
    if (client.connected()) {
      client.publish(topic_data, jsonPayload);
    }
  }
}