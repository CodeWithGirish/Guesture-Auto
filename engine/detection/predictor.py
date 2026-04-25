import os
import json
import numpy as np
import tensorflow as tf


class ModelNotReadyError(RuntimeError):
    """Raised when prediction is attempted without a valid trained model."""
    pass


class GesturePredictor:
    def __init__(self, model_path="models/gesture_recognition_model.keras", class_map_path="models/gesture_classes.json"):
        self.class_map = []
        self.model = None
        self.img_size = (128, 128)
        self._load_error = None  # Stores first-load error message for UI propagation

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if not os.path.isabs(model_path):
            model_path = os.path.join(base_dir, model_path)
        if not os.path.isabs(class_map_path):
            class_map_path = os.path.join(base_dir, class_map_path)

        # 1. Load the Class Mapping
        if os.path.exists(class_map_path):
            try:
                with open(class_map_path, 'r') as f:
                    config_data = json.load(f)
                    self.class_map = config_data.get("classes", [])
            except Exception as e:
                self._load_error = f"Class mapping corrupt: {e}"
                print(f"[Predictor] Warning — {self._load_error}")
        else:
            self._load_error = f"Class map not found at '{class_map_path}'. Train a model first."
            print(f"[Predictor] {self._load_error}")

        # 2. Load the Keras CNN Model
        if os.path.exists(model_path):
            try:
                self.model = tf.keras.models.load_model(model_path)
                print(f"[Predictor] Successfully loaded model from {model_path}")
            except Exception as e:
                self._load_error = f"Model file exists but failed to load: {e}"
                print(f"[Predictor] Error — {self._load_error}")
        else:
            self._load_error = f"Model file not found at '{model_path}'. Train a model first."
            print(f"[Predictor] {self._load_error}")


    def predict_from_landmarks(self, hand_landmarks):
        """
        Direct Keras DNN prediction blended with heuristic fallback.
        """
        if self.model is None or not self.class_map:
            return "Unknown", 0.0

        if not hand_landmarks or len(hand_landmarks) != 21:
            return "Unknown", 0.0

        wrist_x = hand_landmarks[0].x
        wrist_y = hand_landmarks[0].y
        wrist_z = hand_landmarks[0].z
        
        norm_landmarks = []
        for lm in hand_landmarks:
            norm_landmarks.extend([
                lm.x - wrist_x,
                lm.y - wrist_y,
                lm.z - wrist_z
            ])

        # Scale Invariance matching model_trainer logic
        max_val = max([abs(x) for x in norm_landmarks])
        if max_val > 0.0001:
            norm_landmarks = [x / max_val for x in norm_landmarks]

        lm_array = np.array(norm_landmarks, dtype=np.float32)
        lm_batch = np.expand_dims(lm_array, axis=0)

        predictions = self.model.predict(lm_batch, verbose=0)
        predicted_idx = np.argmax(predictions[0])
        confidence = float(predictions[0][predicted_idx])

        # Soften to 75% confidence threshold to prevent false-rejections under different lighting conditions
        if predicted_idx < len(self.class_map) and confidence >= 0.75:
            return self.class_map[predicted_idx], confidence
            
        return "Unknown", confidence

    def is_ready(self):
        """Returns True if the model and class map are both loaded successfully."""
        return self.model is not None and len(self.class_map) > 0

    def get_load_error(self):
        """Returns the error message from model loading, or None if loaded successfully."""
        return self._load_error