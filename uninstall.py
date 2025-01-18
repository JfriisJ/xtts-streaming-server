import subprocess

def uninstall_all_packages():
    # List all installed packages
    result = subprocess.run(["pip", "freeze"], stdout=subprocess.PIPE, text=True)
    packages = result.stdout.splitlines()

    if not packages:
        print("No packages to uninstall.")
        return

    # Uninstall all packages
    uninstall_command = ["pip", "uninstall", "-y"] + [pkg.split("==")[0] for pkg in packages]
    subprocess.run(uninstall_command)

if __name__ == "__main__":
    uninstall_all_packages()
