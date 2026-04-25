import os
import cv2
import numpy as np
import random
import json
import time
import concurrent.futures

class AugmentationEngine:
    def __init__(self):
        self.base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.source_dir = os.path.join(self.base_path, 'Data', 'sample_images')
        self.output_dir = os.path.join(self.base_path, 'Data', 'augumented_data')
        self.abort_flag = False
        
        # --- NEW: Real-time tracking variables ---
        self.processed_count = 0
        self.target_count = 0
        
        os.makedirs(self.output_dir, exist_ok=True)

    def abort(self):
        self.abort_flag = True

    def run_batch(self, gesture_name, params, target_count, use_params=True):
        self.abort_flag = False
        self.processed_count = 0             # Reset counter
        self.target_count = target_count     # Set target
        generated_files = [] 
        
        source_path = os.path.join(self.source_dir, gesture_name)
        save_path = os.path.join(self.output_dir, gesture_name)
        os.makedirs(save_path, exist_ok=True)

        if not os.path.exists(source_path):
            return {"status": "error", "message": "Source gesture folder not found."}

        images = [f for f in os.listdir(source_path) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
        if not images:
            return {"status": "error", "message": "No images found in the selected gesture folder."}

        # Check for duplicate settings
        settings_file = os.path.join(save_path, "last_run_settings.json")
        config_payload = {
            "use_params": use_params,
            "params": params if use_params else "AUTO"
        }
        
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r') as f:
                    last_data = json.load(f)
                if last_data.get("config") == config_payload:
                    return {"status": "error", "message": "Sample Images are Augmented. Try to set new Parameters."}
            except Exception: pass

        import shutil
        for img in images:
            src = os.path.join(source_path, img)
            dst = os.path.join(save_path, f"sample_{img}")
            if not os.path.exists(dst):
                shutil.copy2(src, dst)

        tasks = [(images[i % len(images)], i) for i in range(target_count)]
        run_id = str(int(time.time()))

        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []
            for img_name, idx in tasks:
                futures.append(
                    executor.submit(self._process_and_save, img_path=os.path.join(source_path, img_name), img_name=img_name, save_path=save_path, params=params, idx=idx, use_params=use_params, run_id=run_id)
                )
            
            for future in concurrent.futures.as_completed(futures):
                if self.abort_flag:
                    for f in futures:
                        f.cancel() 
                    break 
                
                try:
                    res = future.result() 
                    if res: 
                        generated_files.append(res)
                        # --- NEW: Update the global tracker ---
                        self.processed_count += 1
                except Exception: pass

        end_time = time.time()
        proc_speed_ms = ((end_time - start_time) / self.processed_count) * 1000 if self.processed_count > 0 else 0

        if self.abort_flag:
            for filename in generated_files:
                filepath = os.path.join(save_path, filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
            return {"status": "aborted", "message": "Batch Processing Aborted. Partial files cleaned up."}

        save_data = {
            "config": config_payload,
            "timestamp": time.time(),
            "proc_speed_ms": proc_speed_ms
        }
        with open(settings_file, 'w') as f:
            json.dump(save_data, f)

        return {"status": "success", "message": f"Successfully generated {self.processed_count} augmented images for '{gesture_name}'."}

    def _process_and_save(self, img_path, img_name, save_path, params, idx, use_params, run_id):
        if self.abort_flag: return False
        img = cv2.imread(img_path)
        if img is None: return False
        aug_img = self._optimized_augment(img, params, use_params)
        if self.abort_flag: return False 
        
        unique_filename = f"aug_{run_id}_{idx}_{img_name}"
        cv2.imwrite(os.path.join(save_path, unique_filename), aug_img)
        return unique_filename 
    
    def _optimized_augment(self, image, params, use_params):
        h, w = image.shape[:2]
        aug_img = image.copy()
        
        if not use_params:
            rot_val = random.uniform(-15, 15)
            do_flip = random.choice([True, False])
            alpha = random.uniform(0.8, 1.2) 
            beta_val = (random.uniform(0.8, 1.2) - 1.0) * 128 
            blur_val = 0 
            noise_int = 0 if random.random() > 0.2 else random.uniform(1, 4) 
        else:
            rot_val = float(params.get('rotation', 0))
            do_flip = params.get('random_flip', False) and random.choice([True, False])
            alpha = float(params.get('contrast', 1.0))
            beta_val = (float(params.get('brightness', 1.0)) - 1.0) * 128 
            blur_val = float(params.get('gaussian_blur', 0))
            noise_int = float(params.get('noise_intensity', 0))

        if rot_val != 0 or do_flip:
            M = cv2.getRotationMatrix2D((w/2, h/2), rot_val, 1.0)
            if do_flip:
                M[0, 0] = -M[0, 0]
                M[0, 1] = -M[0, 1]
                M[0, 2] = w - M[0, 2] 
            aug_img = cv2.warpAffine(aug_img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)

        if alpha != 1.0 or beta_val != 0:
            aug_img = cv2.convertScaleAbs(aug_img, alpha=alpha, beta=beta_val)

        if blur_val > 0:
            ksize = int(blur_val) * 2 + 1 
            aug_img = cv2.GaussianBlur(aug_img, (ksize, ksize), 0)

        if noise_int > 0:
            # Use OpenCV's highly optimized randn instead of numpy
            noise = np.zeros(aug_img.shape, np.int16)
            cv2.randn(noise, 0, noise_int * 2.55)
            aug_img = np.clip(aug_img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        return aug_img  