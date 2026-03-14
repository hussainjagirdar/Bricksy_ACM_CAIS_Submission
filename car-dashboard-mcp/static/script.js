// API Base URL
const API_BASE = window.location.origin;

// Color mapping
const COLOR_MAP = {
    "red": "#FF0000",
    "blue": "#4A90E2",
    "green": "#00FF00",
    "white": "#FFFFFF",
    "purple": "#9333EA",
    "orange": "#FFA500"
};

// Initialize connection to server-sent events
let eventSource;

// Initialize the dashboard
document.addEventListener('DOMContentLoaded', () => {
    updateDateTime();
    setInterval(updateDateTime, 1000);
    connectToEventStream();
    fetchInitialState();
});

// Update date and time
function updateDateTime() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    const dateStr = now.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

    document.getElementById('currentTime').textContent = timeStr;
    document.getElementById('currentDate').textContent = dateStr;
}

// Connect to Server-Sent Events for real-time updates
function connectToEventStream() {
    eventSource = new EventSource(`${API_BASE}/api/events`);

    eventSource.onmessage = (event) => {
        const state = JSON.parse(event.data);
        updateUIFromState(state);
    };

    eventSource.onerror = () => {
        document.getElementById('connectionStatus').style.background = '#ef4444';
        setTimeout(() => {
            connectToEventStream();
        }, 5000);
    };

    eventSource.onopen = () => {
        document.getElementById('connectionStatus').style.background = '#22c55e';
    };
}

// Fetch initial state
async function fetchInitialState() {
    try {
        const response = await fetch(`${API_BASE}/api/state`);
        const state = await response.json();
        updateUIFromState(state);
    } catch (error) {
        console.error('Error fetching initial state:', error);
    }
}

// Update UI from state object
function updateUIFromState(state) {
    // Temperature
    document.getElementById('tempValue').textContent = state.ac_temperature;
    document.getElementById('tempSlider').value = state.ac_temperature;

    // Wipers
    updateWiperUI(state.wipers);

    // Ambient light
    updateAmbientLightUI(state.ambient_light_color);

    // Seat
    document.getElementById('seatSlider').value = state.seat_height;
    document.getElementById('seatValue').textContent = state.seat_height;
    updateSeatVisual(state.seat_height);

    // Speed
    document.getElementById('speedValue').textContent = state.speed;
    updateSpeedGauge(state.speed);

    // Fuel
    document.getElementById('fuelBar').style.width = `${state.fuel_level}%`;
    document.getElementById('fuelValue').textContent = `${state.fuel_level}%`;
}

// Temperature controls
async function adjustTemp(delta) {
    const currentTemp = parseInt(document.getElementById('tempValue').textContent);
    const newTemp = Math.max(16, Math.min(30, currentTemp + delta));
    await updateTemp(newTemp);
}

async function updateTemp(temp) {
    try {
        const response = await fetch(`${API_BASE}/api/ac`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ temperature: parseInt(temp) })
        });

        if (!response.ok) {
            console.error('Failed to update temperature');
        }
    } catch (error) {
        console.error('Error updating temperature:', error);
    }
}

// Wiper controls
async function setWipers(mode) {
    try {
        const response = await fetch(`${API_BASE}/api/wipers`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode })
        });

        if (!response.ok) {
            console.error('Failed to update wipers');
        }
    } catch (error) {
        console.error('Error updating wipers:', error);
    }
}

function updateWiperUI(mode) {
    // Update button states
    document.querySelectorAll('.wiper-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.mode === mode) {
            btn.classList.add('active');
        }
    });

    // Update animation
    const wiper = document.querySelector('.wiper');
    wiper.classList.remove('animate-slow', 'animate-fast');

    if (mode === 'slow') {
        wiper.classList.add('animate-slow');
    } else if (mode === 'fast') {
        wiper.classList.add('animate-fast');
    }
}

// Ambient light controls
async function setAmbientColor(colorName) {
    try {
        const response = await fetch(`${API_BASE}/api/ambient-light`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ color: colorName })
        });

        if (!response.ok) {
            console.error('Failed to update ambient color');
        }
    } catch (error) {
        console.error('Error updating ambient color:', error);
    }
}

function updateAmbientLightUI(colorName) {
    // Update button states
    document.querySelectorAll('.color-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.color === colorName) {
            btn.classList.add('active');
        }
    });

    // Update current color display
    document.getElementById('currentColorName').textContent = colorName;

    // Update ambient overlay
    const hexColor = COLOR_MAP[colorName] || COLOR_MAP["blue"];
    const overlay = document.getElementById('ambientOverlay');
    overlay.style.background = `radial-gradient(ellipse at center, ${hexColor} 0%, transparent 70%)`;
    overlay.style.opacity = 0.15; // Fixed opacity
}

// Seat controls
async function adjustSeat(delta) {
    const currentHeight = parseInt(document.getElementById('seatValue').textContent);
    const newHeight = Math.max(0, Math.min(100, currentHeight + delta));
    await updateSeat(newHeight);
}

async function updateSeat(height) {
    document.getElementById('seatValue').textContent = height;
    updateSeatVisual(height);

    try {
        const response = await fetch(`${API_BASE}/api/seat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ height: parseInt(height) })
        });

        if (!response.ok) {
            console.error('Failed to update seat height');
        }
    } catch (error) {
        console.error('Error updating seat height:', error);
    }
}

function updateSeatVisual(height) {
    const seat = document.getElementById('seatVisual');
    const bottomPosition = 20 + (height * 0.8); // Scale height to pixels
    seat.style.bottom = `${bottomPosition}px`;
}

// Speed gauge
function updateSpeedGauge(speed) {
    const maxSpeed = 150;
    const percentage = Math.min(speed / maxSpeed, 1);
    const circumference = 251.2; // Arc length
    const offset = circumference - (percentage * circumference);

    document.getElementById('speedGauge').style.strokeDashoffset = offset;
}

// Demo functions for testing
async function simulateDrive() {
    // Simulate acceleration
    for (let speed = 0; speed <= 60; speed += 5) {
        await fetch(`${API_BASE}/api/speed`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ speed })
        });
        await new Promise(resolve => setTimeout(resolve, 500));
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowUp') {
        adjustSeat(5);
    } else if (e.key === 'ArrowDown') {
        adjustSeat(-5);
    } else if (e.key === '+' || e.key === '=') {
        adjustTemp(1);
    } else if (e.key === '-') {
        adjustTemp(-1);
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (eventSource) {
        eventSource.close();
    }
});
