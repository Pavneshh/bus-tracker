from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson.objectid import ObjectId
import os
import math
from datetime import datetime

# Import blueprints
from routes.bus_routes import bus_bp
from routes.stop_routes import stop_bp

app = Flask(__name__)
CORS(app)

# Register blueprints
app.register_blueprint(bus_bp, url_prefix='/api/buses')
app.register_blueprint(stop_bp, url_prefix='/stops')

# ========== MONGODB CONNECTION WITH SMART COLLECTION DETECTION ==========
db = None
stops_collection = None
buses_collection = None
connection_success = False

try:
    # Connect to MongoDB
    client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    db = client["bus_tracker"]
    connection_success = True
    print("✅ Connected to MongoDB successfully!")
    
    # Check both collections for stops - FIXED: Don't use collections directly in if statements
    stops_count = db.stops.count_documents({})
    busstops_count = db.busstops.count_documents({})
    print(f"📊 Found {stops_count} stops in 'stops' collection")
    print(f"📊 Found {busstops_count} stops in 'busstops' collection")
    
    # CRITICAL FIX: Use busstops collection since it has data
    if busstops_count > 0:
        stops_collection = db.busstops
        print("✅ Using 'busstops' collection for stops data")
    elif stops_count > 0:
        stops_collection = db.stops
        print("✅ Using 'stops' collection for stops data")
    else:
        stops_collection = None
        print("⚠️ WARNING: No stops data found in any collection!")
    
    # Check buses collection
    buses_count = db.buses.count_documents({})
    print(f"📊 Found {buses_count} buses in 'buses' collection")
    
    if buses_count >= 0:  # Always set buses_collection if db exists
        buses_collection = db.buses
        print("✅ Using 'buses' collection")
    
    # Make collections available globally for routes
    app.config['STOPS_COLLECTION'] = stops_collection
    app.config['BUSES_COLLECTION'] = buses_collection
    app.config['DB'] = db
    
    # Create geospatial index if not exists (for better performance)
    if stops_collection is not None:
        try:
            stops_collection.create_index([("location", "2dsphere")])
            print("✅ Geospatial index created/verified on stops collection")
        except Exception as idx_error:
            print(f"⚠️ Could not create index: {idx_error}")
    
except ConnectionFailure:
    print("❌ Failed to connect to MongoDB. Make sure MongoDB is running.")
    stops_collection = None
    db = None
    buses_collection = None
    connection_success = False
except Exception as e:
    print(f"❌ MongoDB connection error: {e}")
    stops_collection = None
    db = None
    buses_collection = None
    connection_success = False

# ========== HELPER FUNCTIONS ==========

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in kilometers using Haversine formula"""
    R = 6371  # Earth's radius in kilometers
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def validate_coordinates(lat, lng):
    """Validate if coordinates are within valid ranges"""
    try:
        lat = float(lat)
        lng = float(lng)
        if -90 <= lat <= 90 and -180 <= lng <= 180:
            return True, lat, lng
        return False, None, None
    except (TypeError, ValueError):
        return False, None, None

# ========== MAIN ROUTES ==========

@app.route("/")
def home():
    """API Home endpoint with status information"""
    if not connection_success or stops_collection is None or db is None:
        return jsonify({
            'message': 'Bus Tracker API is running, but MongoDB is not connected',
            'status': 'error',
            'version': '1.0.0',
            'instructions': 'Make sure MongoDB is running on localhost:27017'
        }), 503
    
    stops_count = stops_collection.count_documents({}) if stops_collection is not None else 0
    buses_count = buses_collection.count_documents({}) if buses_collection is not None else 0
    
    return jsonify({
        'message': 'Bus Tracker API Running 🚀',
        'version': '1.0.0',
        'status': 'ok',
        'database': {
            'stops': stops_count,
            'buses': buses_count,
            'collection_used': stops_collection.name if stops_collection is not None else 'none'
        },
        'endpoints': [
            '/dashboard - Web interface',
            '/stops - All bus stops (via blueprint)',
            '/stops-direct - Direct stops endpoint',
            '/nearby-stops - Find nearby stops',
            '/stops/search - Search stops by name',
            '/stops/<id> - Get stop by ID',
            '/api/buses - Bus information',
            '/api/stats - Database statistics',
            '/test-distance - Test distance calculation between cities',
            '/test-db - Test database connection'
        ]
    })

@app.route("/dashboard")
def dashboard():
    """Dashboard route - serves the HTML interface"""
    return render_template('index.html')

# ========== STOPS ROUTES (Direct, not using blueprint) ==========

@app.route("/stops-direct")
def get_stops_direct():
    """Get all stops directly (fallback if blueprint fails)"""
    if stops_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        stops = stops_collection.find().limit(100)
        
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
                } if coordinates else None,
            })
        
        return jsonify({
            "stops": result,
            "total": len(result),
            "source": "direct_endpoint"
        })
    except Exception as e:
        print(f"Error in get_stops_direct: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/stops")
def get_stops():
    """Get all stops with pagination"""
    if stops_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        # Get pagination parameters
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 100))
        skip = (page - 1) * limit
        
        # Get total count
        total_stops = stops_collection.count_documents({})
        
        # Fetch stops
        stops = stops_collection.find().skip(skip).limit(limit)
        
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
                } if coordinates else None,
            })
        
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

@app.route("/nearby-stops")
def nearby_stops():
    """Find stops near given coordinates"""
    if stops_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        lat = float(request.args.get("lat"))
        lng = float(request.args.get("lng"))
        radius = float(request.args.get("radius", 5000))  # Default 5km radius
        
        # Validate coordinates
        is_valid, valid_lat, valid_lng = validate_coordinates(lat, lng)
        if not is_valid:
            return jsonify({"error": "Invalid coordinates. Please provide valid lat and lng"}), 400
        
        print(f"🔍 Searching stops near: lat={valid_lat}, lng={valid_lng}, radius={radius}m")
        
        result = []
        
        # Try geospatial query first
        try:
            stops = stops_collection.find({
                "location": {
                    "$near": {
                        "$geometry": {
                            "type": "Point",
                            "coordinates": [valid_lng, valid_lat]
                        },
                        "$maxDistance": radius
                    }
                }
            }).limit(20)
            
            for stop in stops:
                coordinates = stop.get("location", {}).get("coordinates", [])
                if coordinates and len(coordinates) >= 2:
                    distance = calculate_distance(valid_lat, valid_lng, coordinates[1], coordinates[0])
                    
                    result.append({
                        "id": str(stop["_id"]),
                        "name": stop.get("name", "Unknown"),
                        "city": stop.get("city", ""),
                        "location": {
                            "type": "Point",
                            "coordinates": coordinates
                        },
                        "distance_km": round(distance, 2)
                    })
            
            result.sort(key=lambda x: x["distance_km"])
            print(f"✅ Found {len(result)} nearby stops via geospatial query")
            
        except Exception as geo_error:
            # Fallback: manual distance calculation
            print(f"⚠️ Geospatial query failed, using fallback: {geo_error}")
            
            all_stops = list(stops_collection.find())
            for stop in all_stops:
                coords = stop.get("location", {}).get("coordinates", [])
                if coords and len(coords) >= 2:
                    distance = calculate_distance(valid_lat, valid_lng, coords[1], coords[0])
                    if distance <= radius / 1000:
                        result.append({
                            "id": str(stop["_id"]),
                            "name": stop.get("name", "Unknown"),
                            "city": stop.get("city", ""),
                            "location": {
                                "type": "Point",
                                "coordinates": coords
                            },
                            "distance_km": round(distance, 2)
                        })
            
            result.sort(key=lambda x: x["distance_km"])
            print(f"✅ Found {len(result)} nearby stops via manual calculation")
        
        if result:
            nearest = result[0]
            print(f"📍 Nearest stop: {nearest['name']} at {nearest['distance_km']} km")
        
        return jsonify(result[:20])
        
    except Exception as e:
        print(f"❌ Error in nearby_stops: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/stops/search")
def search_stops():
    """Search stops by name or city"""
    if stops_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
    query = request.args.get("q", "")
    if not query:
        return jsonify([])
    
    try:
        stops = stops_collection.find({
            "$or": [
                {"name": {"$regex": query, "$options": "i"}},
                {"city": {"$regex": query, "$options": "i"}}
            ]
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
        print(f"Error in search_stops: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/stops/<stop_id>")
def get_stop(stop_id):
    """Get a specific stop by ID"""
    if stops_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
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

# ========== BUSES ROUTES ==========

@app.route("/api/buses")
def get_buses():
    """Get all buses"""
    if buses_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        buses = buses_collection.find()
        
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
        print(f"Error in get_buses: {e}")
        return jsonify({"error": str(e)}), 500

# ========== STATISTICS ROUTES ==========

@app.route("/api/stats")
def get_stats():
    """Get statistics about stops and buses"""
    if stops_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        stops_count = stops_collection.count_documents({})
        
        cities = stops_collection.aggregate([
            {"$match": {"city": {"$exists": True, "$ne": None, "$ne": ""}}},
            {"$group": {"_id": "$city", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ])
        
        cities_list = []
        for city in cities:
            if city["_id"]:
                cities_list.append({"city": city["_id"], "stops": city["count"]})
        
        buses_count = buses_collection.count_documents({}) if buses_collection is not None else 0
        active_buses = buses_collection.count_documents({"status": "active"}) if buses_collection is not None else 0
        
        return jsonify({
            "total_stops": stops_count,
            "total_buses": buses_count,
            "active_buses": active_buses,
            "top_cities": cities_list,
            "collection_used": stops_collection.name if stops_collection is not None else "none"
        })
    except Exception as e:
        print(f"Error in get_stats: {e}")
        return jsonify({"error": str(e)}), 500

# ========== TEST ROUTES ==========

@app.route("/test-db")
def test_db():
    """Test database connection and data"""
    if not connection_success:
        return jsonify({"error": "Database not connected"}), 503
    
    result = {
        "connected": True,
        "database": "bus_tracker",
        "collections": {}
    }
    
    if stops_collection is not None:
        sample_stop = stops_collection.find_one()
        result["collections"]["stops"] = {
            "count": stops_collection.count_documents({}),
            "has_data": sample_stop is not None,
            "collection_name": stops_collection.name,
            "sample": {
                "id": str(sample_stop["_id"]) if sample_stop else None,
                "name": sample_stop.get("name") if sample_stop else None
            } if sample_stop else None
        }
    else:
        result["collections"]["stops"] = {
            "error": "No stops collection available"
        }
    
    if buses_collection is not None:
        sample_bus = buses_collection.find_one()
        result["collections"]["buses"] = {
            "count": buses_collection.count_documents({}),
            "has_data": sample_bus is not None,
            "sample": {
                "id": str(sample_bus["_id"]) if sample_bus else None,
                "bus_id": sample_bus.get("bus_id") if sample_bus else None
            } if sample_bus else None
        }
    else:
        result["collections"]["buses"] = {
            "error": "No buses collection available"
        }
    
    return jsonify(result)

# ========== ERROR HANDLERS ==========

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

# ========== RUN APP ==========
if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 Bus Tracker Application Starting...")
    print("="*50)
    
    if connection_success and stops_collection is not None:
        print(f"✅ Database ready with {stops_collection.count_documents({})} stops in '{stops_collection.name}' collection")
    else:
        print("⚠️ Running without database - some features will not work")
    
    print("\n📱 Access the app at: http://127.0.0.1:5000/dashboard")
    print("🔧 API endpoints available at: http://127.0.0.1:5000/")
    print("🧪 Test database: http://127.0.0.1:5000/test-db")
    print("="*50 + "\n")
    
    app.run(debug=True, host='127.0.0.1', port=5000)