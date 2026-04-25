import os
import json
import tempfile
from backend.services.storage_service import StorageService

class ActionMappingService:
    def __init__(self):
        self.data_file = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'action_mappings.json')
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        from .search_service import SearchService
        self.search_tool = SearchService()

        if not os.path.exists(self.data_file):
            self._atomic_write([])

    def _atomic_write(self, data):
        """Write JSON atomically: write to a temp file then rename to prevent corruption."""
        dir_name = os.path.dirname(self.data_file)
        try:
            fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
            try:
                with os.fdopen(fd, 'w') as tmp_f:
                    json.dump(data, tmp_f, indent=4)
                os.replace(tmp_path, self.data_file)
            except Exception:
                os.unlink(tmp_path)
                raise
        except Exception as e:
            raise IOError(f"Atomic write failed: {e}")

    # ==========================================
    # ORIGINAL METHODS (Restored)
    # ==========================================
    def get_mappings(self):
        try:
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except Exception:
            return []
            
    def validate_mapping(self, new_mapping):
        mappings = self.get_mappings()
        gesture_name = new_mapping.get('gesture_name')
        target_app = new_mapping.get('target_app', 'Global')
        action_type = new_mapping.get('action_type')

        gesture_conflict = next((m for m in mappings if 
            m.get('gesture_name') == gesture_name and 
            m.get('target_app', 'Global') == target_app), None)

        if gesture_conflict:
            scope = "System Specific" if target_app == "Global" else f"the app '{target_app}'"
            return {"status": "conflict", "message": f"The gesture '{gesture_name}' is already mapped to {scope}."}

        action_conflict = next((m for m in mappings if 
            m.get('action_type') == action_type and 
            m.get('target_app', 'Global') == target_app), None)

        if action_conflict:
            scope = "System Level" if target_app == "Global" else f"the app '{target_app}'"
            return {"status": "conflict", "message": f"The action '{action_type}' is already mapped to '{action_conflict.get('gesture_name')}' at the {scope}."}

        return {"status": "success"}
    
    def save_mapping(self, mapping_data):
        validation = self.validate_mapping(mapping_data) 
        if validation["status"] == "conflict":
            return validation
            
        # Check mouse tracking interlock
        from backend.services.camera_service import CameraService
        cam = CameraService()
        if getattr(cam, 'mouse_tracking_enabled', False):
            if mapping_data.get('gesture_name', '').lower() == "index finger":
                return {"status": "error", "message": "Cannot map action to 'Index Finger' while Mouse Tracking is enabled."}
        
        try:
            mappings = self.get_mappings()
            gesture_name = mapping_data.get('gesture_name')
            target_app = mapping_data.get('target_app', 'Global')
            mappings = [m for m in mappings if not (m.get('gesture_name') == gesture_name and m.get('target_app', 'Global') == target_app)]
            mappings.append(mapping_data)
            self._atomic_write(mappings)
            return {"status": "success", "message": "Mapping saved successfully!"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def delete_mapping(self, gesture_name, target_app="Global"):
        try:
            mappings = self.get_mappings()
            mappings = [m for m in mappings if not (
                m.get('gesture_name') == gesture_name and
                m.get('target_app', 'Global') == target_app
            )]
            self._atomic_write(mappings)
            return {"status": "success", "message": f"Mapping for {gesture_name} on {target_app} deleted."}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def check_mapping_conflicts(self, mapping_data):
        return self.validate_mapping(mapping_data)

    def search_mappings(self, query):
        data = self.get_mappings()
        filtered = self.search_tool.filter_data(query, data, key_to_search="app_name")
        return {"status": "success", "results": filtered}

    # ==========================================
    # NEW REFACTORED METHODS
    # ==========================================
    def get_available_system_actions(self):
        return {
            "Mouse Control": ["Left click", "Right click", "Double-click", "Middle click", "Drag and Drop"],
            "Media Control": ["Play / Pause", "Next Track", "Previous Track", "Volume Up", "Volume Down", "Mute"],
            "Scrolling And Navigation": ["Scroll Up", "Scroll Down", "Scroll Left", "Scroll Right", "Page Up", "Page Down", "Browser Back", "Browser Forward"],
            "Keyboard Shortcuts": ["Undo (Ctrl+Z)", "Select All (Ctrl+A)", "Enter", "Escape"],
            "Application Control": ["Open Application", "Close Application", "Minimize Window", "Maximize Window", "Switch Window (Alt+Tab)", "Task View (Win+Tab)", "Snap Layout (Win+Z)"],
            "Screenshot & Screen Recording": ["Capture Full Screen", "Capture Active Window", "Snipping Tool", "Start/Stop Recording"],
            "System Controls": ["Lock Screen", "Sleep", "Open Task Manager", "Show Desktop (Win+D)", "Open Action Center"],
            "PowerPoint Control": ["Start Presentation (F5)", "Next Slide", "Previous Slide", "End Presentation (Esc)", "Blank Screen (B)"]
        }

    def get_smart_sorted_gestures(self, search_term=""):
        storage = StorageService()
        gestures = storage.get_all_gestures()
        existing_names = {g['name'] for g in gestures}

        # Append built-in pre-calibrated motion gestures
        try:
            from engine.detection.motion_engine import MotionEngine
            engine = MotionEngine()
            for motion_name in engine.get_all_motion_names():
                if motion_name not in existing_names:
                    gestures.append({
                        "name": motion_name,
                        "count": "Motion",
                        "thumbnail": "",
                        "is_motion": True
                    })
                    existing_names.add(motion_name)
        except Exception:
            pass

        if not search_term:
            return sorted(gestures, key=lambda g: g['name'].lower())

        search_term = search_term.lower()
        filtered = [g for g in gestures if search_term in g['name'].lower()]

        def sort_key(g):
            name = g['name'].lower()
            starts_with = 0 if name.startswith(search_term) else 1
            return (starts_with, name)

        return sorted(filtered, key=sort_key)

    def get_paginated_mappings(self, search_term="", status_filter="All", page=1, limit=4):
        mappings = self.get_mappings()
        
        if status_filter == "Active":
            mappings = [m for m in mappings if m.get('is_active', True) is not False]
        elif status_filter == "Inactive":
            mappings = [m for m in mappings if m.get('is_active', True) is False]

        if search_term:
            search_term = search_term.lower()
            mappings = [
                m for m in mappings 
                if search_term in m.get('gesture_name', '').lower() or 
                   search_term in m.get('target_app', 'Global').lower() or 
                   search_term in m.get('action_type', '').lower()
            ]
        
        total_items = len(mappings)
        total_pages = max(1, (total_items + limit - 1) // limit)
        page = max(1, min(page, total_pages))
        
        start_index = (page - 1) * limit
        end_index = start_index + limit
        page_mappings = mappings[start_index:end_index]
        
        storage = StorageService()
        all_gestures = storage.get_all_gestures()
        gesture_map = {g['name']: g.get('thumbnail', '') for g in all_gestures}
        
        for m in page_mappings:
            m['thumbnail'] = gesture_map.get(m['gesture_name'], '')
            
        return {
            "mappings": page_mappings,
            "total_pages": total_pages,
            "current_page": page,
            "total_items": total_items
        }

    def toggle_mapping_status(self, gesture_name, target_app, is_active):
        try:
            mappings = self.get_mappings()
            for m in mappings:
                if m.get('gesture_name') == gesture_name and m.get('target_app', 'Global') == target_app:
                    m['is_active'] = is_active
                    break
            self._atomic_write(mappings)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}