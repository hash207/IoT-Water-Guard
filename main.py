from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
import paho.mqtt.client as mqtt
import threading
import json
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# Get the absolute path of the current directory
basedir = os.path.abspath(os.path.dirname(__file__))

# Force SQLite database creation in the project root directory
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'water_data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Tank Calibration Constants (in cm)
EMPTY_DISTANCE = 161.0  # Distance when tank is empty (0%)
FULL_DISTANCE = 20.0    # Distance when tank is full (100% - sensor blind zone limit)

# Database Model
class WaterRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    distance = db.Column(db.Float, nullable=False)  # Stores calculated water level percentage
    flow_rate = db.Column(db.Float, nullable=False)

# MQTT Configuration
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "hash/waterstatus"

# MQTT on_message callback
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        raw_distance = float(payload.get('distance', EMPTY_DISTANCE))
        flow_rate = float(payload.get('flowRate', 0.0))

        # Calculate tank level percentage (clamped between 0% and 100%)
        level_percent = ((EMPTY_DISTANCE - raw_distance) / (EMPTY_DISTANCE - FULL_DISTANCE)) * 100.0
        level_percent = max(0.0, min(100.0, round(level_percent, 1)))

        # Save readings to the database
        with app.app_context():
            new_record = WaterRecord(distance=level_percent, flow_rate=flow_rate)
            db.session.add(new_record)
            db.session.commit()
            print(f"[SUCCESS] Saved to DB: Level = {level_percent}% (Raw: {raw_distance}cm), Flow Rate = {flow_rate} L/min")
    except Exception as e:
        print(f"[ERROR] Failed to process MQTT data: {e}")

# MQTT Background Thread
def mqtt_thread():
    client = mqtt.Client()
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.subscribe(MQTT_TOPIC)
    client.loop_forever()

# Dashboard Route
@app.route('/')
def index():
    return render_template('dashboard.html')

# API Route for Weekly Chart Data (Sunday to Saturday)
@app.route('/api/history')
def history():
    # Calculate the start of the current week (Sunday at 00:00:00)
    now = datetime.now()
    days_since_sunday = (now.weekday() + 1) % 7
    start_of_week = (now - timedelta(days=days_since_sunday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Fetch all records from Sunday 00:00:00 up to now
    records = WaterRecord.query.filter(WaterRecord.timestamp >= start_of_week).all()

    # Initialize buckets for the 7 days (0 = Sun, 1 = Mon, ..., 6 = Sat)
    daily_levels = [[] for _ in range(7)]
    daily_flows = [0.0 for _ in range(7)]

    # Sampling interval in minutes (ESP8266 publishes every 5 seconds)
    INTERVAL_MINUTES = 5.0 / 60.0

    for r in records:
        day_idx = (r.timestamp.weekday() + 1) % 7
        daily_levels[day_idx].append(r.distance)
        # Convert L/min rate over a 5-second window into Liters
        daily_flows[day_idx] += r.flow_rate * INTERVAL_MINUTES

    # Compute daily average level (%) and round total flow (Liters)
    avg_levels = [
        round(sum(vals) / len(vals), 1) if vals else 0.0
        for vals in daily_levels
    ]
    total_flows = [round(flow, 1) for flow in daily_flows]

    return jsonify({
        "levels": avg_levels,
        "flows": total_flows
    })

if __name__ == '__main__':
    # Create database tables if they do not exist
    with app.app_context():
        db.create_all()
        print(f"[INFO] Database initialized at: {os.path.join(basedir, 'water_data.db')}")
    
    # Start MQTT listener in a daemon thread
    thread = threading.Thread(target=mqtt_thread, daemon=True)
    thread.start()
    
    # Start Flask server (disable reloader to prevent duplicate MQTT threads)
    print("[INFO] Starting Flask Server...")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)