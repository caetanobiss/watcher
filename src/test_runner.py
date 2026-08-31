import os
import subprocess
import re
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

class TestRunner:
    """Runs RSpec tests in parallel for selected Rails engines and parses execution results."""

    def __init__(self, root_dir: str = None):
        if root_dir is None:
            watcher_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            root_dir = os.path.dirname(watcher_dir)
        self.root_dir = os.path.abspath(root_dir)

    def estimate_spec_count(self, engine_name: str, cmd_args: List[str]) -> int:
        """Estimates total number of RSpec examples by scanning spec files."""
        engine_path = os.path.join(self.root_dir, engine_name)
        if not os.path.exists(engine_path):
            return 1

        spec_files = []
        for arg in cmd_args:
            p = os.path.join(engine_path, arg)
            if os.path.isfile(p):
                spec_files.append(p)
            elif os.path.isdir(p):
                for root, _, files in os.walk(p):
                    for f in files:
                        if f.endswith('_spec.rb'):
                            spec_files.append(os.path.join(root, f))
            else:
                target_spec = os.path.join(engine_path, "spec")
                if os.path.exists(target_spec):
                    for root, _, files in os.walk(target_spec):
                        for f in files:
                            if f.endswith('_spec.rb'):
                                spec_files.append(os.path.join(root, f))

        it_pattern = re.compile(r'^\s*(it|scenario|specify|its)\b')
        count = 0
        for sf in spec_files:
            try:
                with open(sf, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if it_pattern.search(line):
                            count += 1
            except Exception:
                pass
        return max(count, len(spec_files), 1)

    def run_engine_tests(self, engine_name: str, scope: str = "all", spec_files: List[str] = None) -> Dict[str, Any]:
        """
        Runs RSpec tests for a specific engine.
        scope options:
          - "impacted_only": runs specified spec_files or infers specs from impacted source files
          - "models": runs spec/models
          - "services": runs spec/services
          - "builders": runs spec/builders
          - "queries": runs spec/queries
          - "requests": runs spec/requests
          - "all": runs spec/
        """
        engine_path = os.path.join(self.root_dir, engine_name)
        if not os.path.exists(engine_path):
            return {
                "engine": engine_name,
                "status": "error",
                "message": f"Diretório da engine {engine_name} não encontrado.",
                "raw_output": "",
                "failures": []
            }

        spec_dir = os.path.join(engine_path, "spec")
        if not os.path.exists(spec_dir):
            return {
                "engine": engine_name,
                "status": "error",
                "message": f"Nenhum diretório spec/ encontrado em {engine_name}.",
                "raw_output": "",
                "failures": []
            }

        cmd_args = []

        if scope == "impacted_only" and spec_files:
            valid_specs = []
            for sf in spec_files:
                possible_paths = [sf]
                if sf.startswith("app/"):
                    possible_paths.append(re.sub(r'^app/', 'spec/', re.sub(r'\.rb$', '_spec.rb', sf)))
                elif not sf.startswith("spec/"):
                    possible_paths.append(f"spec/{sf}")
                    possible_paths.append(f"spec/{re.sub(r'\.rb$', '_spec.rb', sf)}")

                for p in possible_paths:
                    if os.path.exists(os.path.join(engine_path, p)):
                        if p not in valid_specs:
                            valid_specs.append(p)

            if valid_specs:
                cmd_args = valid_specs

        if not cmd_args:
            if scope in ["models", "services", "builders", "queries", "requests", "jobs", "validators"]:
                target_sub = os.path.join(spec_dir, scope)
                if os.path.exists(target_sub):
                    cmd_args = [f"spec/{scope}"]
                else:
                    return {
                        "engine": engine_name,
                        "status": "skipped",
                        "message": f"Diretório spec/{scope} não existe em {engine_name}.",
                        "raw_output": f"Subdiretório spec/{scope} não encontrado no módulo {engine_name}.",
                        "failures": []
                    }
            else:
                cmd_args = ["spec"]

        command = ["bundle", "exec", "rspec"] + cmd_args

        try:
            proc = subprocess.run(
                command,
                cwd=engine_path,
                capture_output=True,
                text=True,
                timeout=300
            )
            raw_output = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
            parsed = self._parse_rspec_output(raw_output, proc.returncode)
            parsed["engine"] = engine_name
            parsed["scope_used"] = " ".join(cmd_args)
            return parsed

        except subprocess.TimeoutExpired:
            return {
                "engine": engine_name,
                "status": "timeout",
                "message": "Execução excedeu o tempo limite (5 minutos).",
                "raw_output": "Timeout na execução do RSpec.",
                "failures": []
            }
        except Exception as e:
            return {
                "engine": engine_name,
                "status": "error",
                "message": str(e),
                "raw_output": str(e),
                "failures": []
            }

    def run_engine_tests_stream(self, engine_name: str, scope: str = "all", spec_files: List[str] = None, progress_callback = None) -> Dict[str, Any]:
        """
        Runs RSpec tests for a specific engine, streaming progress updates via progress_callback.
        """
        engine_path = os.path.join(self.root_dir, engine_name)
        if not os.path.exists(engine_path):
            res = {
                "engine": engine_name,
                "status": "error",
                "message": f"Diretório da engine {engine_name} não encontrado.",
                "raw_output": "",
                "failures": []
            }
            if progress_callback:
                progress_callback({"type": "engine_complete", "engine": engine_name, "result": res})
            return res

        spec_dir = os.path.join(engine_path, "spec")
        if not os.path.exists(spec_dir):
            res = {
                "engine": engine_name,
                "status": "error",
                "message": f"Nenhum diretório spec/ encontrado em {engine_name}.",
                "raw_output": "",
                "failures": []
            }
            if progress_callback:
                progress_callback({"type": "engine_complete", "engine": engine_name, "result": res})
            return res

        cmd_args = []

        if scope == "impacted_only" and spec_files:
            valid_specs = []
            for sf in spec_files:
                possible_paths = [sf]
                if sf.startswith("app/"):
                    possible_paths.append(re.sub(r'^app/', 'spec/', re.sub(r'\.rb$', '_spec.rb', sf)))
                elif not sf.startswith("spec/"):
                    possible_paths.append(f"spec/{sf}")
                    possible_paths.append(f"spec/{re.sub(r'\.rb$', '_spec.rb', sf)}")

                for p in possible_paths:
                    if os.path.exists(os.path.join(engine_path, p)):
                        if p not in valid_specs:
                            valid_specs.append(p)

            if valid_specs:
                cmd_args = valid_specs

        if not cmd_args:
            if scope in ["models", "services", "builders", "queries", "requests", "jobs", "validators"]:
                target_sub = os.path.join(spec_dir, scope)
                if os.path.exists(target_sub):
                    cmd_args = [f"spec/{scope}"]
                else:
                    res = {
                        "engine": engine_name,
                        "status": "skipped",
                        "message": f"Diretório spec/{scope} não existe em {engine_name}.",
                        "raw_output": f"Subdiretório spec/{scope} não encontrado no módulo {engine_name}.",
                        "failures": []
                    }
                    if progress_callback:
                        progress_callback({"type": "engine_complete", "engine": engine_name, "result": res})
                    return res
            else:
                cmd_args = ["spec"]

        total_specs_estimated = self.estimate_spec_count(engine_name, cmd_args)

        if progress_callback:
            progress_callback({
                "type": "start",
                "engine": engine_name,
                "total_specs": total_specs_estimated,
                "scope_used": " ".join(cmd_args)
            })

        command = ["bundle", "exec", "rspec", "--format", "documentation"] + cmd_args
        start_time = time.time()
        raw_output_lines = []
        completed = 0
        passed = 0
        failed = 0
        pending = 0
        current_spec_name = ""

        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            
            proc = subprocess.Popen(
                command,
                cwd=engine_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env
            )

            for line in proc.stdout:
                raw_output_lines.append(line)
                stripped = line.strip()
                is_completed_example = False

                if "(FAILED" in stripped:
                    is_completed_example = True
                    failed += 1
                    completed += 1
                elif "(PENDING" in stripped:
                    is_completed_example = True
                    pending += 1
                    completed += 1
                elif any(keyword in line for keyword in ["  should ", "  it ", "  scenario ", "  is expected to ", "  creates ", "  validates ", "  returns "]):
                    is_completed_example = True
                    passed += 1
                    completed += 1

                if stripped.startswith("spec/") or stripped.endswith("_spec.rb"):
                    current_spec_name = stripped
                elif stripped and len(stripped) > 3:
                    current_spec_name = stripped[:65]

                if progress_callback and (is_completed_example or len(raw_output_lines) % 4 == 0):
                    effective_total = max(total_specs_estimated, completed)
                    percent = min(99, int((completed / effective_total) * 100)) if effective_total > 0 else 0
                    elapsed = round(time.time() - start_time, 1)

                    progress_callback({
                        "type": "progress",
                        "engine": engine_name,
                        "completed": completed,
                        "total": effective_total,
                        "passed": passed,
                        "failed": failed,
                        "pending": pending,
                        "percent": percent,
                        "elapsed": elapsed,
                        "current_spec": current_spec_name,
                        "last_line": stripped[:80]
                    })

            proc.wait(timeout=300)
            raw_output = "".join(raw_output_lines)
            parsed = self._parse_rspec_output(raw_output, proc.returncode)
            parsed["engine"] = engine_name
            parsed["scope_used"] = " ".join(cmd_args)
            parsed["elapsed_seconds"] = round(time.time() - start_time, 1)

            if progress_callback:
                progress_callback({
                    "type": "progress",
                    "engine": engine_name,
                    "completed": parsed.get("total_examples", completed),
                    "total": parsed.get("total_examples", completed),
                    "passed": max(0, parsed.get("total_examples", completed) - parsed.get("failures_count", 0)),
                    "failed": parsed.get("failures_count", 0),
                    "pending": parsed.get("pending_count", 0),
                    "percent": 100,
                    "elapsed": parsed["elapsed_seconds"],
                    "current_spec": "Concluído!",
                    "last_line": "Suíte finalizada com sucesso."
                })

                progress_callback({
                    "type": "engine_complete",
                    "engine": engine_name,
                    "result": parsed
                })

            return parsed

        except subprocess.TimeoutExpired:
            res = {
                "engine": engine_name,
                "status": "timeout",
                "message": "Execução excedeu o tempo limite (5 minutos).",
                "raw_output": "".join(raw_output_lines),
                "failures": []
            }
            if progress_callback:
                progress_callback({"type": "engine_complete", "engine": engine_name, "result": res})
            return res
        except Exception as e:
            res = {
                "engine": engine_name,
                "status": "error",
                "message": str(e),
                "raw_output": str(e),
                "failures": []
            }
            if progress_callback:
                progress_callback({"type": "engine_complete", "engine": engine_name, "result": res})
            return res

    def run_parallel_tests(self, engine_requests: List[Dict[str, Any]], max_workers: int = 4) -> Dict[str, Any]:
        """Runs RSpec tests in parallel across multiple engines using ThreadPoolExecutor."""
        results = {}
        with ThreadPoolExecutor(max_workers=min(max_workers, len(engine_requests) or 1)) as executor:
            future_to_engine = {
                executor.submit(
                    self.run_engine_tests,
                    req["engine"],
                    req.get("scope", "all"),
                    req.get("spec_files")
                ): req["engine"]
                for req in engine_requests
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
                        "raw_output": str(exc),
                        "failures": []
                    }
        return results

    def run_parallel_tests_stream(self, engine_requests: List[Dict[str, Any]], progress_callback = None, max_workers: int = 4) -> Dict[str, Any]:
        """Runs RSpec tests in parallel streaming updates per engine."""
        results = {}
        with ThreadPoolExecutor(max_workers=min(max_workers, len(engine_requests) or 1)) as executor:
            future_to_engine = {
                executor.submit(
                    self.run_engine_tests_stream,
                    req["engine"],
                    req.get("scope", "all"),
                    req.get("spec_files"),
                    progress_callback
                ): req["engine"]
                for req in engine_requests
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
                        "raw_output": str(exc),
                        "failures": []
                    }
        return results

    def _parse_rspec_output(self, raw_output: str, exit_code: int) -> Dict[str, Any]:
        """Parses RSpec stdout/stderr text into structured metadata."""
        summary_match = re.search(r'(\d+)\s+examples?,\s+(\d+)\s+failures?(?:,\s+(\d+)\s+pending)?', raw_output)

        total_examples = 0
        failures_count = 0
        pending_count = 0
        duration = "N/A"

        if summary_match:
            total_examples = int(summary_match.group(1))
            failures_count = int(summary_match.group(2))
            if summary_match.group(3):
                pending_count = int(summary_match.group(3))

        duration_match = re.search(r'Finished in\s+([\d\.\s\w]+)', raw_output)
        if duration_match:
            duration = duration_match.group(1).strip()

        failures = []
        failed_lines = re.findall(r'rspec\s+(\.\/spec\/[^\s]+(?::\d+)?)\s+#\s+(.*)', raw_output)
        for spec_loc, desc in failed_lines:
            failures.append({
                "location": spec_loc,
                "description": desc
            })

        status = "passed" if exit_code == 0 and failures_count == 0 else "failed"
        if exit_code != 0 and total_examples == 0:
            status = "error"

        return {
            "status": status,
            "exit_code": exit_code,
            "total_examples": total_examples,
            "failures_count": failures_count,
            "pending_count": pending_count,
            "duration": duration,
            "failures": failures,
            "raw_output": raw_output
        }

if __name__ == '__main__':
    runner = TestRunner()
    print("Testing TestRunner with scope...")
    res = runner.run_engine_tests("stock", scope="models")
    print(f"Status: {res['status']}, Scope: {res.get('scope_used')}")
