"""Stop-related API routes"""

from flask import Blueprint, jsonify, request, current_app
from bson.objectid import ObjectId
import os

stop_bp = Blueprint('stops', __name__)

@stop_bp.route('/', methods=['GET'])
def get_stops():
    """Get all stops"""
    try:
        stops_collection = current_app.config.get('STOPS_COLLECTION')
        
        if stops_collection is None:
            return jsonify({"error": "Database not connected"}), 503
        
        stops = stops_collection.find().limit(100)
        
        result = []
        for stop in stops:
            result.append({
                "id": str(stop["_id"]),
                "name": stop.get("name", "Unknown"),
                "city": stop.get("city", ""),
                "location": stop.get("location", {}),
                "sequence": stop.get("sequence")
            })
        
        return jsonify(result), 200
    except Exception as e:
        print(f"Error in get_stops: {e}")
        return jsonify({"error": str(e)}), 500

@stop_bp.route('/<stop_id>', methods=['GET'])
def get_stop(stop_id):
    """Get a specific stop"""
    try:
        stops_collection = current_app.config.get('STOPS_COLLECTION')
        
        if stops_collection is None:
            return jsonify({"error": "Database not connected"}), 503
        
        stop = stops_collection.find_one({"_id": ObjectId(stop_id)})
        if stop:
            return jsonify({
                "id": str(stop["_id"]),
                "name": stop.get("name", "Unknown"),
                "city": stop.get("city", ""),
                "location": stop.get("location", {}),
                "sequence": stop.get("sequence"),
                "route_id": stop.get("route_id")
            }), 200
        return jsonify({"error": "Stop not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Invalid stop ID: {str(e)}"}), 400