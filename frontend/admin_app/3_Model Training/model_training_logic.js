// frontend/admin_app/3_Model Training/model_training_logic.js

let selectedOptimizer = "Adam";
let trainingChart = null;
let evalChart = null; // Reference for the Evaluation Tab Chart

/**
 * TAB MANAGEMENT
 */
window.switchTab = function (tabId, title, desc, btnId) {
    document.querySelectorAll('.tab-page').forEach(el => el.classList.add('hidden'));

    const targetTab = document.getElementById(tabId);
    if (targetTab) targetTab.classList.remove('hidden');

    const titleEl = document.getElementById('page-title');
    const descEl = document.getElementById('page-desc');
    if (titleEl) titleEl.textContent = title;
    if (descEl) descEl.textContent = desc;

    document.querySelectorAll('.header-actions').forEach(el => el.classList.add('hidden'));
    const actions = document.getElementById(tabId + '-actions');
    if (actions) actions.classList.remove('hidden');

    document.querySelectorAll('.nav-link').forEach(el => {
        el.className = 'nav-link flex flex-col items-center justify-center border-b-[3px] border-transparent text-[#555a91] pb-4 pt-2 hover:text-primary transition-all';
    });

    const activeBtn = document.getElementById(btnId);
    if (activeBtn) {
        activeBtn.className = 'nav-link flex flex-col items-center justify-center border-b-[3px] border-primary text-primary pb-4 pt-2 group';
    }

    if (tabId === 'tab-train') {
        syncLiveTrainingParams();
    }
};

/**
 * INITIALIZATION
 */
window.addEventListener('pywebviewready', async () => {
    try {
        const data = await pywebview.api.get_training_init_data();
        if (!data) return;

        const slider = document.getElementById('lr-slider');
        if (slider && data.constraints) {
            slider.min = data.constraints.lr_min;
            slider.max = data.constraints.lr_max;
            slider.step = data.constraints.lr_step;
        }

        if (data.constraints?.optimizers) {
            renderOptimizerButtons(data.constraints.optimizers);
        }

        if (data.saved_config) {
            applySavedValuesToUI(data.saved_config);
        }

        if (data.saved_eval) {
            restoreEvaluationUI(data.saved_eval, data.saved_config?.epochs || 10);
        }
    } catch (error) {
        console.error("Failed to initialize training UI:", error);
    }
});

/**
 * OPTIMIZER SELECTION
 */
function renderOptimizerButtons(optimizers) {
    const container = document.getElementById('optimizer-container');
    if (!container) return;

    container.replaceChildren();

    optimizers.forEach(opt => {
        const btn = document.createElement('button');
        btn.textContent = opt;
        btn.id = `opt-btn-${opt}`;
        btn.className = "px-6 py-2 rounded-md text-[#555a91] text-sm font-bold hover:bg-white/50 transition-colors optimizer-option";
        btn.onclick = () => setActiveOptimizer(opt);
        container.appendChild(btn);
    });
    setActiveOptimizer(selectedOptimizer);
}

function setActiveOptimizer(opt) {
    selectedOptimizer = opt;
    document.querySelectorAll('.optimizer-option').forEach(btn => {
        btn.classList.remove('bg-primary', 'text-white', 'shadow-sm');
        btn.classList.add('text-[#555a91]');
    });

    const activeBtn = document.getElementById(`opt-btn-${opt}`);
    if (activeBtn) {
        activeBtn.classList.add('bg-primary', 'text-white', 'shadow-sm');
        activeBtn.classList.remove('text-[#555a91]');
    }
}

/**
 * DATA PERSISTENCE
 */
async function saveTrainingConfig() {
    const config = {
        architecture: document.getElementById('model-architecture')?.value,
        experiment_name: document.getElementById('experiment-name')?.value,
        epochs: parseInt(document.getElementById('training-epochs')?.value || 0),
        batch_size: parseInt(document.getElementById('batch-size')?.value || 0),
        learning_rate: parseFloat(document.getElementById('lr-slider')?.value || 0),
        optimizer: selectedOptimizer,
        augmentation_enabled: document.getElementById('aug-toggle')?.checked ?? true
    };

    const response = await pywebview.api.save_training_config(config);
    showToastNotification(response.message, response.status === "success");
}

/**
 * UI HELPERS
 */
function syncLR(val) {
    const elements = {
        slider: document.getElementById('lr-slider'),
        text: document.getElementById('lr-text'),
        badge: document.getElementById('lr-badge')
    };
    if (elements.slider) elements.slider.value = val;
    if (elements.text) elements.text.value = val;
    if (elements.badge) elements.badge.textContent = val;
}

function applySavedValuesToUI(config) {
    const fields = {
        'model-architecture': config.architecture,
        'experiment-name': config.experiment_name,
        'training-epochs': config.epochs,
        'batch-size': config.batch_size
    };

    Object.entries(fields).forEach(([id, value]) => {
        const el = document.getElementById(id);
        if (el && value !== undefined) el.value = value;
    });

    const augToggle = document.getElementById('aug-toggle');
    if (augToggle) augToggle.checked = config.augmentation_enabled ?? true;

    if (config.learning_rate) syncLR(config.learning_rate);
    if (config.optimizer) setActiveOptimizer(config.optimizer);
}

function showToastNotification(msg, isSuccess) {
    const toast = document.getElementById('save-toast');
    const text = document.getElementById('toast-msg');
    if (!toast || !text) return;

    text.textContent = msg;
    toast.className = `fixed bottom-10 right-10 flex items-center gap-3 px-6 py-4 rounded-xl shadow-2xl z-[100] transition-opacity ${isSuccess ? "bg-emerald-500" : "bg-red-500"
        } text-white`;

    toast.classList.remove('hidden');
    setTimeout(() => toast.classList.add('hidden'), 3000);
}

/**
 * LIVE TRAINING TAB SYNC
 */
async function syncLiveTrainingParams() {
    try {
        const data = await pywebview.api.get_training_init_data();
        const config = data.saved_config;

        if (config) {
            const liveParams = {
                'live-batch-size': config.batch_size,
                'live-lr': config.learning_rate,
                'live-optimizer': config.optimizer,
                'live-epochs': config.epochs
            };

            Object.entries(liveParams).forEach(([id, value]) => {
                const el = document.getElementById(id);
                if (el) el.textContent = value || "--";
            });

            updateAugmentationBadge(config.augmentation_enabled);
        }
    } catch (error) {
        console.error("Error syncing Live Training parameters:", error);
    }
}

function updateAugmentationBadge(isEnabled) {
    const augEl = document.getElementById('live-augmentation');
    if (!augEl) return;

    augEl.textContent = isEnabled ? "Enabled" : "Disabled";
    augEl.className = isEnabled
        ? "text-green-600 font-bold text-[10px] bg-green-100 px-2 py-0.5 rounded-full uppercase"
        : "text-slate-400 font-bold text-[10px] bg-slate-100 px-2 py-0.5 rounded-full uppercase";
}

/**
 * DYNAMIC CONFUSION MATRIX BUILDER
 * Now accepts dynamic class names from Python.
 */
function renderConfusionMatrix(matrix, classes) {
    const container = document.getElementById('confusion-matrix-grid');
    if (!container || !matrix || matrix.length === 0) return;

    container.replaceChildren(); // Clear the "Waiting" message

    const numClasses = matrix.length;

    // NEW: Use the real gesture names if Python sends them, otherwise fallback to Class A, B...
    const classNames = (classes && classes.length === numClasses)
        ? classes
        : Array.from({ length: numClasses }, (_, i) => `Class ${String.fromCharCode(65 + i)}`);

    container.className = `relative grid gap-2 p-2`;
    container.style.gridTemplateColumns = `repeat(${numClasses + 1}, minmax(0, 1fr))`;

    // 1. Top Header Row
    container.appendChild(document.createElement('div'));
    classNames.forEach(name => {
        const el = document.createElement('div');
        // Adjusted text size/truncation slightly to fit longer gesture names
        el.className = "text-center text-[10px] font-bold text-slate-400 uppercase flex items-end justify-center pb-2 truncate overflow-hidden";
        el.textContent = name;
        el.title = name; // Add hover tooltip for long names
        container.appendChild(el);
    });

    let maxVal = 0;
    matrix.forEach(row => row.forEach(val => maxVal = Math.max(maxVal, val)));

    // 2. Data Rows with Heatmap Colors
    matrix.forEach((row, i) => {
        const rowLabel = document.createElement('div');
        rowLabel.className = "flex items-center justify-end pr-2 text-[10px] font-bold text-slate-400 uppercase truncate text-right";
        rowLabel.textContent = classNames[i];
        rowLabel.title = classNames[i];
        container.appendChild(rowLabel);

        row.forEach(val => {
            const cell = document.createElement('div');
            cell.className = "aspect-square flex items-center justify-center rounded text-sm font-bold transition-all duration-500";

            if (val === 0) {
                cell.classList.add('bg-slate-50', 'text-slate-300');
            } else {
                const intensity = Math.max(0.1, val / maxVal);
                cell.style.backgroundColor = `rgba(26, 34, 127, ${intensity})`; // Primary blue with alpha
                cell.style.color = intensity > 0.5 ? 'white' : '#1a227f';
            }

            cell.textContent = val;
            container.appendChild(cell);
        });
    });
}
/**
 * RESTORE EVALUATION UI FROM SAVED DATA
 */
function restoreEvaluationUI(savedEval, totalEpochs) {
    if (!savedEval) return;

    // 1. Restore KPIs
    const kpiMappings = {
        'eval-duration': savedEval.duration_str,
        'eval-precision': savedEval.precision_str,
        'eval-recall': savedEval.recall_str,
        'eval-f1': savedEval.f1_str,
        'eval-final-train-acc': savedEval.final_train_acc_str,
        'eval-final-val-acc': savedEval.final_val_acc_str
    };

    Object.entries(kpiMappings).forEach(([id, value]) => {
        const el = document.getElementById(id);
        if (el && value) el.textContent = value;
    });

    // 2. Restore Confusion Matrix
    if (savedEval.confusion_matrix) {
        renderConfusionMatrix(savedEval.confusion_matrix, savedEval.classes);
    }

    // 3. Restore Charts
    const actualEpochs = Math.max(totalEpochs, savedEval.accuracy_history?.length || 10);
    initLiveChart(actualEpochs);

    if (savedEval.accuracy_history) {
        if (trainingChart) {
            trainingChart.data.datasets[0].data = savedEval.accuracy_history;
            trainingChart.data.datasets[1].data = savedEval.loss_history || [];
            trainingChart.update('none');
        }

        if (evalChart && savedEval.val_accuracy_history) {
            evalChart.data.datasets[0].data = savedEval.accuracy_history;
            evalChart.data.datasets[1].data = savedEval.val_accuracy_history;
            evalChart.update('none');
        }
    }
}

/**
 * CHART.JS INITIALIZATION (BOTH CHARTS)
 */
function initLiveChart(totalEpochs) {
    const labels = Array.from({ length: totalEpochs }, (_, i) => i + 1);

    // 1. Live Training Chart
    const liveCtx = document.getElementById('live-training-chart');
    if (liveCtx) {
        if (trainingChart) trainingChart.destroy();
        trainingChart = new Chart(liveCtx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    { label: 'Accuracy', data: [], borderColor: '#1a227f', borderWidth: 3, tension: 0.4, pointRadius: 0, yAxisID: 'y' },
                    { label: 'Loss', data: [], borderColor: '#fb923c', borderWidth: 2, borderDash: [5, 5], tension: 0.4, pointRadius: 0, yAxisID: 'y1' }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { display: false }, title: { display: true, text: 'Epochs', color: '#94a3b8', font: { size: 10, weight: 'bold' } } },
                    y: { type: 'linear', display: true, position: 'left', min: 0, max: 100, grid: { color: '#f1f5f9' } },
                    y1: { type: 'linear', display: true, position: 'right', min: 0, grid: { drawOnChartArea: false } }
                }
            }
        });
    }

    // 2. Evaluation Validation Chart
    const evalCtx = document.getElementById('eval-accuracy-chart');
    if (evalCtx) {
        if (evalChart) evalChart.destroy();
        evalChart = new Chart(evalCtx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    { label: 'Training', data: [], borderColor: '#1a227f', borderWidth: 3, tension: 0.4, pointRadius: 0 },
                    { label: 'Validation', data: [], borderColor: 'rgba(26, 34, 127, 0.3)', borderWidth: 2, tension: 0.4, pointRadius: 0 }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { display: false } },
                    y: { min: 0, max: 100, grid: { color: '#f1f5f9' } }
                }
            }
        });
    }
}

/**
 * PURE DOM CONSOLE LOG HELPER
 */
function appendConsoleLog(message, type = "INFO") {
    const consoleEl = document.getElementById('training-console-output');
    if (!consoleEl) return;

    const p = document.createElement('p');
    const timeSpan = document.createElement('span');
    const typeSpan = document.createElement('span');
    const msgSpan = document.createElement('span');

    const time = new Date().toLocaleTimeString('en-US', { hour12: false });
    timeSpan.textContent = `[${time}] `;

    if (type === "INFO") {
        p.className = "text-slate-400";
        typeSpan.className = "text-primary/70 pr-1";
        typeSpan.textContent = "INFO:";
    } else if (type === "SUCCESS") {
        p.className = "text-green-400 font-bold";
        typeSpan.className = "text-green-500 pr-1";
        typeSpan.textContent = "SUCCESS:";
    } else if (type === "ERROR") {
        p.className = "text-red-400 font-bold";
        typeSpan.className = "text-red-500 pr-1";
        typeSpan.textContent = "ERROR:";
    }

    msgSpan.textContent = message;

    p.appendChild(timeSpan);
    p.appendChild(typeSpan);
    p.appendChild(msgSpan);

    consoleEl.appendChild(p);
    consoleEl.scrollTop = consoleEl.scrollHeight;
}

/**
 * CONSOLE PROGRESS BAR — shows model BUILD progress (not epoch progress).
 * Appears immediately when training starts and fills as each build phase completes.
 */
function initConsoleBuildProgress() {
    const consoleEl = document.getElementById('training-console-output');
    if (!consoleEl) return;

    // Remove any stale bar from a previous run
    document.getElementById('console-progress-row')?.remove();

    const time = new Date().toLocaleTimeString('en-US', { hour12: false });

    const wrapper = document.createElement('div');
    wrapper.id = 'console-progress-row';
    wrapper.className = 'pt-2 pb-1';
    wrapper.innerHTML = `
        <p class="text-slate-400 mb-1.5">
            <span class="text-yellow-400/80 pr-1">[${time}]</span>
            <span class="text-yellow-400 pr-1">ENGINE:</span>
            <span id="console-build-phase">Initializing — waiting for backend...</span>
        </p>
        <div class="flex items-center gap-2">
            <div class="flex-1 bg-slate-700 rounded-full h-2.5 overflow-hidden">
                <div id="console-progress-bar"
                     class="h-2.5 rounded-full transition-all duration-700 ease-out"
                     style="width: 0%; background: linear-gradient(90deg, #f59e0b, #6366f1, #1a227f)">
                </div>
            </div>
            <span id="console-progress-label"
                  class="text-[10px] font-bold text-amber-400 font-mono w-8 text-right">0%</span>
        </div>`;

    consoleEl.appendChild(wrapper);
    consoleEl.scrollTop = consoleEl.scrollHeight;
}

function updateConsoleBuildProgress(pct, phaseMessage) {
    const bar   = document.getElementById('console-progress-bar');
    const label = document.getElementById('console-progress-label');
    const phase = document.getElementById('console-build-phase');

    if (bar)   bar.style.width = `${pct}%`;
    if (label) label.textContent = `${pct}%`;
    if (phase) phase.textContent = phaseMessage;

    // At 100% change colour to green to signal handoff to training
    if (pct >= 100 && bar) {
        bar.style.background = 'linear-gradient(90deg, #34d399, #10b981)';
        if (label) label.className = 'text-[10px] font-bold text-emerald-400 font-mono w-8 text-right';
    }

    const consoleEl = document.getElementById('training-console-output');
    if (!consoleEl) return;

    // Append a compact phase log line above the bar
    const line = document.createElement('p');
    line.className = 'text-slate-500 text-[11px] pl-1';
    line.innerHTML = `<span class="text-cyan-600/70">▶</span> ${phaseMessage}`;
    const progressRow = document.getElementById('console-progress-row');
    if (progressRow) consoleEl.insertBefore(line, progressRow);
    else consoleEl.appendChild(line);
    consoleEl.scrollTop = consoleEl.scrollHeight;
}

/**
 * INITIATE TRAINING
 */
async function startTrainingProcess() {
    await saveTrainingConfig();
    switchTab('tab-train', 'Live Training', 'Monitor model optimization in real-time.', 'nav-train');

    const totalEpochs = parseInt(document.getElementById('training-epochs')?.value || 10);
    initLiveChart(totalEpochs);

    const progressBar = document.getElementById('training-progress-fill');
    const progressText = document.getElementById('training-progress-text');
    const epochText = document.getElementById('training-epoch-text');
    const consoleOutput = document.getElementById('training-console-output');

    // Reset Progress
    if (progressBar) {
        progressBar.style.backgroundColor = '#1a227f'; // Reset to primary color if halted previously
        progressBar.style.width = '0%';
    }
    if (progressText) progressText.textContent = '0%';
    if (epochText) epochText.textContent = `Epoch 0 / ${totalEpochs}`;

    // Reset KPIs
    ['eval-precision', 'eval-recall', 'eval-f1'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '--%';
    });

    const cmGrid = document.getElementById('confusion-matrix-grid');
    if (cmGrid) {
        cmGrid.replaceChildren();
        cmGrid.textContent = "Matrix will generate after training completes...";
        cmGrid.className = "flex items-center justify-center h-[200px] text-slate-400 text-sm font-medium italic border border-dashed border-slate-200 rounded-lg";
        cmGrid.style.gridTemplateColumns = 'none';
    }

    if (consoleOutput) {
        consoleOutput.replaceChildren();
        initConsoleBuildProgress(); // Show model-build progress bar immediately
    }

    const response = await pywebview.api.start_model_training();
    if (response.status !== "success") {
        showToastNotification(response.message, false);
    }
}

/**
 * STOP TRAINING
 */
async function stopTrainingProcess() {
    if (!confirm("Are you sure you want to stop the training process? All progress for this session will be lost.")) {
        return;
    }

    appendConsoleLog("Sending termination signal to ML Engine...", "INFO");
    const response = await pywebview.api.stop_model_training();

    if (response.status === "success") {
        appendConsoleLog(response.message, "INFO");
        showToastNotification("Training stopped by user.", false);

        const progressBar = document.getElementById('training-progress-fill');
        const progressText = document.getElementById('training-progress-text');
        if (progressBar) {
            progressBar.style.backgroundColor = '#ef4444'; // Red
            progressBar.style.width = '100%';
        }
        if (progressText) progressText.textContent = 'Halted';
    } else {
        appendConsoleLog("Failed to stop training: " + response.message, "ERROR");
    }
}

/**
 * REAL-TIME UI UPDATER (Triggered by Python)
 */
window.updateTrainingProgress = function (data) {
    // --- Model BUILD phase (scanning dataset, extracting landmarks, compiling) ---
    if (data.status === "build_progress") {
        // Update top progress bar (0-100% during build)
        const progressBar = document.getElementById('training-progress-fill');
        const progressText = document.getElementById('training-progress-text');
        const epochText = document.getElementById('training-epoch-text');
        if (progressBar) progressBar.style.width   = `${data.progress}%`;
        if (progressText) progressText.textContent  = `${data.progress}%`;
        if (epochText) epochText.textContent = 'Building model...';
        // Update the console animated bar
        updateConsoleBuildProgress(data.progress, data.message);
        return;
    }

    if (data.status === "completed") {
        appendConsoleLog("Training Completed Successfully!", "SUCCESS");
        showToastNotification("Training Completed Successfully!", true);

        if (data.duration_str) {
            const durLabel = document.getElementById('eval-duration');
            if (durLabel) durLabel.textContent = data.duration_str;
        }

        // NEW: Pass data.classes to the matrix renderer
        if (data.confusion_matrix) {
            renderConfusionMatrix(data.confusion_matrix, data.classes);
        }

        // NEW: Populate KPIs explicitly using the precise calculated strings from the backend
        const kpiMappings = {
            'eval-precision': data.precision_str,
            'eval-recall': data.recall_str,
            'eval-f1': data.f1_str,
            'eval-final-train-acc': data.final_train_acc_str,
            'eval-final-val-acc': data.final_val_acc_str
        };

        Object.entries(kpiMappings).forEach(([id, value]) => {
            const el = document.getElementById(id);
            if (el && value) el.textContent = value;
        });

        return;
    } else if (data.status === "error") {
        appendConsoleLog(data.message, "ERROR");
        return;
    }

    // 1. Update Progress Bar
    const progressBar = document.getElementById('training-progress-fill');
    const progressText = document.getElementById('training-progress-text');
    if (progressBar) progressBar.style.width = `${data.progress}%`;
    if (progressText) progressText.textContent = `${data.progress}%`;

    const epochText = document.getElementById('training-epoch-text');
    if (epochText) epochText.textContent = `Epoch ${data.epoch} / ${data.total_epochs}`;

    // 2. Update HTML Labels
    const accLabel = document.getElementById('live-accuracy');
    const lossLabel = document.getElementById('live-loss');
    if (accLabel) accLabel.textContent = data.accuracy_str;
    if (lossLabel) lossLabel.textContent = data.loss_str;

    // 3. Update Chart.js (Live Training)
    if (trainingChart) {
        trainingChart.data.datasets[0].data.push(data.accuracy_val);
        trainingChart.data.datasets[1].data.push(data.loss_val);
        trainingChart.update('none');
    }

    // 4. Update Chart.js (Evaluation Tab)
    if (evalChart && data.val_accuracy_val !== undefined) {
        evalChart.data.datasets[0].data.push(data.accuracy_val);
        evalChart.data.datasets[1].data.push(data.val_accuracy_val);
        evalChart.update('none');

        const finalTrain = document.getElementById('eval-final-train-acc');
        const finalVal = document.getElementById('eval-final-val-acc');
        if (finalTrain) finalTrain.textContent = data.accuracy_str;
        if (finalVal) finalVal.textContent = data.val_accuracy_str;
    }

    // 5. Update Evaluation KPIs
    const precisionLabel = document.getElementById('eval-precision');
    const recallLabel = document.getElementById('eval-recall');
    const f1Label = document.getElementById('eval-f1');

    if (precisionLabel && data.precision_str) precisionLabel.textContent = data.precision_str;
    if (recallLabel && data.recall_str) recallLabel.textContent = data.recall_str;
    if (f1Label && data.f1_str) f1Label.textContent = data.f1_str;

    // 6. Update Console (epoch summary log line)
    const logMsg = `Epoch ${data.epoch}/${data.total_epochs} — loss: ${data.loss_str}  acc: ${data.accuracy_str}  val_acc: ${data.val_accuracy_str}`;
    appendConsoleLog(logMsg, "INFO");
};