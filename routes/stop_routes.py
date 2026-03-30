# routes/stop_routes.py - Replace with this
from flask import Blueprint, jsonify, request, current_app
from bson.objectid import ObjectId

stop_bp = Blueprint('stops', __name__)

@stop_bp.route('/', methods=['GET'])
def get_stops():
    """Get all stops"""
    try:
        # Get stops collection from app config
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

# ... rest of your stop_routes.py functions