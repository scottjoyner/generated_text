import sys
import subprocess

try:
    import setuptools
except ImportError:
    print("setuptools not found. Listing installed packages:")
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'list'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            print(result.stdout)
        else:
            print("Error running pip list:")
            print(result.stderr)
    except Exception as e:
        print("Failed to run pip list:", e)
