import sys
import subprocess
from setproctitle import setproctitle

def run_script(script_path, title):
    setproctitle(title)
    subprocess.run(["bash", script_path])

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python run_script_with_title.py <path_to_script.sh> <process_title>")
        sys.exit(1)
    
    script_path = sys.argv[1]
    title = sys.argv[2]
    
    run_script(script_path, title)
