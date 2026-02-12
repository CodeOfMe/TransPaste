import os
import shutil
import subprocess
import sys

def run_command(command, cwd=None):
    """Run a shell command and print output."""
    print(f"Running: {command}")
    try:
        subprocess.check_call(command, shell=True, cwd=cwd)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        sys.exit(1)

def clean_build_artifacts():
    """Remove dist, build, and egg-info directories."""
    dirs_to_remove = ["dist", "build", "src/transpaste.egg-info"]
    for d in dirs_to_remove:
        if os.path.exists(d):
            print(f"Removing {d}...")
            shutil.rmtree(d)

def main():
    print("Starting PyPI upload process...")

    # 1. Clean previous builds
    clean_build_artifacts()

    # 2. Install build tools
    print("Installing build tools...")
    run_command(f"{sys.executable} -m pip install --upgrade build twine")

    # 3. Build the package
    print("Building package...")
    run_command(f"{sys.executable} -m build")

    # 4. Upload to PyPI
    print("Uploading to PyPI...")
    # Using 'twine upload' directly. 
    # Note: You need to have configured your credentials in .pypirc or provide them interactively.
    # Alternatively, use environment variables TWINE_USERNAME and TWINE_PASSWORD.
    try:
        run_command("twine upload dist/*")
        print("\nSUCCESS: Package uploaded to PyPI!")
    except SystemExit:
        print("\nUpload failed. Check your credentials or network connection.")

if __name__ == "__main__":
    main()
