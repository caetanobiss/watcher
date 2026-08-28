import os
import subprocess
import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

class TestRunner:
    """Runs RSpec tests in parallel for selected Rails engines and parses execution results."""

    def __init__(self, root_dir: str = None):
        if root_dir is None:
            watcher_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            root_dir = os.path.dirname(watcher_dir)
        self.root_dir = os.path.abspath(root_dir)

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
