import winreg

class AppManager:
    def __init__(self):
        # Common keywords to filter out system junk and redistributables
        self.junk_filters = ['update', 'redistributable', 'runtime', 'sdk', 'driver', 'windows', 'microsoft visual']

    def scan_installed_apps(self):
        """Scans the Windows Registry for installed applications."""
        installed_apps = []
        seen_apps = set()

        # We need to check both 64-bit and 32-bit registry paths, plus Current User
        registry_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
        ]

        for hkey_root, path in registry_paths:
            try:
                key = winreg.OpenKey(hkey_root, path)
                for i in range(0, winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey = winreg.OpenKey(key, subkey_name)
                        
                        # Fetch the Display Name and Version
                        app_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                        try:
                            app_version = winreg.QueryValueEx(subkey, "DisplayVersion")[0]
                        except FileNotFoundError:
                            app_version = "Unknown"

                        # Filter out system components and duplicates
                        name_lower = str(app_name).lower()
                        is_junk = any(junk in name_lower for junk in self.junk_filters)
                        
                        if app_name and not is_junk and app_name not in seen_apps:
                            seen_apps.add(app_name)
                            
                            # Assign a generic material icon based on the name
                            icon = "widgets"
                            if "chrome" in name_lower or "browser" in name_lower: icon = "language"
                            elif "code" in name_lower or "studio" in name_lower: icon = "code"
                            elif "zoom" in name_lower or "teams" in name_lower: icon = "video_call"
                            elif "music" in name_lower or "spotify" in name_lower: icon = "music_note"
                            elif "adobe" in name_lower: icon = "brush"

                            installed_apps.append({
                                "name": app_name,
                                "version": app_version,
                                "icon": icon
                            })
                    except OSError:
                        pass # Subkey doesn't have a DisplayName, skip it
            except OSError:
                pass # Path doesn't exist, skip it

        # Sort alphabetically
        installed_apps.sort(key=lambda x: x['name'])
        return installed_apps