from backend.services.action_mapping_service import ActionMappingService
from backend.services.integration_service import IntegrationService

class DashboardService:
    def __init__(self):
        self.mapping_service = ActionMappingService()
        self.integration_service = IntegrationService()

    def get_metrics(self):
        """Aggregates metrics for the dashboard to prevent frontend data overloading."""
        try:
            # 1. Calculate Connected Apps
            apps = self.integration_service.get_connected_apps()
            connected_apps_count = len(apps) if apps else 0

            # 2. Calculate Active Mappings
            mappings = self.mapping_service.get_mappings()
            
            # BL Note: If 'is_active' is undefined, it defaults to True. 
            active_mappings = [m for m in mappings if m.get('is_active', True) is not False]
            active_gestures_count = len(active_mappings)
            
            # 3. Calculate Running Automations (Based on active gesture mappings)
            running_automations_count = active_gestures_count

            return {
                "status": "success",
                "connected_apps_count": connected_apps_count,
                "active_gestures_count": active_gestures_count,
                "running_automations_count": running_automations_count # <--- NEW
            }
        except Exception as e:
            print(f"Error fetching dashboard metrics: {e}")
            return {
                "status": "error",
                "message": str(e),
                "connected_apps_count": 0,
                "active_gestures_count": 0,
                "running_automations_count": 0 # <--- NEW
            }