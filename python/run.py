import os
import sys
import json
import stat
import urllib
import shutil
import zipfile
import argparse
import platform
import subprocess
import urllib.request
from pathlib import Path


# Check python version
REQUIRED_PYTHON_VERSION = (3, 12)
if sys.version_info[:2] != REQUIRED_PYTHON_VERSION:
    raise RuntimeError(f"Python {REQUIRED_PYTHON_VERSION[0]}.{REQUIRED_PYTHON_VERSION[1]} is required.")


# Set client platform
match platform.system():
    case "Windows":
        client_platform = "win"
    case "Linux":
        client_platform = "linux"
    case "Darwin":
        client_platform = "mac"
    case _:
        raise EnvironmentError(f"Unsupported platform '{platform.system()}'")


# Global properties, update using load_properties()
properties = {
    "skip_version_check": False,
    "compatibility_client": False,
    "on_saturn": False,
    "gcloud_token": None
}


def str_to_bool(value: str) -> bool:
    if isinstance(value, bool):
        return value
    if value.lower() in {'true', 'yes', 'y', '1'}:
        return True
    elif value.lower() in {'false', 'no', 'n', '0'}:
        return False
    else:
        raise argparse.ArgumentTypeError(f"Invalid boolean value: {value}")


class ZipFileWithPermissions(zipfile.ZipFile):
    """ Custom ZipFile class handling file permissions. """

    def _extract_member(self, member, targetpath, pwd):
        if not isinstance(member, zipfile.ZipInfo):
            member = self.getinfo(member)

        targetpath = super()._extract_member(member, targetpath, pwd)

        attr = member.external_attr >> 16

        # Handle symlinks
        if stat.S_ISLNK(attr):
            with self.open(member) as source:
                link_target = source.read().decode('utf-8')
            os.unlink(targetpath)  # Remove the file extracted by super()
            os.symlink(link_target, targetpath)
        else:
            # Set file permissions
            if attr != 0:
                os.chmod(targetpath, attr)

        return targetpath


def install_engine(ver_data, version):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", f".temp/{ver_data['get_filename'](version)}"])
        return True
    except Exception as e:
        print(f"Failed to install package: {e}")
        return False


def install_client(ver_data, version):
    try:
        shutil.rmtree('client', ignore_errors=True)
        with ZipFileWithPermissions(f".temp/{ver_data['get_filename'](version)}", 'r') as zip_ref:
            zip_ref.extractall("client")
        if properties["compatibility_client"]:
            print("COMPATIBILITY CLIENT INSTALLED")
        return True
    except Exception as e:
        print(f"Failed to unpack client: {e}")
        return False


# Constants
SOURCE_DIR = Path("src")
TEST_DIR = Path("test")
ENGINE_VER_DATA = {
    "name": "engine",
    "file": "engine_version.txt",
    "get_property": lambda: "release_version_saturn" if properties["on_saturn"] else "release_version_public",
    "get_url": lambda version: f"maven/org/battlecode/battlecode25-python/{version}/battlecode.tar.gz",
    "get_filename": lambda version: "battlecode.tar.gz",
    "install": install_engine
}
CLIENT_VER_DATA = {
    "name": "client",
    "file": "client_version.txt",
    "get_property": lambda: "release_version_client",
    "get_url": lambda version: f"maven/org/battlecode/battlecode25-client-{client_platform}-{'electron' if properties['compatibility_client'] else 'tauri'}/{version}/battlecode25-client-{client_platform}-{'electron' if properties['compatibility_client'] else 'tauri'}-{version}.zip",
    "get_filename": lambda version: "battlecode25-client.zip",
    "install": install_client
}


def load_properties():
    try:
        with open("properties.json", "r") as f:
            loaded = json.load(f)
        # Update properties with loaded keys
        for k, v in loaded.items():
            if k in properties:
                properties[k] = v
    except Exception as e:
        pass


def download_file(url, output_name):
    # Create temp directory
    output_path = f".temp/{output_name}"
    if not os.path.exists(".temp"):
        os.mkdir(".temp")
    elif os.path.exists(output_path):
        os.remove(output_path)

    if properties["on_saturn"]:
        # GCS download

        from google.cloud import storage

        client = storage.Client()
        bucket = client.bucket("mitbattlecode-releases")
        blob = bucket.blob(url)
        blob.download_to_filename(output_path)

        print(f"File downloaded with GCS to {output_path}")
    else:
        # Standard HTTP download

        url = f"https://releases.battlecode.org/{url}"

        def reporthook(downloaded, total_size):
            if total_size > 0:
                percent = downloaded / total_size * 100
                bar_length = 40
                filled_length = int(bar_length * downloaded // total_size)
                bar = '=' * filled_length + '-' * (bar_length - filled_length)
                sys.stdout.write(f'\r[{bar}] {percent:.2f}%')
                sys.stdout.flush()
            else:
                # Total size unknown
                sys.stdout.write(f'\rDownloaded {downloaded / (1024 ** 2):.2f} MB')
                sys.stdout.flush()

        req = urllib.request.Request(url)
        if properties["gcloud_token"] is not None:
            req.add_header("Authorization", f"Bearer {properties['gcloud_token']}")

        print(f"Downloading {output_name}...")
        with urllib.request.urlopen(req) as response, open(output_path, 'wb') as out_file:
            total_size = int(response.getheader('Content-Length', 0))
            downloaded = 0
            chunk_size = 8192 * 2
            while chunk := response.read(chunk_size):
                out_file.write(chunk)
                downloaded += len(chunk)
                reporthook(downloaded, total_size)

        sys.stdout.write('\n')
        sys.stdout.flush()


def get_local_version(ver_data) -> str:
    version_file = Path(ver_data["file"])
    if version_file.is_file():
        with open(version_file, "r") as vf:
            return vf.read().strip()
    else:
        print("Version file not found, assuming 0.0.0")
        return "0.0.0"


def set_local_version(ver_data, new_version: str):
    version_file = Path(ver_data["file"])
    with open(version_file, "w") as vf:
        vf.write(new_version)


def get_server_version(ver_data) -> str | None:
    """Fetch the latest version from the server"""
    url = "https://api.battlecode.org/api/episode/e/bc25python/?format=json"
    #url = "https://api.battlecode.org/api/episode/e/bc24/?format=json"
    try:
        with urllib.request.urlopen(url) as response:
            parsed = json.loads(response.read())
            version = parsed[ver_data["get_property"]()]
            if version == "":
                return None
            return version
    except Exception as e:
        print(f"Failed to fetch server version: {e}")
        return None


def check_new_version(ver_data) -> str | None:
    """Check for a newer version."""
    latest_version = get_server_version(ver_data)
    if latest_version is None:
        print("WARNING: unable to get the latest version from the server")
        return None
    current_version = get_local_version(ver_data)
    if current_version != latest_version:
        return latest_version
    return None


def run_update(ver_data):
    """Update the version."""
    new_version = check_new_version(ver_data)
    if new_version is None:
        print(f"{ver_data['name']} is up to date.")
        return

    print(f"Updating {ver_data['name']}...")

    # Download package
    filename = ver_data["get_filename"](new_version)
    try:
        url = ver_data['get_url'](new_version)
        download_file(url, filename)
    except Exception as e:
        print(f"Failed to download package: {e}")
        return

    if not ver_data["install"](ver_data, new_version):
        return

    # Update version file
    set_local_version(ver_data, new_version)

    print(f"Successfully updated {ver_data['name']} version to {new_version}")


def verify_package(player_dir):
    if not os.path.exists(player_dir):
        print(f"Player dir {player_dir} missing!")
        return False

    bot_path = os.path.join(player_dir, "bot.py")
    if not os.path.exists(bot_path):
        print(f"Missing bot.py in {player_dir}!")
        return False

    with open(bot_path, "r") as f:
        source = f.read()
    if "def turn():" not in source:
        print("Missing 'def turn()' main function in bot.py!")
        return False

    try:
        # Try compiling the bot
        from battlecode25 import CodeContainer
        container = CodeContainer.from_directory(player_dir)
    except Exception as e:
        print(f"Compile failed! {e}")
        return False

    return True


def list_python_files(directory):
    """List Python files in a directory."""
    return [file for file in directory.rglob("*.py")]


def run_script(script_path, args=None):
    """Run a Python script."""
    if not script_path.is_file():
        raise FileNotFoundError(f"Script not found: {script_path}")
    command = [sys.executable, str(script_path)] + (args or [])
    subprocess.run(command, check=True)


def run_game(args):
    """Run a battlecode game"""
    # Import at run time so that we can ensure the package is installed first
    from battlecode25 import run_game, RunGameArgs

    print(f"Playing game between {args.p1} and {args.p2} on {args.maps}")

    # Run the game
    # TODO: look for builtin maps
    game_args = RunGameArgs(
        player1_dir=Path(args.p1_dir) / args.p1,
        player2_dir=Path(args.p2_dir) / args.p2,
        player1_name=args.p1_team if args.p1_team is not None else args.p1,
        player2_name=args.p2_team if args.p2_team is not None else args.p2,
        map_dir="maps",
        map_names=args.maps,
        out_dir=args.out_file_dir,
        out_name=args.out_file_name,
        show_indicators=args.show_indicators,
        debug=args.debug,
        instrument=args.instrument
    )
    run_game(game_args)


# ====== TASKS =======


def task_tasks(args):
    """Print all valid tasks."""
    print("Available tasks:", ", ".join(tasks.keys()))


def task_test(args):
    """Run all test scripts."""
    test_files = list_python_files(TEST_DIR)
    if not test_files:
        print("No tests found.")
        return
    print(f"Running tests in: {TEST_DIR}")
    for test in test_files:
        print(f"Running test: {test}")
        run_script(test)


def task_version(args):
    """Output the current version."""
    for ver_data in [ENGINE_VER_DATA, CLIENT_VER_DATA]:
        ver = get_local_version(ver_data)
        print(f"Local {ver_data['name']} version: {ver}")


def task_check_version(args):
    """Check for new versions on the server"""
    for ver_data in [ENGINE_VER_DATA, CLIENT_VER_DATA]:
        ver = check_new_version(ver_data)
        if ver is not None:
            print(f"!!! New {ver_data['name']} version available: {ver}. Run 'python run.py update' to update.")
        else:
            print(f"{ver_data['name']} is up to date.")


def task_update(args):
    """Update all packages."""
    run_update(ENGINE_VER_DATA)
    if not args.on_saturn:
        run_update(CLIENT_VER_DATA)


def task_verify(args):
    """Verify a player is ready to submit."""
    player_dir = f"src/{args.p1}"
    if verify_package(player_dir):
        print("Player is valid!")
    else:
        raise RuntimeError("Player is not valid!")


def task_zip_submission(args):
    """Zip your code into a zipfile to be submitted online."""
    with zipfile.ZipFile("submission.zip", 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk("src"):
            relative_root = os.path.relpath(root, "src")
            for file in files:
                if not file.endswith(".py"):
                    continue
                file_path = os.path.join(root, file)
                arcname = os.path.join(relative_root, file) if relative_root != '.' else file
                zipf.write(file_path, arcname)


def task_run(args):
    """Run a match between two players."""
    if not properties["skip_version_check"] and not args.skip_check:
        ver = check_new_version(ENGINE_VER_DATA)
        if ver is not None:
            print(f"!!! New engine version available: {ver}. Run 'python run.py update' to update, or use --skip-check to skip the version check.")
            return
        print("engine is up to date.")
    else:
        print("Skipped version check")

    run_game(args)


# Command-line interface
if __name__ == "__main__":
    tasks = {
        "tasks": task_tasks,
        "test": task_test,
        "version": task_version,
        "check_version": task_check_version,
        "update": task_update,
        "verify": task_verify,
        "zip_submission": task_zip_submission,
        "run": task_run
    }

    load_properties()

    parser = argparse.ArgumentParser(description="Run a Python script with specific arguments and settings.")
    parser.add_argument(
        "task",
        type=str,
        help=f"The task to run. ({', '.join(tasks.keys())})"
    )
    parser.add_argument(
        "--p1",
        type=str,
        default="examplefuncsplayer",
        help="Name of Player 1"
    )
    parser.add_argument(
        "--p2",
        type=str,
        default="examplefuncsplayer",
        help="Name of Player 2"
    )
    parser.add_argument(
        "--p1-dir",
        type=str,
        default="src",
        help="Directory where player 1 is stored"
    )
    parser.add_argument(
        "--p2-dir",
        type=str,
        default="src",
        help="Directory where player 2 is stored"
    )
    parser.add_argument(
        "--p1-team",
        type=str,
        default=None,
        help="Team name for player 1, defaults to value of --p1"
    )
    parser.add_argument(
        "--p2-team",
        type=str,
        default=None,
        help="Team name for player 2, defaults to value of --p2"
    )
    parser.add_argument(
        "--maps",
        type=str,
        default="DefaultSmall",
        help="Name of the maps to run, separated by commas"
    )
    parser.add_argument(
        "--debug",
        type=str_to_bool,
        default=True,
        help="Enable logging within the bot"
    )
    parser.add_argument(
        "--instrument",
        type=str_to_bool,
        default=True,
        help="Whether or not to disable instrumenting for debug purposes",
    )
    parser.add_argument(
        "--show-indicators",
        type=str_to_bool,
        default=True,
        help="Enable showing debug indicators for robots"
    )
    parser.add_argument(
        "--skip-check",
        type=str_to_bool,
        default=False,
        help="Skip the version check when running a match",
    )
    parser.add_argument(
        "--out-file-dir",
        type=str,
        default="matches",
        help="Directory to output matches to"
    )
    parser.add_argument(
        "--out-file-name",
        type=str,
        default=None,
        help="Name override of the output replay file. Defaults to something useful."
    )
    parser.add_argument(
        "--on-saturn",
        type=str_to_bool,
        default=False,
        help="Dev use only. Indicates when running on the server",
    )
    parser.add_argument(
        "--gcloud-token",
        type=str,
        default=None,
        help="Dev use only. Token for accessing private gcloud files",
    )
    args = parser.parse_args()

    properties["on_saturn"] = args.on_saturn
    properties["gcloud_token"] = args.gcloud_token

    if args.task not in tasks:
        print(f"Invalid task '{args.task}'")
        print("Available tasks:", ", ".join(tasks.keys()))
        sys.exit(1)

    tasks[args.task](args)
