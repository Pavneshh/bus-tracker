"""Bus model for database"""

class Bus:
    """Represents a bus in the system"""
    
    def __init__(self, bus_id, route_id, latitude, longitude, capacity=50):
        self.bus_id = bus_id
        self.route_id = route_id
        self.latitude = latitude
        self.longitude = longitude
        self.capacity = capacity
        self.current_passengers = 0
    
    def __repr__(self):
        return f"<Bus {self.bus_id} at ({self.latitude}, {self.longitude})>"
