// ==========================================
// GLOBAL STATE VARIABLES
// ==========================================
let recentScans = [];
let isSelectionMode = false;
let selectedIds = new Set();
let scanCounter = 0;
let currentModalGesture = null;

// ==========================================
// INITIALIZATION (Runs when Python is ready)
// ==========================================
window.addEventListener('pywebviewready', function () {
    // 1. If on "My Gestures" screen
    if (document.getElementById('gestures-grid')) {
        loadSavedGestures();
    }

    // 2. If on "Sample Scan" screen
    if (document.getElementById('live-feed')) {
        pywebview.api.get_current_session().then(sessionData => {
            if (sessionData && sessionData.gesture_name) {
                document.getElementById('gesture-name-input').value = sessionData.gesture_name;
                sessionData.frames.forEach(frame => {
                    recentScans.push({ id: frame.temp_id, base64: frame.base64 });
                });
                scanCounter = sessionData.frames.length;
                renderGallery();
            }
        });
    }
});

window.addEventListener('beforeunload', function() {
    pywebview.api.stop_scan(); // Silent fire-and-forget to clean up threads
});
// ==========================================
// 1. SCAN SCREEN LOGIC
// ==========================================
function updateFrame(base64Image) {
    const feed = document.getElementById('live-feed');
    const placeholder = document.getElementById('camera-placeholder');
    if (feed && placeholder) {
        feed.src = base64Image;
        placeholder.style.display = 'none';
    }
}

function clearFrame() {
    const feed = document.getElementById('live-feed');
    const placeholder = document.getElementById('camera-placeholder');
    if (feed && placeholder) {
        feed.src = '';
        placeholder.style.display = 'flex';
        updateGestureMetrics(0);
    }
}

function updateGestureMetrics(confidence) {
    const confEl = document.getElementById('gesture-confidence');
    const barEl = document.getElementById('confidence-bar');
    const indEl = document.getElementById('gesture-indicator');

    if (confEl) confEl.innerText = confidence + '%';
    if (barEl) barEl.style.width = confidence + '%';
    if (indEl) indEl.style.display = confidence > 0 ? 'inline-block' : 'none';
}

/**
 * Unified frame handler called by Python's _scan_loop.
 * Accepts a single JSON payload to halve PyWebView bridge round-trips,
 * preventing the "Cannot read properties of undefined" JavascriptException
 * caused by rapid evaluate_js calls overwhelming the promise UID tracker.
 * @param {{frame: string, confidence: number}} payload
 */
function updateScanFrame(payload) {
    if (payload && payload.frame) updateFrame(payload.frame);
    if (payload && payload.confidence !== undefined) updateGestureMetrics(payload.confidence);
}


function startScanning() {
    pywebview.api.start_scan();
    document.getElementById('camera-status').innerText = "LIVE: WEBCAM";
    document.getElementById('recording-dot').style.display = "inline-block";
}

function stopScanning() {
    pywebview.api.stop_scan();
    document.getElementById('camera-status').innerText = "OFFLINE";
    document.getElementById('recording-dot').style.display = "none";
}

let currentScanMode = 'static';

function setScanMode(mode) {
    currentScanMode = mode;
    const btnStatic = document.getElementById('mode-static');
    const btnSequence = document.getElementById('mode-sequence');
    const imgGrid = document.getElementById('scanned-images-grid');
    const selectBtns = document.getElementById('select-btn')?.parentElement;

    if (mode === 'static') {
        btnStatic.className = "flex-1 py-2 text-xs font-bold bg-slate-900 dark:bg-slate-700 text-white rounded-lg transition-all shadow-md";
        btnSequence.className = "flex-1 py-2 text-xs font-bold bg-transparent text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-all";
        if (imgGrid) imgGrid.style.display = 'grid';
        if (selectBtns) selectBtns.style.display = 'grid';
        document.querySelector('button[onclick="captureGestureImage()"]').innerHTML = '<span class="material-symbols-outlined">photo_camera</span> Capture';
    } else {
        btnSequence.className = "flex-1 py-2 text-xs font-bold bg-slate-900 dark:bg-slate-700 text-white rounded-lg transition-all shadow-md";
        btnStatic.className = "flex-1 py-2 text-xs font-bold bg-transparent text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-all";
        if (imgGrid) imgGrid.style.display = 'none';
        if (selectBtns) selectBtns.style.display = 'none';
        document.querySelector('button[onclick="captureGestureImage()"]').innerHTML = '<span class="material-symbols-outlined">motion_sensor_active</span> Record Motion';
    }
}

function captureGestureImage() {
    if (currentScanMode === 'sequence') {
        const gestureName = document.getElementById('gesture-name-input').value;
        if (!gestureName || gestureName.trim() === "") {
            alert("Please enter a name for this gesture before recording a motion!");
            document.getElementById('gesture-name-input').focus();
            return;
        }

        const captureBtn = document.querySelector('button[onclick="captureGestureImage()"]');
        const origHtml = captureBtn.innerHTML;
        captureBtn.innerHTML = "Recording...";
        captureBtn.classList.add("animate-pulse", "bg-red-500");
        
        pywebview.api.start_motion_scan().then(() => {
            // Wait 1.5 seconds to capture a nice trailing trajectory buffer
            setTimeout(() => {
                pywebview.api.save_motion_session(gestureName).then((res) => {
                    captureBtn.innerHTML = origHtml;
                    captureBtn.classList.remove("animate-pulse", "bg-red-500");
                    if(res.status === 'success') {
                        alert("Motion sequence recorded successfully!");
                    } else {
                        alert(res.message);
                    }
                });
            }, 1500);
        });
        return;
    }

    // Default static logic
    pywebview.api.capture_image().then(response => {
        if (response.status === "error") alert(response.message);
    });
}

function saveGestureSession() {
    if (currentScanMode === 'sequence') {
        alert("For sequences, use 'Record Motion' and it will save automatically.");
        return;
    }

    if (recentScans.length === 0) {
        alert("No images captured! Please capture some images first.");
        return;
    }

    const gestureName = document.getElementById('gesture-name-input').value;
    if (!gestureName || gestureName.trim() === "") {
        alert("Please enter a name for this gesture before saving!");
        document.getElementById('gesture-name-input').focus();
        return;
    }

    pywebview.api.save_session(gestureName).then(response => {
        if (response.status === "success") {
            recentScans = [];
            selectedIds.clear();
            isSelectionMode = false;

            const selectBtnText = document.getElementById('select-btn-text');
            const selectBtn = document.getElementById('select-btn');
            const nameInput = document.getElementById('gesture-name-input');

            if (selectBtnText) selectBtnText.innerText = 'Select Image';
            if (selectBtn) selectBtn.classList.remove('bg-slate-100', 'dark:bg-slate-700');
            if (nameInput) nameInput.value = '';

            renderGallery();
            alert(response.message);
        } else {
            alert(response.message);
        }
    });
}

function addScannedImage(imgData) {
    recentScans.unshift({ id: imgData.temp_id, base64: imgData.base64 });
    renderGallery();
}

function renderGallery() {
    const grid = document.getElementById('scanned-images-grid');
    const badge = document.getElementById('scan-count-badge');
    if (!grid) return;

    grid.innerHTML = '';
    recentScans.forEach(scan => {
        const isSelected = selectedIds.has(scan.id);

        const wrapper = document.createElement('div');
        wrapper.className = `relative aspect-square rounded-lg overflow-hidden border-2 cursor-pointer transition-all ${isSelected ? 'border-primary' : 'border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800'}`;
        wrapper.onclick = () => handleImageClick(scan.id);

        const img = document.createElement('img');
        img.src = scan.base64;
        img.className = `w-full h-full object-cover transition-all ${isSelectionMode ? (isSelected ? 'opacity-100' : 'opacity-60') : 'hover:grayscale-0 grayscale-[0.2]'}`;
        wrapper.appendChild(img);

        if (isSelected) {
            const check = document.createElement('div');
            check.className = 'absolute top-1 right-1 bg-primary text-white rounded-full size-5 flex items-center justify-center';
            check.innerHTML = '<span class="material-symbols-outlined text-[12px] font-bold">check</span>';
            wrapper.appendChild(check);
        }

        grid.appendChild(wrapper);
    });

    if (badge) badge.innerText = `${recentScans.length} RECENT SCANS`;
    updateDeleteButtonState();
}

function toggleSelectionMode() {
    if (recentScans.length === 0) return;

    isSelectionMode = !isSelectionMode;
    const selectBtn = document.getElementById('select-btn');
    const btnText = document.getElementById('select-btn-text');

    if (isSelectionMode) {
        btnText.innerText = 'Cancel Selection';
        selectBtn.classList.add('bg-slate-100', 'dark:bg-slate-700');
    } else {
        btnText.innerText = 'Select Image';
        selectBtn.classList.remove('bg-slate-100', 'dark:bg-slate-700');
        selectedIds.clear();
    }
    renderGallery();
}

function handleImageClick(id) {
    if (!isSelectionMode) return;
    if (selectedIds.has(id)) selectedIds.delete(id);
    else selectedIds.add(id);
    renderGallery();
}

function updateDeleteButtonState() {
    const deleteBtn = document.getElementById('delete-btn');
    const deleteText = document.getElementById('delete-btn-text');
    if (!deleteBtn || !deleteText) return;

    if (selectedIds.size > 0) {
        deleteBtn.classList.remove('opacity-50', 'cursor-not-allowed');
        deleteBtn.removeAttribute('disabled');
        deleteText.innerText = `Delete (${selectedIds.size})`;
    } else {
        deleteBtn.classList.add('opacity-50', 'cursor-not-allowed');
        deleteBtn.setAttribute('disabled', 'true');
        deleteText.innerText = `Delete`;
    }
}

function deleteSelectedImages() {
    if (selectedIds.size === 0) return;

    const idsToDelete = Array.from(selectedIds);
    pywebview.api.delete_images(idsToDelete).then(response => {
        recentScans = recentScans.filter(scan => !selectedIds.has(scan.id));
        selectedIds.clear();
        isSelectionMode = false;

        const btnText = document.getElementById('select-btn-text');
        const selectBtn = document.getElementById('select-btn');
        if (btnText) btnText.innerText = 'Select Image';
        if (selectBtn) selectBtn.classList.remove('bg-slate-100', 'dark:bg-slate-700');

        renderGallery();
    });
}

function resetSession() {
    if (recentScans.length === 0) {
        alert("No scanned images to reset.");
        return;
    }
    if (!confirm("Are you sure you want to delete ALL scanned images from this session?")) return;

    pywebview.api.clear_session().then(response => {
        recentScans = [];
        selectedIds.clear();
        isSelectionMode = false;

        const btnText = document.getElementById('select-btn-text');
        const selectBtn = document.getElementById('select-btn');
        if (btnText) btnText.innerText = 'Select Image';
        if (selectBtn) selectBtn.classList.remove('bg-slate-100', 'dark:bg-slate-700');

        renderGallery();
    });
}

// gesture_logic.js

function safeNavigate(targetUrl) {
    console.log("Stopping camera before navigation...");
    
    // 1. Call the stop_scan API
    pywebview.api.stop_scan().then((response) => {
        if (response.status === "success") {
            // 2. Only navigate once the camera thread is safely shutting down
            window.location.href = targetUrl;
        }
    }).catch((err) => {
        // Fallback: Force navigation if the API call fails
        console.error("Navigation error:", err);
        window.location.href = targetUrl;
    });
}

// ==========================================
// 2. SAVED GESTURES SCREEN LOGIC
// ==========================================
// backend/frontend/user_app/2_Gusture Module/gesture_logic.js

function loadSavedGestures() {
    pywebview.api.get_saved_gestures().then(gestures => {
        renderGestureGrid(gestures);
    });
}

function deleteGesture(gestureName) {
    if (confirm(`Are you sure you want to permanently delete the '${gestureName}' gesture? This cannot be undone.`)) {
        pywebview.api.delete_gesture(gestureName).then(response => {
            if (response.status === 'success') loadSavedGestures();
            else alert(response.message);
        });
    }
}

// ==========================================
// 3. MODAL LOGIC (Saved Gestures Screen)
// ==========================================
function openImageViewModal(gestureName) {
    currentModalGesture = gestureName;
    const modal = document.getElementById('image-view-modal');
    const grid = document.getElementById('modal-images-grid');
    const title = document.getElementById('modal-title');
    const footerText = document.getElementById('modal-footer-text');
    const imageTemplate = document.getElementById('modal-image-template');
    const selectAllBtn = document.getElementById('select-all-btn');

    if (selectAllBtn) selectAllBtn.innerHTML = '<span class="truncate">Select All</span>';

    modal.classList.remove('hidden');
    grid.innerHTML = '<div class="col-span-full text-center text-slate-500 py-10">Loading images...</div>';
    title.textContent = `Gesture Samples - ${gestureName}`;

    pywebview.api.get_gesture_images(gestureName).then(data => {
        grid.innerHTML = '';

        data.images.forEach(imgData => {
            const clone = imageTemplate.content.cloneNode(true);
            clone.querySelector('.modal-img').src = imgData.base64;
            clone.querySelector('.modal-filename').textContent = imgData.filename;
            clone.querySelector('.modal-checkbox').value = imgData.filename;
            grid.appendChild(clone);
        });

        footerText.textContent = `Showing ${data.images.length} samples`;
    });
}

function closeImageViewModal() {
    const modal = document.getElementById('image-view-modal');
    if (modal) modal.classList.add('hidden');

    const grid = document.getElementById('modal-images-grid');
    if (grid) grid.innerHTML = '';

    currentModalGesture = null;
}

function selectAllModalImages(btn) {
    const checkboxes = document.querySelectorAll('#modal-images-grid .modal-checkbox');
    const isSelectingAll = btn.innerText.trim() === "Select All";

    checkboxes.forEach(cb => cb.checked = isSelectingAll);
    btn.innerHTML = `<span class="truncate">${isSelectingAll ? "Deselect All" : "Select All"}</span>`;
}

function deleteSelectedModalImages() {
    if (!currentModalGesture) return;

    const checkedBoxes = document.querySelectorAll('#modal-images-grid .modal-checkbox:checked');
    if (checkedBoxes.length === 0) {
        alert("Please select at least one image to delete.");
        return;
    }

    if (!confirm(`Are you sure you want to permanently delete these ${checkedBoxes.length} images?`)) return;

    const filenames = Array.from(checkedBoxes).map(cb => cb.value);

    pywebview.api.delete_saved_images(currentModalGesture, filenames).then(response => {
        if (response.status === 'success') {
            if (response.folder_deleted) {
                alert("All images deleted. Gesture folder removed.");
                closeImageViewModal();
                loadSavedGestures();
            } else {
                openImageViewModal(currentModalGesture);
                loadSavedGestures();
            }
        } else {
            alert(response.message);
        }
    });
}

/**
 * Executes a search via the Python SearchService and re-renders the gesture grid.
 */
function liveSearch() {
    const query = document.getElementById('main-search-input').value;
    const grid = document.getElementById('gestures-grid');
    
    if (!grid) return;

    // Use the backend API to filter items based on the query
    pywebview.api.search_items("gestures", query).then(response => {
        if (response.status === "success") {
            // Re-use the rendering logic to update the screen
            renderGestureGrid(response.results);
        }
    });
}

/**
 * Helper function to render the gesture grid from a list of objects.
 */
function renderGestureGrid(gestures) {
    const grid = document.getElementById('gestures-grid');
    grid.innerHTML = ''; 
    
    const cardTemplate = document.getElementById('gesture-card-template');
    const addNewTemplate = document.getElementById('add-new-card-template');

    // 1. Render matching gestures
    if (gestures && gestures.length > 0) {
        gestures.forEach(gesture => {
            const cardClone = cardTemplate.content.cloneNode(true);
            const imgElement = cardClone.querySelector('.gesture-img');
            
            imgElement.src = gesture.thumbnail || 'https://via.placeholder.com/400x225?text=No+Image';
            cardClone.querySelector('.gesture-name').textContent = gesture.name;
            cardClone.querySelector('.gesture-count').textContent = gesture.count;
            
            cardClone.querySelector('.view-trigger').onclick = () => openImageViewModal(gesture.name);
            cardClone.querySelector('.edit-btn').onclick = () => {
                pywebview.api.edit_gesture(gesture.name).then(() => {
                    window.location.href = '2_Guesture Scan Screen.html';
                });
            };
            cardClone.querySelector('.delete-btn').onclick = () => deleteGesture(gesture.name);
            grid.appendChild(cardClone);
        });
    }

    // 2. Always show the "New Training Sample" card at the end
    if (addNewTemplate) {
        const addNewClone = addNewTemplate.content.cloneNode(true);
        grid.appendChild(addNewClone);
    }
}