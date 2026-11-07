# FlowGuard 💧

**Smart IoT Water Management & Pump Automation System**

FlowGuard is a full-stack Internet of Things (IoT) solution designed to monitor municipal water flow, track water tank levels, and remotely control water pumps. Built with an ESP8266 microcontroller and a Flask backend, the system ensures real-time data visualization and hardware automation through the MQTT protocol.

## ✨ Key Features

* **Real-Time Monitoring:** Live tracking of tank water levels via ultrasonic sensing and municipal water supply via flow rate calculation.
* **Remote Pump Control:** Direct ON/OFF manual override for the water pump from the web dashboard.
* **Non-Blocking Firmware:** Highly optimized C++ firmware utilizing hardware interrupts and `millis()` to prevent system freezing, avoid heap fragmentation, and ensure continuous data streaming.
* **Interactive Dashboard:** A responsive, modern UI built with Tailwind CSS, featuring Dark Mode, bilingual support (English/Arabic), and live data plotting using Chart.js (configured for a Sunday-start workweek in Jordan).
* **Automated Data Logging:** A Python Flask backend that silently listens to MQTT streams in a background thread and logs sensor data into a local SQLite database for historical analysis.

## 🛠️ Tech Stack

**Hardware:**
* ESP8266 (NodeMCU)
* AJ-SR04M Ultrasonic Sensor (Tank Level)
* 3/4" Brass Water Flow Sensor (Municipal Water)
* 5V Relay Module (Pump Contactor)
* IP65 Waterproof Enclosure

**Software & Backend:**
* Python 3.x
* Flask & Flask-SQLAlchemy (SQLite)
* Paho-MQTT

**Frontend:**
* HTML5 / JavaScript
* Tailwind CSS
* MQTT.js (WebSockets)
* Chart.js

## 🏗️ System Architecture

1. **Edge Node (ESP8266):** Reads sensor data without blocking the main loop and publishes a JSON payload to `hash/waterstatus`. Simultaneously subscribes to `hash/pumpcontrol` for incoming relay commands.
2. **Message Broker:** Employs `broker.emqx.io` to route real-time telemetry and commands between the hardware and the interfaces.
3. **Backend Server (Flask):** Runs a daemon thread listening to the broker, parsing JSON data, and committing it to the SQLite database (`water_data.db`) via SQLAlchemy.
4. **Web Client:** Connects directly to the MQTT broker via WebSockets for zero-latency UI updates, and fetches historical weekly data from the Flask API (`/api/history`) for charts.

## ⚙️ Hardware Wiring

| Component | ESP8266 Pin | Description |
| :--- | :--- | :--- |
| **Ultrasonic Trig** | `D1` (GPIO 5) | Triggers the ultrasonic pulse. |
| **Ultrasonic Echo** | `D2` (GPIO 4) | Receives the bounce-back signal. |
| **Flow Sensor** | `D5` (GPIO 14) | Hardware interrupt pin for pulse counting. |
| **Pump Relay** | `D6` (GPIO 12) | Controls the heavy-duty pump contactor. |
| **Status LED** | `D4` (GPIO 2) | Indicates Wi-Fi and MQTT connection status. |

## 🚀 Installation & Setup

### 1. Backend Server Setup
Clone the repository and set up the Python environment:
```bash
git clone [https://github.com/YOUR_USERNAME/FlowGuard.git](https://github.com/YOUR_USERNAME/FlowGuard.git)
cd FlowGuard
python -m venv water_venv

```

Activate the virtual environment:

* **Windows:** `water_venv\Scripts\activate`
* **Linux/Mac:** `source water_venv/bin/activate`

Install dependencies and start the server:

```bash
pip install Flask Flask-SQLAlchemy paho-mqtt
python app.py

```

*The SQLite database (`water_data.db`) will be automatically generated in the project root upon the first run.*

### 2. Dashboard Access

Open your web browser and navigate to:

```text
http://localhost:5000

```

## 👤 Author

**Hashem Osama Khair alla Alsharif**

Electrical Engineering Student at Al Hussein Technical University (HTU) - Jordan