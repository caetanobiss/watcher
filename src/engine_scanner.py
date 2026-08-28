import os
import subprocess
from typing import List, Dict, Any

class EngineScanner:
    """Discovers and scans all modules/engines in the workspace parent directory."""

    def __init__(self, root_dir: str = None):
        if root_dir is None:
            # Default to parent directory of watcher workspace
            watcher_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            root_dir = os.path.dirname(watcher_dir)
        self.root_dir = os.path.abspath(root_dir)

    def discover_engines(self) -> List[Dict[str, Any]]:
        """Scans workspace for all engine subdirectories and their git/type status."""
        engines = []
        if not os.path.exists(self.root_dir):
            return engines

        for entry in sorted(os.listdir(self.root_dir)):
            full_path = os.path.join(self.root_dir, entry)
            if not os.path.isdir(full_path) or entry.startswith('.') or entry == 'watcher':
                continue

            has_git = os.path.exists(os.path.join(full_path, '.git'))
            has_app = os.path.exists(os.path.join(full_path, 'app'))
            has_frontend = os.path.exists(os.path.join(full_path, 'package.json')) or os.path.exists(os.path.join(full_path, 'src'))

            module_type = "Rails Engine" if has_app else ("Frontend" if has_frontend else "Other")

            git_info = self._get_git_info(full_path) if has_git else {
                "branch": "N/A",
                "dirty": False,
                "uncommitted_files": 0,
                "staged_files": 0,
                "last_commit": "N/A"
            }

            engines.append({
                "name": entry,
                "path": full_path,
                "type": module_type,
                "has_git": has_git,
                "git": git_info
            })

        return engines

    def _get_git_info(self, repo_path: str) -> Dict[str, Any]:
        """Fetches git branch, status, dirty files count, and last commit info."""
        try:
            # Current branch
            branch_proc = subprocess.run(
                ['git', '-C', repo_path, 'rev-parse', '--abbrev-ref', 'HEAD'],
                capture_output=True, text=True, check=False
            )
            branch = branch_proc.stdout.strip() if branch_proc.returncode == 0 else "unknown"

            # Status short
            status_proc = subprocess.run(
                ['git', '-C', repo_path, 'status', '--porcelain'],
                capture_output=True, text=True, check=False
            )
            lines = [l for l in status_proc.stdout.split('\n') if l.strip()]
            
            staged = sum(1 for l in lines if l[0] in ['M', 'A', 'D', 'R', 'C'])
            unstaged = sum(1 for l in lines if l[1] in ['M', 'D', '?'])

            # Last commit summary
            log_proc = subprocess.run(
                ['git', '-C', repo_path, 'log', '-1', '--format=%h %s (%cr)'],
                capture_output=True, text=True, check=False
            )
            last_commit = log_proc.stdout.strip() if log_proc.returncode == 0 else ""

            return {
                "branch": branch,
                "dirty": len(lines) > 0,
                "uncommitted_files": unstaged,
                "staged_files": staged,
                "total_changed": len(lines),
                "last_commit": last_commit
            }
        except Exception as e:
            return {
                "branch": "error",
                "dirty": False,
                "uncommitted_files": 0,
                "staged_files": 0,
                "last_commit": str(e)
            }

if __name__ == '__main__':
    scanner = EngineScanner()
    res = scanner.discover_engines()
    print(f"Discovered {len(res)} engines.")
    for e in res[:5]:
        print(e)
