"""Stop model for database"""

class Stop:
    """Represents a bus stop in the system"""
    
    def __init__(self, stop_id, name, latitude, longitude, sequence=None, route_id=None):
        self.stop_id = stop_id
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.sequence = sequence
        self.route_id = route_id
    
    def to_dict(self):
        """Convert stop to dictionary for MongoDB"""
        return {
            "stop_id": self.stop_id,
            "name": self.name,
            "location": {
                "type": "Point",
                "coordinates": [self.longitude, self.latitude]
            },
            "sequence": self.sequence,
            "route_id": self.route_id
        }
    
    def __repr__(self):
        return f"<Stop {self.name} at ({self.latitude}, {self.longitude})>"