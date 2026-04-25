// ==========================================
// INTEGRATION MODULE LOGIC (STRICT JS ONLY)
// ==========================================

window.addEventListener('pywebviewready', function () {
    if (document.getElementById('rescan-btn')) {
        setupAddApplicationScreen();
    }
    if (document.getElementById('connected-apps-grid')) {
        loadConnectedApps();

        // --- NEW: Bind the Search Bar ---
        const searchInput = document.getElementById('app-search-input');
        if (searchInput) {
            searchInput.oninput = function (e) {
                loadConnectedApps(e.target.value);
            };
        }
    }
});

// ------------------------------------------
// SCREEN 1: CONNECTED APPS LOGIC
// ------------------------------------------
function loadConnectedApps(searchTerm = null) {
    const grid = document.getElementById('connected-apps-grid');
    if (!grid) return;

    // Show loading template
    grid.replaceChildren();
    grid.appendChild(document.getElementById('loading-template').content.cloneNode(true));

    // --- UPDATED to pass searchTerm to Python ---
    pywebview.api.get_connected_apps(searchTerm).then(apps => {
        grid.replaceChildren();

        if (apps.length === 0) {
            grid.appendChild(document.getElementById('empty-state-template').content.cloneNode(true));
            return;
        }

        const template = document.getElementById('connected-app-card-template');

        apps.forEach(app => {
            const cardClone = template.content.cloneNode(true);

            cardClone.querySelector('.app-icon').textContent = app.icon;
            cardClone.querySelector('.app-name').textContent = app.name;
            cardClone.querySelector('.app-version').textContent = `v${app.version}`;
            cardClone.querySelector('.app-mappings').textContent = `${app.mappings || 0} Active Mappings`;

            cardClone.querySelector('.disconnect-btn').onclick = function () {
                if (confirm(`Are you sure you want to disconnect ${app.name}? This will delete all associated gesture mappings.`)) {
                    pywebview.api.disconnect_app(app.name).then(response => {
                        if (response.status === 'success') {
                            loadConnectedApps(); // Refresh the grid
                        } else {
                            alert(response.message);
                        }
                    });
                }
            };

            cardClone.querySelector('.configure-btn').onclick = function () {
                window.location.href = '../3_Action Mapping/2_Create Mapping Screen.html?app=' + encodeURIComponent(app.name);
            };

            grid.appendChild(cardClone);
        });
    });
}

// ------------------------------------------
// SCREEN 2: ADD APPLICATION LOGIC
// ------------------------------------------
function setupAddApplicationScreen() {
    const rescanBtn = document.getElementById('rescan-btn');
    const clearConsoleBtn = document.getElementById('clear-console-btn');
    const saveBtn = document.getElementById('save-integrations-btn');
    const cancelBtn = document.getElementById('cancel-integrations-btn'); // NEW

    logToConsole("Application scanner module initialized. Ready to scan.", "INF");

    rescanBtn.addEventListener('click', handleSystemRescan);
    clearConsoleBtn.addEventListener('click', clearConsole);
    saveBtn.addEventListener('click', handleSaveIntegrations);
    cancelBtn.addEventListener('click', handleCancelIntegrations); // NEW
}

function handleSystemRescan() {
    const rescanBtn = document.getElementById('rescan-btn');
    const rescanIcon = document.getElementById('rescan-icon');
    const rescanText = document.getElementById('rescan-text');
    const grid = document.getElementById('app-grid');

    rescanBtn.disabled = true;
    rescanIcon.classList.add('animate-spin');
    rescanText.textContent = "Scanning...";

    grid.replaceChildren();
    grid.appendChild(document.getElementById('grid-loading-template').content.cloneNode(true));

    logToConsole("Initiating deep system registry scan...", "INF");

    pywebview.api.scan_system_apps().then(response => {
        if (response.status === "success") {
            logToConsole(response.message, "INF");
            renderAppGrid(response.data);
        } else {
            logToConsole(`Scan failed: ${response.message}`, "ERR");
        }

        rescanBtn.disabled = false;
        rescanIcon.classList.remove('animate-spin');
        rescanText.textContent = "Rescan System";
    });
}

function renderAppGrid(apps) {
    const grid = document.getElementById('app-grid');
    const template = document.getElementById('app-card-template');

    grid.replaceChildren();

    apps.forEach(app => {
        const cardClone = template.content.cloneNode(true);

        cardClone.querySelector('.app-icon').textContent = app.icon;

        const nameElement = cardClone.querySelector('.app-name');
        nameElement.textContent = app.name;
        nameElement.title = app.name;

        cardClone.querySelector('.app-version').textContent = `v${app.version}`;

        const connectBtn = cardClone.querySelector('.connect-btn');

        // Style presets
        const defaultClass = "connect-btn w-full py-2 bg-background-light hover:bg-primary hover:text-white border border-[#d2d4e5] rounded-lg text-sm font-bold transition-all text-primary";
        const stagedClass = "connect-btn w-full py-2 bg-yellow-50 border border-yellow-200 rounded-lg text-sm font-bold text-yellow-600 transition-all";
        const connectedClass = "w-full py-2 bg-green-50 border border-green-200 rounded-lg text-sm font-bold text-green-600 cursor-default";

        // --- NEW: Set initial button state based strictly on Backend Data ---
        if (app.is_connected) {
            connectBtn.textContent = "Already Connected";
            connectBtn.className = connectedClass;
            connectBtn.disabled = true; // Permanently lock it
            connectBtn.dataset.staged = "false";
        } else if (app.is_staged) {
            connectBtn.textContent = "Staged (Unsaved)";
            connectBtn.className = stagedClass;
            connectBtn.dataset.staged = "true";
        } else {
            connectBtn.textContent = "Connect";
            connectBtn.className = defaultClass;
            connectBtn.dataset.staged = "false";
        }

        // --- Toggle Logic remains clean ---
        connectBtn.onclick = function () {
            // Temporarily disable while communicating with Python
            connectBtn.disabled = true;

            if (connectBtn.dataset.staged === "false") {
                // User wants to Connect (Stage)
                logToConsole(`Staging connection for ${app.name}...`, "INF");
                connectBtn.textContent = "Staging...";

                pywebview.api.stage_app_connection(app).then(response => {
                    if (response.status === "success") {
                        logToConsole(response.message, "INF");
                        connectBtn.textContent = "Staged (Unsaved)";
                        connectBtn.className = stagedClass;
                        connectBtn.dataset.staged = "true";
                        connectBtn.disabled = false; // Re-enable so they can unclick it
                    } else if (response.status === "info") {
                        logToConsole(response.message, "WRN");
                        connectBtn.textContent = "Already Connected";
                        connectBtn.className = connectedClass;
                        // Leave disabled=true here because it's permanently saved in the DB
                    } else {
                        logToConsole(response.message, "ERR");
                        connectBtn.textContent = "Connect";
                        connectBtn.disabled = false;
                    }
                });
            } else {
                // User wants to Cancel (Unstage)
                logToConsole(`Canceling staging for ${app.name}...`, "INF");
                connectBtn.textContent = "Canceling...";

                pywebview.api.unstage_app_connection(app.name).then(response => {
                    if (response.status === "success") {
                        logToConsole(response.message, "INF");
                        connectBtn.textContent = "Connect";
                        connectBtn.className = defaultClass; // Revert to original blue outline
                        connectBtn.dataset.staged = "false";
                        connectBtn.disabled = false;
                    } else {
                        logToConsole(response.message, "ERR");
                        connectBtn.textContent = "Staged (Unsaved)"; // Revert text on failure
                        connectBtn.disabled = false;
                    }
                });
            }
        };

        grid.appendChild(cardClone);
    });
}

// --- NEW: Handle saving the staged integrations to the database ---
function handleSaveIntegrations() {
    pywebview.api.save_staged_integrations().then(response => {
        if (response.status === "success") {
            logToConsole(response.message, "INF");
            alert(response.message);

            // Navigate the user back to the Connected Apps screen to see their new integrations!
            window.location.href = '1_Apllications Integration Screen.html';
        } else {
            logToConsole(response.message, "ERR");
            alert(response.message);
        }
    });
}

// --- NEW: Handle canceling the staging process ---
function handleCancelIntegrations() {
    logToConsole("Canceling staged integrations...", "WRN");

    // 1. Tell Python to wipe the temporary memory
    pywebview.api.clear_staged_integrations().then(() => {

        // 2. Visually reset all "Staged" buttons back to "Connect"
        const defaultClass = "connect-btn w-full py-2 bg-background-light hover:bg-primary hover:text-white border border-[#d2d4e5] rounded-lg text-sm font-bold transition-all text-primary";
        const stagedButtons = document.querySelectorAll('.connect-btn[data-staged="true"]');

        stagedButtons.forEach(btn => {
            btn.textContent = "Connect";
            btn.className = defaultClass;
            btn.dataset.staged = "false";
        });

        // 3. Navigate back to the Connected Apps screen
        window.location.href = '1_Apllications Integration Screen.html';
    });
}

// ------------------------------------------
// UTILITY: CONSOLE LOGGING
// ------------------------------------------
function logToConsole(message, type = "INF") {
    const consoleContainer = document.getElementById('console-container');
    const consoleOutput = document.getElementById('console-output');
    const template = document.getElementById('console-log-template');

    const logClone = template.content.cloneNode(true);

    const now = new Date();
    const timeStr = `[${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}]`;

    logClone.querySelector('.log-time').textContent = timeStr;
    logClone.querySelector('.log-msg').textContent = message;

    const typeElement = logClone.querySelector('.log-type');
    typeElement.textContent = `${type}:`;

    if (type === "INF") {
        typeElement.className = "log-type font-bold text-[#76e5b1]";
    } else if (type === "ERR") {
        typeElement.className = "log-type font-bold text-red-500";
    } else if (type === "WRN") {
        typeElement.className = "log-type font-bold text-[#f9d423]";
    }

    consoleContainer.appendChild(logClone);
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
}

function clearConsole() {
    document.getElementById('console-container').replaceChildren();
    logToConsole("Console cleared.", "INF");
}