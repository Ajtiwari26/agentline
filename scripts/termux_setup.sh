#!/bin/bash
# ---------------------------------------------------------
# AgentLine — One-Time Termux Setup Script for Android
# Run this inside Termux on your phone
# ---------------------------------------------------------

echo "=========================================="
echo "Starting AgentLine Termux Setup..."
echo "=========================================="

# 1. Update package lists and upgrade existing packages
echo "[1/4] Updating package lists..."
pkg update -y && pkg upgrade -y

# 2. Install required system build tools and python
echo "[2/4] Installing Python, Git, and build essentials..."
pkg install python python-pip git ndk-sysroot clang make -y

# 3. Upgrade pip and install required python modules
echo "[3/4] Installing Python dependencies (websockets, aiohttp, etc.)..."
pip install --upgrade pip
pip install websockets aiohttp google-generativeai pymongo

# 4. Success message and usage instruction
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo "To run the agent:"
echo "1. Copy the 'agentline' folder to your Termux home directory (~/)"
echo "2. Run the following command inside Termux:"
echo "   python ~/agentline/termux_agent.py"
echo "=========================================="
