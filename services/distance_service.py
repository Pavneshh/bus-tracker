"""Service for calculating distances"""

import math

class DistanceService:
    """Handles distance calculations between locations"""
    
    @staticmethod
    def haversine_distance(lat1, lon1, lat2, lon2):
        """
        Calculate the great circle distance between two points 
        on the earth (specified in decimal degrees)
        Returns distance in kilometers
        """
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 6371  # Radius of earth in kilometers
        
        return c * r
    
    @staticmethod
    def calculate_eta(distance_km, average_speed_kmh=30):
        """
        Calculate estimated time of arrival in minutes
        """
        if average_speed_kmh == 0:
            return 0
        return (distance_km / average_speed_kmh) * 60
