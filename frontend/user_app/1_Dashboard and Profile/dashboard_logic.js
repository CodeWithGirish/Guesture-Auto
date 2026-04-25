// ==========================================
// INITIALIZATION
// ==========================================
let healthInterval;

window.addEventListener('pywebviewready', function () {
    console.log("Dashboard API Bridge Ready");

    // Call the new metrics function when Python is ready
    loadDashboardMetrics();
    startHealthPolling();
});

function startHealthPolling() {
    // Initial fetch
    fetchSystemHealth();
    
    // Poll every 2 seconds
    healthInterval = setInterval(fetchSystemHealth, 2000);
}

function fetchSystemHealth() {
    if (pywebview.api && pywebview.api.get_system_health) {
        pywebview.api.get_system_health().then(res => {
            const healthKpi = document.getElementById('system-health-kpi');
            const healthLabel = document.getElementById('system-health-label');
            
            if (res.status === "success" && healthKpi && healthLabel) {
                healthKpi.innerText = res.health + "%";
                
                if (res.health >= 80) {
                    healthLabel.innerText = "Optimal";
                    healthLabel.className = "text-emerald-500 text-xs font-bold";
                } else if (res.health >= 50) {
                    healthLabel.innerText = "Fair";
                    healthLabel.className = "text-amber-500 text-xs font-bold";
                } else {
                    healthLabel.innerText = "Critical";
                    healthLabel.className = "text-red-500 text-xs font-bold";
                }
            }
        }).catch(err => {
            console.error("Error fetching system health:", err);
        });
    }
}

// ==========================================
// SYSTEM CONTROL & PREVIEW
// ==========================================
let isSystemActive = false;

// --- Helper Function to fix ReferenceError ---
function updateSystemUI(active) {
    const statusText = document.getElementById('system-status-text');
    const statusDot = document.getElementById('system-status-dot');
    const dashPlaceholder = document.getElementById('dashboard-placeholder');
    const dashFeed = document.getElementById('dashboard-live-feed');

    if (active) {
        if (statusText) {
            statusText.innerText = "Online";
            statusText.className = "text-[10px] font-bold uppercase tracking-wider text-emerald-500";
        }
        if (statusDot) {
            statusDot.className = "size-2 rounded-full bg-emerald-500 animate-pulse";
        }
        if (dashPlaceholder) {
            dashPlaceholder.style.display = 'none';
            dashPlaceholder.innerHTML = '<span class="material-symbols-outlined text-6xl mb-2">videocam_off</span><p class="font-bold">System Offline</p>';
        }
        if (dashFeed) dashFeed.style.display = 'block';
    } else {
        if (statusText) {
            statusText.innerText = "Offline";
            statusText.className = "text-[10px] font-bold uppercase tracking-wider text-slate-500";
        }
        if (statusDot) {
            statusDot.className = "size-2 rounded-full bg-slate-400";
        }
        if (dashPlaceholder) {
            dashPlaceholder.style.display = 'flex';
            dashPlaceholder.innerHTML = '<span class="material-symbols-outlined text-6xl mb-2">videocam_off</span><p class="font-bold">System Offline</p>';
        }

        // Clear feed on stop
        if (dashFeed) {
            dashFeed.src = "";
            dashFeed.style.display = 'block';
        }
        
        // Clear accuracy metrics on stop
        updateGestureMetrics(0, 0);
    }
}

function updateGestureMetrics(handConfidence, gestureConfidence = null) {
    if (!isSystemActive && handConfidence !== 0) return;
    
    const staticGesturesEl = document.getElementById('dash-static-gestures');
    const motionTrackingEl = document.getElementById('dash-motion-tracking');
    const totalSuccessEl = document.getElementById('dash-total-success');
    const circleProgress = document.getElementById('dash-circle-progress');
    
    let combined = Math.max(handConfidence, gestureConfidence || 0);

    if (totalSuccessEl) totalSuccessEl.innerText = combined + "%";
    if (staticGesturesEl) staticGesturesEl.innerText = (gestureConfidence || 0) + "%";
    if (motionTrackingEl) motionTrackingEl.innerText = handConfidence + "%";
    
    if (circleProgress) {
        let circ = 552.92;
        let offset = circ - (combined / 100) * circ;
        circleProgress.setAttribute('stroke-dashoffset', offset);
    }
}

function startSystem() {
    pywebview.api.start_automation().then((response) => {
        if (response.status === "success") {
            isSystemActive = true; // System is now active
            updateSystemUI(true);  // Helper to change UI to 'Online'
        }
    });
}

function stopSystem() {
    pywebview.api.stop_scan().then((response) => {
        if (response.status === "success") {
            isSystemActive = false; // System is now inactive
            updateSystemUI(false); // Helper to change UI to 'Offline'

            // Reset float window button since stop_scan auto-closes it
            const btnText = document.getElementById('float-btn-text');
            if (btnText) btnText.innerText = 'Float Window';
        }
    });
}

function toggleFloatWindow() {
    // Guard: system must be running before the float window can open
    if (!isSystemActive) {
        alert("Please start the system first before opening the Floating Window.");
        return;
    }

    pywebview.api.toggle_float_window().then(response => {
        if (response && response.status === "error") {
            alert(response.message);
            return;
        }
        // Update button text to reflect current state
        const btnText = document.getElementById('float-btn-text');
        if (btnText) {
            btnText.innerText = response.action === 'opened' ? 'Close Float' : 'Float Window';
        }
    }).catch(err => {
        console.error("Float window toggle error:", err);
    });
}

function updateFrame(base64Image, isFloatOpen = false) {
    const dashFeed = document.getElementById('dashboard-live-feed');
    const dashPlaceholder = document.getElementById('dashboard-placeholder');
    
    if (dashFeed && isSystemActive) {
        if (isFloatOpen) {
            dashFeed.style.display = 'none';
            if (dashPlaceholder) {
                dashPlaceholder.style.display = 'flex';
                dashPlaceholder.innerHTML = '<span class="material-symbols-outlined text-6xl mb-2">picture_in_picture_alt</span><p class="font-bold">Camera view moved to Float Window</p>';
            }
        } else {
            dashFeed.style.display = 'block';
            if (dashPlaceholder) dashPlaceholder.style.display = 'none';
            dashFeed.src = base64Image;
        }
    }
}

function safeNavigate(targetUrl) {
    // Ensure camera is stopped before switching pages to avoid thread errors
    pywebview.api.stop_scan().then(() => {
        window.location.href = targetUrl;
    });
}

// ==========================================
// METRICS & DATA FETCHING (REFACTORED)
// ==========================================
function loadDashboardMetrics() {
    const connectedAppsCountEl = document.getElementById('connected-apps-count');
    const activeGesturesCountEl = document.getElementById('active-gestures-count');
    const runningAutomationsCountEl = document.getElementById('running-automations-count'); // <--- NEW

    // --- REFACTORED: Single API call fetching pre-calculated backend metrics ---
    pywebview.api.get_dashboard_metrics().then(metrics => {
        if (metrics.status === "success") {
            if (connectedAppsCountEl) {
                connectedAppsCountEl.innerText = metrics.connected_apps_count.toString().padStart(2, '0');
            }
            if (activeGesturesCountEl) {
                activeGesturesCountEl.innerText = metrics.active_gestures_count.toString().padStart(2, '0');
            }
            if (runningAutomationsCountEl) { // <--- NEW
                runningAutomationsCountEl.innerText = metrics.running_automations_count.toString().padStart(2, '0');
            }
        } else {
            console.error("Failed to load dashboard metrics:", metrics.message);
            // Fallback UI in case of error
            if (connectedAppsCountEl) connectedAppsCountEl.innerText = "00";
            if (activeGesturesCountEl) activeGesturesCountEl.innerText = "00";
            if (runningAutomationsCountEl) runningAutomationsCountEl.innerText = "00"; // <--- NEW
        }
    }).catch(err => {
        console.error("Communication error fetching metrics:", err);
    });
}