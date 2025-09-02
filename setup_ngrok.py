#!/usr/bin/env python3
"""
Setup script for ngrok configuration
This script helps set up ngrok for local development with Twilio
"""

import os
import sys
import subprocess
from pathlib import Path

def check_ngrok_installed():
    """Check if ngrok is installed"""
    try:
        result = subprocess.run(['ngrok', 'version'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def install_ngrok():
    """Install ngrok if not present"""
    print("ngrok not found. Installing...")
    
    if sys.platform == "darwin":  # macOS
        try:
            subprocess.run(['brew', 'install', 'ngrok'], check=True)
            print("✅ ngrok installed via Homebrew")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install ngrok via Homebrew")
            print("Please install manually from https://ngrok.com/")
            return False
    else:
        print("Please install ngrok manually from https://ngrok.com/")
        return False

def start_ngrok(port=8000):
    """Start ngrok tunnel"""
    if not check_ngrok_installed():
        if not install_ngrok():
            return None
    
    print(f"🚀 Starting ngrok tunnel on port {port}...")
    print("📱 Use the HTTPS URL in your Twilio webhook configuration")
    print("⏹️  Press Ctrl+C to stop ngrok")
    
    try:
        subprocess.run(['ngrok', 'http', str(port)])
    except KeyboardInterrupt:
        print("\n⏹️  ngrok stopped")

def main():
    """Main setup function"""
    print("🔧 WhatsApp Memory Assistant - ngrok Setup")
    print("=" * 50)
    
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}. Using default port 8000.")
    
    start_ngrok(port)

if __name__ == "__main__":
    main()
