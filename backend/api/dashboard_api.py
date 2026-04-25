from backend.services.dashboard_service import DashboardService

class DashboardAPI:
    def __init__(self):
        self.service = DashboardService()

    def get_dashboard_metrics(self):
        """Endpoint to fetch all dashboard numbers in a single call."""
        return self.service.get_metrics()
        
    def get_system_health(self):
        """Endpoint to fetch dynamic system health using psutil"""
        try:
            import psutil
            cpu_usage = psutil.cpu_percent(interval=None)
            mem_usage = psutil.virtual_memory().percent
            
            # Health = 100 - average load
            health = int(100 - ((cpu_usage + mem_usage) / 2))
            
            # Ensure within 0-100 bounds
            health = max(0, min(100, health))
            
            return {
                "status": "success",
                "health": health
            }
        except Exception as e:
            print(f"Error calculating system health: {e}")
            return {
                "status": "error",
                "health": 98
            }