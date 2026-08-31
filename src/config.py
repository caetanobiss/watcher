import os
import json
import re

def get_version_info():
    """Reads VERSION file to get the latest version number string and date."""
    version_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION")
    latest_ver = "1.3.1"
    latest_date = "31/08/2026"
    if os.path.exists(version_file):
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                content = f.read()
                ver_match = re.search(r'\[v?(\d+\.\d+\.\d+)\](?:\s*-\s*([\d\/]+|\d{4}-\d{2}-\d{2}))?', content)
                if ver_match:
                    latest_ver = ver_match.group(1)
                    if ver_match.group(2):
                        latest_date = ver_match.group(2)
                else:
                    first_line = content.strip().splitlines()[0]
                    clean = re.sub(r'[^\d\.]', '', first_line)
                    if clean:
                        latest_ver = clean
        except Exception:
            pass
    return latest_ver, latest_date

VERSION, LAST_UPDATE = get_version_info()

def get_default_root_dir(root_dir: str = None) -> str:
    """
    Resolves the target project root directory containing engines/modules.
    Priority:
    1. Explicit root_dir argument (if provided and valid)
    2. WATCHER_TARGET_DIR / WATCHER_PROJECT_DIR / WATCHER_ROOT_DIR env var
    3. 'project_dir' or 'target_dir' or 'root_dir' from settings.json
    4. Auto-detection of 'auriga_project' directory:
       - Parent of watcher directory (e.g. /home/caetano/workspace/auriga_project)
       - Subdirectory of parent or cwd
    5. Subdirectories of parent containing engine markers (app/, Gemfile, package.json)
    6. Fallback to parent directory of watcher workspace
    """
    if root_dir and os.path.exists(root_dir):
        return os.path.abspath(root_dir)

    # 1. Environment Variable
    for env_var in ["WATCHER_TARGET_DIR", "WATCHER_PROJECT_DIR", "WATCHER_ROOT_DIR"]:
        env_val = os.environ.get(env_var)
        if env_val and os.path.exists(env_val):
            return os.path.abspath(env_val)

    # Watcher root directory (where watcher.py lives)
    watcher_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parent_dir = os.path.dirname(watcher_dir)

    # 2. settings.json
    settings_file = os.path.join(watcher_dir, "settings.json")
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                configured = data.get("target_dir") or data.get("project_dir") or data.get("root_dir")
                if configured:
                    if not os.path.isabs(configured):
                        candidate1 = os.path.abspath(os.path.join(parent_dir, configured))
                        candidate2 = os.path.abspath(os.path.join(watcher_dir, configured))
                        if os.path.exists(candidate1):
                            return candidate1
                        elif os.path.exists(candidate2):
                            return candidate2
                    elif os.path.exists(configured):
                        return os.path.abspath(configured)
        except Exception:
            pass

    # 3. Check for 'auriga_project' specifically
    auriga_in_parent = os.path.join(parent_dir, 'auriga_project')
    if os.path.isdir(auriga_in_parent):
        return auriga_in_parent

    auriga_in_cwd = os.path.join(os.getcwd(), 'auriga_project')
    if os.path.isdir(auriga_in_cwd):
        return auriga_in_cwd

    # 4. Check if parent_dir itself directly contains engine subdirectories
    if _contains_engines(parent_dir):
        return parent_dir

    # 5. Check if any subdirectory of parent_dir contains engines
    try:
        for entry in sorted(os.listdir(parent_dir)):
            sub = os.path.join(parent_dir, entry)
            if os.path.isdir(sub) and not entry.startswith('.') and entry != 'watcher':
                if _contains_engines(sub):
                    return sub
    except Exception:
        pass

    return parent_dir

def _contains_engines(directory: str) -> bool:
    """Checks if a directory contains engine/module subdirectories."""
    if not os.path.isdir(directory):
        return False
    try:
        for entry in os.listdir(directory):
            if entry.startswith('.') or entry == 'watcher':
                continue
            full = os.path.join(directory, entry)
            if os.path.isdir(full):
                if (os.path.exists(os.path.join(full, 'app')) or
                    os.path.exists(os.path.join(full, 'Gemfile')) or
                    os.path.exists(os.path.join(full, 'package.json'))):
                    return True
    except Exception:
        pass
    return False
