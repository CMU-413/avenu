from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from setup.timeslots import time_slots

app = Flask(__name__)
vm_ip_addr = "http://localhost:3000"
CORS(app, resources={r"/*": {"origins": vm_ip_addr}}, supports_credentials=True)

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["email_db"]
collection = db["emails"]
time_slots_collection = db["time_slots"]

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"message": "HEALTH OK"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
