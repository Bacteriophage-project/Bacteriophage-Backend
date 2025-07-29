#!/usr/bin/env python3
"""
Startup script for the Genome Analysis Tool
This script starts the Flask API server and provides instructions for the React frontend.
"""

import os
import sys
import subprocess
import time
import webbrowser
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    print("🔍 Checking dependencies...")
    
    # Check Python dependencies
    try:
        import flask
        import pandas
        import requests
        import Bio  # Correct import for Biopython
        print("✅ Python dependencies are installed")
    except ImportError as e:
        print(f"❌ Missing Python dependency: {e}")
        print("Please install dependencies with: pip install -r requirements.txt")
        return False
    
    # Check if Node.js is installed
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            print(f"✅ Node.js is installed: {result.stdout.strip()}")
        else:
            print("❌ Node.js is not installed")
            return False
    except FileNotFoundError:
        print("❌ Node.js is not installed")
        return False
    
    # Check if npm is installed - try multiple methods for Windows compatibility
    npm_found = False
    try:
        # Method 1: Direct command
        result = subprocess.run(['npm', '--version'], capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            print(f"✅ npm is installed: {result.stdout.strip()}")
            npm_found = True
    except FileNotFoundError:
        pass
    
    if not npm_found:
        try:
            # Method 2: Try with full path
            result = subprocess.run(['where', 'npm'], capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                npm_path = result.stdout.strip().split('\n')[0]
                result = subprocess.run([npm_path, '--version'], capture_output=True, text=True, shell=True)
                if result.returncode == 0:
                    print(f"✅ npm is installed: {result.stdout.strip()}")
                    npm_found = True
        except FileNotFoundError:
            pass
    
    if not npm_found:
        try:
            # Method 3: Try with npx
            result = subprocess.run(['npx', '--version'], capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                print(f"✅ npm/npx is available: {result.stdout.strip()}")
                npm_found = True
        except FileNotFoundError:
            pass
    
    if not npm_found:
        print("❌ npm is not installed or not in PATH")
        print("Please install npm or add it to your PATH")
        return False
    
    return True

def install_frontend_dependencies():
    """Install React frontend dependencies"""
    frontend_dir = Path("genome-analysis-frontend")
    
    if not frontend_dir.exists():
        print("❌ Frontend directory not found")
        return False
    
    # Check if node_modules already exists (dependencies already installed)
    node_modules = frontend_dir / "node_modules"
    if node_modules.exists():
        print("✅ Frontend dependencies already installed")
        return True
    
    print("📦 Installing React frontend dependencies...")
    try:
        # Use shell=True for better Windows compatibility
        result = subprocess.run(
            ['npm', 'install'], 
            cwd=frontend_dir, 
            capture_output=True, 
            text=True, 
            shell=True
        )
        if result.returncode == 0:
            print("✅ Frontend dependencies installed successfully")
            return True
        else:
            print(f"❌ Failed to install frontend dependencies: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error installing frontend dependencies: {e}")
        return False

def start_backend():
    """Start the Flask API server"""
    print("🚀 Starting Flask API server...")
    
    # Create necessary directories
    os.makedirs("resfinder_results", exist_ok=True)
    os.makedirs("phastest_results", exist_ok=True)
    os.makedirs("vfdb_results", exist_ok=True)
    
    try:
        # Start the Flask server
        process = subprocess.Popen([
            sys.executable, "api_server.py"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Wait a moment for the server to start
        time.sleep(3)
        
        # Check if the server is running
        if process.poll() is None:
            print("✅ Flask API server is running on http://localhost:5000")
            return process
        else:
            stdout, stderr = process.communicate()
            print(f"❌ Failed to start Flask server: {stderr}")
            return None
            
    except Exception as e:
        print(f"❌ Error starting Flask server: {e}")
        return None

def start_frontend():
    """Start the React frontend"""
    frontend_dir = Path("genome-analysis-frontend")
    
    if not frontend_dir.exists():
        print("❌ Frontend directory not found")
        return None
    
    print("🌐 Starting React frontend...")
    
    # Try multiple methods to start the frontend
    start_commands = [
        ['yarn', 'start'],
        ['npm', 'start'],
        ['npx', 'react-scripts', 'start']
    ]
    
    for cmd in start_commands:
        try:
            print(f"Trying: {' '.join(cmd)}")
            process = subprocess.Popen(
                cmd, 
                cwd=frontend_dir, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True,
                shell=True
            )
            
            # Wait a moment for the server to start
            time.sleep(5)
            
            # Check if the server is running
            if process.poll() is None:
                print("✅ React frontend is running on http://localhost:3000")
                return process
            else:
                stdout, stderr = process.communicate()
                print(f"Failed with {cmd}: {stderr}")
                continue
                
        except Exception as e:
            print(f"Error with {cmd}: {e}")
            continue
    
    print("❌ Failed to start React frontend with all methods")
    return None

def main():
    """Main startup function"""
    print("🧬 Genome Analysis Tool - Startup")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        print("\n❌ Dependency check failed. Please install missing dependencies.")
        return
    
    # Install frontend dependencies if needed
    if not install_frontend_dependencies():
        print("\n❌ Frontend dependency installation failed.")
        return
    
    print("\n🚀 Starting services...")
    
    # Start backend
    backend_process = start_backend()
    if not backend_process:
        print("❌ Failed to start backend. Exiting.")
        return
    
    # Start frontend
    frontend_process = start_frontend()
    if not frontend_process:
        print("❌ Failed to start frontend. Exiting.")
        backend_process.terminate()
        return
    
    print("\n🎉 Both services are running!")
    print("📱 React Frontend: http://localhost:3000")
    print("🔧 Flask API: http://localhost:5000")
    print("\n💡 Usage:")
    print("1. Open http://localhost:3000 in your browser")
    print("2. Enter a BioProject ID to fetch genomes")
    print("3. Run ResFinder, PHASTEST, or VFDB analyses")
    print("4. Monitor progress and download results")
    
    # Open browser
    try:
        webbrowser.open('http://localhost:3000')
        print("\n🌐 Opened browser automatically")
    except:
        print("\n🌐 Please open http://localhost:3000 in your browser")
    
    print("\n⏹️  Press Ctrl+C to stop both services")
    
    try:
        # Keep the script running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping services...")
        backend_process.terminate()
        frontend_process.terminate()
        print("✅ Services stopped")

if __name__ == "__main__":
    main() 