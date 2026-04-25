
// ============================================================================
// DATASET HUB LOGIC (Preview Gallery & Batch Augmentation)
// ============================================================================

// --- GLOBAL STATE: GALLERY ---
let allGestures = [];
let filteredGestures = [];
let currentPage = 1;
const itemsPerPage = 10;

// --- GLOBAL STATE: AUGMENTATION ---
const sliderConfig = [
    { id: 'rotation-slider', valId: 'rotation-val', suffix: '°' },
    { id: 'blur-slider', valId: 'blur-val', suffix: 'px' },
    { id: 'noise-slider', valId: 'noise-val', suffix: '%' },
    { id: 'brightness-slider', valId: 'brightness-val', suffix: 'x' },
    { id: 'contrast-slider', valId: 'contrast-val', suffix: 'x' }
];

const defaultParams = {
    rotation: 0,
    gaussian_blur: 0,
    noise_intensity: 0,
    brightness: 1,
    contrast: 1,
    random_flip: false
};

// ============================================================================
// INITIALIZATION
// ============================================================================

// --- 1. UI Default Setup (Runs instantly when HTML loads) ---
document.addEventListener("DOMContentLoaded", () => {
    // Instantly switch to the Gallery tab so it is the first thing the Admin sees
    if (typeof switchTab === 'function') {
        switchTab('tab-gallery', 'Augmentation Preview', 'nav-gallery');
    }
});

// --- 2. Backend Data Setup (Runs when Python bridge connects) ---
window.addEventListener('pywebviewready', async () => {
    // Initialize Gallery & start background poller that waits for previous request to finish
    let isPollingGallery = false;
    const pollGalleryData = async () => {
        // Only fetch if tab is visible AND previous request is settled
        if (!isPollingGallery && !document.hidden) {
            isPollingGallery = true;
            try {
                await fetchAndUpdateData();
            } catch(e) {}
            isPollingGallery = false;
        }
        setTimeout(pollGalleryData, 4000); // 4 s — wide enough for OpenCV thumbnail ops to finish
    };
    pollGalleryData();

    // Initialize Augmentation Screen Data
    await initializeAugmentationScreen();

    // Attach all static DOM Event Listeners
    attachStaticEventListeners();
});
// ============================================================================
// MODULE 1: PREVIEW GALLERY LOGIC
// ============================================================================

async function fetchAndUpdateData() {
    try {
        const response = await pywebview.api.get_augmented_gestures_summary();
        // 'busy' means a previous call is still processing on the backend — skip silently
        if (!response || response.status === 'busy') return;
        if (response.status === 'success') {
            allGestures = response.gestures;

            // Calculate total augmented images
            const totalImages = allGestures.reduce((sum, gesture) => sum + gesture.count, 0);
            const totalCountUI = document.getElementById('total-augmented-count');
            if (totalCountUI) totalCountUI.textContent = totalImages.toLocaleString();

            updateGestureDropdown();
            applyFiltersAndSort();
        }
    } catch (e) {
        console.error("Failed to fetch augmented gestures gallery data:", e);
    }
}

function updateGestureDropdown() {
    const gestureFilter = document.getElementById('gesture-filter');
    if (!gestureFilter) return;

    const currentSelection = gestureFilter.value;
    const newNames = allGestures.map(g => g.name).sort();

    gestureFilter.innerHTML = '<option value="all">All Gestures</option>';
    newNames.forEach(name => {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        gestureFilter.appendChild(opt);
    });

    if (newNames.includes(currentSelection)) {
        gestureFilter.value = currentSelection;
    } else {
        gestureFilter.value = 'all';
    }
}

function applyFiltersAndSort() {
    const gestureFilter = document.getElementById('gesture-filter');
    const sortFilter = document.getElementById('sort-filter');

    const selectedGesture = gestureFilter ? gestureFilter.value : 'all';

    if (selectedGesture === 'all') {
        filteredGestures = [...allGestures];
    } else {
        filteredGestures = allGestures.filter(g => g.name === selectedGesture);
    }

    const sortValue = sortFilter ? sortFilter.value : 'newest';

    filteredGestures.sort((a, b) => {
        if (sortValue === 'name-asc') return a.name.localeCompare(b.name);
        if (sortValue === 'name-desc') return b.name.localeCompare(a.name);
        if (sortValue === 'count-desc') return b.count - a.count;
        if (sortValue === 'count-asc') return a.count - b.count;
        return 0;
    });

    renderCurrentPage();
}

function renderCurrentPage() {
    const grid = document.getElementById('augmented-gestures-grid');
    const template = document.getElementById('gesture-card-template');
    const emptyState = document.getElementById('empty-state');
    const paginationContainer = document.getElementById('pagination-controls');

    if (!grid || !template) return;

    if (filteredGestures.length === 0) {
        if (emptyState) emptyState.classList.remove('hidden');
        if (paginationContainer) paginationContainer.classList.add('hidden');

        const existingCards = grid.querySelectorAll('.gesture-card');
        existingCards.forEach(card => card.remove());
        return;
    } else {
        if (emptyState) emptyState.classList.add('hidden');
        if (paginationContainer) paginationContainer.classList.remove('hidden');
    }

    const totalPages = Math.ceil(filteredGestures.length / itemsPerPage);

    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1) currentPage = 1;

    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const currentGestures = filteredGestures.slice(startIndex, endIndex);

    const existingCards = Array.from(grid.querySelectorAll('.gesture-card'));
    const newNames = currentGestures.map(g => g.name);

    existingCards.forEach(card => {
        if (!newNames.includes(card.dataset.name)) card.remove();
    });

    currentGestures.forEach((gesture, index) => {
        let card = grid.querySelector(`.gesture-card[data-name="${gesture.name}"]`);

        if (card) {
            const img = card.querySelector('.gesture-thumbnail');
            const count = card.querySelector('.gesture-count');

            if (img && img.src !== gesture.thumbnail) img.src = gesture.thumbnail;
            if (count && count.textContent !== String(gesture.count)) count.textContent = gesture.count;
            card.style.order = index;
        } else {
            const clone = template.content.cloneNode(true);
            const newCard = clone.querySelector('.gesture-card');

            newCard.dataset.name = gesture.name;
            newCard.style.order = index;

            const img = clone.querySelector('.gesture-thumbnail');
            const name = clone.querySelector('.gesture-name');
            const count = clone.querySelector('.gesture-count');
            const deleteBtn = clone.querySelector('.delete-gesture-btn');

            if (img) img.src = gesture.thumbnail;
            if (name) name.textContent = gesture.name;
            if (count) count.textContent = gesture.count;

            newCard.onclick = () => {
                alert(`Viewing Augmented Dataset for: ${gesture.name}\nTotal Generated Images: ${gesture.count}`);
            };

            if (deleteBtn) {
                deleteBtn.onclick = async (e) => {
                    e.stopPropagation();
                    if (confirm(`Are you sure you want to completely delete all augmented images for '${gesture.name}'? This cannot be undone.`)) {
                        newCard.style.opacity = '0.5';
                        newCard.style.pointerEvents = 'none';
                        const response = await pywebview.api.delete_augmented_gesture(gesture.name);
                        if (response.status === 'success') {
                            fetchAndUpdateData();
                        } else {
                            alert(response.message);
                            newCard.style.opacity = '1';
                            newCard.style.pointerEvents = 'auto';
                        }
                    }
                };
            }
            grid.appendChild(clone);
        }
    });

    updatePaginationUI(startIndex, Math.min(endIndex, filteredGestures.length), filteredGestures.length, totalPages);
}

function updatePaginationUI(start, end, total, totalPages) {
    const startElem = document.getElementById('page-start');
    const endElem = document.getElementById('page-end');
    const totalElem = document.getElementById('page-total');
    const btnContainer = document.getElementById('pagination-buttons');

    if (startElem) startElem.textContent = total === 0 ? 0 : start + 1;
    if (endElem) endElem.textContent = end;
    if (totalElem) totalElem.textContent = total;

    if (btnContainer) {
        btnContainer.innerHTML = '';

        const prevBtn = document.createElement('button');
        prevBtn.className = `p-2 rounded-lg border ${currentPage === 1 ? 'border-slate-100 text-slate-300 cursor-not-allowed bg-slate-50' : 'border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-primary'} flex items-center justify-center transition-all`;
        prevBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">chevron_left</span>';
        prevBtn.disabled = currentPage === 1;
        prevBtn.onclick = () => { if (currentPage > 1) { currentPage--; renderCurrentPage(); } };
        btnContainer.appendChild(prevBtn);

        for (let i = 1; i <= totalPages; i++) {
            const pageBtn = document.createElement('button');
            if (i === currentPage) {
                pageBtn.className = 'w-8 h-8 rounded-lg bg-primary text-white font-bold text-sm shadow-md shadow-primary/20 flex items-center justify-center transition-all';
            } else {
                pageBtn.className = 'w-8 h-8 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-primary hover:border-slate-300 font-semibold text-sm transition-all flex items-center justify-center';
            }
            pageBtn.textContent = i;
            pageBtn.onclick = () => { currentPage = i; renderCurrentPage(); };
            btnContainer.appendChild(pageBtn);
        }

        const nextBtn = document.createElement('button');
        nextBtn.className = `p-2 rounded-lg border ${currentPage === totalPages || totalPages === 0 ? 'border-slate-100 text-slate-300 cursor-not-allowed bg-slate-50' : 'border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-primary'} flex items-center justify-center transition-all`;
        nextBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">chevron_right</span>';
        nextBtn.disabled = currentPage === totalPages || totalPages === 0;
        nextBtn.onclick = () => { if (currentPage < totalPages) { currentPage++; renderCurrentPage(); } };
        btnContainer.appendChild(nextBtn);
    }
}

// ============================================================================
// MODULE 2: BATCH AUGMENTATION LOGIC
// ============================================================================

async function initializeAugmentationScreen() {
    const savedConfig = await pywebview.api.get_augmentation_params();

    if (savedConfig && savedConfig.status === "success") {
        const params = savedConfig.data;
        sliderConfig.forEach(item => {
            const slider = document.getElementById(item.id);
            const label = document.getElementById(item.valId);
            const key = item.id.replace('-slider', '').replace('blur', 'gaussian_blur');

            if (slider && params[key] !== undefined) {
                slider.value = params[key];
                if (label) label.textContent = slider.value + item.suffix;
            }
        });

        const flipToggle = document.getElementById('flip-toggle');
        if (flipToggle) flipToggle.checked = params.random_flip;
    }

    const gestures = await pywebview.api.get_saved_gestures();
    const selector = document.getElementById('gesture-selector');

    if (selector) {
        selector.innerHTML = "";
        gestures.forEach(g => {
            const opt = document.createElement('option');
            opt.value = g.name;
            opt.textContent = g.name;
            selector.appendChild(opt);
        });
    }

    if (gestures.length > 0) {
        updateImageCount(gestures[0].name);
        updateLiveStream(gestures[0].name);
    }

    setupSliderListeners();
    updateKPIs();
}

function setupSliderListeners() {
    sliderConfig.forEach(item => {
        const slider = document.getElementById(item.id);
        const label = document.getElementById(item.valId);

        if (slider && label) {
            slider.addEventListener('input', (e) => {
                label.textContent = e.target.value + item.suffix;
            });
        }
    });
}

async function updateImageCount(name) {
    const countSpan = document.getElementById('image-count-num');
    if (!countSpan) return;
    const response = await pywebview.api.get_gesture_summary(name);
    if (response.status === "success") countSpan.textContent = response.count;
}

async function saveAugmentationSettings() {
    const params = {
        rotation: document.getElementById('rotation-slider') ? document.getElementById('rotation-slider').value : 0,
        gaussian_blur: document.getElementById('blur-slider') ? document.getElementById('blur-slider').value : 0,
        noise_intensity: document.getElementById('noise-slider') ? document.getElementById('noise-slider').value : 0,
        brightness: document.getElementById('brightness-slider') ? document.getElementById('brightness-slider').value : 1,
        contrast: document.getElementById('contrast-slider') ? document.getElementById('contrast-slider').value : 1,
        random_flip: document.getElementById('flip-toggle') ? document.getElementById('flip-toggle').checked : false
    };

    const response = await pywebview.api.save_augmentation_params(params);
    if (response.status === "success") {
        alert("Parameters saved successfully.");
    } else {
        alert("Error saving parameters: " + response.message);
    }
}

function resetAugmentationSettings() {
    sliderConfig.forEach(item => {
        const slider = document.getElementById(item.id);
        const label = document.getElementById(item.valId);
        const key = item.id.replace('-slider', '').replace('blur', 'gaussian_blur');

        if (slider && defaultParams[key] !== undefined) {
            slider.value = defaultParams[key];
            if (label) label.textContent = slider.value + item.suffix;
        }
    });

    const flipToggle = document.getElementById('flip-toggle');
    if (flipToggle) flipToggle.checked = defaultParams.random_flip;
}

async function updateKPIs() {
    try {
        const kpis = await pywebview.api.get_augmentation_kpis();
        if (kpis && kpis.status === 'success') {
            const dsElem = document.getElementById('kpi-dataset-size');
            const spElem = document.getElementById('kpi-proc-speed');
            const memElem = document.getElementById('kpi-memory');
            const runElem = document.getElementById('kpi-last-run');

            if (dsElem && dsElem.childNodes.length > 0) dsElem.childNodes[0].textContent = kpis.dataset_size + " ";
            if (spElem && spElem.childNodes.length > 0) spElem.childNodes[0].textContent = kpis.proc_speed + " ";
            if (memElem) memElem.innerText = kpis.memory;
            if (runElem) runElem.innerText = kpis.last_run;
        }
    } catch (e) {
        console.error("Failed to update KPIs", e);
    }
}

async function updateLiveStream(gestureName, limit = 500) {
    const streamGrid = document.getElementById('live-stream-grid');
    const template = document.getElementById('stream-card-template');
    const emptyState = document.getElementById('stream-empty-state');

    if (!streamGrid || !template || !gestureName) return;

    try {
        const response = await pywebview.api.get_augmented_images(gestureName, limit);
        // Skip silently if backend is still processing a previous encode
        if (!response || response.status === 'busy') return;
        if (response.status === 'success') {
            const existingCards = streamGrid.querySelectorAll('.stream-card');
            existingCards.forEach(card => card.remove());

            if (response.images.length === 0) {
                if (emptyState) emptyState.classList.remove('hidden');
                return;
            }

            if (emptyState) emptyState.classList.add('hidden');

            response.images.forEach(img => {
                const clone = template.content.cloneNode(true);
                const imgElement = clone.querySelector('.stream-img');
                const nameElement = clone.querySelector('.stream-filename');

                if (imgElement) {
                    imgElement.src = img.base64;
                    imgElement.alt = img.filename;
                }
                if (nameElement) nameElement.textContent = img.filename;

                streamGrid.appendChild(clone);
            });
        }
    } catch (e) {
        console.error("Failed to load stream images:", e);
    }
}

// ============================================================================
// EVENT LISTENERS BINDING
// ============================================================================
function attachStaticEventListeners() {
    // --- Gallery Filters ---
    const gestureFilter = document.getElementById('gesture-filter');
    const sortFilter = document.getElementById('sort-filter');

    if (gestureFilter) {
        gestureFilter.addEventListener('change', () => {
            currentPage = 1;
            applyFiltersAndSort();
        });
    }
    if (sortFilter) sortFilter.addEventListener('change', applyFiltersAndSort);

    // --- Augmentation Controls ---
    const selector = document.getElementById('gesture-selector');
    if (selector) {
        selector.addEventListener('change', (e) => {
            updateImageCount(e.target.value);
            updateLiveStream(e.target.value);
        });
    }

    const saveBtn = document.getElementById('apply-batch-btn');
    if (saveBtn) saveBtn.onclick = saveAugmentationSettings;

    const resetBtn = document.getElementById('reset-aug-btn');
    if (resetBtn) resetBtn.onclick = resetAugmentationSettings;

    const useParamsToggle = document.getElementById('use-params-toggle');
    const paramsContainer = document.getElementById('params-container');

    if (useParamsToggle && paramsContainer) {
        useParamsToggle.addEventListener('change', (e) => {
            if (e.target.checked) {
                paramsContainer.classList.remove('opacity-50', 'pointer-events-none', 'grayscale');
            } else {
                paramsContainer.classList.add('opacity-50', 'pointer-events-none', 'grayscale');
            }
        });
    }

    // --- Batch Processing Execution ---
    const startBatchBtn = document.getElementById('start-batch-btn');
    if (startBatchBtn) {
        startBatchBtn.onclick = async () => {
            const gesture = document.getElementById('gesture-selector') ? document.getElementById('gesture-selector').value : null;
            const countInput = document.getElementById('augment-count-input') ? document.getElementById('augment-count-input').value : 500;
            const targetCount = parseInt(countInput, 10);
            const useParams = useParamsToggle ? useParamsToggle.checked : true;

            if (!gesture || isNaN(targetCount) || targetCount <= 0) {
                alert("Please check your configuration. Select a valid gesture and enter a count greater than 0.");
                return;
            }

            // UI Elements
            const gestureNameUI = document.getElementById('processing-gesture-name');
            const percentTextUI = document.getElementById('processing-percent-text');
            const progressBarUI = document.getElementById('processing-progress-bar');
            const processedCountUI = document.getElementById('processed-count');
            const remainingCountUI = document.getElementById('remaining-count');
            const etaTextUI = document.getElementById('eta-text');
            const processIconUI = document.getElementById('processing-icon');
            const btnIcon = document.getElementById('start-btn-icon');
            const btnText = document.getElementById('start-btn-text');
            const abortBatchBtn = document.getElementById('abort-batch-btn');
            const abortBtnText = document.getElementById('abort-btn-text');

            if (gestureNameUI) gestureNameUI.innerText = gesture;

            startBatchBtn.disabled = true;
            startBatchBtn.classList.add('opacity-75', 'cursor-not-allowed');
            if (btnIcon) { btnIcon.innerText = "sync"; btnIcon.classList.add('animate-spin'); }
            if (btnText) btnText.innerText = "Processing...";

            if (abortBatchBtn) {
                abortBatchBtn.disabled = false;
                abortBatchBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                abortBatchBtn.onclick = async () => {
                    if (abortBtnText) abortBtnText.innerText = "Aborting...";
                    await pywebview.api.abort_augmentation_batch();
                };
            }

            if (percentTextUI) percentTextUI.innerText = "0% Complete";
            if (progressBarUI) progressBarUI.style.width = "0%";
            if (processedCountUI) processedCountUI.innerText = `0 / ${targetCount} images`;
            if (remainingCountUI) remainingCountUI.innerText = "Processing in background...";
            if (etaTextUI) etaTextUI.innerText = "Est. time: calculating...";

            if (processIconUI) {
                processIconUI.innerText = "sync";
                processIconUI.classList.add('animate-spin', 'text-primary');
                processIconUI.classList.remove('text-green-500', 'text-slate-400', 'text-red-500');
            }

            let stopLiveStream = false;
            let isFetchingStream = false;
            const pollLiveStream = async () => {
                if (stopLiveStream) return;
                if (!isFetchingStream) {
                    isFetchingStream = true;
                    try {
                        await updateLiveStream(gesture, 30);
                    } catch(e) {}
                    isFetchingStream = false;
                }
                setTimeout(pollLiveStream, 3000); // 3 s — prevents JS bridge UID collision on heavy image batches
            };
            pollLiveStream();

            try {
                let response = await pywebview.api.start_augmentation_batch(gesture, targetCount, useParams);

                if (response.status === 'started') {
                    response = await new Promise((resolve) => {
                        const pollProgress = async () => {
                            try {
                                const progress = await pywebview.api.get_batch_progress();

                                if (progress && progress.status === 'processing') {
                                    if (progress.target > 0) {
                                        const percent = Math.round((progress.processed / progress.target) * 100);
                                        if (progressBarUI) progressBarUI.style.width = `${percent}%`;
                                        if (percentTextUI) percentTextUI.innerText = `${percent}% Complete`;
                                        if (processedCountUI) processedCountUI.innerText = `${progress.processed} / ${progress.target} images`;
                                    }
                                    setTimeout(pollProgress, 150);
                                } else if (progress && progress.status !== 'idle') {
                                    resolve(progress);
                                }
                            } catch (e) {
                                resolve({ status: 'error', message: 'Lost connection to backend.' });
                            }
                        };
                        pollProgress();
                    });
                }

                if (response.status === 'success') {
                    if (progressBarUI) progressBarUI.style.width = "100%";
                    if (percentTextUI) percentTextUI.innerText = "100% Complete";
                    if (processedCountUI) processedCountUI.innerText = `${targetCount} / ${targetCount} images`;
                    if (remainingCountUI) remainingCountUI.innerText = "Completed!";
                    if (etaTextUI) etaTextUI.innerText = "Finished";

                    if (processIconUI) {
                        processIconUI.classList.remove('animate-spin', 'text-primary');
                        processIconUI.classList.add('text-green-500');
                        processIconUI.innerText = "check_circle";
                    }
                    setTimeout(() => alert(response.message), 300);

                } else if (response.status === 'aborted') {
                    if (progressBarUI) progressBarUI.style.width = "0%";
                    if (percentTextUI) percentTextUI.innerText = "Aborted";
                    if (remainingCountUI) remainingCountUI.innerText = "Reverted partial generation.";
                    if (etaTextUI) etaTextUI.innerText = "Process Stopped";

                    if (processIconUI) {
                        processIconUI.classList.remove('animate-spin', 'text-primary');
                        processIconUI.classList.add('text-red-500');
                        processIconUI.innerText = "cancel";
                    }
                    setTimeout(() => alert(response.message), 100);
                } else {
                    if (remainingCountUI) remainingCountUI.innerText = "Aborted";
                    alert(`Notice: ${response.message}`);
                }
            } catch (error) {
                if (remainingCountUI) remainingCountUI.innerText = "Failed";
                alert("An unexpected error occurred while processing.");
            } finally {
                stopLiveStream = true;
                updateLiveStream(gesture, targetCount + 50);
                updateKPIs();

                startBatchBtn.disabled = false;
                startBatchBtn.classList.remove('opacity-75', 'cursor-not-allowed');
                if (btnIcon) { btnIcon.innerText = "play_arrow"; btnIcon.classList.remove('animate-spin'); }
                if (btnText) btnText.innerText = "Start Batch Processing";

                if (abortBatchBtn) {
                    abortBatchBtn.disabled = true;
                    abortBatchBtn.classList.add('opacity-50', 'cursor-not-allowed');
                    if (abortBtnText) abortBtnText.innerText = "Abort Batch";
                }
            }
        };
    }
}