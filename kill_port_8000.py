import os
import re
import subprocess
import sys

def main():
    try:
        # Run netstat to find port 8000
        output = subprocess.check_output("netstat -ano", shell=True).decode(errors='ignore')
        pids = []
        for line in output.splitlines():
            if ":8000 " in line or " 0.0.0.0:8000 " in line or " 127.0.0.1:8000 " in line:
                parts = line.strip().split()
                if len(parts) >= 5:
                    pid = parts[-1]
                    pids.append(pid)
                    
        pids = list(set(pids)) # Unique PIDs
        if not pids:
            print("No process found holding port 8000.")
            return
            
        print(f"Found process(es) holding port 8000: {pids}")
        for pid in pids:
            try:
                # Force kill process
                subprocess.check_call(f"taskkill /F /PID {pid}", shell=True)
                print(f"Successfully killed process {pid}.")
            except Exception as ke:
                print(f"Failed to kill process {pid}: {ke}")
    except Exception as e:
        print(f"Error checking port 8000: {e}")

if __name__ == "__main__":
    main()
