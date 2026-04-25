# backend/services/training_service.py
import json
import os

class TrainingService:
    def __init__(self):
        self.config_dir = 'data'
        self.config_path = os.path.join(self.config_dir, 'training_config.json')
        # Centralized constraints for the UI
        self.constraints = {
            "lr_min": 0.001,
            "lr_max": 0.1,
            "lr_step": 0.001,
            "optimizers": ["Adam", "SGD", "RMSProp"]
        }

    def _get_default_config(self):
        """Returns a default configuration if no file exists."""
        return {
            "architecture": "CNN",
            "experiment_name": "New Experiment",
            "epochs": 10,
            "batch_size": 32,
            "learning_rate": self.constraints["lr_min"],
            "optimizer": "Adam",
            "augmentation_enabled": True
        }

    def get_training_ui_metadata(self):
        """Returns constraints and the full saved configuration."""
        saved_config = self._get_default_config()
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    file_data = json.load(f)
                    if file_data:
                        saved_config.update(file_data) # Merge saved data into defaults
            except Exception:
                pass # Fallback to default config on error
        
        saved_eval = None
        eval_path = os.path.join(self.config_dir, 'training_eval.json')
        if os.path.exists(eval_path):
            try:
                with open(eval_path, 'r') as f:
                    saved_eval = json.load(f)
            except Exception:
                pass
        
        return {
            "constraints": self.constraints,
            "saved_config": saved_config,
            "saved_eval": saved_eval
        }

    def save_config(self, data):
        """Persists the training configuration to a JSON file."""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=4)
            return {"status": "success", "message": "Configuration saved successfully!"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to save: {str(e)}"}