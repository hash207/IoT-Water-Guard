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
volatile uint32_t pulseCount = 0;
uint32_t previousPulseCount = 0;

float flowRate = 0.0f;

// G3/4 1–30 L/min sensor: Frequency = 4.5 × flow rate in L/min
const float calibrationFactor = 4.5f;

// Network Clients
WiFiClient espClient;
PubSubClient client(espClient);

// Timing Variables
unsigned long previousMillis = 0;
const long interval = 2000;  // Read and publish every 2 seconds

unsigned long previousLedMillis = 0;
const long ledInterval = 300;

unsigned long lastReconnectAttempt = 0;

// Flow-sensor interrupt
void ICACHE_RAM_ATTR pulseCounter() {
  pulseCount++;
}

// MQTT Callback
void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Command received on: ");
  Serial.println(topic);

  if (length >= 2 && payload[0] == 'O' && payload[1] == 'N') {
    digitalWrite(relayPin, HIGH);
    Serial.println("Action: Pump turned ON");
  }
  else if (length >= 3 &&
           payload[0] == 'O' &&
           payload[1] == 'F' &&
           payload[2] == 'F') {
    digitalWrite(relayPin, LOW);
    Serial.println("Action: Pump turned OFF");
  }
}

void setup_wifi() {
  Serial.print("Connecting to WiFi");
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    digitalWrite(ledPin, !digitalRead(ledPin));
    delay(500);
    Serial.print(".");
  }

  digitalWrite(ledPin, LOW);
  Serial.println("\nWiFi connected");
}

// Non-blocking MQTT reconnect
boolean reconnect() {
  char clientId[20];
  snprintf(clientId, sizeof(clientId), "ESP8266-%04X", random(0xffff));

  if (client.connect(clientId)) {
    Serial.println("MQTT reconnected");
    client.subscribe(topic_command);
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
  digitalWrite(relayPin, LOW);

  // Use INPUT when the yellow sensor wire passes through
  // a 5 V-to-3.3 V level shifter or resistor divider.
  pinMode(flowPin, INPUT);
  attachInterrupt(digitalPinToInterrupt(flowPin), pulseCounter, FALLING);

  setup_wifi();

  client.setServer(mqtt_server, 1883);
  client.setCallback(callback);
}

void loop() {
  unsigned long currentMillis = millis();

  // Wi-Fi status LED
  if (WiFi.status() != WL_CONNECTED) {
    if (currentMillis - previousLedMillis >= ledInterval) {
      previousLedMillis = currentMillis;
      digitalWrite(ledPin, !digitalRead(ledPin));
    }
  } else {
    digitalWrite(ledPin, LOW);
  }

  // MQTT reconnect
  if (!client.connected()) {
    if (currentMillis - lastReconnectAttempt > 5000) {
      lastReconnectAttempt = currentMillis;

      if (reconnect()) {
        lastReconnectAttempt = 0;
      }
    }
  } else {
    client.loop();
  }

  // Sensor reading and publishing
  if (currentMillis - previousMillis >= interval) {
    float elapsedTime = (currentMillis - previousMillis) / 1000.0f;
    previousMillis = currentMillis;

    // Safe pulse-count snapshot; interrupt remains active.
    noInterrupts();
    uint32_t pulsesNow = pulseCount;
    interrupts();

    uint32_t pulsesInSample = pulsesNow - previousPulseCount;
    previousPulseCount = pulsesNow;

    float pulseFrequency = pulsesInSample / elapsedTime;
    flowRate = pulseFrequency / calibrationFactor;

    // Read ultrasonic distance
    digitalWrite(trigPin, LOW);
    delayMicroseconds(2);
    digitalWrite(trigPin, HIGH);
    delayMicroseconds(10);
    digitalWrite(trigPin, LOW);

    long duration = pulseIn(echoPin, HIGH, 30000);

    float distance = 0.0f;
    if (duration > 0) {
      distance = duration * 0.034f / 2.0f;
    }

    // Sends flowRate: 0.00 when no water is flowing
    char jsonPayload[64];
    snprintf(
      jsonPayload,
      sizeof(jsonPayload),
      "{\"distance\":%.2f, \"flowRate\":%.2f}",
      distance,
      flowRate
    );

    Serial.print("Publishing: ");
    Serial.println(jsonPayload);

    if (client.connected()) {
      client.publish(topic_data, jsonPayload);
    }
  }
}