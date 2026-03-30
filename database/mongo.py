"""Database setup script for MongoDB"""

from pymongo import MongoClient
import os

def setup_database():
    """Initialize database with indexes and sample data"""
    
    client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017/'))
    db = client["bus_tracker"]
    
    # Create 2dsphere index for geospatial queries
    print("Creating geospatial index on stops...")
    db.stops.create_index([("location", "2dsphere")])
    
    print("Creating geospatial index on buses...")
    db.buses.create_index([("current_location", "2dsphere")])
    
    # Create other indexes for performance
    print("Creating indexes...")
    db.stops.create_index("name")
    db.stops.create_index("route_id")
    db.buses.create_index("bus_id", unique=True)
    db.buses.create_index("route_id")
    
    # Insert sample stops if collection is empty
    if db.stops.count_documents({}) == 0:
        print("Inserting sample stops...")
        sample_stops = [
            {
                "name": "Central Station",
                "location": {"type": "Point", "coordinates": [72.8777, 19.0760]},
                "sequence": 1,
                "route_id": "R001"
            },
            {
                "name": "Andheri Bus Depot",
                "location": {"type": "Point", "coordinates": [72.8514, 19.1190]},
                "sequence": 2,
                "route_id": "R001"
            },
            {
                "name": "Bandra Terminus",
                "location": {"type": "Point", "coordinates": [72.8400, 19.0596]},
                "sequence": 3,
                "route_id": "R001"
            },
            {
                "name": "Dadar Bus Stop",
                "location": {"type": "Point", "coordinates": [72.8480, 19.0178]},
                "sequence": 4,
                "route_id": "R001"
            }
        ]
        
        db.stops.insert_many(sample_stops)
        print(f"Inserted {len(sample_stops)} sample stops")
    
    # Insert sample bus
    if db.buses.count_documents({}) == 0:
        print("Inserting sample bus...")
        sample_bus = {
            "bus_id": "GJ05AB1234",
            "route_id": "R001",
            "capacity": 50,
            "current_passengers": 25,
            "status": "active",
            "current_location": {
                "type": "Point",
                "coordinates": [72.8600, 19.0900]
            }
        }
        
        db.buses.insert_one(sample_bus)
        print("Inserted sample bus")
    
    print("Database setup complete!")

if __name__ == "__main__":
    setup_database()