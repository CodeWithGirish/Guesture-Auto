# main_admin.py
import webview
import os
from backend.api.api_handler import MasterAPI

def main():
    root = os.path.dirname(os.path.abspath(__file__))
    ui_path = os.path.join(root, 'frontend', 'admin_app', '2_Image Augumentation', 'Dataset Overview Screen.html')

    # Debug mode: set env var GESTUREATO_DEBUG=1 to enable DevTools (dev only).
    # Defaults to False so the debug console is never exposed in production.
    debug_mode = os.environ.get('GESTUREATO_DEBUG', '0') == '1'

    api = MasterAPI()
    webview.create_window(
        title='GestureAuto',
        url=f'file://{ui_path}',
        js_api=api,
        width=1280,
        height=800
    )

    try:
        webview.start(debug=debug_mode)
    finally:
        api.shutdown()

if __name__ == '__main__':
    main()