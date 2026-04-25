from backend.services.integration_service import IntegrationService

class IntegrationAPI:
    def __init__(self):
        # Delegate all logic to the newly created service layer
        self.service = IntegrationService()

    def scan_system_apps(self):
        return self.service.scan_system_apps()

    def stage_app_connection(self, app_data):
        return self.service.stage_app_connection(app_data)

    def unstage_app_connection(self, app_name):
        return self.service.unstage_app_connection(app_name)

    def save_staged_integrations(self):
        return self.service.save_staged_integrations()
    
    def clear_staged_integrations(self):
        return self.service.clear_staged_integrations()

    def get_connected_apps(self, search_term=None):
        return self.service.get_connected_apps(search_term)
        
    def disconnect_app(self, app_name):
        return self.service.disconnect_app(app_name)