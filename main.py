import os
import json
import threading
from datetime import datetime
import paho.mqtt.client as mqtt
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, render_template, jsonify

app = Flask(__name__)

# Get the absolute path of the current directory
basedir = os.path.abspath(os.path.dirname(__file__))

# Force database creation in the same project directory
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'water_data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database Model
class WaterRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    distance = db.Column(db.Float, nullable=False)
    flow_rate = db.Column(db.Float, nullable=False)

# MQTT Configuration
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "hash/waterstatus"

# MQTT on_message callback
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        distance = payload.get('distance', 0)
        flow_rate = payload.get('flowRate', 0)
        
        # Save readings to the database
        with app.app_context():
            new_record = WaterRecord(distance=distance, flow_rate=flow_rate)
            db.session.add(new_record)
            db.session.commit()
            # English feedback for Terminal
            print(f"[SUCCESS] Saved to DB: Distance = {distance}cm, Flow Rate = {flow_rate} L/min")
    except Exception as e:
        # English error feedback
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
    # Fetch the last 50 records
    records = WaterRecord.query.order_by(WaterRecord.timestamp.desc()).limit(50).all()
    records.reverse()
    
    data = [{
        "time": r.timestamp.strftime("%H:%M:%S"),
        "distance": r.distance,
        "flow_rate": r.flow_rate
    } for r in records]
    
    return jsonify(data)

if __name__ == '__main__':
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()
        # English feedback for database initialization
        print(f"[INFO] Database initialized at: {os.path.join(basedir, 'water_data.db')}")
    
    # Start MQTT thread
    thread = threading.Thread(target=mqtt_thread, daemon=True)
    thread.start()
    
    # Start Flask server
    print("[INFO] Starting Flask Server...")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)