import os
import subprocess
import re
import json
import time
import select
import signal
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

from src.config import get_default_root_dir

CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_cache.json")

def load_test_cache() -> Dict[str, Any]:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_test_cache(cache_data: Dict[str, Any]):
    try:
        current = load_test_cache()
        current.update(cache_data)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
    except Exception:
        pass

class TestRunner:
    """Runs RSpec tests in parallel for selected Rails engines and parses execution results."""

    def __init__(self, root_dir: str = None):
        self.root_dir = get_default_root_dir(root_dir)
        self.active_processes = {}
        self.active_fds = set()
        self.active_processes_lock = threading.Lock()
        self.is_cancelled = False

    def cancel_all_tests(self):
        """Kills all running RSpec test subprocesses and process groups immediately."""
        self.is_cancelled = True
        with self.active_processes_lock:
            for eng, proc in list(self.active_processes.items()):
                try:
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGKILL)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            self.active_processes.clear()

            for fd in list(self.active_fds):
                try:
                    os.close(fd)
                except Exception:
                    pass
            self.active_fds.clear()
        
        try:
            subprocess.run(["pkill", "-9", "-f", "rspec"], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        except Exception:
            pass

    def _resolve_scope_args(self, engine_path: str, spec_dir: str, scope: str) -> List[str]:
        """Resolves RSpec spec path arguments for a specific scope (services, models, etc.)."""
        if scope == "all" or not scope:
            return ["spec"]

        if scope in ["models", "services", "builders", "queries", "requests", "jobs", "validators"]:
            candidates = [
                os.path.join(spec_dir, scope),
                os.path.join(spec_dir, "app", scope),
                os.path.join(spec_dir, "unit", scope),
                os.path.join(spec_dir, os.path.basename(engine_path), scope)
            ]
            for cand in candidates:
                if os.path.exists(cand):
                    return [os.path.relpath(cand, engine_path)]

            # Check matching files inside spec/ directory
            singular = scope[:-1] if scope.endswith('s') else scope
            matched = []
            for root, _, files in os.walk(spec_dir):
                for f in files:
                    f_lower = f.lower()
                    if f_lower.endswith(f"_{singular}_spec.rb") or f_lower.endswith(f"_{scope}_spec.rb") or f"/{scope}/" in root:
                        matched.append(os.path.relpath(os.path.join(root, f), engine_path))

            return matched

        return ["spec"]

    def get_cached_spec_info(self, engine_name: str, scope_key: str, cmd_args: List[str]) -> Dict[str, Any]:
        """Retrieves cached total examples & last duration if available, else scans spec files."""
        cache_key = f"{engine_name}:{scope_key}"
        cache = load_test_cache()
        if cache_key in cache:
            entry = cache[cache_key]
            return {
                "total_examples": entry.get("total_examples", 100),
                "last_duration": entry.get("last_duration", 0),
                "is_cached": True
            }

        count = self.estimate_spec_count(engine_name, cmd_args)
        return {
            "total_examples": count,
            "last_duration": 0,
            "is_cached": False
        }

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

    def _resolve_impacted_specs(self, engine_path: str, spec_files: List[str]) -> List[str]:
        """
        Maps impacted source files (e.g. app/models/daily_balance.rb) to actual spec test files
        (e.g. spec/models/daily_balance_spec.rb). Never returns raw application source files.
        """
        valid_specs = []
        for sf in spec_files or []:
            possible_paths = []
            if sf.startswith("spec/") or sf.endswith("_spec.rb"):
                possible_paths.append(sf)
            elif sf.startswith("app/"):
                possible_paths.append(re.sub(r'^app/', 'spec/', re.sub(r'\.rb$', '_spec.rb', sf)))
                if sf.startswith("app/models/concerns/"):
                    possible_paths.append(re.sub(r'^app/models/concerns/', 'spec/concerns/', re.sub(r'\.rb$', '_spec.rb', sf)))
                elif sf.startswith("app/controllers/"):
                    possible_paths.append(re.sub(r'^app/controllers/', 'spec/requests/', re.sub(r'_controller\.rb$', '_request_spec.rb', sf)))
                    possible_paths.append(re.sub(r'^app/controllers/', 'spec/requests/', re.sub(r'\.rb$', '_spec.rb', sf)))
            else:
                possible_paths.append(f"spec/{re.sub(r'\.rb$', '_spec.rb', sf)}")

            for p in possible_paths:
                if (p.startswith("spec/") or p.endswith("_spec.rb")) and not p.startswith("app/"):
                    if os.path.exists(os.path.join(engine_path, p)):
                        if p not in valid_specs:
                            valid_specs.append(p)

        return valid_specs

    def run_engine_tests(self, engine_name: str, scope: str = "all", spec_files: List[str] = None) -> Dict[str, Any]:
        """
        Runs RSpec tests for a specific engine.
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

        if scope == "impacted_only":
            if spec_files:
                valid_specs = self._resolve_impacted_specs(engine_path, spec_files)
                if valid_specs:
                    cmd_args = valid_specs
                else:
                    return {
                        "engine": engine_name,
                        "status": "skipped",
                        "message": f"Nenhum arquivo _spec.rb correspondente foi encontrado em spec/ para os arquivos impactados no módulo {engine_name}.",
                        "raw_output": f"Escopo 'Apenas Impactados': Nenhum spec correspondente encontrado em spec/ para os {len(spec_files)} arquivos alterados.",
                        "failures": []
                    }
            else:
                return {
                    "engine": engine_name,
                    "status": "skipped",
                    "message": f"Nenhum arquivo impactado registrado para o módulo {engine_name}.",
                    "raw_output": "Nenhum arquivo impactado para testar neste módulo.",
                    "failures": []
                }

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
        Runs RSpec tests for a specific engine, streaming progress updates via progress_callback at native speed.
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

        if scope == "impacted_only":
            if spec_files:
                valid_specs = self._resolve_impacted_specs(engine_path, spec_files)
                if valid_specs:
                    cmd_args = valid_specs
                else:
                    res = {
                        "engine": engine_name,
                        "status": "skipped",
                        "message": f"Nenhum arquivo _spec.rb correspondente foi encontrado em spec/ para os arquivos impactados no módulo {engine_name}.",
                        "raw_output": f"Escopo 'Apenas Impactados': Nenhum spec correspondente encontrado em spec/ para os {len(spec_files)} arquivos alterados.",
                        "failures": []
                    }
                    if progress_callback:
                        progress_callback({"type": "engine_complete", "engine": engine_name, "result": res})
                    return res
            else:
                res = {
                    "engine": engine_name,
                    "status": "skipped",
                    "message": f"Nenhum arquivo impactado registrado para o módulo {engine_name}.",
                    "raw_output": "Nenhum arquivo impactado para testar neste módulo.",
                    "failures": []
                }
                if progress_callback:
                    progress_callback({"type": "engine_complete", "engine": engine_name, "result": res})
                return res

        if not cmd_args:
            cmd_args = self._resolve_scope_args(engine_path, spec_dir, scope)
            if not cmd_args:
                res = {
                    "engine": engine_name,
                    "status": "skipped",
                    "message": f"Nenhum arquivo de teste para o escopo '{scope}' foi encontrado no módulo {engine_name}.",
                    "raw_output": f"Escopo '{scope}': Nenhum subdiretório spec/{scope} ou arquivo *_spec.rb correspondente foi encontrado em {engine_name}.",
                    "failures": []
                }
                if progress_callback:
                    progress_callback({"type": "engine_complete", "engine": engine_name, "result": res})
                return res

        self.is_cancelled = False
        scope_key = scope if scope != "impacted_only" else f"impacted_{len(spec_files or [])}"
        cached_info = self.get_cached_spec_info(engine_name, scope_key, cmd_args)
        total_specs_estimated = cached_info["total_examples"]

        if progress_callback:
            progress_callback({
                "type": "start",
                "engine": engine_name,
                "total_specs": total_specs_estimated,
                "last_duration": cached_info.get("last_duration", 0),
                "is_cached": cached_info.get("is_cached", False),
                "scope_used": " ".join(cmd_args)
            })

        import pty
        master_fd, slave_fd = pty.openpty()

        command = ["bundle", "exec", "rspec", "--tty"] + cmd_args
        start_time = time.time()
        raw_chunks = []
        completed = 0
        passed = 0
        failed = 0
        pending = 0

        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["DISABLE_SPRING"] = "1"
            
            proc = subprocess.Popen(
                command,
                cwd=engine_path,
                stdin=subprocess.DEVNULL,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
                env=env,
                start_new_session=True
            )
            os.close(slave_fd)

            with self.active_processes_lock:
                self.active_processes[engine_name] = proc
                self.active_fds.add(master_fd)

            last_update_time = 0

            while True:
                if self.is_cancelled:
                    try:
                        pgid = os.getpgid(proc.pid)
                        os.killpg(pgid, signal.SIGKILL)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                    break

                try:
                    r, _, _ = select.select([master_fd], [], [], 0.05)
                    if not r:
                        if proc.poll() is not None:
                            while True:
                                r_rem, _, _ = select.select([master_fd], [], [], 0.01)
                                if not r_rem:
                                    break
                                rem_data = os.read(master_fd, 4096)
                                if not rem_data:
                                    break
                                raw_chunks.append(rem_data.decode('utf-8', errors='replace'))
                            break

                        now = time.time()
                        if progress_callback and (now - last_update_time >= 0.5):
                            last_update_time = now
                            effective_total = max(total_specs_estimated, completed)
                            percent = min(99, int((completed / effective_total) * 100)) if effective_total > 0 else 0
                            elapsed = round(now - start_time, 1)

                            all_text = "".join(raw_chunks).strip()
                            last_line = all_text.splitlines()[-1] if all_text.splitlines() else f"Inicializando RSpec em [{engine_name}]..."
                            if len(last_line) > 80:
                                last_line = last_line[:77] + "..."

                            spec_msg = (
                                f"{last_line} ({completed} executados)"
                                if not cached_info.get("is_cached")
                                else f"{last_line} ({completed}/{effective_total})"
                            )

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
                                "is_cached": cached_info.get("is_cached", False),
                                "current_spec": spec_msg
                            })
                        continue

                    data = os.read(master_fd, 1024)
                    if not data:
                        break
                    chunk = data.decode('utf-8', errors='replace')
                    raw_chunks.append(chunk)

                    has_new_spec = False
                    for ch in chunk:
                        if ch == '.':
                            passed += 1
                            completed += 1
                            has_new_spec = True
                        elif ch == 'F':
                            failed += 1
                            completed += 1
                            has_new_spec = True
                        elif ch == '*':
                            pending += 1
                            completed += 1
                            has_new_spec = True

                    now = time.time()
                    if progress_callback and (has_new_spec or completed == 0) and (now - last_update_time >= 0.08 or completed == total_specs_estimated):
                        last_update_time = now
                        effective_total = max(total_specs_estimated, completed)
                        percent = min(99, int((completed / effective_total) * 100)) if effective_total > 0 else 0
                        elapsed = round(now - start_time, 1)

                        all_text = "".join(raw_chunks).strip()
                        last_line = all_text.splitlines()[-1] if all_text.splitlines() else "Executando..."
                        if len(last_line) > 80:
                            last_line = last_line[:77] + "..."

                        spec_msg = (
                            f"{last_line} ({completed} executados)"
                            if not cached_info.get("is_cached")
                            else f"{last_line} ({completed}/{effective_total})"
                        )

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
                            "is_cached": cached_info.get("is_cached", False),
                            "current_spec": spec_msg
                        })
                except OSError:
                    break

            if self.is_cancelled:
                res = {
                    "engine": engine_name,
                    "status": "cancelled",
                    "message": "Execução cancelada pelo usuário.",
                    "raw_output": "".join(raw_chunks),
                    "failures": []
                }
                if progress_callback:
                    progress_callback({"type": "engine_complete", "engine": engine_name, "result": res})
                return res

            proc.wait(timeout=5)
            raw_output = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', "".join(raw_chunks))
            parsed = self._parse_rspec_output(raw_output, proc.returncode)
            parsed["engine"] = engine_name
            parsed["scope_used"] = " ".join(cmd_args)
            elapsed_dur = round(time.time() - start_time, 1)
            parsed["elapsed_seconds"] = elapsed_dur

            final_total = parsed.get("total_examples") or completed
            if final_total > 0:
                save_test_cache({
                    f"{engine_name}:{scope_key}": {
                        "total_examples": final_total,
                        "last_duration": elapsed_dur,
                        "last_run": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                })

            if progress_callback:
                progress_callback({
                    "type": "progress",
                    "engine": engine_name,
                    "completed": final_total,
                    "total": final_total,
                    "passed": max(0, final_total - parsed.get("failures_count", 0)),
                    "failed": parsed.get("failures_count", 0),
                    "pending": parsed.get("pending_count", 0),
                    "percent": 100,
                    "elapsed": elapsed_dur,
                    "is_cached": True,
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
                "raw_output": "".join(raw_chunks),
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
        finally:
            try:
                os.close(master_fd)
            except Exception:
                pass
            with self.active_processes_lock:
                self.active_processes.pop(engine_name, None)
                self.active_fds.discard(master_fd)

    def run_parallel_tests(self, engine_requests: List[Dict[str, Any]], max_workers: int = 4) -> Dict[str, Any]:
        """Runs RSpec tests in parallel across multiple engines using ThreadPoolExecutor."""
        self.is_cancelled = False
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
        self.is_cancelled = False
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
        message = None
        if exit_code != 0 and total_examples == 0:
            status = "error"
            message = f"Falha na execução do RSpec (Exit Code {exit_code}). Verifique a saída do terminal para detalhes do erro de inicialização ou dependências."

        return {
            "status": status,
            "exit_code": exit_code,
            "total_examples": total_examples,
            "failures_count": failures_count,
            "pending_count": pending_count,
            "duration": duration,
            "failures": failures,
            "message": message,
            "raw_output": raw_output
        }

if __name__ == '__main__':
    runner = TestRunner()
    print("Testing TestRunner with scope...")
    res = runner.run_engine_tests("stock", scope="models")
    print(f"Status: {res['status']}, Scope: {res.get('scope_used')}")
