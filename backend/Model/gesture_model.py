from tensorflow.keras import layers, models

def create_gesture_cnn(num_classes, input_shape=(128, 128, 3)):
    """
    Pure Keras CNN Model Logic for GestureAuto.
    Replaces PyTorch/LSTM. Extracts spatial features from raw image pixels.
    """
    model = models.Sequential([
        # 1. First Convolutional Block
        layers.Conv2D(32, (3, 3), activation='relu', input_shape=input_shape),
        layers.MaxPooling2D(2, 2),
        
        # 2. Second Convolutional Block
        layers.Conv2D(64, (3, 3), activation='relu'),
        layers.MaxPooling2D(2, 2),
        
        # 3. Third Convolutional Block
        layers.Conv2D(128, (3, 3), activation='relu'),
        layers.MaxPooling2D(2, 2),
        
        # 4. Flatten 2D matrices into 1D Vector
        layers.Flatten(),
        
        # 5. Fully Connected (Dense) Classification
        layers.Dense(128, activation='relu'),
        layers.Dropout(0.5), # Crucial for preventing overfitting on augmented images
        layers.Dense(num_classes, activation='softmax')
    ])
    
    # Compile the model for training
    model.compile(
        optimizer='adam',
        loss='sparse_categorical_crossentropy', 
        metrics=['accuracy']
    )
    
    return model