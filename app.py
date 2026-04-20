from flask import Flask, jsonify, request, render_template, redirect
from flask_cors import CORS
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson.objectid import ObjectId
import os
import math
from datetime import datetime, timedelta
import json
from urllib.parse import unquote
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import blueprints
from routes.bus_routes import bus_bp
from routes.stop_routes import stop_bp

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"]
    }
})

# Register blueprints
app.register_blueprint(bus_bp, url_prefix='/api/buses')
app.register_blueprint(stop_bp, url_prefix='/stops')

# ========== MONGODB CONNECTION (CLOUD ATLAS) ==========
db = None
stops_collection = None
buses_collection = None
connection_success = False

# Get MongoDB URI from environment variable
MONGO_URI = os.getenv('MONGO_URI')

if not MONGO_URI:
    print("❌ MONGO_URI not found in environment variables!")
    print("   Please set MONGO_URI in .env file or Render environment variables")
else:
    try:
        print(f"🔗 Connecting to MongoDB Atlas...")
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
        # Test connection
        client.admin.command('ping')
        db = client["bus_tracker"]
        connection_success = True
        print("✅ Connected to MongoDB Atlas successfully!")
        
        # Check stops in different possible collections
        stops_count = db.stops.count_documents({}) if 'stops' in db.list_collection_names() else 0
        busstops_count = db.busstops.count_documents({}) if 'busstops' in db.list_collection_names() else 0
        print(f"📊 Found {stops_count} stops in 'stops' collection")
        print(f"📊 Found {busstops_count} stops in 'busstops' collection")
        
        if busstops_count > 0:
            stops_collection = db.busstops
            print("✅ Using 'busstops' collection for stops data")
        elif stops_count > 0:
            stops_collection = db.stops
            print("✅ Using 'stops' collection for stops data")
        else:
            stops_collection = None
            print("⚠️ WARNING: No stops data found! Please import your stops data.")
        
        # Get buses collection
        if 'buses' in db.list_collection_names():
            buses_collection = db.buses
            print(f"✅ Using 'buses' collection with {buses_collection.count_documents({})} buses")
        else:
            buses_collection = None
            print("⚠️ WARNING: No 'buses' collection found!")
        
        # Create drivers collection if not exists
        if 'drivers' not in db.list_collection_names():
            db.create_collection("drivers")
            print("✅ Created 'drivers' collection")
        else:
            print(f"✅ 'drivers' collection already exists with {db.drivers.count_documents({})} records")
        
        app.config['STOPS_COLLECTION'] = stops_collection
        app.config['BUSES_COLLECTION'] = buses_collection
        app.config['DB'] = db
        
        # Create geospatial index if stops collection exists
        if stops_collection is not None:
            try:
                stops_collection.create_index([("location", "2dsphere")])
                print("✅ Geospatial index created on stops collection")
            except Exception as idx_error:
                print(f"⚠️ Could not create index: {idx_error}")
        
    except ConnectionFailure as e:
        print(f"❌ Failed to connect to MongoDB Atlas: {e}")
        print("   Please check:")
        print("   1. MONGO_URI is correct")
        print("   2. Network access allows your IP (0.0.0.0/0)")
        print("   3. Username/password are correct")
        stops_collection = None
        db = None
        buses_collection = None
        connection_success = False
    except Exception as e:
        print(f"❌ MongoDB error: {e}")
        stops_collection = None
        db = None
        buses_collection = None
        connection_success = False

# ========== HELPER FUNCTIONS ==========

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def validate_coordinates(lat, lng):
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
    if not connection_success or stops_collection is None or db is None:
        return jsonify({'message': 'API running, MongoDB not connected', 'status': 'error'}), 503
    
    stops_count = stops_collection.count_documents({}) if stops_collection is not None else 0
    buses_count = buses_collection.count_documents({}) if buses_collection is not None else 0
    
    return jsonify({
        'message': 'Bus Tracker API Running 🚀',
        'status': 'ok',
        'database': {'stops': stops_count, 'buses': buses_count}
    })

@app.route("/dashboard")
def dashboard():
    return render_template('index.html')

@app.route("/buses")
def buses_page():
    return render_template('buses.html')

@app.route("/seats")
def seats_page():
    return render_template('seats.html')

@app.route("/driver")
def driver_page():
    return render_template('driver.html')

@app.route("/driver-register")
def driver_register_page():
    """Driver registration page"""
    return render_template('driver-register.html')

@app.route("/admin")
def admin_page():
    """Admin approval panel"""
    return render_template('admin.html')

# ========== OFFER REDIRECT ROUTES ==========

@app.route("/offer/mmt")
def offer_mmt():
    return redirect("https://www.makemytrip.com/bus/")

@app.route("/offer/mydeal")
def offer_mydeal():
    return redirect("https://www.makemytrip.com/bus/")

# ========== STOPS ROUTES ==========

@app.route("/stops-direct")
def get_stops_direct():
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
                "location": {"type": "Point", "coordinates": coordinates} if coordinates else None,
            })
        return jsonify({"stops": result, "total": len(result)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/stops")
def get_stops():
    if stops_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 100))
        skip = (page - 1) * limit
        
        total_stops = stops_collection.count_documents({})
        stops = stops_collection.find().skip(skip).limit(limit)
        
        result = []
        for stop in stops:
            coordinates = stop.get("location", {}).get("coordinates", [])
            result.append({
                "id": str(stop["_id"]),
                "name": stop.get("name", "Unknown"),
                "city": stop.get("city", ""),
                "location": {"type": "Point", "coordinates": coordinates} if coordinates else None,
            })
        
        return jsonify({"stops": result, "total": total_stops, "page": page, "limit": limit})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/nearby-stops")
def nearby_stops():
    if stops_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        lat = float(request.args.get("lat"))
        lng = float(request.args.get("lng"))
        radius = float(request.args.get("radius", 5000))
        
        is_valid, valid_lat, valid_lng = validate_coordinates(lat, lng)
        if not is_valid:
            return jsonify({"error": "Invalid coordinates"}), 400
        
        result = []
        try:
            stops = stops_collection.find({
                "location": {
                    "$near": {
                        "$geometry": {"type": "Point", "coordinates": [valid_lng, valid_lat]},
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
                        "location": {"type": "Point", "coordinates": coordinates},
                        "distance_km": round(distance, 2)
                    })
            result.sort(key=lambda x: x["distance_km"])
        except Exception:
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
                            "location": {"type": "Point", "coordinates": coords},
                            "distance_km": round(distance, 2)
                        })
            result.sort(key=lambda x: x["distance_km"])
        
        return jsonify(result[:20])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/stops/search")
def search_stops():
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
                "location": {"type": "Point", "coordinates": coordinates} if coordinates else None
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/stops/<stop_id>")
def get_stop(stop_id):
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
                "location": {"type": "Point", "coordinates": coordinates} if coordinates else None
            })
        return jsonify({"error": "Stop not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Invalid stop ID: {str(e)}"}), 400

# ========== BUSES ROUTES ==========

@app.route("/api/buses")
def get_buses():
    if buses_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        buses = list(buses_collection.find())
        result = []
        for bus in buses:
            result.append({
                "id": str(bus["_id"]),
                "bus_id": bus.get("bus_id"),
                "bus_name": bus.get("bus_name"),
                "operator_name": bus.get("operator_name"),
                "ac_type": bus.get("ac_type"),
                "seat_type": bus.get("seat_type"),
                "price": bus.get("price"),
                "departure_time": bus.get("departure_time"),
                "arrival_time": bus.get("arrival_time"),
                "duration": bus.get("duration"),
                "available_seats": bus.get("available_seats", 50),
                "rating": bus.get("rating"),
                "status": bus.get("status", "inactive"),
                "city": bus.get("city"),
                "current_location": bus.get("current_location", {})
            })
        return jsonify(result)
    except Exception as e:
        print(f"Error in get_buses: {e}")
        return jsonify({"error": str(e)}), 500

# ========== LIVE BUS TRACKING (FIXED - Only actively sharing buses) ==========

@app.route("/api/buses/live", methods=["GET"])
def get_live_buses():
    """Get ONLY buses with recent location updates (active sharing)"""
    if buses_collection is None:
        return jsonify([])
    
    try:
        # Only get buses that have current_location coordinates
        all_buses = list(buses_collection.find({
            "current_location.coordinates": {"$exists": True, "$ne": []}
        }))
        
        result = []
        current_time = datetime.now()
        
        for bus in all_buses:
            loc = bus.get("current_location", {})
            coords = loc.get("coordinates", [])
            last_updated = bus.get("last_updated")
            
            if coords and len(coords) >= 2:
                # Check if update is recent (within last 5 minutes)
                is_recent = False
                if last_updated:
                    try:
                        # Parse last_updated string
                        if isinstance(last_updated, str):
                            if 'T' in last_updated:
                                last_dt = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                            else:
                                last_dt = datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S")
                        else:
                            last_dt = last_updated
                        
                        if isinstance(last_dt, datetime):
                            time_diff = (current_time - last_dt).total_seconds()
                            is_recent = time_diff < 300  # 5 minutes = 300 seconds
                    except Exception as e:
                        print(f"Error parsing date for {bus.get('bus_name')}: {e}")
                        is_recent = False  # If can't parse, don't show
                
                # Only include if location is recent
                if is_recent:
                    result.append({
                        "id": str(bus["_id"]),
                        "bus_id": bus.get("bus_id", bus.get("bus_name", "Unknown")),
                        "bus_name": bus.get("bus_name", "Unknown"),
                        "route_name": bus.get("route_name", "On Route"),
                        "city": bus.get("city", "Gujarat"),
                        "available_seats": bus.get("available_seats", 0),
                        "lat": coords[1],
                        "lng": coords[0],
                        "last_updated": last_updated if last_updated else "Just now"
                    })
        
        print(f"📍 Found {len(result)} actively sharing buses (updated in last 5 minutes)")
        return jsonify(result)
    except Exception as e:
        print(f"Error in get_live_buses: {e}")
        return jsonify([]), 500

# FIXED - Location update endpoint with proper URL decoding
@app.route("/api/buses/<path:bus_id>/location", methods=["POST", "OPTIONS"])
def update_bus_location(bus_id):
    """Update bus location - works with any bus ID format"""
    if request.method == "OPTIONS":
        return "", 200
        
    if buses_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        # Decode URL encoded bus_id
        decoded_bus_id = unquote(bus_id)
        print(f"\n=== LOCATION UPDATE ===")
        print(f"Original Bus ID: {bus_id}")
        print(f"Decoded Bus ID: {decoded_bus_id}")
        
        # Get raw data
        raw_data = request.get_data(as_text=True)
        print(f"Raw data: {raw_data}")
        print(f"Content-Type: {request.content_type}")
        
        data = {}
        
        # Parse data regardless of content type
        if raw_data:
            # Try JSON
            try:
                data = json.loads(raw_data)
                print(f"Parsed as JSON: {data}")
            except:
                # Try URL encoded
                try:
                    from urllib.parse import parse_qs
                    parsed = parse_qs(raw_data)
                    data = {k: v[0] for k, v in parsed.items()}
                    print(f"Parsed as URL encoded: {data}")
                except:
                    pass
        
        if not data:
            return jsonify({"error": "No valid data received"}), 400
        
        # Get lat/lng
        lat = data.get('lat') or data.get('latitude')
        lng = data.get('lng') or data.get('longitude')
        
        if lat is None or lng is None:
            return jsonify({
                "error": "Missing lat/lng",
                "received_keys": list(data.keys())
            }), 400
        
        lat = float(lat)
        lng = float(lng)
        
        # Validate coordinates
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            return jsonify({"error": "Invalid coordinates"}), 400
        
        # Find bus by bus_id OR bus_name (case insensitive)
        bus = buses_collection.find_one({
            "$or": [
                {"bus_id": {"$regex": f"^{decoded_bus_id}$", "$options": "i"}},
                {"bus_name": {"$regex": f"^{decoded_bus_id}$", "$options": "i"}}
            ]
        })
        
        if not bus:
            # List available buses for debugging
            available = list(buses_collection.find({}, {"bus_name": 1, "bus_id": 1}))
            print(f"Available buses: {available}")
            return jsonify({
                "error": f"Bus '{decoded_bus_id}' not found",
                "available_buses": [b.get("bus_name") for b in available]
            }), 404
        
        # Update location with timestamp
        buses_collection.update_one(
            {"_id": bus["_id"]},
            {
                "$set": {
                    "current_location": {
                        "type": "Point",
                        "coordinates": [lng, lat]
                    },
                    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status": "active"
                }
            }
        )
        
        print(f"✅ Updated: {bus.get('bus_name')} at ({lat}, {lng})")
        
        return jsonify({
            "success": True,
            "bus_id": bus.get("bus_name"),
            "lat": lat,
            "lng": lng,
            "message": "Location updated successfully"
        })
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"error": str(e)}), 500

# ========== DRIVER MANAGEMENT ENDPOINTS ==========

@app.route("/api/drivers/register", methods=["POST"])
def register_driver():
    """Driver registration request"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        data = request.get_json()
        
        existing = db.drivers.find_one({"bus_id": data.get('bus_id')})
        if existing:
            return jsonify({
                "success": False,
                "message": f"Bus '{data.get('bus_id')}' already registered. Status: {existing.get('status')}"
            }), 400
        
        driver = {
            "bus_id": data.get('bus_id'),
            "bus_name": data.get('bus_name'),
            "driver_name": data.get('driver_name'),
            "phone": data.get('phone'),
            "email": data.get('email'),
            "status": "pending",
            "requested_at": datetime.now(),
            "approved_by": None,
            "approved_at": None
        }
        
        db.drivers.insert_one(driver)
        
        return jsonify({
            "success": True,
            "message": "Registration request submitted. Waiting for admin approval.",
            "status": "pending"
        })
    except Exception as e:
        print(f"Error in register_driver: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/drivers/status/<bus_id>", methods=["GET"])
def get_driver_status(bus_id):
    """Check driver approval status"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        driver = db.drivers.find_one({"bus_id": bus_id})
        
        if not driver:
            return jsonify({
                "registered": False,
                "status": "not_registered",
                "message": "Please register first"
            })
        
        return jsonify({
            "registered": True,
            "status": driver.get("status"),
            "bus_id": driver.get("bus_id"),
            "bus_name": driver.get("bus_name"),
            "driver_name": driver.get("driver_name"),
            "requested_at": driver.get("requested_at").isoformat() if driver.get("requested_at") else None,
            "approved_at": driver.get("approved_at").isoformat() if driver.get("approved_at") else None
        })
    except Exception as e:
        print(f"Error in get_driver_status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/drivers/pending", methods=["GET"])
def get_pending_drivers():
    """Get all pending driver requests (Admin only)"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        pending = list(db.drivers.find({"status": "pending"}))
        
        result = []
        for driver in pending:
            result.append({
                "id": str(driver["_id"]),
                "bus_id": driver.get("bus_id"),
                "bus_name": driver.get("bus_name"),
                "driver_name": driver.get("driver_name"),
                "phone": driver.get("phone"),
                "email": driver.get("email"),
                "requested_at": driver.get("requested_at").isoformat() if driver.get("requested_at") else None
            })
        
        return jsonify({
            "drivers": result,
            "count": len(result)
        })
    except Exception as e:
        print(f"Error in get_pending_drivers: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/drivers/approve/<driver_id>", methods=["POST"])
def approve_driver(driver_id):
    """Approve a driver request (Admin only)"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        result = db.drivers.update_one(
            {"_id": ObjectId(driver_id)},
            {
                "$set": {
                    "status": "approved",
                    "approved_by": "admin",
                    "approved_at": datetime.now()
                }
            }
        )
        
        if result.modified_count > 0:
            return jsonify({"success": True, "message": "Driver approved successfully"})
        else:
            return jsonify({"success": False, "message": "Driver not found"}), 404
    except Exception as e:
        print(f"Error in approve_driver: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/drivers/reject/<driver_id>", methods=["POST"])
def reject_driver(driver_id):
    """Reject a driver request (Admin only)"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        result = db.drivers.update_one(
            {"_id": ObjectId(driver_id)},
            {
                "$set": {
                    "status": "rejected",
                    "approved_by": "admin",
                    "approved_at": datetime.now()
                }
            }
        )
        
        if result.modified_count > 0:
            return jsonify({"success": True, "message": "Driver rejected"})
        else:
            return jsonify({"success": False, "message": "Driver not found"}), 404
    except Exception as e:
        print(f"Error in reject_driver: {e}")
        return jsonify({"error": str(e)}), 500

# ========== BUS BOOKING API ENDPOINTS ==========

@app.route("/api/buses/search")
def search_buses_api():
    if buses_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        from_city = request.args.get('from', '')
        to_city = request.args.get('to', '')
        ac_type = request.args.get('ac_type', '')
        seat_type = request.args.get('seat_type', '')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        sort_by = request.args.get('sort_by', 'relevance')
        sort_order = request.args.get('sort_order', 'asc')
        
        skip = (page - 1) * limit
        query = {}
        
        if from_city:
            query['from_city'] = {'$regex': from_city, '$options': 'i'}
        if to_city:
            query['to_city'] = {'$regex': to_city, '$options': 'i'}
        if ac_type:
            query['ac_type'] = ac_type
        if seat_type:
            query['seat_type'] = seat_type
        
        sort_field = {
            'price': 'price',
            'rating': 'rating',
            'departure': 'departure_time',
            'arrival': 'arrival_time',
            'relevance': 'rating'
        }.get(sort_by, 'rating')
        
        sort_direction = 1 if sort_order == 'asc' else -1
        
        total_buses = buses_collection.count_documents(query)
        buses = buses_collection.find(query).sort(sort_field, sort_direction).skip(skip).limit(limit)
        
        result = []
        for bus in buses:
            result.append({
                "id": str(bus["_id"]),
                "bus_name": bus.get("bus_name", "Unknown"),
                "operator_name": bus.get("operator_name", "Local Operator"),
                "bus_type": f"{bus.get('ac_type', 'NON A/C')} {bus.get('seat_type', 'Seater')} (2+1)",
                "price": bus.get("price", 3000),
                "original_price": bus.get("original_price", bus.get("price", 3000)),
                "discount": bus.get("discount", 0),
                "departure_time": bus.get("departure_time", "16:50"),
                "arrival_time": bus.get("arrival_time", "17:10"),
                "duration": bus.get("duration", "00h 20m"),
                "available_seats": bus.get("available_seats", 37),
                "single_seats": bus.get("single_seats", 11),
                "rating": bus.get("rating", 4.2),
                "reviews_count": bus.get("reviews_count", 150),
                "amenities": bus.get("amenities", ["Water", "Charging Point"]),
                "pickup_points": bus.get("pickup_points", []),
                "drop_points": bus.get("drop_points", []),
                "cancellation_policy": bus.get("cancellation_policy", "Free cancellation up to 6 hours"),
                "cancellation_policy_details": bus.get("cancellation_policy_details", {}),
                "travel_policy": bus.get("travel_policy", {}),
                "is_prime": bus.get("is_prime", False),
                "status": bus.get("status", "active")
            })
        
        return jsonify({
            "buses": result,
            "total": total_buses,
            "page": page,
            "limit": limit,
            "total_pages": (total_buses + limit - 1) // limit,
            "has_more": skip + limit < total_buses
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/buses/test", methods=["GET"])
def test_buses_endpoint():
    if buses_collection is None:
        return jsonify({"error": "Buses collection not available"}), 503
    
    try:
        count = buses_collection.count_documents({})
        sample = buses_collection.find_one()
        return jsonify({
            "status": "ok",
            "buses_count": count,
            "sample_bus": sample.get("bus_name") if sample else None
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========== STATISTICS ROUTES ==========

@app.route("/api/stats")
def get_stats():
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
        cities_list = [{"city": c["_id"], "stops": c["count"]} for c in cities if c["_id"]]
        buses_count = buses_collection.count_documents({}) if buses_collection else 0
        active_buses = buses_collection.count_documents({"status": "active"}) if buses_collection else 0
        
        return jsonify({
            "total_stops": stops_count,
            "total_buses": buses_count,
            "active_buses": active_buses,
            "top_cities": cities_list
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/test-db")
def test_db():
    if not connection_success:
        return jsonify({"error": "Database not connected"}), 503
    
    result = {"connected": True, "database": "bus_tracker"}
    
    if stops_collection:
        sample = stops_collection.find_one()
        result["stops"] = {
            "count": stops_collection.count_documents({}),
            "collection": stops_collection.name,
            "sample_name": sample.get("name") if sample else None
        }
    
    if buses_collection:
        sample = buses_collection.find_one()
        result["buses"] = {
            "count": buses_collection.count_documents({}),
            "sample_name": sample.get("bus_name") if sample else None
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
        print(f"✅ Database ready with {stops_collection.count_documents({})} stops")
    else:
        print("⚠️ Running without database")
    
    print("\n📱 Dashboard: http://127.0.0.1:5000/dashboard")
    print("🚌 Bus Booking: http://127.0.0.1:5000/buses")
    print("🚗 Driver Mode: http://127.0.0.1:5000/driver")
    print("📝 Driver Registration: http://127.0.0.1:5000/driver-register")
    print("👑 Admin Panel: http://127.0.0.1:5000/admin")
    print("🎫 Seat Selection: http://127.0.0.1:5000/seats")
    print("="*50 + "\n")
    
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))