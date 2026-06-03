#!/bin/bash
echo "🚀 Setting up Raspberry Pi environment..."

# Update system
sudo apt update
sudo apt upgrade -y

# Install system-level dependencies for OpenCV and Camera
sudo apt install -y python3-pip python3-venv libcamera-apps libopenjp2-7

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Setup complete! Activate environment with: source venv/bin/activate"