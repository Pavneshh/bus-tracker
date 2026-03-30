"""Stop-related API routes"""

from flask import Blueprint, jsonify, request
from pymongo import MongoClient
from bson.objectid import ObjectId
import os

stop_bp = Blueprint('stops', __name__)

# MongoDB connection
client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017/'))
db = client["bus_tracker"]

@stop_bp.route('/', methods=['GET'])
def get_stops():
    """Get all stops"""
    stops = db.stops.find().limit(100)
    
    result = []
    for stop in stops:
        result.append({
            "id": str(stop["_id"]),
            "name": stop["name"],
            "location": stop.get("location", {}),
            "sequence": stop.get("sequence")
        })
    
    return jsonify(result), 200

@stop_bp.route('/<stop_id>', methods=['GET'])
def get_stop(stop_id):
    """Get a specific stop"""
    try:
        stop = db.stops.find_one({"_id": ObjectId(stop_id)})
        if stop:
            return jsonify({
                "id": str(stop["_id"]),
                "name": stop["name"],
                "location": stop.get("location", {}),
                "sequence": stop.get("sequence"),
                "route_id": stop.get("route_id")
            }), 200
        return jsonify({"error": "Stop not found"}), 404
    except:
        return jsonify({"error": "Invalid stop ID"}), 400

@stop_bp.route('/', methods=['POST'])
def create_stop():
    """Create a new stop"""
    data = request.get_json()
    
    if not data or 'name' not in data or 'latitude' not in data or 'longitude' not in data:
        return jsonify({"error": "Missing required fields: name, latitude, longitude"}), 400
    
    stop_doc = {
        "name": data['name'],
        "location": {
            "type": "Point",
            "coordinates": [float(data['longitude']), float(data['latitude'])]
        },
        "sequence": data.get('sequence'),
        "route_id": data.get('route_id')
    }
    
    result = db.stops.insert_one(stop_doc)
    
    return jsonify({
        "id": str(result.inserted_id),
        "message": "Stop created successfully"
    }), 201

@stop_bp.route('/<stop_id>', methods=['PUT'])
def update_stop(stop_id):
    """Update a stop"""
    data = request.get_json()
    
    try:
        update_data = {}
        
        if 'name' in data:
            update_data['name'] = data['name']
        
        if 'latitude' in data and 'longitude' in data:
            update_data['location'] = {
                "type": "Point",
                "coordinates": [float(data['longitude']), float(data['latitude'])]
            }
        
        if 'sequence' in data:
            update_data['sequence'] = data['sequence']
        
        if 'route_id' in data:
            update_data['route_id'] = data['route_id']
        
        result = db.stops.update_one(
            {"_id": ObjectId(stop_id)},
            {"$set": update_data}
        )
        
        if result.modified_count:
            return jsonify({"message": "Stop updated successfully"}), 200
        return jsonify({"error": "Stop not found"}), 404
    except:
        return jsonify({"error": "Invalid stop ID"}), 400

@stop_bp.route('/<stop_id>', methods=['DELETE'])
def delete_stop(stop_id):
    """Delete a stop"""
    try:
        result = db.stops.delete_one({"_id": ObjectId(stop_id)})
        
        if result.deleted_count:
            return jsonify({"message": "Stop deleted successfully"}), 200
        return jsonify({"error": "Stop not found"}), 404
    except:
        return jsonify({"error": "Invalid stop ID"}), 400