// augumentation_logic.js

const selector = document.getElementById('gesture-selector');
const countSpan = document.getElementById('image-count-num');

const sliderConfig = [
    { id: 'rotation-slider', valId: 'rotation-val', suffix: '°' },
    { id: 'blur-slider', valId: 'blur-val', suffix: 'px' },
    { id: 'noise-slider', valId: 'noise-val', suffix: '%' },
    { id: 'brightness-slider', valId: 'brightness-val', suffix: 'x' },
    { id: 'contrast-slider', valId: 'contrast-val', suffix: 'x' }
];

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
        if (countSpan) updateImageCount(gestures[0].name);
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
    if (!countSpan) return;
    const response = await pywebview.api.get_gesture_summary(name);
    if (response.status === "success") {
        countSpan.textContent = response.count;
    }
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

if (selector) {
    selector.addEventListener('change', (e) => {
        updateImageCount(e.target.value);
        updateLiveStream(e.target.value);
    });
}

const defaultParams = {
    rotation: 0,
    gaussian_blur: 0,
    noise_intensity: 0,
    brightness: 1,
    contrast: 1,
    random_flip: false
};

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
                if (nameElement) {
                    nameElement.textContent = img.filename;
                }

                streamGrid.appendChild(clone);
            });
        }
    } catch (e) {
        console.error("Failed to load stream images:", e);
    }
}

document.addEventListener('DOMContentLoaded', () => {
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

            // Safe non-overlapping live-stream poller — uses recursive setTimeout
            // so the next call only starts AFTER the previous one settles.
            let stopLiveStream = false;
            let isFetchingStream = false;
            const pollLiveStream = async () => {
                if (stopLiveStream) return;
                if (!isFetchingStream) {
                    isFetchingStream = true;
                    try { await updateLiveStream(gesture, 30); } catch(e) {}
                    isFetchingStream = false;
                }
                setTimeout(pollLiveStream, 3000); // 3 s — prevents JS bridge UID collision
            };
            pollLiveStream();

            try {
                // 1. Kick off the background task instantly
                let response = await pywebview.api.start_augmentation_batch(gesture, targetCount, useParams);

                if (response.status === 'started') {
                    // 2. Poll for real-time progress AND wait for the background thread to finish
                    response = await new Promise((resolve) => {
                        // Replaced setInterval with a recursive timeout function
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
                                    // Schedule the next poll ONLY after this one is fully processed
                                    setTimeout(pollProgress, 150);
                                } else if (progress && progress.status !== 'idle') {
                                    resolve(progress);
                                }
                            } catch (e) {
                                resolve({ status: 'error', message: 'Lost connection to backend.' });
                            }
                        };

                        pollProgress(); // Start the polling loop
                    });
                }

                // --- 3. HANDLE FINAL RESPONSES ---
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
                // --- 4. UNLOCK UI & FETCH FINAL IMAGES ---
                stopLiveStream = true; // Stop the recursive setTimeout live-stream poller
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
});

window.addEventListener('pywebviewready', initializeAugmentationScreen);