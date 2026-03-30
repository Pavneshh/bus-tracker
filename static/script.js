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

// ========== TRAFFIC & ETA CALCULATION FUNCTIONS ==========

// Calculate ETA with traffic and distance-based logic
function calculateRealisticETA(distance_km, base_duration_minutes) {
    const SPEEDS = {
        ideal: 45,
        moderate: 35,
        heavy: 25,
        peak: 20
    };
    
    const currentHour = new Date().getHours();
    let trafficFactor = 1.0;
    let trafficCondition = "Normal";
    
    if ((currentHour >= 8 && currentHour <= 10) || (currentHour >= 17 && currentHour <= 19)) {
        trafficFactor = 1.8;
        trafficCondition = "Heavy Traffic";
    } else if ((currentHour >= 7 && currentHour < 8) || (currentHour >= 19 && currentHour < 20)) {
        trafficFactor = 1.5;
        trafficCondition = "Moderate Traffic";
    } else if (currentHour >= 22 || currentHour <= 5) {
        trafficFactor = 0.8;
        trafficCondition = "Light Traffic";
    } else {
        trafficFactor = 1.2;
        trafficCondition = "Normal Traffic";
    }
    
    let distanceBuffer = 0;
    if (distance_km > 80) {
        distanceBuffer = Math.min(40, Math.floor(distance_km * 0.4));
    } else if (distance_km > 50) {
        distanceBuffer = Math.min(30, Math.floor(distance_km * 0.35));
    } else if (distance_km > 30) {
        distanceBuffer = Math.min(20, Math.floor(distance_km * 0.3));
    } else if (distance_km > 15) {
        distanceBuffer = Math.min(10, Math.floor(distance_km * 0.25));
    } else {
        distanceBuffer = Math.min(5, Math.floor(distance_km * 0.2));
    }
    
    const baseIdealTime = (distance_km / SPEEDS.ideal) * 60;
    let estimatedTime = baseIdealTime * trafficFactor;
    estimatedTime += distanceBuffer;
    
    if (distance_km >= 10 && distance_km <= 40) {
        estimatedTime += Math.floor(distance_km * 0.15);
    }
    
    const minTime = distance_km * 2;
    if (estimatedTime < minTime) {
        estimatedTime = minTime;
    }
    
    estimatedTime = Math.round(estimatedTime);
    
    let formattedTime = '';
    if (estimatedTime >= 60) {
        const hours = Math.floor(estimatedTime / 60);
        const minutes = estimatedTime % 60;
        formattedTime = minutes > 0 ? `${hours} hr ${minutes} min` : `${hours} hr`;
    } else {
        formattedTime = `${estimatedTime} min`;
    }
    
    return {
        minutes: estimatedTime,
        formatted: formattedTime,
        trafficCondition: trafficCondition,
        distanceBuffer: distanceBuffer
    };
}

// ========== MAP LOADING FUNCTIONS ==========

async function loadStops() {
    try {
        let response = await fetch('/stops?limit=500');
        if (!response.ok) {
            response = await fetch('/stops-direct');
        }
        
        const data = await response.json();
        const stops = data.stops || data;
        
        allStops = stops;
        stopsLayer.clearLayers();
        currentMarkers = [];
        
        console.log(`✅ Loaded ${stops.length} bus stops`);
        
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
            
            if (lat && lng && !isNaN(lat) && !isNaN(lng)) {
                const marker = L.marker([lat, lng], {
                    icon: L.divIcon({
                        className: 'custom-marker',
                        html: '<i class="fas fa-bus-stop" style="color: #6366f1; font-size: 20px;"></i>',
                        iconSize: [20, 20],
                        popupAnchor: [0, -10]
                    })
                }).bindPopup(`
                    <div style="min-width: 150px;">
                        <b style="color: #6366f1;">${escapeHtml(stop.name)}</b><br>
                        ${stop.city ? `<small>📍 ${escapeHtml(stop.city)}</small><br>` : ''}
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
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ========== LOCATION FUNCTIONS ==========

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

async function geocodeLocation(location) {
    if (location === 'My Location' && userLocation) {
        return userLocation;
    }
    
    try {
        let searchQuery = location;
        if (!location.includes('Gujarat') && !location.includes('Maharashtra') && 
            !location.includes('India') && location !== 'My Location') {
            searchQuery = `${location}, India`;
        }
        
        const response = await fetch(
            `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(searchQuery)}&limit=1`,
            {
                headers: {
                    'User-Agent': 'BusTrackerApp/1.0'
                }
            }
        );
        const data = await response.json();
        
        if (data && data[0]) {
            return {
                lat: parseFloat(data[0].lat),
                lng: parseFloat(data[0].lon)
            };
        }
        return null;
    } catch (error) {
        console.error('Geocoding error:', error);
        return null;
    }
}

// ========== ROUTE SEARCH ==========

async function searchRoute() {
    const start = document.getElementById('startInput').value;
    const dest = document.getElementById('destInput').value;
    
    if (!start || !dest) {
        alert('Please enter both starting location and destination');
        return;
    }
    
    const distanceElement = document.getElementById('routeDistance');
    const timeElement = document.getElementById('routeTime');
    
    distanceElement.innerHTML = '<div class="spinner-small"></div> Loading...';
    timeElement.innerHTML = '<div class="spinner-small"></div> Calculating...';
    
    try {
        const startCoords = await geocodeLocation(start);
        const destCoords = await geocodeLocation(dest);
        
        if (!startCoords || !destCoords) {
            alert('Could not find location coordinates. Please check the location names.');
            distanceElement.textContent = 'Not found';
            timeElement.textContent = 'Not found';
            return;
        }
        
        // Calculate straight line distance
        const straightDistance = calculateDistance(
            startCoords.lat, startCoords.lng, 
            destCoords.lat, destCoords.lng
        );
        
        let finalDistance = straightDistance;
        let osrmDuration = (straightDistance / 45) * 60;
        
        // Try OSRM
        try {
            const routeResponse = await fetch(
                `https://router.project-osrm.org/route/v1/driving/${startCoords.lng},${startCoords.lat};${destCoords.lng},${destCoords.lat}?overview=full&geometries=geojson`
            );
            const routeData = await routeResponse.json();
            
            if (routeData.routes && routeData.routes[0]) {
                const osrmDistance = routeData.routes[0].distance / 1000;
                osrmDuration = routeData.routes[0].duration / 60;
                
                if (osrmDistance > 0.5 && osrmDistance <= straightDistance * 2.5) {
                    finalDistance = osrmDistance;
                } else {
                    finalDistance = straightDistance * 1.3;
                }
                
                // Draw route on map
                if (routeData.routes[0].geometry) {
                    if (window.currentRoute) map.removeLayer(window.currentRoute);
                    
                    window.currentRoute = L.geoJSON(routeData.routes[0].geometry, {
                        style: { color: '#6366f1', weight: 5, opacity: 0.8 }
                    }).addTo(map);
                    
                    setTimeout(() => {
                        map.fitBounds(window.currentRoute.getBounds());
                    }, 100);
                }
            }
        } catch (osrmError) {
            console.error('OSRM error:', osrmError);
            finalDistance = straightDistance * 1.3;
        }
        
        // Calculate ETA
        const realisticETA = calculateRealisticETA(finalDistance, osrmDuration);
        
        // Display distance
        let distanceDisplay = finalDistance < 1 ? `${(finalDistance * 1000).toFixed(0)} m` : `${finalDistance.toFixed(0)} km`;
        distanceElement.innerHTML = `<strong>${distanceDisplay}</strong>`;
        
        // Display time with traffic info
        let trafficIcon = '';
        let trafficColor = '';
        switch (realisticETA.trafficCondition) {
            case 'Heavy Traffic':
                trafficIcon = '🚗🚕🚙';
                trafficColor = '#ef4444';
                break;
            case 'Moderate Traffic':
                trafficIcon = '🚗🚕';
                trafficColor = '#f59e0b';
                break;
            case 'Light Traffic':
                trafficIcon = '🚗';
                trafficColor = '#10b981';
                break;
            default:
                trafficIcon = '🚌';
                trafficColor = '#6366f1';
        }
        
        timeElement.innerHTML = `
            <strong>${realisticETA.formatted}</strong>
            <small style="display: block; font-size: 0.7rem; color: ${trafficColor};">
                ${trafficIcon} ${realisticETA.trafficCondition} • +${realisticETA.distanceBuffer} min buffer
            </small>
        `;
        
        loadBuses();
        
    } catch (error) {
        console.error('Error searching route:', error);
        distanceElement.textContent = 'Error';
        timeElement.textContent = 'Try again';
    }
}

// ========== BUS FUNCTIONS ==========

async function loadBuses() {
    try {
        const response = await fetch('/api/buses');
        const buses = await response.json();
        
        const busesList = document.getElementById('busesList');
        
        if (!buses || buses.length === 0) {
            busesList.innerHTML = '<div class="loading-spinner"><p>No buses available</p></div>';
            return;
        }
        
        busesList.innerHTML = '';
        buses.forEach(bus => {
            const busCard = document.createElement('div');
            busCard.className = 'bus-card';
            busCard.innerHTML = `
                <div class="bus-number">${escapeHtml(bus.bus_id || 'Bus')}</div>
                <div class="bus-badge">${bus.status === 'active' ? 'Active' : 'Inactive'}</div>
                <div class="bus-time-row">
                    <span><i class="far fa-clock"></i> Route: ${escapeHtml(bus.route_id || 'N/A')}</span>
                    <span><i class="fas fa-users"></i> ${bus.current_passengers || 0}/${bus.capacity || 50}</span>
                </div>
            `;
            busCard.onclick = () => {
                if (bus.current_location && bus.current_location.coordinates) {
                    map.setView([bus.current_location.coordinates[1], bus.current_location.coordinates[0]], 15);
                    L.marker([bus.current_location.coordinates[1], bus.current_location.coordinates[0]])
                        .addTo(map)
                        .bindPopup(`<b>Bus ${escapeHtml(bus.bus_id)}</b>`)
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

// ========== DISTANCE CALCULATION ==========

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

// ========== NEAREST STOP FUNCTIONS ==========

async function findNearestStop() {
    if (!userLocation) {
        useMyLocation();
        setTimeout(() => {
            if (userLocation) getNearestStop();
            else alert('Please enable location');
        }, 2000);
    } else {
        getNearestStop();
    }
}

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
            document.getElementById('nearestStopCard').classList.remove('hidden');
            
            L.marker([nearestStop.location.coordinates[1], nearestStop.location.coordinates[0]], {
                icon: L.divIcon({
                    className: 'nearest-marker',
                    html: '<i class="fas fa-star" style="color: #fbbf24; font-size: 28px;"></i>',
                    iconSize: [28, 28]
                })
            }).addTo(map)
                .bindPopup(`<b>Nearest: ${nearestStop.name}</b><br>${distance.toFixed(1)} km away`)
                .openPopup();
                
            setTimeout(() => map.closePopup(), 5000);
        }
    } catch (error) {
        console.error('Error finding nearest stop:', error);
    }
}

// ========== ALL STOPS MODAL ==========

function showAllStops() {
    let allStopsModal = document.getElementById('allStopsModal');
    
    if (!allStopsModal) {
        allStopsModal = document.createElement('div');
        allStopsModal.id = 'allStopsModal';
        allStopsModal.className = 'modal-overlay hidden';
        allStopsModal.innerHTML = `
            <div class="modal-content all-stops-modal">
                <div class="modal-header"><i class="fas fa-list-ul"></i> All Bus Stops</div>
                <div class="stops-search-container">
                    <input type="text" id="stopSearchInput" placeholder="🔍 Search bus stops...">
                </div>
                <div class="stops-list-container" id="stopsListContainer">
                    <div class="loading-spinner"><div class="spinner"></div><p>Loading stops...</p></div>
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
            if (e.target === allStopsModal) allStopsModal.classList.add('hidden');
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
            distanceText = `<div class="distance-badge">📍 ${distance.toFixed(1)} km</div>`;
        }
        
        stopDiv.innerHTML = `
            <strong>${escapeHtml(stop.name)}</strong>
            <small>${stop.city ? escapeHtml(stop.city) : ''}</small>
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
                    .bindPopup(`<b>${escapeHtml(stop.name)}</b>`)
                    .openPopup();
                allStopsModal.classList.add('hidden');
                setTimeout(() => map.closePopup(), 5000);
            }
        };
        
        container.appendChild(stopDiv);
    });
}

// ========== MAP CONTROLS ==========

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

// ========== MODAL HANDLING ==========

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

// ========== EVENT LISTENERS ==========

document.getElementById('menuIcon').addEventListener('click', showMenuModal);
document.getElementById('aboutBtn').addEventListener('click', showAboutModal);
document.getElementById('closeMenuModal').addEventListener('click', closeModals);
document.getElementById('closeAboutModal').addEventListener('click', closeModals);
document.getElementById('myLocationBtn').addEventListener('click', useMyLocation);
document.getElementById('searchRouteBtn').addEventListener('click', searchRoute);
document.getElementById('findNearestStopBtn').addEventListener('click', findNearestStop);
document.getElementById('hideStopsBtn').addEventListener('click', toggleStops);
document.getElementById('satelliteToggleBtn').addEventListener('click', toggleSatellite);

document.addEventListener('DOMContentLoaded', () => {
    const nearestCard = document.getElementById('nearestStopCard');
    if (nearestCard) {
        const closeBtn = document.createElement('button');
        closeBtn.className = 'close-stop-card';
        closeBtn.innerHTML = '<i class="fas fa-times"></i>';
        closeBtn.onclick = closeNearestStopCard;
        nearestCard.insertBefore(closeBtn, nearestCard.firstChild);
    }
    
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

window.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay')) closeModals();
});

// ========== INITIALIZATION ==========

loadStops();
loadBuses();

if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(position => {
        userLocation = {
            lat: position.coords.latitude,
            lng: position.coords.longitude
        };
        map.setView([userLocation.lat, userLocation.lng], 13);
    });
}

setInterval(loadBuses, 30000);

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