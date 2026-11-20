from flask import Flask, render_template, jsonify
from flask_sqlalchemy import SQLAlchemy
import paho.mqtt.client as mqtt
import threading
import json
from datetime import datetime
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
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
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

# API Route for Chart Data
@app.route('/api/history')
def history():
    # Fetch the last 50 records in chronological order
    records = WaterRecord.query.order_by(WaterRecord.timestamp.desc()).limit(50).all()
    records.reverse()
    
    data = [{
        "time": r.timestamp.strftime("%H:%M:%S"),
        "level_percent": r.distance,
        "flow_rate": r.flow_rate
    } for r in records]
    
    return jsonify(data)

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