#!/bin/bash

# Raspberry Pi Camera Control Setup Script
# This script sets up the Python environment and installs dependencies

echo "🎥 Raspberry Pi Camera Control Setup"
echo "=================================="

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
    echo "   The camera functionality may not work properly"
fi

# Update system packages
echo "📦 Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install system dependencies for camera and OpenCV
echo "🔧 Installing system dependencies..."
sudo apt install -y \
    python3-dev \
    python3-pip \
    python3-venv \
    libcamera-dev \
    libcamera-apps \
    python3-libcamera \
    python3-kms++ \
    libatlas-base-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev

# Enable camera interface
echo "📷 Enabling camera interface..."
if ! grep -q "camera_auto_detect=1" /boot/config.txt; then
    echo "camera_auto_detect=1" | sudo tee -a /boot/config.txt
    echo "⚠️  Camera interface enabled - reboot required after setup"
fi

# Create virtual environment
echo "🐍 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p /home/pi/Desktop/logs
mkdir -p /home/pi/Desktop/timelapse
mkdir -p Pictures

# Set proper permissions
chmod 755 /home/pi/Desktop/logs
chmod 755 /home/pi/Desktop/timelapse
chmod 755 Pictures

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Run the application: python app.py"
echo "3. Access the camera stream at: http://localhost:5000"
echo ""
echo "🌐 The server will be accessible from other devices on your network at:"
echo "   http://$(hostname -I | awk '{print $1}'):5000"
echo ""
if grep -q "camera_auto_detect=1" /boot/config.txt && ! lsmod | grep -q bcm2835_v4l2; then
    echo "⚠️  Please reboot your Raspberry Pi to enable the camera interface:"
    echo "   sudo reboot"
fi