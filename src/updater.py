import os
import json
import re
import shutil
import tempfile
import urllib.request
import zipfile
from typing import Dict, Any, Tuple

from src.config import get_version_info

REMOTE_VERSION_URL = "https://raw.githubusercontent.com/caetanobiss/watcher/master/VERSION"
REMOTE_ZIP_URL = "https://github.com/caetanobiss/watcher/archive/refs/heads/master.zip"

class WatcherUpdater:
    """Handles checking for updates and performing self-updates without requiring Git or GitHub login."""

    def __init__(self):
        self.watcher_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def check_for_updates(self) -> Dict[str, Any]:
        """Fetches remote VERSION from GitHub master branch and compares with local version."""
        current_ver, current_date = get_version_info()
        
        try:
            req = urllib.request.Request(
                REMOTE_VERSION_URL,
                headers={"User-Agent": "Watcher-Updater/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                remote_content = resp.read().decode("utf-8")

            latest_ver, latest_date = self._parse_version_file(remote_content)
            has_update = self._compare_versions(latest_ver, current_ver)

            # Extract first few lines of changelog
            changelog_lines = remote_content.strip().splitlines()[:10]
            changelog_summary = "\n".join(changelog_lines)

            return {
                "status": "success",
                "current_version": current_ver,
                "latest_version": latest_ver,
                "current_date": current_date,
                "latest_date": latest_date,
                "has_update": has_update,
                "changelog": changelog_summary
            }
        except Exception as e:
            return {
                "status": "error",
                "current_version": current_ver,
                "has_update": False,
                "message": f"Não foi possível verificar atualizações: {str(e)}"
            }

    def perform_update(self) -> Dict[str, Any]:
        """Downloads the latest master.zip from GitHub, extracts and updates local files while preserving settings.json."""
        current_ver, _ = get_version_info()

        # Check latest version first
        check_res = self.check_for_updates()
        latest_ver = check_res.get("latest_version", current_ver)

        try:
            req = urllib.request.Request(
                REMOTE_ZIP_URL,
                headers={"User-Agent": "Watcher-Updater/1.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                zip_bytes = resp.read()

            with tempfile.TemporaryDirectory() as temp_dir:
                zip_path = os.path.join(temp_dir, "master.zip")
                with open(zip_path, "wb") as f:
                    f.write(zip_bytes)

                with zipfile.ZipFile(zip_path, "r") as z:
                    z.extractall(temp_dir)

                # Identify extracted folder (e.g. watcher-master)
                extracted_folders = [
                    os.path.join(temp_dir, d) for d in os.listdir(temp_dir)
                    if os.path.isdir(os.path.join(temp_dir, d)) and d.startswith("watcher")
                ]
                if not extracted_folders:
                    return {
                        "status": "error",
                        "message": "Estrutura de arquivo ZIP inválida baixada do GitHub."
                    }
                
                extracted_root = extracted_folders[0]
                preserved_files = {"settings.json", ".git"}

                # Copy updated files into watcher_dir
                for root, dirs, files in os.walk(extracted_root):
                    rel_path = os.path.relpath(root, extracted_root)
                    dest_dir = self.watcher_dir if rel_path == "." else os.path.join(self.watcher_dir, rel_path)

                    os.makedirs(dest_dir, exist_ok=True)

                    for file_name in files:
                        if rel_path == "." and file_name in preserved_files:
                            continue  # Keep user's local settings.json!

                        src_file = os.path.join(root, file_name)
                        dest_file = os.path.join(dest_dir, file_name)
                        shutil.copy2(src_file, dest_file)

            # Read new version after update
            import importlib
            import src.config
            importlib.reload(src.config)
            new_ver, new_date = src.config.get_version_info()

            return {
                "status": "success",
                "message": f"Watcher atualizado com sucesso para v{new_ver} ({new_date})!",
                "previous_version": current_ver,
                "new_version": new_ver,
                "new_date": new_date
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Erro durante a instalação da atualização: {str(e)}"
            }

    def _parse_version_file(self, content: str) -> Tuple[str, str]:
        latest_ver = "1.0.0"
        latest_date = "N/A"
        ver_match = re.search(r'\[v?(\d+\.\d+\.\d+)\](?:\s*-\s*([\d\/]+|\d{4}-\d{2}-\d{2}))?', content)
        if ver_match:
            latest_ver = ver_match.group(1)
            if ver_match.group(2):
                latest_date = ver_match.group(2)
        else:
            first_line = content.strip().splitlines()[0] if content else ""
            clean = re.sub(r'[^\d\.]', '', first_line)
            if clean:
                latest_ver = clean
        return latest_ver, latest_date

    def _compare_versions(self, remote_ver: str, local_ver: str) -> bool:
        """Returns True if remote_ver > local_ver."""
        def parse_tuple(v: str) -> Tuple[int, ...]:
            parts = re.findall(r'\d+', v)
            return tuple(int(p) for p in parts) if parts else (0, 0, 0)
        return parse_tuple(remote_ver) > parse_tuple(local_ver)
