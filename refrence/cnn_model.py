import os
import cv2
import numpy as np
import logging
import threading
import json
from glob import glob

# Configure Logger
logger = logging.getLogger(__name__)

# Try importing TensorFlow
try:
    import tensorflow as tf
    from tensorflow.keras import layers, models, callbacks
    TF_AVAILABLE = True
except ImportError:
    logger.error("TensorFlow not installed. CNN features disabled.")
    TF_AVAILABLE = False

class GestureCNN:
    def __init__(self, model_path='models/gesture_cnn.keras'):
        self.model_path = model_path
        self.model = None
        self.class_names = []

        # State
        self.is_training = False
        self.is_loading = False
        self.loading_progress = 0
        self.stop_training_flag = False

        # Data Cache
        self.cached_X = None
        self.cached_y = None

        self.training_stats = {
            'epoch': 0, 'total_epochs': 0,
            'loss': 0.0, 'accuracy': 0.0,
            'val_loss': 0.0, 'val_accuracy': 0.0,
            'logs': [], 'history': []
        }

        if TF_AVAILABLE:
            self.load_model()

    def load_model(self):
        if os.path.exists(self.model_path):
            try:
                self.model = tf.keras.models.load_model(self.model_path)
                map_path = self.model_path.replace('.keras', '_classes.json')
                if os.path.exists(map_path):
                    with open(map_path, 'r') as f:
                        self.class_names = json.load(f)
                logger.info("CNN Model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load CNN model: {e}")

    def load_dataset_task(self, data_dir, selected_gestures=None, img_size=(64, 64)):
        if not os.path.exists(data_dir):
            self.is_loading = False
            return

        self.is_loading = True
        self.loading_progress = 0

        try:
            images = []
            labels = []
            all_dirs = sorted([d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))])

            if selected_gestures and len(selected_gestures) > 0:
                target_classes = [d for d in all_dirs if d in selected_gestures]
            else:
                target_classes = all_dirs

            self.class_names = target_classes
            label_map = {name: i for i, name in enumerate(self.class_names)}
            total_classes = len(target_classes)

            if total_classes == 0:
                self.training_stats['logs'].append("Error: No classes found.")
                self.is_loading = False
                return

            for idx, class_name in enumerate(target_classes):
                class_path = os.path.join(data_dir, class_name)
                files = glob(os.path.join(class_path, "*.jpg"))
                for f in files:
                    try:
                        img = cv2.imread(f)
                        if img is None: continue
                        img = cv2.resize(img, img_size)
                        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        img = img / 255.0
                        images.append(img)
                        labels.append(label_map[class_name])
                    except: pass
                self.loading_progress = int(((idx + 1) / total_classes) * 100)

            if images:
                self.cached_X = np.array(images, dtype=np.float32)
                self.cached_y = np.array(labels, dtype=np.int32)
                # Shuffle data to fix validation split issues
                perm = np.random.permutation(len(self.cached_X))
                self.cached_X = self.cached_X[perm]
                self.cached_y = self.cached_y[perm]
                self.training_stats['logs'].append(f"Dataset Loaded: {len(images)} images, {total_classes} classes.")
            else:
                self.cached_X = None
                self.cached_y = None
                self.training_stats['logs'].append("Error: No images loaded.")

        except Exception as e:
            logger.error(f"Dataset loading failed: {e}")
            self.training_stats['logs'].append(f"Load Error: {str(e)}")
        finally:
            self.is_loading = False
            self.loading_progress = 100

    def create_model(self, num_classes, input_shape=(64, 64, 3)):
        model = models.Sequential([
            layers.Conv2D(32, (3, 3), activation='relu', input_shape=input_shape),
            layers.MaxPooling2D((2, 2)),
            layers.Conv2D(64, (3, 3), activation='relu'),
            layers.MaxPooling2D((2, 2)),
            layers.Conv2D(64, (3, 3), activation='relu'),
            layers.Flatten(),
            layers.Dense(64, activation='relu'),
            layers.Dropout(0.3),
            layers.Dense(num_classes, activation='softmax')
        ])
        model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
        return model

    def train(self, config):
        if not TF_AVAILABLE: return
        if self.cached_X is None or self.cached_y is None:
            self.training_stats['logs'].append("Error: Dataset not loaded.")
            return

        self.is_training = True
        self.stop_training_flag = False
        self.training_stats['logs'].append("Starting training...")
        self.training_stats['history'] = []

        try:
            epochs = int(config.get('epochs', 10))
            batch_size = int(config.get('batchSize', 32))
            num_classes = len(self.class_names)
            
            # Prevent silent failures if zero classes are sent
            if num_classes == 0:
                raise ValueError("No classes available to train. Ensure gestures are added and selected.")

            self.model = self.create_model(num_classes)

            # Custom callback for live updates
            class StatusCallback(callbacks.Callback):
                def __init__(self, cnn_instance):
                    self.cnn = cnn_instance

                def on_train_batch_end(self, batch, logs=None):
                    # Update stats live during the epoch
                    if logs:
                        self.cnn.training_stats['loss'] = float(logs.get('loss', 0))
                        self.cnn.training_stats['accuracy'] = float(logs.get('accuracy', 0)) * 100
                    if self.cnn.stop_training_flag:
                        self.model.stop_training = True

                def on_epoch_end(self, epoch, logs=None):
                    if self.cnn.stop_training_flag:
                        self.cnn.training_stats['logs'].append("Training stopped by user.")

                    self.cnn.training_stats['epoch'] = epoch + 1
                    self.cnn.training_stats['loss'] = float(logs.get('loss', 0))
                    self.cnn.training_stats['accuracy'] = float(logs.get('accuracy', 0)) * 100
                    self.cnn.training_stats['val_loss'] = float(logs.get('val_loss', 0))
                    self.cnn.training_stats['val_accuracy'] = float(logs.get('val_accuracy', 0)) * 100

                    self.cnn.training_stats['logs'].append(
                        f"Epoch {epoch+1}: acc={self.cnn.training_stats['accuracy']:.1f}%, loss={self.cnn.training_stats['loss']:.4f}"
                    )

                    self.cnn.training_stats['history'].append({
                        'epoch': epoch + 1,
                        'loss': self.cnn.training_stats['loss'],
                        'accuracy': self.cnn.training_stats['accuracy']
                    })

            self.model.fit(
                self.cached_X, self.cached_y,
                epochs=epochs,
                batch_size=batch_size,
                validation_split=config.get('valSplit', 0.2),
                callbacks=[StatusCallback(self)]
            )

            if not self.stop_training_flag:
                os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
                self.model.save(self.model_path)
                map_path = self.model_path.replace('.keras', '_classes.json')
                with open(map_path, 'w') as f:
                    json.dump(self.class_names, f)
                self.training_stats['logs'].append("Training Complete. Model Saved.")

        except Exception as e:
            logger.error(f"Training error: {e}")
            self.training_stats['logs'].append(f"Error: {str(e)}")
        finally:
            self.is_training = False # Guarantees UI can recover from an error state