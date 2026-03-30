"""Bus-related API routes"""

from flask import Blueprint, jsonify, request
from pymongo import MongoClient
from bson.objectid import ObjectId
import os
from datetime import datetime

bus_bp = Blueprint('buses', __name__)

# MongoDB connection
client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017/'))
db = client["bus_tracker"]

# Import services
from services.tracking_service import TrackingService
tracking_service = TrackingService()

@bus_bp.route('/', methods=['GET'])
def get_buses():
    """Get all buses"""
    buses = db.buses.find()
    
    result = []
    for bus in buses:
        result.append({
            "id": str(bus["_id"]),
            "bus_id": bus.get("bus_id"),
            "route_id": bus.get("route_id"),
            "capacity": bus.get("capacity"),
            "status": bus.get("status", "active"),
            "current_location": bus.get("current_location", {})
        })
    
    return jsonify(result), 200

@bus_bp.route('/<bus_id>', methods=['GET'])
def get_bus(bus_id):
    """Get a specific bus"""
    try:
        bus = db.buses.find_one({"bus_id": bus_id})
        if bus:
            return jsonify({
                "id": str(bus["_id"]),
                "bus_id": bus["bus_id"],
                "route_id": bus.get("route_id"),
                "capacity": bus.get("capacity"),
                "current_passengers": bus.get("current_passengers", 0),
                "status": bus.get("status", "active"),
                "current_location": bus.get("current_location", {})
            }), 200
        return jsonify({"error": "Bus not found"}), 404
    except:
        return jsonify({"error": "Invalid bus ID"}), 400

@bus_bp.route('/', methods=['POST'])
def create_bus():
    """Create a new bus"""
    data = request.get_json()
    
    if not data or 'bus_id' not in data:
        return jsonify({"error": "Missing required field: bus_id"}), 400
    
    bus_doc = {
        "bus_id": data['bus_id'],
        "route_id": data.get('route_id'),
        "capacity": data.get('capacity', 50),
        "current_passengers": 0,
        "status": "active",
        "created_at": datetime.utcnow()
    }
    
    result = db.buses.insert_one(bus_doc)
    
    return jsonify({
        "id": str(result.inserted_id),
        "message": "Bus created successfully"
    }), 201

@bus_bp.route('/<bus_id>/location', methods=['GET'])
def get_bus_location(bus_id):
    """Get current location of a bus"""
    bus = db.buses.find_one({"bus_id": bus_id})
    
    if bus and bus.get('current_location'):
        return jsonify({
            'bus_id': bus_id,
            'latitude': bus['current_location']['coordinates'][1],
            'longitude': bus['current_location']['coordinates'][0],
            'last_updated': bus.get('location_updated_at')
        }), 200
    
    return jsonify({'error': 'Bus location not found'}), 404

@bus_bp.route('/<bus_id>/location', methods=['POST'])
def update_bus_location(bus_id):
    """Update bus location"""
    data = request.get_json()
    
    if not data or 'latitude' not in data or 'longitude' not in data:
        return jsonify({"error": "Missing latitude and longitude"}), 400
    
    try:
        lat = float(data['latitude'])
        lng = float(data['longitude'])
        
        # Update location in MongoDB
        result = db.buses.update_one(
            {"bus_id": bus_id},
            {
                "$set": {
                    "current_location": {
                        "type": "Point",
                        "coordinates": [lng, lat]
                    },
                    "location_updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count:
            # Also update tracking service
            tracking_service.track_bus(bus_id, lat, lng)
            
            return jsonify({
                'bus_id': bus_id,
                'message': 'Location updated',
                'latitude': lat,
                'longitude': lng
            }), 200
        
        return jsonify({'error': 'Bus not found'}), 404
    except ValueError:
        return jsonify({'error': 'Invalid coordinates'}), 400

@bus_bp.route('/route/<route_id>', methods=['GET'])
def get_buses_by_route(route_id):
    """Get all buses on a specific route"""
    buses = db.buses.find({"route_id": route_id, "status": "active"})
    
    result = []
    for bus in buses:
        result.append({
            "bus_id": bus["bus_id"],
            "capacity": bus.get("capacity"),
            "current_passengers": bus.get("current_passengers", 0),
            "current_location": bus.get("current_location", {})
        })
    
    return jsonify({
        'route_id': route_id,
        'buses': result
    }), 200

@bus_bp.route('/<bus_id>/eta/<stop_id>', methods=['GET'])
def get_bus_eta_to_stop(bus_id, stop_id):
    """Get ETA for bus to reach a specific stop"""
    try:
        # Get bus location
        bus = db.buses.find_one({"bus_id": bus_id})
        if not bus or not bus.get('current_location'):
            return jsonify({'error': 'Bus location not found'}), 404
        
        # Get stop location
        stop = db.stops.find_one({"_id": ObjectId(stop_id)})
        if not stop:
            return jsonify({'error': 'Stop not found'}), 404
        
        bus_lat = bus['current_location']['coordinates'][1]
        bus_lng = bus['current_location']['coordinates'][0]
        
        stop_lat = stop['location']['coordinates'][1]
        stop_lng = stop['location']['coordinates'][0]
        
        # Calculate distance and ETA
        eta_info = tracking_service.get_distance_to_stop(bus_id, stop_lat, stop_lng)
        
        if eta_info:
            return jsonify({
                'bus_id': bus_id,
                'stop_id': stop_id,
                'stop_name': stop['name'],
                'distance_km': eta_info['distance_km'],
                'eta_minutes': eta_info['eta_minutes']
            }), 200
        
        return jsonify({'error': 'Could not calculate ETA'}), 500
    except:
        return jsonify({'error': 'Invalid IDs'}), 400