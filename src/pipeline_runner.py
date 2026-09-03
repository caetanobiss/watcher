import os
import re
import json
import time
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

from src.config import get_default_root_dir

class PipelineRunner:
    """
    Parses bitbucket-pipelines.yml for Rails engines and executes pipeline steps
    (RSpec test suites + RuboCop code quality checks) in dev local environment.
    """

    def __init__(self, root_dir: Optional[str] = None):
        self.root_dir = get_default_root_dir(root_dir)
        self.active_processes = {}
        self.active_processes_lock = threading.Lock()
        self.is_cancelled = False

    def cancel_all_pipelines(self):
        """Kills all running pipeline processes immediately."""
        self.is_cancelled = True
        with self.active_processes_lock:
            for eng, proc in list(self.active_processes.items()):
                try:
                    proc.kill()
                except Exception:
                    pass
            self.active_processes.clear()

        try:
            subprocess.run(["pkill", "-9", "-f", "rubocop"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            subprocess.run(["pkill", "-9", "-f", "rspec"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        except Exception:
            pass

    def parse_pipeline_config(self, engine_name: str) -> Dict[str, Any]:
        """
        Parses bitbucket-pipelines.yml for the specified engine and returns structured steps.
        """
        engine_path = os.path.join(self.root_dir, engine_name)
        pipeline_file = None
        for candidate in ["bitbucket-pipelines.yml", "bitbucket-pipeline.yml", ".bitbucket-pipelines.yml"]:
            full_p = os.path.join(engine_path, candidate)
            if os.path.exists(full_p):
                pipeline_file = full_p
                break

        if not pipeline_file:
            # Fallback default pipeline steps if file not present
            return {
                "engine": engine_name,
                "has_config": False,
                "steps": [
                    {"name": "RSpec Test Suite", "command": "bundle exec rspec", "type": "rspec"},
                    {"name": "Code Quality (RuboCop)", "command": "bundle exec rubocop", "type": "rubocop"}
                ]
            }

        steps = []
        try:
            with open(pipeline_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract step blocks and scripts via regex parsing to avoid strict yaml dependency issues
            step_blocks = re.findall(r'-\s*step:\s*[\s\S]*?(?=(?:-\s*step:|\Z|definitions:))', content)

            for block in step_blocks:
                name_match = re.search(r'name:\s*(.+)', block)
                step_name = name_match.group(1).strip().strip('"\'') if name_match else "Pipeline Step"

                script_lines = re.findall(r'-\s*(.+)', block)
                valid_cmds = []
                for raw_cmd in script_lines:
                    cmd = raw_cmd.strip().strip('"\'')
                    # Ignore CI setup commands that are redundant in local dev
                    if any(cmd.startswith(skip) for skip in [
                        "gem install", "bundle install", "bundle update",
                        "rails db:test:prepare", "echo ", "export "
                    ]):
                        continue

                    # Prepend bundle exec if needed
                    if cmd.startswith("rspec ") or cmd == "rspec":
                        cmd = "bundle exec " + cmd
                    elif cmd.startswith("rubocop") and not cmd.startswith("bundle exec"):
                        cmd = "bundle exec " + cmd

                    if cmd not in valid_cmds:
                        valid_cmds.append(cmd)

                if valid_cmds:
                    step_type = "rubocop" if "rubocop" in " ".join(valid_cmds) else "rspec"
                    steps.append({
                        "name": step_name,
                        "commands": valid_cmds,
                        "type": step_type
                    })

        except Exception as e:
            print(f"Error parsing pipeline file for {engine_name}: {e}")

        if not steps:
            steps = [
                {"name": "RSpec Test Suite", "commands": ["bundle exec rspec"], "type": "rspec"},
                {"name": "Code Quality (RuboCop)", "commands": ["bundle exec rubocop"], "type": "rubocop"}
            ]

        return {
            "engine": engine_name,
            "has_config": True,
            "file_path": pipeline_file,
            "steps": steps
        }

    def run_pipeline_for_engine(self, engine_name: str, progress_callback=None) -> Dict[str, Any]:
        """
        Executes all pipeline steps (RSpec + RuboCop) for a single engine, streaming progress updates.
        """
        engine_path = os.path.join(self.root_dir, engine_name)
        if not os.path.exists(engine_path):
            res = {
                "engine": engine_name,
                "status": "error",
                "message": f"Diretório da engine {engine_name} não encontrado.",
                "step_results": []
            }
            if progress_callback:
                progress_callback({"type": "pipeline_complete", "engine": engine_name, "result": res})
            return res

        config = self.parse_pipeline_config(engine_name)
        steps = config["steps"]
        step_results = []
        overall_status = "passed"
        start_time = time.time()

        if progress_callback:
            progress_callback({
                "type": "pipeline_start",
                "engine": engine_name,
                "total_steps": len(steps),
                "steps": [s["name"] for s in steps]
            })

        for idx, step in enumerate(steps):
            if self.is_cancelled:
                break

            step_name = step["name"]
            cmds = step.get("commands", [step.get("command", "bundle exec rspec")])
            step_type = step.get("type", "rspec")

            if progress_callback:
                progress_callback({
                    "type": "step_start",
                    "engine": engine_name,
                    "step_name": step_name,
                    "step_index": idx + 1,
                    "total_steps": len(steps),
                    "step_type": step_type
                })

            step_output = []
            step_passed = True

            for cmd in cmds:
                if self.is_cancelled:
                    break

                try:
                    proc = subprocess.Popen(
                        cmd,
                        shell=True,
                        cwd=engine_path,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1
                    )

                    with self.active_processes_lock:
                        self.active_processes[engine_name] = proc

                    for line in iter(proc.stdout.readline, ''):
                        if self.is_cancelled:
                            proc.kill()
                            break
                        step_output.append(line)
                        if progress_callback and line.strip():
                            progress_callback({
                                "type": "pipeline_log",
                                "engine": engine_name,
                                "step_name": step_name,
                                "line": line.rstrip()
                            })

                    proc.stdout.close()
                    return_code = proc.wait()

                    if return_code != 0:
                        step_passed = False

                except Exception as exc:
                    step_passed = False
                    step_output.append(f"\nErro ao executar comando '{cmd}': {str(exc)}\n")

            full_output = "".join(step_output)
            step_status = "passed" if step_passed else "failed"

            if not step_passed:
                overall_status = "failed"

            parsed_info = self._parse_step_summary(step_type, full_output, step_passed)

            step_res = {
                "step_name": step_name,
                "step_type": step_type,
                "status": step_status,
                "output": full_output,
                "summary": parsed_info
            }
            step_results.append(step_res)

            if progress_callback:
                progress_callback({
                    "type": "step_complete",
                    "engine": engine_name,
                    "step_name": step_name,
                    "step_result": step_res
                })

        total_duration = round(time.time() - start_time, 1)

        result = {
            "engine": engine_name,
            "status": "cancelled" if self.is_cancelled else overall_status,
            "duration": f"{total_duration}s",
            "total_steps": len(steps),
            "step_results": step_results
        }

        if progress_callback:
            progress_callback({
                "type": "pipeline_complete",
                "engine": engine_name,
                "result": result
            })

        return result

    def run_parallel_pipelines_stream(self, engine_names: List[str], progress_callback=None, max_workers: int = 4) -> Dict[str, Any]:
        """Runs bitbucket pipeline checks in parallel for multiple engines."""
        self.is_cancelled = False
        results = {}
        with ThreadPoolExecutor(max_workers=min(max_workers, len(engine_names) or 1)) as executor:
            future_to_engine = {
                executor.submit(self.run_pipeline_for_engine, eng, progress_callback): eng
                for eng in engine_names
            }
            for future in as_completed(future_to_engine):
                eng_name = future_to_engine[future]
                try:
                    res = future.result()
                    results[eng_name] = res
                except Exception as exc:
                    results[eng_name] = {
                        "engine": eng_name,
                        "status": "error",
                        "message": str(exc),
                        "step_results": []
                    }
        return results

    def _parse_step_summary(self, step_type: str, output: str, is_passed: bool) -> Dict[str, Any]:
        """Parses output summary for RSpec or RuboCop steps."""
        if step_type == "rubocop":
            # Extract RuboCop summary line: "15 files inspected, no offenses detected" or "15 files inspected, 4 offenses detected"
            offense_match = re.search(r'(\d+)\s+files?\s+inspected,\s+([0-9\s\w]+offenses?\s+detected|no offenses detected)', output, re.IGNORECASE)
            files_count = 0
            offenses_count = 0
            if offense_match:
                files_count = int(offense_match.group(1))
                off_text = offense_match.group(2).lower()
                if "no offenses" in off_text:
                    offenses_count = 0
                else:
                    digit_match = re.search(r'(\d+)', off_text)
                    if digit_match:
                        offenses_count = int(digit_match.group(1))

            return {
                "type": "rubocop",
                "files_inspected": files_count,
                "offenses_count": offenses_count,
                "passed": is_passed
            }
        else:
            # RSpec summary parser
            summary_match = re.search(r'(\d+)\s+examples?,\s+(\d+)\s+failures?', output)
            total = 0
            failures = 0
            if summary_match:
                total = int(summary_match.group(1))
                failures = int(summary_match.group(2))

            return {
                "type": "rspec",
                "total_examples": total,
                "failures_count": failures,
                "passed": is_passed
            }
