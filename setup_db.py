from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import os

app = Flask(__name__)
CORS(app)

# MongoDB connection
try:
    client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
    # Test connection
    client.admin.command('ping')
    db = client["bus_tracker"]
    print("✅ Connected to MongoDB successfully!")
except ConnectionFailure:
    print("❌ Failed to connect to MongoDB. Make sure MongoDB is running.")
    db = None
except Exception as e:
    print(f"❌ MongoDB connection error: {e}")
    db = None

# Home route
@app.route("/")
def home():
    if db is None:
        return jsonify({
            'message': 'Bus Tracker API is running, but MongoDB is not connected',
            'status': 'error',
            'version': '1.0.0'
        }), 503
    
    return jsonify({
        'message': 'Bus Tracker API Running 🚀',
        'version': '1.0.0',
        'status': 'ok',
        'endpoints': [
            '/stops',
            '/nearby-stops',
            '/stops/search',
            '/stops/<id>'
        ]
    })

# Get all stops
@app.route("/stops")
def get_stops():
    if db is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        stops = db.stops.find()
        
        result = []
        for stop in stops:
            result.append({
                "id": str(stop["_id"]),
                "name": stop["name"],
                "location": stop.get("location", {}),
                "route_id": stop.get("route_id")
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Get nearby stops API
@app.route("/nearby-stops")
def nearby_stops():
    if db is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        lat = float(request.args.get("lat"))
        lng = float(request.args.get("lng"))
        radius = float(request.args.get("radius", 2000))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid coordinates. Please provide valid lat and lng"}), 400
    
    try:
        stops = db.stops.find({
            "location": {
                "$near": {
                    "$geometry": {
                        "type": "Point",
                        "coordinates": [lng, lat]
                    },
                    "$maxDistance": radius
                }
            }
        }).limit(10)
        
        result = []
        for stop in stops:
            result.append({
                "id": str(stop["_id"]),
                "name": stop["name"],
                "location": stop.get("location", {})
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Get stop by ID
@app.route("/stops/<stop_id>")
def get_stop(stop_id):
    if db is None:
        return jsonify({"error": "Database not connected"}), 503
    
    from bson.objectid import ObjectId
    
    try:
        stop = db.stops.find_one({"_id": ObjectId(stop_id)})
        if stop:
            return jsonify({
                "id": str(stop["_id"]),
                "name": stop["name"],
                "location": stop.get("location", {}),
                "route_id": stop.get("route_id")
            })
        return jsonify({"error": "Stop not found"}), 404
    except:
        return jsonify({"error": "Invalid stop ID"}), 400

# Search stops by name
@app.route("/stops/search")
def search_stops():
    if db is None:
        return jsonify({"error": "Database not connected"}), 503
    
    query = request.args.get("q", "")
    if not query:
        return jsonify([])
    
    try:
        stops = db.stops.find({
            "name": {"$regex": query, "$options": "i"}
        }).limit(10)
        
        result = []
        for stop in stops:
            result.append({
                "id": str(stop["_id"]),
                "name": stop["name"],
                "location": stop.get("location", {})
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host='127.0.0.1', port=5000)