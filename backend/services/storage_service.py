import os
import shutil
import cv2
import base64
import json

class StorageService:
    def __init__(self):
        # Calculate path relative to project root
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.dataset_dir = os.path.join(self.base_dir, 'Data', 'sample_images')
        os.makedirs(self.dataset_dir, exist_ok=True)
        # To save the Augumentation Parameter from Augumentation tab
        self.config_dir = os.path.join(self.base_dir, 'Data')
        self.aug_config_path = os.path.join(self.config_dir, 'augmentation_params.json')
        os.makedirs(self.config_dir, exist_ok=True)

    def get_all_gestures(self):
        """Fetches all saved gestures for the My Gestures screen."""
        gestures = []
        if not os.path.exists(self.dataset_dir):
            return gestures
        for folder_name in os.listdir(self.dataset_dir):
            path = os.path.join(self.dataset_dir, folder_name)
            if os.path.isdir(path):
                images = [f for f in os.listdir(path) if f.endswith(('.jpg', '.png', '.jpeg'))]
                if not images:
                    try:
                        shutil.rmtree(path)
                    except Exception:
                        pass
                    continue
                thumbnail = ""
                with open(os.path.join(path, images[0]), "rb") as f:
                    thumbnail = f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode('utf-8')}"
                gestures.append({"name": folder_name, "count": len(images), "thumbnail": thumbnail})
        return gestures

    def get_gesture_sample_images(self, gesture_name):
        """Fetches all individual images for the Gesture Samples dialog."""
        images_data = []
        folder_path = os.path.join(self.dataset_dir, gesture_name)
        if os.path.exists(folder_path):
            images = [f for f in os.listdir(folder_path) if f.endswith(('.jpg', '.png', '.jpeg'))]
            for img_name in images:
                img_path = os.path.join(folder_path, img_name)
                with open(img_path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode('utf-8')
                    images_data.append({"filename": img_name, "base64": f"data:image/jpeg;base64,{encoded}"})
        return {"gesture_name": gesture_name, "images": images_data}

    def save_session_to_disk(self, gesture_name, session_frames):
        """Wipes existing folder and saves new session frames."""
        safe_name = "".join([c for c in gesture_name if c.isalnum() or c == ' ']).strip()
        folder = os.path.join(self.dataset_dir, safe_name)
        if os.path.exists(folder):
            shutil.rmtree(folder)
        os.makedirs(folder, exist_ok=True)
        for i, (tid, frame) in enumerate(session_frames.items()):
            path = os.path.join(folder, f"{safe_name.replace(' ', '_')}_{i+1}.jpg")
            cv2.imwrite(path, frame)
        return len(session_frames)

    def delete_gesture_folder(self, gesture_name):
        """Deletes an entire gesture category."""
        path = os.path.join(self.dataset_dir, gesture_name)
        if os.path.exists(path):
            shutil.rmtree(path)
            return True
        return False

    def delete_specific_images(self, gesture_name, filenames):
        """Deletes selected images and removes folder if empty."""
        folder_path = os.path.join(self.dataset_dir, gesture_name)
        deleted_count = 0
        folder_deleted = False
        if os.path.exists(folder_path):
            for filename in filenames:
                file_path = os.path.join(folder_path, filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_count += 1
            if not [f for f in os.listdir(folder_path) if f.endswith(('.jpg', '.png', '.jpeg'))]:
                shutil.rmtree(folder_path)
                folder_deleted = True
        return deleted_count, folder_deleted


    #########################################
    # Dataset Hub - Augumentation Tab
    #########################################
    def save_augmentation_config(self, params):
        """Saves augmentation parameters for GAAN model use."""
        try:
            with open(self.aug_config_path, 'w') as f:
                json.dump(params, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def get_augmentation_config(self):
        """Loads saved augmentation parameters."""
        if os.path.exists(self.aug_config_path):
            with open(self.aug_config_path, 'r') as f:
                return json.load(f)
        # Default 'Middle' values if no file exists
        return {
            "rotation": 0, "gaussian_blur": 5, "noise_intensity": 50,
            "brightness": 1.0, "contrast": 1.0, "random_flip": False
        }