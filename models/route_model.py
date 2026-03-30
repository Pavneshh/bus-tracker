"""Route model for database"""

class Route:
    """Represents a bus route in the system"""
    
    def __init__(self, route_id, name, start_point, end_point, stops=None):
        self.route_id = route_id
        self.name = name
        self.start_point = start_point
        self.end_point = end_point
        self.stops = stops or []
    
    def add_stop(self, stop):
        """Add a stop to the route"""
        self.stops.append(stop)
    
    def __repr__(self):
        return f"<Route {self.name} ({self.start_point} -> {self.end_point})>"
