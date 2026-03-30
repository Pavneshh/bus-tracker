from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import os
import math

app = Flask(__name__)
CORS(app)

# MongoDB connection
db = None
stops_collection = None

try:
    client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
    # Test connection
    client.admin.command('ping')
    db = client["bus_tracker"]
    print("✅ Connected to MongoDB successfully!")
    
    # Check both collections
    stops_count = db.stops.count_documents({})
    busstops_count = db.busstops.count_documents({})
    print(f"📊 Found {stops_count} stops in 'stops' collection")
    print(f"📊 Found {busstops_count} stops in 'busstops' collection")
    
    # Use busstops collection for stop data (this has all your Gujarat stops)
    stops_collection = db.busstops
    
except ConnectionFailure:
    print("❌ Failed to connect to MongoDB. Make sure MongoDB is running.")
    stops_collection = None
    db = None
except Exception as e:
    print(f"❌ MongoDB connection error: {e}")
    stops_collection = None
    db = None

# Home route
@app.route("/")
def home():
    # Check if database is connected (compare with None, not boolean)
    if stops_collection is None or db is None:
        return jsonify({
            'message': 'Bus Tracker API is running, but MongoDB is not connected',
            'status': 'error',
            'version': '1.0.0'
        }), 503
    
    stops_count = stops_collection.count_documents({})
    buses_count = db.buses.count_documents({}) if db is not None else 0
    
    return jsonify({
        'message': 'Bus Tracker API Running 🚀',
        'version': '1.0.0',
        'status': 'ok',
        'database': {
            'stops': stops_count,
            'buses': buses_count
        },
        'endpoints': [
            '/dashboard - Web interface',
            '/stops - All bus stops',
            '/nearby-stops - Find nearby stops',
            '/stops/search - Search stops by name',
            '/stops/<id> - Get stop by ID',
            '/api/buses - Bus information',
            '/api/stats - Database statistics'
        ]
    })

# Dashboard route - serves the HTML interface
@app.route("/dashboard")
def dashboard():
    return render_template('index.html')

# Get all stops from busstops collection
@app.route("/stops")
def get_stops():
    if stops_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 100))
        skip = (page - 1) * limit
        
        stops = stops_collection.find().skip(skip).limit(limit)
        
        result = []
        for stop in stops:
            # Get coordinates
            coordinates = stop.get("location", {}).get("coordinates", [])
            
            result.append({
                "id": str(stop["_id"]),
                "name": stop.get("name", "Unknown"),
                "city": stop.get("city", ""),
                "location": {
                    "type": "Point",
                    "coordinates": coordinates
                } if coordinates else None,
            })
        
        total_stops = stops_collection.count_documents({})
        
        return jsonify({
            "stops": result,
            "total": total_stops,
            "page": page,
            "limit": limit,
            "has_more": skip + limit < total_stops
        })
    except Exception as e:
        print(f"Error in get_stops: {e}")
        return jsonify({"error": str(e)}), 500

# Get nearby stops API using busstops collection
@app.route("/nearby-stops")
def nearby_stops():
    if stops_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        lat = float(request.args.get("lat"))
        lng = float(request.args.get("lng"))
        radius = float(request.args.get("radius", 5000))  # Default 5km radius
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid coordinates. Please provide valid lat and lng"}), 400
    
    try:
        # Try geospatial query first
        stops = stops_collection.find({
            "location": {
                "$near": {
                    "$geometry": {
                        "type": "Point",
                        "coordinates": [lng, lat]
                    },
                    "$maxDistance": radius
                }
            }
        }).limit(20)
        
        result = []
        for stop in stops:
            coordinates = stop.get("location", {}).get("coordinates", [])
            # Calculate distance for response
            distance = calculate_distance(lat, lng, coordinates[1], coordinates[0]) if coordinates else 0
            
            result.append({
                "id": str(stop["_id"]),
                "name": stop.get("name", "Unknown"),
                "city": stop.get("city", ""),
                "location": {
                    "type": "Point",
                    "coordinates": coordinates
                } if coordinates else None,
                "distance_km": round(distance, 2)
            })
        
        return jsonify(result)
    except Exception as e:
        # Fallback: manual distance calculation if geospatial query fails
        print(f"Geospatial query failed, using fallback: {e}")
        try:
            all_stops = list(stops_collection.find())
            nearby = []
            
            for stop in all_stops:
                coords = stop.get("location", {}).get("coordinates", [])
                if coords and len(coords) >= 2:
                    distance = calculate_distance(lat, lng, coords[1], coords[0])
                    if distance <= radius / 1000:  # Convert to km
                        nearby.append({
                            "id": str(stop["_id"]),
                            "name": stop.get("name", "Unknown"),
                            "city": stop.get("city", ""),
                            "location": {
                                "type": "Point",
                                "coordinates": coords
                            },
                            "distance_km": round(distance, 2)
                        })
            
            nearby.sort(key=lambda x: x["distance_km"])
            return jsonify(nearby[:20])
        except Exception as fallback_error:
            return jsonify({"error": str(fallback_error)}), 500

# Get stop by ID
@app.route("/stops/<stop_id>")
def get_stop(stop_id):
    if stops_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
    from bson.objectid import ObjectId
    
    try:
        stop = stops_collection.find_one({"_id": ObjectId(stop_id)})
        if stop:
            coordinates = stop.get("location", {}).get("coordinates", [])
            return jsonify({
                "id": str(stop["_id"]),
                "name": stop.get("name", "Unknown"),
                "city": stop.get("city", ""),
                "location": {
                    "type": "Point",
                    "coordinates": coordinates
                } if coordinates else None
            })
        return jsonify({"error": "Stop not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Invalid stop ID: {str(e)}"}), 400

# Search stops by name
@app.route("/stops/search")
def search_stops():
    if stops_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
    query = request.args.get("q", "")
    if not query:
        return jsonify([])
    
    try:
        stops = stops_collection.find({
            "name": {"$regex": query, "$options": "i"}
        }).limit(20)
        
        result = []
        for stop in stops:
            coordinates = stop.get("location", {}).get("coordinates", [])
            result.append({
                "id": str(stop["_id"]),
                "name": stop.get("name", "Unknown"),
                "city": stop.get("city", ""),
                "location": {
                    "type": "Point",
                    "coordinates": coordinates
                } if coordinates else None
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API endpoint for buses
@app.route("/api/buses")
def get_buses():
    if db is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        buses = db.buses.find()
        
        result = []
        for bus in buses:
            result.append({
                "id": str(bus["_id"]),
                "bus_id": bus.get("bus_id"),
                "route_id": bus.get("route_id"),
                "capacity": bus.get("capacity", 50),
                "current_passengers": bus.get("current_passengers", 0),
                "status": bus.get("status", "active"),
                "current_location": bus.get("current_location", {})
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Helper function for distance calculation
def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in kilometers using Haversine formula"""
    R = 6371  # Earth's radius in kilometers
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

# Get statistics about stops
@app.route("/api/stats")
def get_stats():
    if stops_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        stops_count = stops_collection.count_documents({})
        
        # Get cities with most stops
        cities = stops_collection.aggregate([
            {"$group": {"_id": "$city", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ])
        
        cities_list = []
        for city in cities:
            if city["_id"]:
                cities_list.append({"city": city["_id"], "stops": city["count"]})
        
        return jsonify({
            "total_stops": stops_count,
            "top_cities": cities_list
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host='127.0.0.1', port=5000)