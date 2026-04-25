// ==========================================
// ACTION MAPPING MODULE LOGIC (STRICT JS)
// ==========================================

let systemActionsMap = {}; // Loaded dynamically from backend
let currentMappingPage = 1;
const mappingsPerPage = 4;

window.addEventListener('pywebviewready', function () {
    // Logic for Screen 2 (Create Mapping)
    if (document.getElementById('gesture-selection-grid')) {
        // Fetch configuration from backend first
        pywebview.api.get_system_actions().then(actionsMap => {
            systemActionsMap = actionsMap;
            setupSystemActionDropdowns();

            loadGestureSelection(""); // Load default grid
            loadConnectedAppsDropdown();
            setupMutualExclusivity();
            setupDelaySlider();
            
            // Initialize Mouse Tracking Toggle
            const toggle = document.getElementById('mouse-tracking-toggle');
            if (toggle && pywebview.api.get_mouse_tracking_state) {
                // Helper to apply the correct UI state
                const applyTrackingState = (isOn) => {
                    const banner = document.getElementById('mouse-tracking-banner');

                    // Show/hide the inline warning strip
                    if (isOn) {
                        banner?.classList.remove('hidden');
                    } else {
                        banner?.classList.add('hidden');
                    }

                    // Lock/unlock the Index Finger gesture card in the grid
                    document.querySelectorAll('.gesture-radio').forEach(radio => {
                        if (radio.value.toLowerCase() === 'index finger') {
                            radio.disabled = isOn;
                            if (isOn) {
                                // Visually mark it as reserved
                                const card = radio.closest('label');
                                if (card) {
                                    card.classList.add('opacity-40', 'cursor-not-allowed', 'pointer-events-none');
                                    let badge = card.querySelector('.tracking-reserved-badge');
                                    if (!badge) {
                                        badge = document.createElement('div');
                                        badge.className = 'tracking-reserved-badge absolute bottom-2 left-0 right-0 text-center text-[9px] font-bold text-amber-600 uppercase tracking-widest';
                                        badge.textContent = 'Reserved';
                                        card.style.position = 'relative';
                                        card.appendChild(badge);
                                    }
                                }
                                // Deselect if currently selected
                                if (radio.checked) radio.checked = false;
                            } else {
                                const card = radio.closest('label');
                                if (card) {
                                    card.classList.remove('opacity-40', 'cursor-not-allowed', 'pointer-events-none');
                                    card.querySelector('.tracking-reserved-badge')?.remove();
                                }
                            }
                        }
                    });
                };

                // Re-apply the lock any time the gesture grid is rebuilt (e.g. search)
                document.addEventListener('gesturesRendered', () => {
                    applyTrackingState(toggle.checked);
                });

                // Sync UI to current backend state on load
                pywebview.api.get_mouse_tracking_state().then(state => {
                    toggle.checked = !!state;
                    applyTrackingState(!!state);
                });

                toggle.addEventListener('change', function () {
                    const isChecked = this.checked;

                    if (isChecked) {
                        // Before enabling, validate index finger dataset exists
                        this.disabled = true; // Prevent double-clicks during async scan
                        pywebview.api.validate_index_finger_dataset().then(validation => {
                            this.disabled = false;
                            if (!validation.valid) {
                                this.checked = false; // revert toggle
                                alert(`⚠️ Cannot Enable Mouse Tracking\n\n${validation.message}`);
                                return;
                            }
                            // Dataset is valid — now activate tracking
                            pywebview.api.toggle_mouse_tracking(true).then(res => {
                                if (res.status !== 'success') {
                                    this.checked = false;
                                    alert(`Error: ${res.message}`);
                                } else {
                                    applyTrackingState(true);
                                }
                            });
                        }).catch(() => {
                            this.disabled = false;
                            this.checked = false;
                            alert('Validation failed. Please try again.');
                        });
                    } else {
                        pywebview.api.toggle_mouse_tracking(false).then(res => {
                            if (res.status !== 'success') {
                                this.checked = true; // revert
                                alert('Failed to disable tracking.');
                            } else {
                                applyTrackingState(false);
                            }
                        });
                    }
                });
            }
        });

        document.getElementById('gesture-search')?.addEventListener('input', (e) => loadGestureSelection(e.target.value));
        document.getElementById('save-mapping-btn')?.addEventListener('click', handleSaveMapping);
    }

    // Logic for Screen 1 (Mapped Actions Table)
    if (document.getElementById('mapped-actions-tbody')) {
        loadMappedActionsTable();

        // Triggers for server-side filtering
        document.getElementById('mapping-search')?.addEventListener('input', () => { currentMappingPage = 1; loadMappedActionsTable(); });
        document.getElementById('mapping-status-filter')?.addEventListener('change', () => { currentMappingPage = 1; loadMappedActionsTable(); });
    }
});

// ==========================================
// CREATE MAPPING SCREEN (SCREEN 2)
// ==========================================
function loadGestureSelection(searchTerm = "") {
    const grid = document.getElementById('gesture-selection-grid');
    const loadingTemplate = document.getElementById('gesture-loading-template');

    if (!grid) return;
    grid.replaceChildren(loadingTemplate.content.cloneNode(true));

    pywebview.api.get_smart_sorted_gestures(searchTerm).then(gestures => {
        renderGestures(gestures);
    });
}

function renderGestures(gesturesToRender) {
    const grid = document.getElementById('gesture-selection-grid');
    const template = document.getElementById('gesture-selection-template');
    const emptyTemplate = document.getElementById('gesture-empty-template');

    grid.replaceChildren();

    if (gesturesToRender.length === 0) {
        grid.appendChild(emptyTemplate.content.cloneNode(true));
        return;
    }

    gesturesToRender.forEach(gesture => {
        const clone = template.content.cloneNode(true);
        const imgEl = clone.querySelector('.gesture-img');
        const iconEl = clone.querySelector('.gesture-icon');
        const countEl = clone.querySelector('.gesture-count');

        const isMotion = gesture.is_motion || gesture.count === 'Motion' || gesture.count === 'Sequence';

        if (gesture.thumbnail) {
            imgEl.src = gesture.thumbnail;
            imgEl.classList.remove('hidden');
            iconEl.classList.add('hidden');
        }

        if (isMotion) {
            // Show a motion icon instead of image thumbnail
            iconEl.classList.remove('hidden');
            imgEl.classList.add('hidden');
            if (iconEl.tagName === 'SPAN') {
                iconEl.textContent = 'gesture';
            }
        }

        clone.querySelector('.gesture-name').textContent = gesture.name;
        // Show count label: "Motion" in teal, "Sequence" in purple, otherwise as-is
        if (isMotion) {
            countEl.textContent = gesture.count === 'Sequence' ? '🔴 Custom Motion' : '🟢 Built-in Motion';
        } else {
            countEl.textContent = `${gesture.count} Samples`;
        }
        clone.querySelector('.gesture-radio').value = gesture.name;

        grid.appendChild(clone);
    });

    // Signal that the grid has been rebuilt (so mouse tracking state can be re-applied)
    document.dispatchEvent(new CustomEvent('gesturesRendered'));
}

function loadConnectedAppsDropdown() {
    const select = document.getElementById('target-app-select');
    const openAppSelect = document.getElementById('open-app-target-select');
    if (!select) return;

    select.options.length = 1; // Keep only the default option
    if (openAppSelect) openAppSelect.options.length = 1;

    pywebview.api.get_connected_apps().then(apps => {
        if (!apps) return;
        apps.forEach(app => {
            const option = document.createElement('option');
            option.value = app.name;
            option.textContent = app.name;
            select.appendChild(option);
            
            if (openAppSelect) {
                const opt2 = document.createElement('option');
                opt2.value = app.name;
                opt2.textContent = app.name;
                openAppSelect.appendChild(opt2);
            }
        });
    });
}

function setupSystemActionDropdowns() {
    const categorySelect = document.getElementById('system-category-select');
    const actionSelect = document.getElementById('system-action-select');
    if (!categorySelect || !actionSelect) return;

    // Clear and set default to prevent duplicates
    categorySelect.options.length = 0;
    const defaultCatOption = document.createElement('option');
    defaultCatOption.value = "";
    defaultCatOption.textContent = "Select System action";
    categorySelect.appendChild(defaultCatOption);

    // Dynamically populate categories based on the dictionary from the backend
    Object.keys(systemActionsMap).forEach(category => {
        const option = document.createElement('option');
        option.value = category;
        option.textContent = category;
        categorySelect.appendChild(option);
    });

    categorySelect.addEventListener('change', function () {
        const selectedCategory = this.value;
        actionSelect.options.length = 1; // Clear previous options, keep default

        if (selectedCategory && systemActionsMap[selectedCategory]) {
            actionSelect.disabled = false;
            systemActionsMap[selectedCategory].forEach(action => {
                const option = document.createElement('option');
                option.value = action;
                option.textContent = action;
                actionSelect.appendChild(option);
            });
        } else {
            actionSelect.disabled = true;
        }
    });
}

function setupMutualExclusivity() {
    const sysCategory = document.getElementById('system-category-select');
    const sysAction = document.getElementById('system-action-select');
    const targetApp = document.getElementById('target-app-select');
    const targetAction = document.getElementById('target-action-select');
    const secondaryApp = document.getElementById('secondary-app-select');
    const openAppContainer = document.getElementById('open-app-target-container');

    if (!sysCategory || !targetApp || !targetAction) return;

    sysCategory.addEventListener('change', function () {
        if (this.value !== "") {
            targetApp.disabled = true; targetAction.disabled = true;
            if (secondaryApp) secondaryApp.disabled = true;
            targetApp.value = "Global"; targetAction.value = "";
            if (secondaryApp) secondaryApp.value = "None";
            
            if (sysAction.value !== "Open Application" && openAppContainer) {
                openAppContainer.classList.add('hidden');
            }
        } else {
            targetApp.disabled = false; targetAction.disabled = false;
            if (secondaryApp) secondaryApp.disabled = false;
            if (openAppContainer) openAppContainer.classList.add('hidden');
        }
    });
    
    if (sysAction) {
        sysAction.addEventListener('change', function () {
            if (this.value === "Open Application" && openAppContainer) {
                openAppContainer.classList.remove('hidden');
            } else if (openAppContainer) {
                openAppContainer.classList.add('hidden');
            }
        });
    }

    targetApp.addEventListener('change', function () {
        const selectedApp = this.value;

        if (selectedApp && selectedApp !== 'Global') {
            // Disable system-specific dropdowns
            sysCategory.disabled = true;
            sysAction.disabled = true;
            sysCategory.value = '';
            if (openAppContainer) openAppContainer.classList.add('hidden');

            // Clear system action dropdown
            sysAction.options.length = 0;
            const defaultSysOpt = document.createElement('option');
            defaultSysOpt.value = '';
            defaultSysOpt.textContent = 'Select Action Type';
            sysAction.appendChild(defaultSysOpt);

            // Show loading state in target action dropdown
            targetAction.options.length = 0;
            const loadingOpt = document.createElement('option');
            loadingOpt.value = '';
            loadingOpt.textContent = 'Loading actions...';
            targetAction.appendChild(loadingOpt);
            targetAction.disabled = true;

            // Fetch app-specific actions from backend
            pywebview.api.get_app_specific_actions(selectedApp).then(actions => {
                targetAction.options.length = 0;
                const defaultOpt = document.createElement('option');
                defaultOpt.value = '';
                defaultOpt.textContent = 'Select Action';
                targetAction.appendChild(defaultOpt);

                actions.forEach(action => {
                    const opt = document.createElement('option');
                    opt.value = action;
                    opt.textContent = action;
                    targetAction.appendChild(opt);
                });

                targetAction.disabled = false;
            }).catch(() => {
                targetAction.options.length = 0;
                const errOpt = document.createElement('option');
                errOpt.value = '';
                errOpt.textContent = 'Failed to load actions';
                targetAction.appendChild(errOpt);
            });

        } else {
            // Reset — re-enable system dropdowns
            sysCategory.disabled = false;
            sysAction.disabled = false;

            // Reset target action to placeholder
            targetAction.options.length = 0;
            const placeholder = document.createElement('option');
            placeholder.value = '';
            placeholder.textContent = 'Select an app first...';
            targetAction.appendChild(placeholder);
            targetAction.disabled = true;
        }
    });
}

function setupDelaySlider() {
    const slider = document.getElementById('detection-delay-slider');
    const display = document.getElementById('detection-delay-display');
    if (slider && display) slider.addEventListener('input', function () { display.textContent = `${this.value}ms`; });
}

function handleSaveMapping() {
    const selectedGestureNode = document.querySelector('input[name="gesture"]:checked');
    const sysCategory = document.getElementById('system-category-select').value;
    const sysAction = document.getElementById('system-action-select').value;
    let targetApp = document.getElementById('target-app-select').value;
    const targetAction = document.getElementById('target-action-select').value;
    const detectionDelay = parseInt(document.getElementById('detection-delay-slider')?.value || 250);

    if (!selectedGestureNode) return alert('Please select a gesture from the list.');

    // === PATH A: System-Level Mapping (left panel) ===
    if (sysCategory !== '') {
        if (!sysAction || sysAction === '') return alert('Please select an Action Type.');

        // Handle "Open Application" special case
        if (sysAction === 'Open Application') {
            const openAppSelect = document.getElementById('open-app-target-select');
            if (!openAppSelect || !openAppSelect.value) return alert('Please select a target application to open.');
            targetApp = openAppSelect.value;
        }

        const mappingData = {
            gesture_name: selectedGestureNode.value,
            target_app: targetApp || 'Global',
            action_type: sysAction,
            system_category: sysCategory,
            mapping_mode: 'System Level',
            detection_delay_ms: detectionDelay
        };
        return _doSave(mappingData);
    }

    // === PATH B: Application-Level Mapping (right panel) ===
    if (!targetApp || targetApp === 'Global') return alert('Please select a Target Application, or use the System Specific panel.');
    if (!targetAction || targetAction === '') return alert('Please select an Action Type for the selected application.');

    const mappingData = {
        gesture_name: selectedGestureNode.value,
        target_app: targetApp,
        action_type: targetAction,
        system_category: '',
        mapping_mode: 'Application Level',
        detection_delay_ms: detectionDelay
    };
    return _doSave(mappingData);
}

function _doSave(mappingData) {
    const saveBtn = document.getElementById('save-mapping-btn');
    saveBtn.disabled = true;

    pywebview.api.save_mapping(mappingData).then(response => {
        if (response.status === 'success') {
            window.location.href = '1_Action Mapping Screen.html';
        } else {
            alert(`Error: ${response.message}`);
            saveBtn.disabled = false;
        }
    }).catch(() => saveBtn.disabled = false);
}

// ==========================================
// MAPPED ACTIONS TABLE LOGIC (SCREEN 1)
// ==========================================
function loadMappedActionsTable() {
    const tbody = document.getElementById('mapped-actions-tbody');
    const loadingTemplate = document.getElementById('mapping-loading-template');
    if (!tbody) return;

    if (loadingTemplate) {
        tbody.replaceChildren(loadingTemplate.content.cloneNode(true));
    }

    const search = document.getElementById('mapping-search')?.value.trim() || "";
    const status = document.getElementById('mapping-status-filter')?.value || "All";

    // Load both the paginated mappings AND the mouse tracking state in parallel
    Promise.all([
        pywebview.api.get_paginated_mappings(search, status, currentMappingPage, mappingsPerPage),
        pywebview.api.get_mouse_tracking_state()
    ]).then(([data, isTrackingOn]) => {
        renderMappingsPage(data, isTrackingOn);
    });
}

function renderMappingsPage(pageData, isTrackingOn = false) {
    const tbody = document.getElementById('mapped-actions-tbody');
    const rowTemplate = document.getElementById('mapping-row-template');
    const emptyTemplate = document.getElementById('mapping-empty-template');
    const paginationContainer = document.getElementById('pagination-container');

    tbody.replaceChildren();

    // --- Pinned Mouse Tracking row (always first when enabled) ---
    if (isTrackingOn) {
        const pinnedRow = document.createElement('tr');
        pinnedRow.className = 'border-b border-amber-200/60 bg-amber-50/60';
        pinnedRow.innerHTML = `
            <td class="px-4 py-3">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center">
                        <span class="material-symbols-outlined text-amber-600 text-xl">back_hand</span>
                    </div>
                    <div>
                        <p class="font-semibold text-slate-800 text-sm">Index Finger</p>
                        <p class="text-[11px] text-amber-600 font-medium">Reserved for Mouse Tracking</p>
                    </div>
                </div>
            </td>
            <td class="px-4 py-3">
                <span class="px-2.5 py-1 rounded-full bg-amber-100 text-amber-700 text-[11px] font-bold uppercase tracking-tight">System Level</span>
            </td>
            <td class="px-4 py-3">
                <span class="px-2.5 py-1 rounded-full bg-amber-200 text-amber-800 text-[11px] font-bold uppercase tracking-tight">
                    🖱 Mouse Tracking
                </span>
            </td>
            <td class="px-4 py-3 text-slate-500 text-sm">Global</td>
            <td class="px-4 py-3 text-slate-400 text-sm">—</td>
            <td class="px-4 py-3">
                <span class="px-2.5 py-1 rounded-full bg-green-100 text-green-700 text-[11px] font-bold">Active</span>
            </td>
            <td class="px-4 py-3">
                <span class="text-[11px] text-slate-400 italic">Toggle off mouse tracking to edit</span>
            </td>`;
        tbody.appendChild(pinnedRow);
    }

    if (pageData.mappings.length === 0 && !isTrackingOn) {
        tbody.appendChild(emptyTemplate.content.cloneNode(true));
        if (paginationContainer) paginationContainer.classList.add('hidden');
        return;
    }

    if (paginationContainer) paginationContainer.classList.remove('hidden');

    pageData.mappings.forEach(mapping => {
        const clone = rowTemplate.content.cloneNode(true);

        if (mapping.thumbnail) {
            const imgEl = clone.querySelector('.row-gesture-img');
            imgEl.src = mapping.thumbnail;
            imgEl.classList.remove('hidden');
            clone.querySelector('.row-gesture-icon').classList.add('hidden');
        }

        clone.querySelector('.row-gesture-name').textContent = mapping.gesture_name;
        clone.querySelector('.row-mapping-mode').textContent = mapping.mapping_mode;

        const actionTypeBadge = clone.querySelector('.row-action-type');
        actionTypeBadge.textContent = mapping.action_type;
        if (mapping.mapping_mode === "Application Level") {
            actionTypeBadge.className = "row-action-type px-2.5 py-1 rounded-full bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 text-[11px] font-bold uppercase tracking-tight";
        }

        let targetText = mapping.target_app || "Global";
        if (mapping.secondary_app && mapping.secondary_app !== "None") targetText += ` + ${mapping.secondary_app}`;
        clone.querySelector('.row-target-app').textContent = targetText;
        clone.querySelector('.row-delay').textContent = mapping.detection_delay_ms ? `${mapping.detection_delay_ms}ms` : '250ms';

        const statusToggle = clone.querySelector('.row-status-toggle');
        statusToggle.checked = mapping.is_active !== false;
        statusToggle.addEventListener('change', function () {
            pywebview.api.toggle_mapping_status(mapping.gesture_name, mapping.target_app || "Global", this.checked).then(res => {
                if (res.status !== "success") alert("Failed to save status.");
            });
        });

        clone.querySelector('.row-delete-btn').onclick = function () {
            const targetApp = mapping.target_app || "Global";
            if (confirm(`Are you sure you want to delete the mapping for '${mapping.gesture_name}' on '${targetApp}'?`)) {
                pywebview.api.delete_mapping(mapping.gesture_name, targetApp).then(response => {
                    if (response.status === 'success') loadMappedActionsTable();
                    else alert(response.message);
                });
            }
        };

        tbody.appendChild(clone);
    });

    updatePaginationUI(pageData);
}

function updatePaginationUI(pageData) {
    const pageText = document.getElementById('pagination-text');
    const prevBtn = document.getElementById('pagination-prev');
    const nextBtn = document.getElementById('pagination-next');

    if (pageText) {
        const startItem = (pageData.current_page - 1) * mappingsPerPage + 1;
        const endItem = Math.min(pageData.current_page * mappingsPerPage, pageData.total_items);
        pageText.textContent = `Showing ${startItem} to ${endItem} of ${pageData.total_items} mappings`;
    }

    if (prevBtn) {
        prevBtn.disabled = pageData.current_page === 1;
        prevBtn.onclick = () => { currentMappingPage--; loadMappedActionsTable(); };
    }

    if (nextBtn) {
        nextBtn.disabled = pageData.current_page >= pageData.total_pages;
        nextBtn.onclick = () => { currentMappingPage++; loadMappedActionsTable(); };
    }
}