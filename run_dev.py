 #!/usr/bin/env python
"""
Development server runner for HydroZap with Redis support.
This script checks if Redis is running and starts the Django development server.
"""

import os
import sys
import subprocess
import time
import socket

def is_redis_running(host='localhost', port=6379):
    """Check if Redis is running on the specified host and port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex((host, port))
    sock.close()
    return result == 0

def start_redis():
    """Start Redis server in the background."""
    try:
        print("Starting Redis server...")
        # For Windows (using redis-server.exe)
        if os.name == 'nt':
            subprocess.Popen(['redis-server'], 
                           creationflags=subprocess.CREATE_NEW_CONSOLE,
                           shell=True)
        # For Linux/Mac
        else:
            subprocess.Popen(['redis-server'], 
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
        
        # Wait for Redis to start
        retries = 5
        while retries > 0 and not is_redis_running():
            print(f"Waiting for Redis to start. Retries left: {retries}")
            time.sleep(1)
            retries -= 1
            
        if is_redis_running():
            print("Redis server started successfully!")
            return True
        else:
            print("Failed to start Redis server. Please start it manually.")
            return False
    except Exception as e:
        print(f"Error starting Redis: {e}")
        print("Please make sure Redis is installed and in your PATH.")
        return False

def start_django_server():
    """Start Django development server with ASGI."""
    print("Starting Django development server...")
    try:
        cmd = ["daphne", "-b", "0.0.0.0", "-p", "8000", "hydrozap.asgi:application"]
        subprocess.call(cmd)
    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Error starting Django server: {e}")
        print("Make sure daphne is installed: pip install daphne")
        sys.exit(1)

if __name__ == "__main__":
    # Check if Redis is running
    if not is_redis_running():
        # If Redis is not running, try to start it
        if not start_redis():
            print("Redis is required for WebSockets. Please start Redis manually.")
            sys.exit(1)
    else:
        print("Redis is already running.")
    
    # Start Django development server
    start_django_server()