from flask import Flask, jsonify, request, render_template, redirect
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
    
    # Check both collections for stops
    stops_count = db.stops.count_documents({})
    busstops_count = db.busstops.count_documents({})
    print(f"📊 Found {stops_count} stops in 'stops' collection")
    print(f"📊 Found {busstops_count} stops in 'busstops' collection")
    
    # Use busstops collection since it has data
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
    buses_collection = db.buses
    print("✅ Using 'buses' collection")
    
    # Make collections available globally for routes
    app.config['STOPS_COLLECTION'] = stops_collection
    app.config['BUSES_COLLECTION'] = buses_collection
    app.config['DB'] = db
    
    # Create geospatial index if not exists
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
    R = 6371
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
            '/buses - Bus booking page',
            '/stops - All bus stops',
            '/nearby-stops - Find nearby stops',
            '/api/buses - Bus information',
            '/api/buses/search - Search buses with filters',
            '/api/buses/clear-all-buses - Clear all fake buses',
            '/api/buses/insert-real-buses - Insert real bus data',
            '/api/stats - Database statistics',
            '/test-db - Test database connection'
        ]
    })

@app.route("/dashboard")
def dashboard():
    """Dashboard route - serves the HTML interface"""
    return render_template('index.html')

@app.route("/buses")
def buses_page():
    """Bus booking page - similar to MakeMyTrip"""
    return render_template('buses.html')

@app.route("/seats")
def seats_page():
    """Seat selection page"""
    return render_template('seats.html')

# ========== OFFER REDIRECT ROUTES ==========

@app.route("/offer/mmt")
def offer_mmt():
    """Redirect to MakeMyTrip with MMT offer"""
    return redirect("https://www.makemytrip.com/bus/")

@app.route("/offer/mydeal")
def offer_mydeal():
    """Redirect to MakeMyTrip with MyDeal offer"""
    return redirect("https://www.makemytrip.com/bus/")

# ========== STOPS ROUTES ==========

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
        radius = float(request.args.get("radius", 5000))
        
        is_valid, valid_lat, valid_lng = validate_coordinates(lat, lng)
        if not is_valid:
            return jsonify({"error": "Invalid coordinates"}), 400
        
        result = []
        
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
                        "location": {"type": "Point", "coordinates": coordinates},
                        "distance_km": round(distance, 2)
                    })
            
            result.sort(key=lambda x: x["distance_km"])
            
        except Exception as geo_error:
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
    if buses_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        buses = buses_collection.find()
        
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
                "available_seats": bus.get("available_seats", bus.get("capacity", 50)),
                "rating": bus.get("rating"),
                "status": bus.get("status", "inactive"),
                "current_location": bus.get("current_location", {})
            })
        
        return jsonify(result)
    except Exception as e:
        print(f"Error in get_buses: {e}")
        return jsonify({"error": str(e)}), 500

# ========== BUS BOOKING API ENDPOINTS ==========

@app.route("/api/buses/clear-all-buses", methods=["DELETE"])
def clear_all_buses():
    """Clear all existing buses from database"""
    if buses_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        result = buses_collection.delete_many({})
        return jsonify({
            "success": True,
            "message": f"Deleted {result.deleted_count} buses"
        })
    except Exception as e:
        print(f"Error clearing buses: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/buses/search")
def search_buses_api():
    """Search buses with filters and pagination"""
    if buses_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        from_city = request.args.get('from', '')
        to_city = request.args.get('to', '')
        date = request.args.get('date', '')
        ac_type = request.args.get('ac_type', '')
        seat_type = request.args.get('seat_type', '')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 10))
        sort_by = request.args.get('sort_by', 'relevance')
        sort_order = request.args.get('sort_order', 'asc')
        
        skip = (page - 1) * limit
        
        # Build query
        query = {}
        
        if from_city:
            query['from_city'] = {'$regex': from_city, '$options': 'i'}
        if to_city:
            query['to_city'] = {'$regex': to_city, '$options': 'i'}
        
        if ac_type:
            query['ac_type'] = ac_type
        
        if seat_type:
            query['seat_type'] = seat_type
        
        # Build sort
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
        print(f"Error in search_buses_api: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/buses/insert-real-buses", methods=["POST"])
def insert_real_buses():
    """Insert the real bus data from the screenshots"""
    if buses_collection is None:
        return jsonify({"error": "Database not connected"}), 503
    
    try:
        # Real bus data from screenshots (ONLY THESE 4 BUSES)
        real_buses = [
            {
                "bus_name": "VISHWAKARMA TRAVELS",
                "operator_name": "VISHWAKARMA TRAVELS",
                "ac_type": "NON A/C",
                "seat_type": "Sleeper",
                "price": 5000,
                "original_price": 5000,
                "discount": 0,
                "from_city": "Bhilad",
                "to_city": "Vapi",
                "departure_time": "13:15",
                "arrival_time": "13:45",
                "duration": "00h 30m",
                "available_seats": 37,
                "single_seats": 11,
                "rating": 4.2,
                "reviews_count": 234,
                "amenities": ["Water Bottle", "Charging Point", "Reading Light"],
                "pickup_points": ["Bhilad (Naroli Fatak) - Giriraj Kathiyawadi Hotel", "Bhilad Hanuman Mandir", "Bhilad Railway Station Highway"],
                "drop_points": ["Vapi (Gunjan Chokdi NH-48) - Hotel Pappilion", "Gunjan Chokdi", "Vapi Ayush Hospital"],
                "cancellation_policy": "Partial cancellation not allowed",
                "cancellation_policy_details": {
                    "more_than_24hrs": {"percentage": 50, "amount": 2500},
                    "12_to_24hrs": {"percentage": 80, "amount": 4000},
                    "0_to_12hrs": {"percentage": 100, "amount": 5000}
                },
                "travel_policy": {
                    "child_passenger": "Children above age 5 need ticket",
                    "luggage": "2 pieces free, excess chargeable",
                    "pets": "Not allowed",
                    "liquor": "Prohibited",
                    "pickup_time": "Operator not obligated to wait"
                },
                "is_prime": False,
                "status": "active"
            },
            {
                "bus_name": "JAY KHODIYAR BUS SERVICE",
                "operator_name": "JAY KHODIYAR BUS SERVICE",
                "ac_type": "NON A/C",
                "seat_type": "Sleeper",
                "price": 1890,
                "original_price": 2100,
                "discount": 210,
                "from_city": "Bhilad",
                "to_city": "Vapi",
                "departure_time": "03:00",
                "arrival_time": "03:30",
                "duration": "00h 30m",
                "available_seats": 32,
                "single_seats": 10,
                "rating": 4.5,
                "reviews_count": 567,
                "amenities": ["Water Bottle", "Charging Point", "Reading Light", "Blanket"],
                "pickup_points": ["Bhilad (Naroli Fatak) - Giriraj Kathiyawadi Hotel", "Bhilad Hanuman Mandir"],
                "drop_points": ["Vapi (Gunjan Chokdi NH-48) - Hotel Pappilion", "GUNJAN CHOKDI, HIGHWAY", "Vapi Ayush Hospital"],
                "cancellation_policy": "Free cancellation available",
                "cancellation_policy_details": {
                    "more_than_24hrs": {"percentage": 15, "amount": 375},
                    "12_to_24hrs": {"percentage": 20, "amount": 500},
                    "4_to_12hrs": {"percentage": 50, "amount": 1250},
                    "0_to_4hrs": {"percentage": 100, "amount": 2500}
                },
                "travel_policy": {
                    "child_passenger": "Children above age 5 need ticket",
                    "luggage": "2 pieces free, excess chargeable",
                    "pets": "Not allowed",
                    "liquor": "Prohibited",
                    "pickup_time": "Operator not obligated to wait"
                },
                "is_prime": True,
                "status": "active"
            },
            {
                "bus_name": "Jay Travels (Ekta Travels)",
                "operator_name": "Jay Travels (Ekta Travels)",
                "ac_type": "NON A/C",
                "seat_type": "Sleeper",
                "price": 900,
                "original_price": 900,
                "discount": 0,
                "from_city": "Bhilad",
                "to_city": "Vapi",
                "departure_time": "16:45",
                "arrival_time": "17:00",
                "duration": "00h 15m",
                "available_seats": 32,
                "single_seats": 10,
                "rating": 4.1,
                "reviews_count": 345,
                "amenities": ["Charging Point", "Reading Light"],
                "pickup_points": ["Bhilad (Naroli Fatak) - Giriraj Kathiyawadi Hotel"],
                "drop_points": ["Vapi (Gunjan Chokdi NH-48) - Hotel Pappilion"],
                "cancellation_policy": "Partial cancellation not allowed",
                "cancellation_policy_details": {
                    "more_than_48hrs": {"percentage": 10, "amount": 90},
                    "24_to_48hrs": {"percentage": 20, "amount": 180},
                    "12_to_24hrs": {"percentage": 40, "amount": 360},
                    "8_to_12hrs": {"percentage": 50, "amount": 450},
                    "0_to_8hrs": {"percentage": 100, "amount": 900}
                },
                "travel_policy": {
                    "child_passenger": "Children above age 5 need ticket",
                    "luggage": "2 pieces free, excess chargeable",
                    "pets": "Not allowed",
                    "liquor": "Prohibited"
                },
                "is_prime": True,
                "status": "active"
            },
            {
                "bus_name": "J K travels",
                "operator_name": "J K travels",
                "ac_type": "NON A/C",
                "seat_type": "Sleeper",
                "price": 1500,
                "original_price": 1500,
                "discount": 0,
                "from_city": "Bhilad",
                "to_city": "Vapi",
                "departure_time": "18:30",
                "arrival_time": "18:55",
                "duration": "00h 25m",
                "available_seats": 45,
                "single_seats": 15,
                "rating": 3.9,
                "reviews_count": 189,
                "amenities": ["Water Bottle", "Charging Point"],
                "pickup_points": ["Bhilad Bus Stand", "Bhilad Chokdi"],
                "drop_points": ["Vapi Bus Stand", "Vapi Railway Station"],
                "cancellation_policy": "Free cancellation up to 6 hours",
                "travel_policy": {
                    "child_passenger": "Children above age 5 need ticket",
                    "luggage": "2 pieces free",
                    "pets": "Not allowed"
                },
                "is_prime": False,
                "status": "active"
            }
        ]
        
        # Clear existing buses first
        deleted_count = buses_collection.delete_many({}).deleted_count
        
        # Insert real buses
        buses_collection.insert_many(real_buses)
        
        return jsonify({
            "success": True,
            "message": f"Deleted {deleted_count} fake buses and inserted {len(real_buses)} real buses",
            "total_buses": len(real_buses)
        })
        
    except Exception as e:
        print(f"Error inserting real buses: {e}")
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
                "bus_name": sample_bus.get("bus_name") if sample_bus else None
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
    
    print("\n📱 Access the app at: http://127.0.0.1:5000/")
    print("🚌 Bus Booking Page: http://127.0.0.1:5000/buses")
    print("📍 Dashboard: http://127.0.0.1:5000/dashboard")
    print("🎫 Seat Selection: http://127.0.0.1:5000/seats")
    print("🔧 API endpoints available at: http://127.0.0.1:5000/")
    print("🧪 Test database: http://127.0.0.1:5000/test-db")
    print("="*50 + "\n")
    
    app.run(debug=True, host='127.0.0.1', port=5000)