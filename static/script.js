// Initialize map centered on Gujarat
let map = L.map('map').setView([22.2587, 71.1924], 7);
let currentTileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
}).addTo(map);

let stopsLayer = L.layerGroup().addTo(map);
let busesLayer = L.layerGroup().addTo(map);
let userLocation = null;
let allStops = [];
let stopsVisible = true;
let isSatellite = false;
let currentMarkers = [];

// Load stops on map
async function loadStops() {
    try {
        const response = await fetch('/stops?limit=500');
        const data = await response.json();
        const stops = data.stops || data;
        
        allStops = stops;
        
        stopsLayer.clearLayers();
        currentMarkers = [];
        
        console.log(`Loaded ${stops.length} bus stops`);
        
        stops.forEach(stop => {
            let lat, lng;
            
            if (stop.location && stop.location.coordinates) {
                lng = stop.location.coordinates[0];
                lat = stop.location.coordinates[1];
            } else if (stop.latitude && stop.longitude) {
                lat = stop.latitude;
                lng = stop.longitude;
            } else {
                return;
            }
            
            if (lat && lng) {
                const marker = L.marker([lat, lng], {
                    icon: L.divIcon({
                        className: 'custom-marker',
                        html: '<i class="fas fa-bus-stop" style="color: #6366f1; font-size: 20px;"></i>',
                        iconSize: [20, 20],
                        popupAnchor: [0, -10]
                    })
                }).bindPopup(`
                    <div style="min-width: 150px;">
                        <b style="color: #6366f1;">${stop.name}</b><br>
                        ${stop.city ? `<small>📍 ${stop.city}</small><br>` : ''}
                        <small>Stop ID: ${stop.id}</small>
                    </div>
                `);
                marker.addTo(stopsLayer);
                currentMarkers.push(marker);
            }
        });
        
        if (currentMarkers.length > 0) {
            const group = L.featureGroup(currentMarkers);
            map.fitBounds(group.getBounds().pad(0.2));
        }
        
    } catch (error) {
        console.error('Error loading stops:', error);
        alert('Error loading bus stops. Please check if the server is running.');
    }
}

// Use my location
function useMyLocation() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(position => {
            const { latitude, longitude } = position.coords;
            document.getElementById('startInput').value = 'My Location';
            userLocation = { lat: latitude, lng: longitude };
            
            map.setView([latitude, longitude], 14);
            L.marker([latitude, longitude], {
                icon: L.divIcon({
                    className: 'user-marker',
                    html: '<i class="fas fa-user-circle" style="color: #10b981; font-size: 24px;"></i>',
                    iconSize: [24, 24]
                })
            }).addTo(map)
                .bindPopup('<b>Your Location</b><br>You are here!')
                .openPopup();
            
            map.closePopup();
            
            setTimeout(() => {
                getNearestStop();
            }, 1000);
            
        }, error => {
            console.error('Geolocation error:', error);
            alert('Unable to get your location. Please check location permissions.');
        });
    } else {
        alert('Geolocation is not supported by this browser.');
    }
}

// Geocode location using Nominatim
async function geocodeLocation(location) {
    if (location === 'My Location' && userLocation) {
        return userLocation;
    }
    
    try {
        const response = await fetch(
            `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(location)}&limit=1`
        );
        const data = await response.json();
        
        if (data && data[0]) {
            return {
                lat: parseFloat(data[0].lat),
                lng: parseFloat(data[0].lon)
            };
        }
    } catch (error) {
        console.error('Geocoding error:', error);
    }
    return null;
}

// Search route using OSRM
async function searchRoute() {
    const start = document.getElementById('startInput').value;
    const dest = document.getElementById('destInput').value;
    
    if (!start || !dest) {
        alert('Please enter both starting location and destination');
        return;
    }
    
    document.getElementById('routeDistance').textContent = 'Loading...';
    document.getElementById('routeTime').textContent = 'Loading...';
    
    try {
        const startCoords = await geocodeLocation(start);
        const destCoords = await geocodeLocation(dest);
        
        if (startCoords && destCoords) {
            const routeResponse = await fetch(
                `https://router.project-osrm.org/route/v1/driving/${startCoords.lng},${startCoords.lat};${destCoords.lng},${destCoords.lat}?overview=full&geometries=geojson`
            );
            const routeData = await routeResponse.json();
            
            if (routeData.routes && routeData.routes[0]) {
                const distance = routeData.routes[0].distance / 1000;
                const duration = routeData.routes[0].duration / 60;
                
                document.getElementById('routeDistance').textContent = `${distance.toFixed(1)} km`;
                document.getElementById('routeTime').textContent = `${Math.floor(duration / 60)} hr ${Math.floor(duration % 60)} min`;
                
                if (routeData.routes[0].geometry) {
                    if (window.currentRoute) {
                        map.removeLayer(window.currentRoute);
                    }
                    
                    window.currentRoute = L.geoJSON(routeData.routes[0].geometry, {
                        style: { color: '#6366f1', weight: 5, opacity: 0.7 }
                    }).addTo(map);
                    
                    setTimeout(() => {
                        map.fitBounds(window.currentRoute.getBounds());
                    }, 100);
                }
            }
        } else {
            alert('Could not find location coordinates');
        }
        
        loadBuses();
        
    } catch (error) {
        console.error('Error searching route:', error);
        document.getElementById('routeDistance').textContent = 'Error';
        document.getElementById('routeTime').textContent = 'Error';
    }
}

// Load available buses
async function loadBuses() {
    try {
        const response = await fetch('/api/buses');
        const buses = await response.json();
        
        const busesList = document.getElementById('busesList');
        
        if (buses.length === 0) {
            busesList.innerHTML = '<div class="loading-spinner"><p>No buses available at the moment</p></div>';
            return;
        }
        
        busesList.innerHTML = '';
        buses.forEach(bus => {
            const busCard = document.createElement('div');
            busCard.className = 'bus-card';
            busCard.innerHTML = `
                <div class="bus-number">${bus.bus_id}</div>
                <div class="bus-badge">${bus.status === 'active' ? 'Active' : 'Inactive'}</div>
                <div class="bus-time-row">
                    <span><i class="far fa-clock"></i> Route: ${bus.route_id || 'N/A'}</span>
                    <span><i class="fas fa-users"></i> ${bus.current_passengers || 0}/${bus.capacity || 50}</span>
                </div>
                <div class="bus-fare">Track Live</div>
            `;
            busCard.onclick = () => {
                if (bus.current_location && bus.current_location.coordinates) {
                    map.setView([bus.current_location.coordinates[1], bus.current_location.coordinates[0]], 15);
                    L.marker([bus.current_location.coordinates[1], bus.current_location.coordinates[0]])
                        .addTo(map)
                        .bindPopup(`<b>Bus ${bus.bus_id}</b><br>Currently tracking`)
                        .openPopup();
                }
            };
            busesList.appendChild(busCard);
        });
    } catch (error) {
        console.error('Error loading buses:', error);
        document.getElementById('busesList').innerHTML = '<div class="loading-spinner"><p>Error loading buses</p></div>';
    }
}

// Calculate distance between two points
function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

// Find nearest stop
async function findNearestStop() {
    if (!userLocation) {
        useMyLocation();
        setTimeout(() => {
            if (userLocation) {
                getNearestStop();
            } else {
                alert('Please enable location or enter a starting location');
            }
        }, 2000);
    } else {
        getNearestStop();
    }
}

// Close nearest stop card
function closeNearestStopCard() {
    document.getElementById('nearestStopCard').classList.add('hidden');
}

async function getNearestStop() {
    if (!userLocation) return;
    
    try {
        const response = await fetch(
            `/nearby-stops?lat=${userLocation.lat}&lng=${userLocation.lng}&radius=10000`
        );
        const stops = await response.json();
        
        if (stops && stops.length > 0) {
            const nearestStop = stops[0];
            const distance = nearestStop.distance_km || calculateDistance(
                userLocation.lat, userLocation.lng,
                nearestStop.location.coordinates[1],
                nearestStop.location.coordinates[0]
            );
            
            document.getElementById('nearestStopName').textContent = nearestStop.name;
            document.getElementById('nearestDist').textContent = `${distance.toFixed(1)} km`;
            document.getElementById('nearestTime').textContent = `${Math.floor(distance * 12)} min`;
            document.getElementById('nearestStraight').textContent = `${distance.toFixed(1)} km`;
            document.getElementById('nearestStopCard').classList.remove('hidden');
            
            // Highlight nearest stop on map
            L.marker([nearestStop.location.coordinates[1], nearestStop.location.coordinates[0]], {
                icon: L.divIcon({
                    className: 'nearest-marker',
                    html: '<i class="fas fa-star" style="color: #fbbf24; font-size: 28px;"></i>',
                    iconSize: [28, 28]
                })
            }).addTo(map)
                .bindPopup(`
                    <b>Nearest Stop: ${nearestStop.name}</b><br>
                    Distance: ${distance.toFixed(1)} km<br>
                    Walking time: ~${Math.floor(distance * 12)} min
                `)
                .openPopup();
                
            setTimeout(() => {
                map.closePopup();
            }, 5000);
        } else {
            alert('No stops found within 10km radius');
        }
    } catch (error) {
        console.error('Error finding nearest stop:', error);
        alert('Could not find nearest stop');
    }
}

// Show all bus stops in a modal with search functionality
function showAllStops() {
    // Create modal if not exists
    let allStopsModal = document.getElementById('allStopsModal');
    
    if (!allStopsModal) {
        allStopsModal = document.createElement('div');
        allStopsModal.id = 'allStopsModal';
        allStopsModal.className = 'modal-overlay hidden';
        allStopsModal.innerHTML = `
            <div class="modal-content all-stops-modal">
                <div class="modal-header">
                    <i class="fas fa-list-ul"></i> All Bus Stops
                </div>
                <div class="stops-search-container">
                    <input type="text" id="stopSearchInput" placeholder="🔍 Search bus stops by name or city...">
                </div>
                <div class="stops-list-container" id="stopsListContainer">
                    <div class="loading-spinner">
                        <div class="spinner"></div>
                        <p>Loading stops...</p>
                    </div>
                </div>
                <button class="close-modal" id="closeAllStopsModal">Close</button>
            </div>
        `;
        document.body.appendChild(allStopsModal);
        
        document.getElementById('closeAllStopsModal').addEventListener('click', () => {
            allStopsModal.classList.add('hidden');
        });
        
        document.getElementById('stopSearchInput').addEventListener('input', (e) => {
            renderStopsList(e.target.value);
        });
        
        allStopsModal.addEventListener('click', (e) => {
            if (e.target === allStopsModal) {
                allStopsModal.classList.add('hidden');
            }
        });
    }
    
    allStopsModal.classList.remove('hidden');
    renderStopsList('');
}

function renderStopsList(searchTerm = '') {
    const container = document.getElementById('stopsListContainer');
    if (!container) return;
    
    let filteredStops = allStops;
    
    if (searchTerm) {
        const term = searchTerm.toLowerCase();
        filteredStops = allStops.filter(stop => 
            stop.name.toLowerCase().includes(term) || 
            (stop.city && stop.city.toLowerCase().includes(term))
        );
    }
    
    if (filteredStops.length === 0) {
        container.innerHTML = '<div class="loading-spinner"><p>No stops found</p></div>';
        return;
    }
    
    container.innerHTML = '';
    
    filteredStops.forEach(stop => {
        let lat, lng;
        
        if (stop.location && stop.location.coordinates) {
            lng = stop.location.coordinates[0];
            lat = stop.location.coordinates[1];
        } else if (stop.latitude && stop.longitude) {
            lat = stop.latitude;
            lng = stop.longitude;
        } else {
            return;
        }
        
        const stopDiv = document.createElement('div');
        stopDiv.className = 'stop-list-item';
        
        let distanceText = '';
        if (userLocation && lat && lng) {
            const distance = calculateDistance(userLocation.lat, userLocation.lng, lat, lng);
            distanceText = `<div class="distance-badge">📍 ${distance.toFixed(1)} km from you</div>`;
        }
        
        stopDiv.innerHTML = `
            <strong>${stop.name}</strong>
            <small>${stop.city ? `🏙️ ${stop.city}` : ''}</small>
            ${distanceText}
        `;
        
        stopDiv.onclick = () => {
            if (lat && lng) {
                map.setView([lat, lng], 15);
                L.marker([lat, lng], {
                    icon: L.divIcon({
                        className: 'selected-marker',
                        html: '<i class="fas fa-map-marker-alt" style="color: #ec489a; font-size: 28px;"></i>',
                        iconSize: [28, 28]
                    })
                }).addTo(map)
                    .bindPopup(`<b>${stop.name}</b><br>${stop.city ? stop.city : ''}`)
                    .openPopup();
                
                allStopsModal.classList.add('hidden');
                
                setTimeout(() => {
                    map.closePopup();
                }, 5000);
            }
        };
        
        container.appendChild(stopDiv);
    });
}

// Toggle stops visibility
function toggleStops() {
    const hideBtn = document.getElementById('hideStopsBtn');
    if (stopsVisible) {
        map.removeLayer(stopsLayer);
        hideBtn.innerHTML = '<i class="fas fa-eye"></i> Show Stops';
        stopsVisible = false;
    } else {
        stopsLayer.addTo(map);
        hideBtn.innerHTML = '<i class="fas fa-eye-slash"></i> Hide Stops';
        stopsVisible = true;
    }
}

// Toggle satellite view
function toggleSatellite() {
    map.removeLayer(currentTileLayer);
    
    if (!isSatellite) {
        currentTileLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Esri'
        }).addTo(map);
        document.getElementById('satelliteToggleBtn').innerHTML = '<i class="fa-solid fa-map"></i> Map';
        isSatellite = true;
    } else {
        currentTileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);
        document.getElementById('satelliteToggleBtn').innerHTML = '<i class="fa-solid fa-satellite"></i> Satellite';
        isSatellite = false;
    }
}

// Modal handling
function showMenuModal() {
    document.getElementById('menuModal').classList.remove('hidden');
}

function showAboutModal() {
    document.getElementById('aboutModal').classList.remove('hidden');
}

function closeModals() {
    document.getElementById('menuModal').classList.add('hidden');
    document.getElementById('aboutModal').classList.add('hidden');
}

// Event Listeners
document.getElementById('menuIcon').addEventListener('click', showMenuModal);
document.getElementById('aboutBtn').addEventListener('click', showAboutModal);
document.getElementById('closeMenuModal').addEventListener('click', closeModals);
document.getElementById('closeAboutModal').addEventListener('click', closeModals);
document.getElementById('myLocationBtn').addEventListener('click', useMyLocation);
document.getElementById('searchRouteBtn').addEventListener('click', searchRoute);
document.getElementById('findNearestStopBtn').addEventListener('click', findNearestStop);
document.getElementById('hideStopsBtn').addEventListener('click', toggleStops);
document.getElementById('satelliteToggleBtn').addEventListener('click', toggleSatellite);

// Add close button for nearest stop card
document.addEventListener('DOMContentLoaded', () => {
    const nearestCard = document.getElementById('nearestStopCard');
    const closeBtn = document.createElement('button');
    closeBtn.className = 'close-stop-card';
    closeBtn.innerHTML = '<i class="fas fa-times"></i>';
    closeBtn.onclick = closeNearestStopCard;
    nearestCard.insertBefore(closeBtn, nearestCard.firstChild);
});

// Add menu item for showing all stops
document.addEventListener('DOMContentLoaded', () => {
    const menuItems = document.querySelectorAll('.menu-list li');
    menuItems.forEach(item => {
        if (item.innerHTML.includes('Show All Bus Stops')) {
            item.addEventListener('click', () => {
                closeModals();
                showAllStops();
            });
        }
    });
});

// Close modals when clicking outside
window.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) {
        closeModals();
    }
});

// Initialize
loadStops();
loadBuses();

// Auto-find nearest stop if location is available
if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(position => {
        userLocation = {
            lat: position.coords.latitude,
            lng: position.coords.longitude
        };
        map.setView([userLocation.lat, userLocation.lng], 13);
    });
}

// Refresh buses every 30 seconds
setInterval(loadBuses, 30000);

// Load stats
async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();
        console.log('Stats:', stats);
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}
loadStats();