#!/bin/bash

#-------------------------------------------
# Fungi Forge Setup Script
#-------------------------------------------
# This script performs:
#   - System package updates and dependency installation
#   - Python virtual environment creation and setup
#   - Python dependencies installation
#   - Optional systemd service configuration and startup
#-------------------------------------------

echo "Updating system packages..."
sudo apt update

# Install required system packages for camera and Python development
echo "Installing required system dependencies..."
sudo apt install -y \
  libcamera-dev libcamera-apps python3-libcamera \
  python3-picamera2 python3-kms++ \
  python3-venv python3-dev libcap-dev libopenblas-dev libopenjp2-7 libtiff-dev cmake

#-------------------------------------------
# Python virtual environment setup
#-------------------------------------------

if [ -d ".venv" ]; then
    read -p "The .venv virtual environment already exists. Do you want to delete and recreate it? (y/n): " answer
    if [[ "$answer" =~ ^[yY]$ ]]; then
        echo "Deleting existing virtual environment..."
        rm -rf .venv
    else
        echo "Using the existing virtual environment."
    fi
fi

if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment with access to system packages..."
    python3 -m venv .venv --system-site-packages
fi

echo "Activating virtual environment and installing Python dependencies..."
source .venv/bin/activate
pip install --upgrade pip

echo "Uninstalling system-wide numpy to avoid conflicts with venv..."
sudo apt remove -y python3-numpy

pip install -r requirements.txt

#-------------------------------------------
# Picamera2 sanity check
#-------------------------------------------
echo "Verifying picamera2 module import..."

python3 -c "from picamera2 import Picamera2; print('✅ Picamera2 imported successfully')" || {
    echo "❌ Failed to import Picamera2. Try rebooting or manually checking system packages."
}

#-------------------------------------------
# Virtual environment prompt
#-------------------------------------------
read -p "Setup complete. Do you want to activate the virtual environment now? (y/n): " activate_env
if [[ "$activate_env" =~ ^[yY]$ ]]; then
    source .venv/bin/activate
    echo "Virtual environment activated."
else
    echo "You can activate the environment later with: source .venv/bin/activate"
fi

#-------------------------------------------
# systemd service setup
#-------------------------------------------

echo "Starting the Fungi Forge service configuration..."

read -p "Do you want to set up fungiforge.service in systemd to start on boot? (y/n): " setup_choice
if [[ "$setup_choice" =~ ^[Yy]$ ]]; then
    export FUNGIFORCE_PATH="$(pwd)"
    echo "Detected repository path: $FUNGIFORCE_PATH"

    echo "Rendering systemd service file with correct path..."
    envsubst < fungiforge.service.in > /tmp/fungiforge.service

    echo "Installing systemd service file..."
    sudo cp /tmp/fungiforge.service /etc/systemd/system/fungiforge.service

    echo "Reloading systemd to recognize the new service..."
    sudo systemctl daemon-reload

    echo "Enabling the service to start on boot..."
    sudo systemctl enable fungiforge.service
    echo "Service enabled to start on boot."
else
    echo "Skipped systemd setup."
fi

read -p "Do you want to start the fungiforge.service now? (y/n): " start_choice
if [[ "$start_choice" =~ ^[Yy]$ ]]; then
    echo "Starting the service..."
    sudo systemctl start fungiforge.service
    echo "Service started successfully."
else
    echo "Skipped starting the service now."
fi

#-------------------------------------------
# Final notes
#-------------------------------------------
echo
echo "You can always manage the service with the following commands:"
echo "  To start the service:   sudo systemctl start FungiForge.service"
echo "  To stop the service:    sudo systemctl stop FungiForge.service"
echo "  To check the status:    sudo systemctl status FungiForge.service"
echo "  To view the logs:       journalctl -u FungiForge.service -f"
