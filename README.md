#  Bus Tracker - Real-time Bus Tracking System
A modern, intelligent bus tracking and monitoring system with real-time location tracking, traffic-aware ETA calculations, and driver management.

# Core Features
- **Live Bus Tracking** - Real-time GPS tracking of buses on interactive map
- **Traffic-Intelligent ETA** - Smart arrival time predictions based on time of day
- **Nearest Stop Finder** - Find closest bus stops with walking distance & time
- **Route Planning** - Search routes between any two locations with OSRM integration
- **Satellite & Street View** - Toggle between map and satellite views

# Driver Management
- **Driver Registration** - Drivers must register before sharing location
- **Admin Approval System** - Admin approval required for location sharing
- **Real-time Location Sharing** - Drivers share live location every 5 seconds

# User Features
- **Book Buses** - Redirect to MakeMyTrip for ticket booking
- **All Bus Stops** - Browse 500+ bus stops across Gujarat
- **Live Tracking Modal** - View actively sharing buses
- **Notifications** - Real-time alerts for bus updates

# 🛠️ Tech Stack
# Backend
- **Framework**: Flask 2.3.3
- **Database**: MongoDB (PyMongo 4.5.0)
- **Server**: Gunicorn (Production)
- **APIs**: OSRM Routing, Nominatim Geocoding

# Frontend
- **Map**: Leaflet.js
- **Icons**: Font Awesome 6
- **Styling**: Custom CSS with Glassmorphism
- **JavaScript**: Vanilla JS with async/await

# Development Tools
- **Version Control**: Git & GitHub
- **Environment**: Python 3.11+
- **Package Manager**: pip




##### Project Structure #####
bus-tracker/
├── app.py # Main Flask application
├── requirements.txt # Python dependencies
├── .env # Environment variables
├── routes/
│ ├── bus_routes.py # Bus API endpoints
│ └── stop_routes.py # Stop API endpoints
├── templates/
│ ├── index.html # Dashboard
│ ├── buses.html # Bus booking page
│ ├── seats.html # Seat selection layout
│ ├── driver.html # Driver mode
│ ├── driver-register.html # Driver registration
│ └── admin.html # Admin approval panel
├── static/
│ ├── script.js # Frontend JavaScript
│ └── style.css # Custom styles
└── database/
└── mongo.py # Database utilities



## 🚀 Installation & Setup
# Prerequisites
- Python 3.11 or higher
- MongoDB (local or Atlas)
- Git


# Step 1: Clone Repository
```bash
git clone https://github.com/Pavneshh/bus-tracker.git
cd bus-tracker


Step 2: Create Virtual Environment
bash
# Windows
python -m venv venv
venv\Scripts\activate
# Mac/Linux
python3 -m venv venv
source venv/bin/activate


Step 3: Install Dependencies
bash
pip install -r requirements.txt


Step 4: Setup MongoDB
bash
# Local MongoDB
mongod
# OR use MongoDB Atlas (cloud)
# Get connection string from MongoDB Atlas


Step 5: Environment Variables
Create .env file:

env
MONGO_URI=mongodb://localhost:27017/
SECRET_KEY=your-secret-key-here
FLASK_ENV=development


Step 6: Seed Database
bash
# Insert real bus data
python -c "
from pymongo import MongoClient
client = MongoClient('mongodb://localhost:27017/')
db = client['bus_tracker']
# Insert your bus data here
"

Step 7: Run Application
bash
python app.py


Step 8: Access Application
Open browser and navigate to:
Dashboard: http://127.0.0.1:5000/dashboard
Driver Mode: http://127.0.0.1:5000/driver
Admin Panel: http://127.0.0.1:5000/admin
Bus Booking: http://127.0.0.1:5000/buses




##################  ABOUT  ############### 
 Route Coverage
Bhilad to Mumbai

# Traffic Intelligence Logic
Time Slot	Traffic Condition	Time Multiplier
8-10 AM, 5-7 PM	Heavy Traffic	+80%
7-8 AM, 7-8 PM	Moderate Traffic	+50%
10 AM - 5 PM	Normal Traffic	+20%
10 PM - 5 AM	Light Traffic	-20%
Distance Buffers:
80km: +40% buffer
50km: +35% buffer
30km: +30% buffer
15km: +25% buffer
≤15km: +20% buffer

# Driver Approval System
Driver Flow:
Driver registers on /driver-register
Admin approves/rejects on /admin
Approved drivers can share location on /driver
Location broadcasts every 5 seconds
Admin Flow:
Login to /admin
View pending driver requests
Approve or reject drivers
Approved drivers appear in live tracking

# API Endpoints
Bus Tracking
Endpoint	Method	Description
/api/buses	GET	Get all buses
/api/buses/live	GET	Get actively sharing buses
/api/buses/<id>/location	POST	Update bus location
Driver Management
Endpoint	Method	Description
/api/drivers/register	POST	Register new driver
/api/drivers/status/<id>	GET	Check driver status
/api/drivers/pending	GET	Get pending requests
/api/drivers/approve/<id>	POST	Approve driver
/api/drivers/reject/<id>	POST	Reject driver
Stops & Routes
Endpoint	Method	Description
/stops	GET	Get all bus stops
/nearby-stops	GET	Find nearby stops
/stops/search	GET	Search stops by name
/api/buses/search	GET	Search buses with filters

# OSRM Integration
The system uses OSRM (Open Source Routing Machine) for:
Real-time route calculation
Distance and duration estimates
Traffic-adjusted ETAs

#Supported Bus Operators
VISHWAKARMA TRAVELS
JAY KHODIYAR BUS SERVICE
Jay Travels (Ekta Travels)
J K travels

# Security Features
Driver registration required
Admin approval system
No unauthorized location sharing
Input validation for coordinates
CORS properly configured

# Performance
Location Update Interval: 5 seconds
Live Buses Refresh: 10 seconds
Map Rendering: Leaflet.js optimized
Database Indexes: Geospatial indexes for fast queries

# UI/UX Features
Responsive design for mobile & desktop
Glassmorphism effects
Smooth animations
Dark-themed map controls
Toast notifications
Loading spinners
Debug panel for drivers

# Known Issues & Limitations#
Background Location: Browser tab must be open for location sharing
GPS Accuracy: Depends on device GPS
Internet Required: Real-time updates need active connection
No WebSocket: Uses polling (can be upgraded)

# Future Enhancements#
WebSocket for real-time updates
Push notifications
Trip history tracking
Geofencing alerts
Payment integration
Mobile app (React Native)
Multi-language support
Dark mode toggle
Driver earnings dashboard
Route optimization