"""Service for bus tracking operations"""

from services.location_service import LocationService
from services.distance_service import DistanceService

class TrackingService:
    """Handles real-time tracking of buses"""
    
    def __init__(self):
        self.location_service = LocationService()
        self.distance_service = DistanceService()
    
    def track_bus(self, bus_id, latitude, longitude):
        """Track a bus by updating its location"""
        return self.location_service.update_bus_location(bus_id, latitude, longitude)
    
    def get_bus_info(self, bus_id):
        """Get information about a tracked bus"""
        location = self.location_service.get_bus_location(bus_id)
        if location:
            return {
                'bus_id': bus_id,
                'latitude': location['latitude'],
                'longitude': location['longitude'],
                'status': 'active'
            }
        return None
    
    def get_distance_to_stop(self, bus_id, stop_latitude, stop_longitude):
        """Calculate distance from bus to a stop"""
        bus_location = self.location_service.get_bus_location(bus_id)
        if bus_location:
            distance = self.distance_service.haversine_distance(
                bus_location['latitude'],
                bus_location['longitude'],
                stop_latitude,
                stop_longitude
            )
            eta = self.distance_service.calculate_eta(distance)
            return {'distance_km': distance, 'eta_minutes': eta}
        return None
