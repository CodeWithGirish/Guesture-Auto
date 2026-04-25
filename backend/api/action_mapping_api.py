#
class ActionMappingAPI:
    def __init__(self):
        from backend.services.action_mapping_service import ActionMappingService
        self.service = ActionMappingService()

    def get_mappings(self):
        return self.service.get_mappings()

    def save_mapping(self, mapping_data):
        """Python Service now handles validation and saving."""
        return self.service.save_mapping(mapping_data)

    def delete_mapping(self, gesture_name, target_app="Global"):
        return self.service.delete_mapping(gesture_name, target_app)
    
    def search_mappings(self, query):
        """Corrected to use the existing service."""
        # Ensure you have search_service accessible here or via self.service
        return self.service.search_mappings(query)
    
    def get_system_actions(self):
        return self.service.get_available_system_actions()

    def get_smart_sorted_gestures(self, search_term=""):
        return self.service.get_smart_sorted_gestures(search_term)

    def get_paginated_mappings(self, search_term="", status_filter="All", page=1, limit=4):
        return self.service.get_paginated_mappings(search_term, status_filter, int(page), int(limit))

    def toggle_mapping_status(self, gesture_name, target_app, is_active):
        return self.service.toggle_mapping_status(gesture_name, target_app, is_active)

    def get_app_specific_actions(self, app_name):
        """Returns a list of actions relevant to the detected category of an application."""
        name_lower = app_name.lower()

        # Browser family
        if any(x in name_lower for x in ['chrome', 'firefox', 'edge', 'brave', 'opera', 'safari']):
            return [
                "New Tab", "Close Tab", "Reload Page", "Go Back", "Go Forward",
                "Zoom In", "Zoom Out", "Open Bookmarks", "Open History",
                "Open Downloads", "Toggle DevTools", "Scroll Up", "Scroll Down",
                "Find on Page (Ctrl+F)", "Open New Window"
            ]

        # Media players
        if any(x in name_lower for x in ['vlc', 'spotify', 'media player', 'groove', 'itunes', 'winamp']):
            return [
                "Play / Pause", "Next Track", "Previous Track",
                "Volume Up", "Volume Down", "Mute / Unmute",
                "Seek Forward", "Seek Backward", "Toggle Fullscreen",
                "Toggle Shuffle", "Toggle Repeat"
            ]

        # Code editors / IDEs
        if any(x in name_lower for x in ['code', 'visual studio', 'pycharm', 'intellij', 'eclipse', 'notepad']):
            return [
                "Save File (Ctrl+S)", "Undo (Ctrl+Z)", "Redo (Ctrl+Y)",
                "Find (Ctrl+F)", "Replace (Ctrl+H)", "Toggle Terminal",
                "Comment Line (Ctrl+/)", "Format Document", "Go to Definition",
                "Run Code", "Stop Execution", "Split Editor"
            ]

        # File managers
        if any(x in name_lower for x in ['explorer', 'file manager', 'finder', 'total commander']):
            return [
                "Go Back", "Go Forward", "Go to Parent Folder",
                "New Folder", "Rename Selected", "Delete Selected",
                "Refresh View", "Toggle Hidden Files", "Select All (Ctrl+A)"
            ]

        # Video conferencing
        if any(x in name_lower for x in ['zoom', 'teams', 'meet', 'skype', 'webex']):
            return [
                "Mute / Unmute Mic", "Toggle Camera", "Share Screen",
                "Raise Hand", "End Call", "Open Chat",
                "Toggle Participants List", "Record Meeting", "Leave Meeting"
            ]

        # Generic fallback for unknown apps
        return [
            "Undo (Ctrl+Z)", "Select All (Ctrl+A)",
            "Save (Ctrl+S)", "Find (Ctrl+F)", "Close Window (Alt+F4)",
            "Minimize Window", "Maximize Window", "Switch Window (Alt+Tab)",
            "Scroll Up", "Scroll Down", "Play / Pause"
        ]

    def get_mouse_tracking_state(self):
        """Read persisted tracking state from disk so it survives page re-navigation."""
        import json, os
        settings_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'data', 'app_settings.json'
        )
        try:
            with open(settings_path, 'r') as f:
                enabled = bool(json.load(f).get('mouse_tracking_enabled', False))
        except Exception:
            enabled = False
        # Also keep live camera service in sync so tracking actually works
        try:
            from backend.services.camera_service import CameraService
            CameraService().mouse_tracking_enabled = enabled
        except Exception:
            pass
        return enabled

    def validate_index_finger_dataset(self):
        """
        Fast check: looks for any gesture folder whose name contains 'index'.
        Returns {"valid": bool, "message": str}.
        """
        import os
        base_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
        dirs_to_scan = [
            os.path.join(base_dir, 'sample_images'),
            os.path.join(base_dir, 'augumented_data')
        ]

        for scan_dir in dirs_to_scan:
            if not os.path.exists(scan_dir):
                continue
            for folder_name in os.listdir(scan_dir):
                folder_path = os.path.join(scan_dir, folder_name)
                if os.path.isdir(folder_path) and 'index' in folder_name.lower():
                    # Check it has at least one image inside
                    files = [f for f in os.listdir(folder_path)
                             if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                    if files:
                        return {"valid": True, "message": "Index finger dataset verified."}

        return {
            "valid": False,
            "message": "No 'Index Finger' gesture found in the dataset.\n"
                       "Please use the Scan screen to scan and save an 'Index Finger' gesture first."
        }

    def toggle_mouse_tracking(self, is_enabled):
        from backend.services.camera_service import CameraService
        import json, os
        # Validation is handled on the frontend side before calling here

        # Persist state to disk so it survives page re-navigation
        settings_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'data', 'app_settings.json'
        )
        try:
            try:
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
            except Exception:
                settings = {}
            settings['mouse_tracking_enabled'] = is_enabled
            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            return {"status": "error", "message": f"Failed to save tracking state: {e}"}

        # Also update the live camera service instance if running
        cam = CameraService()
        cam.mouse_tracking_enabled = is_enabled

        if is_enabled:
            mappings = self.service.get_mappings()
            updated = False
            for m in mappings:
                if m.get('gesture_name', '').lower() == "index finger":
                    m['is_active'] = False
                    updated = True
            if updated:
                with open(self.service.data_file, 'w') as f:
                    json.dump(mappings, f, indent=4)

        return {"status": "success", "is_enabled": is_enabled, "mappings_updated": is_enabled}