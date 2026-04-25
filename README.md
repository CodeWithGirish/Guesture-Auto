# GestureAuto 🖐️💻

**GestureAuto** is a cross-platform desktop automation tool that allows users to control their computers using hand gestures. By leveraging Computer Vision (MediaPipe) and Deep Learning (Keras/TensorFlow), the application translates real-time hand movements into system-level or application-specific actions, such as controlling media, navigating browsers, or launching applications.


## 🌟 Key Features

* **Real-time Gesture Recognition:** Uses MediaPipe for high-accuracy hand landmarking and a custom CNN model for gesture classification.
* **Dual-App Architecture:** * **User App:** For daily automation, action mapping, and dashboard monitoring.
    * **Admin App:** For dataset management, image augmentation, and model training/evaluation.
* **Context-Aware Automation:** Distinguishes between "Global" system actions and "Application Level" actions that only trigger when a specific app (like Spotify or VS Code) is in focus.
* **Advanced Augmentation:** Includes built-in tools for expanding training datasets using GANs and Diffusion models to improve model robustness.
* **Cross-Platform Support:** Logic designed to work across Windows, macOS, and Linux.

## 🛠️ Tech Stack

* **Language:** Python 3.11+
* **UI Framework:** PyWebView (HTML/JS/CSS Frontend)
* **Computer Vision:** OpenCV, MediaPipe
* **Deep Learning:** TensorFlow/Keras, PyTorch
* **Automation:** PyAutoGUI, Keyboard, psutil

## 📂 Project Structure

```text
GuestureAuto/
├── backend/            # API handlers and business logic services
├── engine/             
│   ├── automation/     # Action execution (PyAutoGUI) logic
│   ├── detection/      # Gesture prediction and motion tracking
│   ├── training/       # Model training pipelines
│   └── augumentation/  # GAN/Diffusion data expansion
├── frontend/           # HTML/JS/CSS for User and Admin dashboards
├── models/             # Trained .keras models and class mappings
└── data/               # Configuration and mapping JSON files
```

## 🚀 Getting Started

### Prerequisites
* Python 3.11 or higher
* A webcam for gesture detection

### Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/yourusername/Gesture-Auto.git
    cd Gesture-Auto
    ```

2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### Usage

* **To Run the Automation Tool (User Mode):**
    ```bash
    python main_user.py
    ```
    *This opens the dashboard where you can map gestures like "Open Palm" to "Play/Pause" or "Fist" to "Mute".*

* **To Train/Manage Models (Admin Mode):**
    ```bash
    python main_admin.py
    ```
    *This provides access to the Dataset Overview and Model Configuration screens for training new gestures.*

## ⚙️ How it Works

1.  **Detection:** The `GesturePredictor` captures frames from the webcam, detects 21 hand landmarks, and normalizes them for scale invariance.
2.  **Classification:** A trained CNN model processes these landmarks to identify the gesture with a confidence threshold (default 75%).
3.  **Resolution:** The `AutomationExecutor` checks which application is currently in the foreground.
4.  **Execution:** If a mapping exists for that gesture and context, it triggers the corresponding hotkey or system command via PyAutoGUI.

## 🛡️ Safety & Controls

* **Fail-Safe:** Moving the mouse to any corner of the screen will immediately abort automation actions.
* **Cooldowns:** Prevents accidental double-triggers by implementing configurable detection delays.

## 📄 License
This project is licensed under the MIT License - see the LICENSE file for details.
