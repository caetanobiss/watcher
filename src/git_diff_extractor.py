import os
import subprocess
import re
from typing import List, Dict, Any, Optional

class GitDiffExtractor:
    """Extracts and parses unified Git diffs for a given module/engine."""

    def __init__(self, root_dir: str = None):
        if root_dir is None:
            watcher_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            root_dir = os.path.dirname(watcher_dir)
        self.root_dir = os.path.abspath(root_dir)

    def get_engine_diff(self, engine_name: str, target: str = "working", base_branch: str = "master") -> Dict[str, Any]:
        """
        Extracts git diff for engine.
        target: 'working' (default: unstaged+staged vs HEAD), 'staged', 'branch' (vs base_branch), 'last_commit'
        """
        engine_path = os.path.join(self.root_dir, engine_name)
        if not os.path.exists(engine_path):
            raise ValueError(f"Engine path does not exist: {engine_path}")

        raw_diff = ""
        diff_cmd = []

        if target == "working":
            # Includes both staged and unstaged working tree changes vs HEAD
            diff_cmd = ['git', '-C', engine_path, 'diff', 'HEAD']
        elif target == "staged":
            diff_cmd = ['git', '-C', engine_path, 'diff', '--cached']
        elif target == "branch":
            diff_cmd = ['git', '-C', engine_path, 'diff', f'{base_branch}...HEAD']
        elif target == "last_commit":
            diff_cmd = ['git', '-C', engine_path, 'diff', 'HEAD~1', 'HEAD']
        else:
            diff_cmd = ['git', '-C', engine_path, 'diff', 'HEAD']

        proc = subprocess.run(diff_cmd, capture_output=True, text=True, check=False)
        raw_diff = proc.stdout

        # If `git diff HEAD` returned empty (e.g. initial repo or no HEAD), try `git diff`
        if not raw_diff.strip() and target == "working":
            proc2 = subprocess.run(['git', '-C', engine_path, 'diff'], capture_output=True, text=True, check=False)
            raw_diff = proc2.stdout

        # Also get list of untracked files if target is working
        untracked_files = []
        if target == "working":
            status_proc = subprocess.run(
                ['git', '-C', engine_path, 'status', '--porcelain'],
                capture_output=True, text=True, check=False
            )
            for line in status_proc.stdout.split('\n'):
                if line.startswith('?? '):
                    filepath = line[3:].strip()
                    untracked_files.append(filepath)

        parsed_files = self._parse_unified_diff(raw_diff, engine_path)

        # Include untracked new files as 'added'
        for ufile in untracked_files:
            full_ufile = os.path.join(engine_path, ufile)
            if os.path.isfile(full_ufile):
                try:
                    with open(full_ufile, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    added_lines = [(i+1, line) for i, line in enumerate(content.split('\n'))]
                    parsed_files.append({
                        "file_path": ufile,
                        "full_path": full_ufile,
                        "status": "added",
                        "added_lines": added_lines,
                        "deleted_lines": [],
                        "raw_diff": f"--- /dev/null\n+++ b/{ufile}\n@@ -0,0 +1,{len(added_lines)} @@\n" + "\n".join(f"+{l[1]}" for l in added_lines),
                        "untracked": True
                    })
                except Exception:
                    pass

        return {
            "engine": engine_name,
            "target": target,
            "total_changed_files": len(parsed_files),
            "files": parsed_files,
            "raw_diff": raw_diff
        }

    def _parse_unified_diff(self, diff_text: str, engine_path: str) -> List[Dict[str, Any]]:
        """Parses unified diff format into structured file objects."""
        files = []
        if not diff_text.strip():
            return files

        file_diff_blocks = re.split(r'^diff --git ', diff_text, flags=re.MULTILINE)
        for block in file_diff_blocks:
            if not block.strip():
                continue

            header_match = re.search(r'a/(\S+)\s+b/(\S+)', block)
            if not header_match:
                continue

            old_path, new_path = header_match.group(1), header_match.group(2)
            rel_path = new_path if new_path != '/dev/null' else old_path

            status = "modified"
            if old_path == '/dev/null' or "new file mode" in block:
                status = "added"
            elif new_path == '/dev/null' or "deleted file mode" in block:
                status = "deleted"
            elif old_path != new_path:
                status = "renamed"

            full_path = os.path.join(engine_path, rel_path)

            added_lines = []
            deleted_lines = []
            hunks = []

            cur_line_old = 0
            cur_line_new = 0

            for line in block.split('\n'):
                hunk_match = re.match(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
                if hunk_match:
                    cur_line_old = int(hunk_match.group(1))
                    cur_line_new = int(hunk_match.group(2))
                    hunks.append(line)
                    continue

                if line.startswith('+') and not line.startswith('+++'):
                    added_lines.append((cur_line_new, line[1:]))
                    cur_line_new += 1
                elif line.startswith('-') and not line.startswith('---'):
                    deleted_lines.append((cur_line_old, line[1:]))
                    cur_line_old += 1
                elif not line.startswith('\\') and not line.startswith('index '):
                    cur_line_old += 1
                    cur_line_new += 1

            files.append({
                "file_path": rel_path,
                "full_path": full_path,
                "status": status,
                "added_lines": added_lines,
                "deleted_lines": deleted_lines,
                "hunks": hunks,
                "raw_diff": "diff --git " + block,
                "untracked": False
            })

        return files

if __name__ == '__main__':
    extractor = GitDiffExtractor()
    res = extractor.get_engine_diff('stock', 'working')
    print(f"Diff for stock: {res['total_changed_files']} files changed.")
