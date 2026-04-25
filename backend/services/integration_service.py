import os
import json
from backend.services.app_manager import AppManager
from backend.services.action_mapping_service import ActionMappingService
from backend.services.search_service import SearchService

class IntegrationService:
    def __init__(self):
        self.app_manager = AppManager()
        self.mapping_service = ActionMappingService() # Connect to the mappings database
        
        # Ensure 'data' folder is lowercase to avoid OS mismatches
        self.data_file = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'connected_apps.json')
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        
        if not os.path.exists(self.data_file):
            with open(self.data_file, 'w') as f:
                json.dump([], f)

        self.staged_apps = []

    def scan_system_apps(self):
        print("Scanning system for applications...")
        try:
            apps = self.app_manager.scan_installed_apps()
            
            # --- NEW: Cross-reference state before sending to frontend ---
            # 1. Get a fast-lookup set of names currently staged in memory
            staged_app_names = {app['name'] for app in self.staged_apps}
            
            # 2. Get a fast-lookup set of names already permanently connected in the JSON DB
            connected_app_names = set()
            try:
                with open(self.data_file, 'r') as f:
                    import json
                    permanent_apps = json.load(f)
                connected_app_names = {app['name'] for app in permanent_apps}
            except Exception:
                pass # Failsafe if file is empty/missing
                
            # 3. Augment the app data with their true state
            for app in apps:
                app['is_staged'] = app['name'] in staged_app_names
                app['is_connected'] = app['name'] in connected_app_names

            return {"status": "success", "data": apps, "message": f"Successfully scanned {len(apps)} applications."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def stage_app_connection(self, app_data):
        try:
            with open(self.data_file, 'r') as f:
                permanent_apps = json.load(f)
            
            if any(a['name'] == app_data['name'] for a in permanent_apps):
                return {"status": "info", "message": f"{app_data['name']} is already permanently connected."}
                
            if any(a['name'] == app_data['name'] for a in self.staged_apps):
                return {"status": "info", "message": f"{app_data['name']} is already staged for connection."}

            app_data['status'] = 'Active'
            app_data['mappings'] = 0
            self.staged_apps.append(app_data)
            
            return {"status": "success", "message": f"Staged {app_data['name']}. Remember to click 'Save Integrations'!"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to stage: {str(e)}"}
    
    def unstage_app_connection(self, app_name):
        initial_count = len(self.staged_apps)
        self.staged_apps = [a for a in self.staged_apps if a['name'] != app_name]
        
        if len(self.staged_apps) < initial_count:
            return {"status": "success", "message": f"Unstaged {app_name}."}
        else:
            return {"status": "error", "message": f"{app_name} was not staged."}

    def save_staged_integrations(self):
        if not self.staged_apps:
            return {"status": "error", "message": "No new applications staged to save."}
            
        try:
            with open(self.data_file, 'r') as f:
                apps = json.load(f)
                
            apps.extend(self.staged_apps)
            
            with open(self.data_file, 'w') as f:
                json.dump(apps, f, indent=4)
                
            saved_count = len(self.staged_apps)
            self.staged_apps.clear() 
            
            return {"status": "success", "message": f"Successfully saved {saved_count} new integrations!"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def clear_staged_integrations(self):
        self.staged_apps.clear()
        return {"status": "success", "message": "Cleared all staged integrations."}

    def get_connected_apps(self, search_term=None):
        try:
            with open(self.data_file, 'r') as f:
                apps = json.load(f)
                
            # Dynamically count active mappings for each app
            all_mappings = self.mapping_service.get_mappings()
            
            for app in apps:
                count = sum(1 for m in all_mappings if m.get('target_app') == app['name'] and m.get('is_active', True) != False)
                app['mappings'] = count
            
            # --- FIXED: Apply Universal SearchService ---
            if search_term:
                # 1. Create an instance of the SearchService
                search_obj = SearchService()
                
                # 2. Call the available filter_data method
                apps = search_obj.filter_data(
                    query=search_term,
                    data_list=apps,
                    key_to_search='name'
                )
                
                # 3. Sort the filtered results alphabetically by name
                apps = sorted(apps, key=lambda x: x.get('name', '').lower())
                
            return apps
        except Exception as e:
            # Print the error to your backend console so it doesn't fail silently
            print(f"Error in get_connected_apps: {e}") 
            return []
            
    def disconnect_app(self, app_name):
        try:
            with open(self.data_file, 'r') as f:
                apps = json.load(f)
            
            apps = [a for a in apps if a['name'] != app_name]
            
            with open(self.data_file, 'w') as f:
                json.dump(apps, f, indent=4)
                
            # --- NEW: Automatically delete associated mappings when an app is disconnected ---
            all_mappings = self.mapping_service.get_mappings()
            for mapping in all_mappings:
                if mapping.get('target_app') == app_name:
                    self.mapping_service.delete_mapping(mapping.get('gesture_name'), app_name)
                    
            return {"status": "success", "message": f"Disconnected {app_name} and deleted associated mappings."}
        except Exception as e:
            return {"status": "error", "message": str(e)}