"""Service for handling location-related operations"""

class LocationService:
    """Handles location tracking and updates"""
    
    def __init__(self):
        self.bus_locations = {}
    
    def update_bus_location(self, bus_id, latitude, longitude):
        """Update the location of a bus"""
        self.bus_locations[bus_id] = {
            'latitude': latitude,
            'longitude': longitude
        }
        return True
    
    def get_bus_location(self, bus_id):
        """Get the current location of a bus"""
        return self.bus_locations.get(bus_id, None)
    
    def get_all_bus_locations(self):
        """Get locations of all buses"""
        return self.bus_locations
