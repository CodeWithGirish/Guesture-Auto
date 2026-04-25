import numpy as np
import json
import os
import logging
import shutil
# UPDATED IMPORT
from .config import Config

logger = logging.getLogger(__name__)

class GestureEngine:
    def __init__(self, gestures_file=None):
        self.gestures_file = gestures_file or Config.GESTURES_FILE
        self.match_threshold = 0.85
        self.gestures = {}
        self.samples_matrix = None
        self.labels_map = []

        self.load_gestures()

    def load_gestures(self):
        if os.path.exists(self.gestures_file):
            try:
                with open(self.gestures_file, 'r') as f:
                    self.gestures = json.load(f)
                    self._rebuild_vector_cache()
                    logger.info(f"Loaded {len(self.gestures)} gestures.")
            except Exception as e:
                logger.error(f"Failed to load gestures: {e}")
        else:
            self.gestures = {}

    def _rebuild_vector_cache(self):
        all_samples = []
        self.labels_map = []

        for name, samples in self.gestures.items():
            if not samples: continue
            
            # Handle list-based (legacy) and dict-based (new) formats
            sample_list = samples if isinstance(samples, list) else samples.get('samples', [])
            
            for s in sample_list:
                s_arr = np.array(s).flatten()
                all_samples.append(s_arr)
                self.labels_map.append(name)

        if all_samples:
            self.samples_matrix = np.stack(all_samples)
        else:
            self.samples_matrix = None

    def save_gesture(self, name: str, landmarks):
        try:
            normalized = self._normalize_landmarks(landmarks)

            if name not in self.gestures:
                self.gestures[name] = []

            # If it's the old list format, append directly. 
            # If it's dict format, this needs logic update, but we keep it compatible for now.
            if isinstance(self.gestures[name], list):
                self.gestures[name].append(normalized.tolist())
            elif isinstance(self.gestures[name], dict):
                 if 'samples' not in self.gestures[name]: self.gestures[name]['samples'] = []
                 self.gestures[name]['samples'].append(normalized.tolist())

            os.makedirs(os.path.dirname(self.gestures_file), exist_ok=True)
            with open(self.gestures_file, 'w') as f:
                json.dump(self.gestures, f, indent=4)

            self._rebuild_vector_cache()
            return True
        except Exception as e:
            logger.error(f"Failed to save gesture '{name}': {e}")
            return False

    def find_gesture(self, landmarks):
        if self.samples_matrix is None:
            return None

        query_vector = self._normalize_landmarks(landmarks).flatten()
        distances = np.linalg.norm(self.samples_matrix - query_vector, axis=1)

        min_idx = np.argmin(distances)
        min_dist = distances[min_idx]

        if min_dist < self.match_threshold:
            if len(distances) > 1:
                partitioned = np.partition(distances, 1)
                second_min = partitioned[1]
                if (second_min - min_dist) < 0.10:
                    return None

            return self.labels_map[min_idx]

        return None

    def _normalize_landmarks(self, landmarks):
        coords = []
        for lm in landmarks:
            if hasattr(lm, 'x'): coords.append([lm.x, lm.y, lm.z])
            else: coords.append(lm)
        coords = np.array(coords)
        return self._original_normalize_logic(coords)

    def _original_normalize_logic(self, coords):
        connections = [(0,1), (1,2), (2,3), (3,4), (0,5), (5,6), (6,7), (7,8), (0,9), (9,10), (10,11), (11,12), (0,13), (13,14), (14,15), (15,16), (0,17), (17,18), (18,19), (19,20)]
        vectors = []
        for start, end in connections:
            v = coords[end] - coords[start]
            norm = np.linalg.norm(v)
            v_norm = v / norm if norm != 0 else v
            vectors.append(v_norm)

        angles = []
        finger_indices = [[0,1,2,3], [4,5,6,7], [8,9,10,11], [12,13,14,15], [16,17,18,19]]
        for f_vecs in finger_indices:
            for i in range(len(f_vecs)-1):
                dot = np.clip(np.dot(vectors[f_vecs[i]], vectors[f_vecs[i+1]]), -1.0, 1.0)
                angles.append(np.arccos(dot))

        bases = [0, 4, 8, 12, 16]
        for i in range(len(bases)-1):
            dot = np.clip(np.dot(vectors[bases[i]], vectors[bases[i+1]]), -1.0, 1.0)
            angles.append(np.arccos(dot))

        return np.array(angles)

    def delete_gesture(self, name):
        if name in self.gestures:
            del self.gestures[name]
            with open(self.gestures_file, 'w') as f: json.dump(self.gestures, f, indent=4)

            sample_dir = os.path.join(os.path.dirname(self.gestures_file), "samples", name)
            if os.path.exists(sample_dir): shutil.rmtree(sample_dir)
            self._rebuild_vector_cache()
            return True
        return False

    def rename_gesture(self, old_name, new_name):
        if old_name in self.gestures and new_name not in self.gestures:
            self.gestures[new_name] = self.gestures.pop(old_name)
            
            # Save JSON
            with open(self.gestures_file, 'w') as f:
                json.dump(self.gestures, f, indent=4)
            
            # Rename samples directory
            old_dir = os.path.join(os.path.dirname(self.gestures_file), "samples", old_name)
            new_dir = os.path.join(os.path.dirname(self.gestures_file), "samples", new_name)
            if os.path.exists(old_dir):
                os.rename(old_dir, new_dir)
                
            self._rebuild_vector_cache()
            return True
        return False