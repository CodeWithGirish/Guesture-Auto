# backend/api/training_api.py
import webview
import json
from engine.training.model_trainer import ModelTrainer
from backend.services.training_service import TrainingService

class TrainingAPI:
    def __init__(self):
        self.trainer = ModelTrainer()
        self.config_service = TrainingService()

    def get_training_init_data(self):
        """Fetches initialization data for the config UI."""
        return self.config_service.get_training_ui_metadata()

    def save_training_config(self, config):
        """Saves the config from the UI."""
        return self.config_service.save_config(config)

    def start_model_training(self):
        """Triggered when the user clicks 'Start Training'."""
        return self.trainer.start_training(self._update_frontend_progress)

    def stop_model_training(self):
        """Triggered when the user clicks 'Stop Training'."""
        return self.trainer.stop_training()

    def _update_frontend_progress(self, data):
        """Sends data via pywebview evaluate_js to update the UI."""
        if webview.windows:
            try:
                js_data = json.dumps(data)
                js_command = f"if (typeof updateTrainingProgress !== 'undefined') {{ updateTrainingProgress({js_data}); }}"
                for window in webview.windows:
                    window.evaluate_js(js_command)
            except Exception as e:
                print(f"Error updating UI: {e}")