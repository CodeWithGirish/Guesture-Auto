# engine/training/model_trainer.py
import os
import json
import threading
import time
import numpy as np
import cv2
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.optimizers import Adam, SGD, RMSprop
from tensorflow.keras.utils import to_categorical
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix
import mediapipe as mp

class WebviewProgressCallback(tf.keras.callbacks.Callback):
    def __init__(self, trainer, val_data=None):
        super().__init__()
        self.trainer = trainer
        self.val_data = val_data
        self.start_time = time.time()

    def on_epoch_end(self, epoch, logs=None):
        if not self.trainer.is_training:
            self.model.stop_training = True
            return

        logs = logs or {}
        progress_percent = int(((epoch + 1) / self.trainer.total_epochs) * 100)

        acc     = logs.get('accuracy', 0) * 100
        val_acc = logs.get('val_accuracy', 0) * 100
        loss    = logs.get('loss', 0)

        # NOTE: Precision/Recall/F1 are only computed once at train_end to avoid
        # the massive performance hit of running model.predict() per epoch.
        # The UI shows '--' during training and gets real values at completion.

        if self.trainer.progress_callback:
            self.trainer.progress_callback({
                "status": "training",
                "epoch": epoch + 1,
                "total_epochs": self.trainer.total_epochs,
                "progress": progress_percent,
                "accuracy_val": float(f"{acc:.2f}"),
                "val_accuracy_val": float(f"{val_acc:.2f}"),
                "loss_val": float(f"{loss:.4f}"),
                "accuracy_str": f"{acc:.2f}%",
                "val_accuracy_str": f"{val_acc:.2f}%" if val_acc > 0 else "--",
                "loss_str": f"{loss:.4f}",
                "precision_str": "--%",
                "recall_str": "--%",
                "f1_str": "--%"
            })

    def on_train_end(self, logs=None):
        if self.trainer.is_training:
            elapsed = int(time.time() - self.start_time)
            hours, remainder = divmod(elapsed, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.trainer.final_duration_str = f"{hours:02d}h {minutes:02d}m {seconds:02d}s"


class ModelTrainer:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.data_dir = os.path.join(self.base_dir, 'data')
        self.models_dir = os.path.join(self.base_dir, 'models')
        self.config_path = os.path.join(self.data_dir, 'training_config.json')
        
        self.is_training = False
        self.current_epoch = 0
        self.total_epochs = 0
        self.progress_callback = None
        self.final_duration_str = "00h 00m 00s"
        self.img_size = (128, 128) # Strict CNN input size

    def _load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception:
            return {"epochs": 20, "batch_size": 16, "learning_rate": 0.001, "optimizer": "Adam"}

    def _get_optimizer(self, name, lr):
        name = str(name).strip().upper()
        if name == "SGD": 
            return SGD(learning_rate=lr, momentum=0.9)
        if name == "RMSPROP": 
            return RMSprop(learning_rate=lr)
        return Adam(learning_rate=lr)

    def _load_dataset(self, on_progress=None):
        """Scans directories, uses MediaPipe to extract 3D landmarks, normalizes relative to wrist."""
        x_data = []
        y_data = []
        classes = []
        
        dirs_to_scan = [
            os.path.join(self.data_dir, 'sample_images'),
            os.path.join(self.data_dir, 'augumented_data')
        ]

        # 1. Discover all unique classes across both directories
        for d in dirs_to_scan:
            if os.path.exists(d):
                for folder in os.listdir(d):
                    if folder not in classes and os.path.isdir(os.path.join(d, folder)):
                        classes.append(folder)
                        
        classes.sort() # Ensure consistent label ordering

        mp_hands = mp.solutions.hands
        hands_detector = mp_hands.Hands(
            static_image_mode=True, 
            max_num_hands=1, 
            min_detection_confidence=0.5
        )

        # Pre-count total images for progress reporting
        all_images = []
        for d in dirs_to_scan:
            if not os.path.exists(d): continue
            for folder_name in os.listdir(d):
                folder_path = os.path.join(d, folder_name)
                if not os.path.isdir(folder_path): continue
                for file_name in os.listdir(folder_path):
                    if file_name.lower().endswith(('.png', '.jpg', '.jpeg')):
                        all_images.append((folder_name, os.path.join(folder_path, file_name)))

        total_images = max(len(all_images), 1)
        processed = 0

        # 2. Load and preprocess images into normalized landmarks
        for folder_name, file_path in all_images:
            if folder_name not in classes:
                continue
            label_idx = classes.index(folder_name)
            img = cv2.imread(file_path)
            
            if img is not None:
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                results = hands_detector.process(img_rgb)

                if results.multi_hand_landmarks:
                    hand_landmarks = results.multi_hand_landmarks[0].landmark
                    
                    # Normalization: Make Wrist (Landmark 0) the origin
                    wrist_x, wrist_y, wrist_z = hand_landmarks[0].x, hand_landmarks[0].y, hand_landmarks[0].z
                    
                    norm_landmarks = []
                    for lm in hand_landmarks:
                        norm_landmarks.extend([
                            lm.x - wrist_x,
                            lm.y - wrist_y,
                            lm.z - wrist_z
                        ])
                    
                    # Scale Invariance: Divide by the maximum absolute coordinate to constrain hand size
                    max_val = max([abs(x) for x in norm_landmarks])
                    if max_val > 0.0001:
                        norm_landmarks = [x / max_val for x in norm_landmarks]
                    
                    x_data.append(norm_landmarks)
                    y_data.append(label_idx)

            processed += 1
            # Report landmark extraction progress (maps to 5%–65% of total build)
            if on_progress and processed % max(1, total_images // 20) == 0:
                pct = 5 + int((processed / total_images) * 60)
                on_progress(pct, f"Extracting landmarks... {processed}/{total_images} images")

        hands_detector.close()

        if len(x_data) == 0:
            raise ValueError("No gesture hands detected in dataset images.")

        x_data = np.array(x_data, dtype=np.float32)
        y_data = to_categorical(y_data, num_classes=len(classes)) 
        
        return x_data, y_data, classes

    def start_training(self, callback):
        if self.is_training:
            return {"status": "error", "message": "Training is already running."}

        self.progress_callback = callback
        self.is_training = True
        
        config = self._load_config()
        self.total_epochs = config.get('epochs', 20)

        threading.Thread(target=self._run_real_training, args=(config,), daemon=True).start()
        return {"status": "success", "message": "ML Engine started."}

    def _run_real_training(self, config):
        def build_progress(pct, message):
            """Emits a build-phase progress event to the UI."""
            if self.progress_callback:
                self.progress_callback({
                    "status": "build_progress",
                    "progress": pct,
                    "message": message
                })

        try:
            # --- Phase 1: Scanning dataset (0% → 5%) ---
            build_progress(2, "Scanning dataset folders...")

            # --- Phase 2: Extracting MediaPipe landmarks (5% → 65%) ---
            build_progress(5, "Initializing MediaPipe landmark detector...")
            X, Y, class_names = self._load_dataset(on_progress=build_progress)
            num_classes = len(class_names)
            build_progress(65, f"Landmarks extracted — {len(X)} samples across {num_classes} classes")

            # --- Phase 3: Splitting into train / validation sets (65% → 75%) ---
            build_progress(70, "Splitting dataset into train / validation sets...")
            x_train, x_val, y_train, y_val = train_test_split(X, Y, test_size=0.2, random_state=42)
            build_progress(75, f"Split complete — {len(x_train)} train  |  {len(x_val)} val samples")

            # --- Phase 4: Building model architecture (75% → 88%) ---
            build_progress(78, "Building Dense neural network architecture...")
            model = Sequential([
                Dense(128, activation='relu', input_shape=(63,)),
                Dropout(0.2),
                Dense(64, activation='relu'),
                Dense(32, activation='relu'),
                Dense(num_classes, activation='softmax')
            ])
            build_progress(85, f"Architecture built — {model.count_params():,} trainable parameters")

            # --- Phase 5: Compiling model (88% → 100%) ---
            opt_name = config.get('optimizer', 'Adam')
            lr = config.get('learning_rate', 0.001)
            batch_size = config.get('batch_size', 16)
            build_progress(90, f"Compiling with {opt_name} (lr={lr})...")
            optimizer = self._get_optimizer(opt_name, lr)
            model.compile(optimizer=optimizer, loss='categorical_crossentropy', metrics=['accuracy'])
            build_progress(100, f"Model ready — starting {self.total_epochs} epochs at batch_size={batch_size}")

            # --- Phase 6: Training (epochs handled by WebviewProgressCallback) ---
            ui_callback = WebviewProgressCallback(self, val_data=(x_val, y_val))
            history = model.fit(
                x_train, y_train,
                validation_data=(x_val, y_val),
                epochs=self.total_epochs,
                batch_size=batch_size,
                callbacks=[ui_callback],
                verbose=0 
            )

            # 5. Handle Completion & Save as .keras
            if not self.is_training:
                if self.progress_callback:
                     self.progress_callback({"status": "error", "message": "Training was aborted. Model discarded."})
            else:
                os.makedirs(self.models_dir, exist_ok=True)
                
                # CRITICAL: Save using the modern .keras format
                model_path = os.path.join(self.models_dir, 'gesture_recognition_model.keras')
                model.save(model_path)
                
                mapping_path = os.path.join(self.models_dir, 'gesture_classes.json')
                with open(mapping_path, 'w') as f:
                    json.dump({"classes": class_names, "input_shape": [63]}, f, indent=4)

                predictions = model.predict(x_val, verbose=0)
                y_pred = np.argmax(predictions, axis=1)
                y_true = np.argmax(y_val, axis=1)
                cm = confusion_matrix(y_true, y_pred, labels=range(num_classes))
                
                precision = precision_score(y_true, y_pred, average='weighted', zero_division=0) * 100
                recall = recall_score(y_true, y_pred, average='weighted', zero_division=0) * 100
                f1 = f1_score(y_true, y_pred, average='weighted', zero_division=0) * 100
                
                final_train_acc = history.history.get('accuracy', [0])[-1] * 100
                final_val_acc = history.history.get('val_accuracy', [0])[-1] * 100

                eval_data = {
                    "duration_str": self.final_duration_str,
                    "confusion_matrix": cm.tolist(),
                    "classes": class_names,
                    "precision_str": f"{precision:.1f}%",
                    "recall_str": f"{recall:.1f}%",
                    "f1_str": f"{f1:.1f}%",
                    "accuracy_history": [float(x * 100) for x in history.history.get('accuracy', [])],
                    "loss_history": [float(x) for x in history.history.get('loss', [])],
                    "val_accuracy_history": [float(x * 100) for x in history.history.get('val_accuracy', [])],
                    "final_train_acc_str": f"{final_train_acc:.2f}%",
                    "final_val_acc_str": f"{final_val_acc:.2f}%"
                }

                # Save evaluation data to disk
                eval_path = os.path.join(self.data_dir, 'training_eval.json')
                with open(eval_path, 'w') as f:
                    json.dump(eval_data, f, indent=4)

                if self.progress_callback:
                    payload = {"status": "completed"}
                    payload.update(eval_data)
                    self.progress_callback(payload)

        except Exception as e:
            print(f"Training crashed: {e}")
            if self.progress_callback:
                self.progress_callback({"status": "error", "message": f"Training failed: {str(e)}"})
        finally:
            self.is_training = False

    def stop_training(self):
        self.is_training = False
        return {"status": "success", "message": "Termination signal sent. Stopping..."}