import os
import subprocess
import json
import re
import shutil
from typing import List, Dict, Any, Set

from src.config import get_default_root_dir, is_db_migration_file, is_path_blacklisted
from src.dependency_graph import DependencyGraph

# Common generic words that should never be searched as un-scoped wildcards
GENERIC_STOP_WORDS = {
    'execute', 'call', 'load', 'setup', 'run', 'init', 'initialize',
    'id', 'name', 'type', 'status', 'value', 'code', 'data', 'params',
    'base', 'record', 'user', 'application', 'object', 'result'
}

class ImpactTracer:
    """Executes high-speed searches across monorepo engines to trace cross-module impacts,
    respecting Gemfile/gemspec dependencies to eliminate false positives.
    Uses Ripgrep ('rg') if installed, with seamless pure-Python fallback."""

    def __init__(self, root_dir: str = None):
        self.root_dir = get_default_root_dir(root_dir)
        self.graph = DependencyGraph(self.root_dir)

    def trace_impacts(self, source_engine: str, entities: List[Dict[str, Any]], hide_db_migrations: bool = True, impact_blacklist: list = None) -> Dict[str, Any]:
        """Traces references to all entities across modules that depend on source_engine."""
        rg_installed = shutil.which('rg') is not None
        if not entities:
            return {
                "source_engine": source_engine,
                "total_impacted_files": 0,
                "impacted_engines_count": 0,
                "engine_impacts": {},
                "rg_installed": rg_installed
            }

        source_ns = self._to_camel_case(source_engine)
        allowed_consumers = self.graph.get_consumers(source_engine)

        # Build list of patterns to search for each entity
        search_terms = set()
        entity_map = {}

        for entity in entities:
            full_name = entity.get("full_name", "")
            short_name = entity.get("short_name", "")
            etype = entity.get("type", "")

            # 1. Full namespaced entity: e.g. Stock::Batch, Stock::BatchBuilder
            if "::" in full_name:
                search_terms.add(full_name)
                entity_map[full_name] = entity

                parts = full_name.split('::')
                snake_name = '_'.join([self._to_snake_case(p) for p in parts])
                if len(snake_name) > 3 and snake_name not in GENERIC_STOP_WORDS:
                    search_terms.add(snake_name)
                    search_terms.add(f"{snake_name}_id")
                    entity_map[snake_name] = entity
                    entity_map[f"{snake_name}_id"] = entity
            elif len(short_name) >= 3 and short_name.lower() not in GENERIC_STOP_WORDS:
                ns_class = f"{source_ns}::{short_name}"
                search_terms.add(ns_class)
                entity_map[ns_class] = entity

                snake_short = self._to_snake_case(short_name)
                if len(snake_short) >= 4 and snake_short not in GENERIC_STOP_WORDS:
                    scoped_snake = f"{source_engine}_{snake_short}"
                    search_terms.add(scoped_snake)
                    search_terms.add(f"{scoped_snake}_id")
                    entity_map[scoped_snake] = entity
                    entity_map[f"{scoped_snake}_id"] = entity

            # 2. Methods or specific builders - only search if scoped or long unique method name
            if etype == "method" and len(short_name) >= 4 and short_name.lower() not in GENERIC_STOP_WORDS:
                # E.g. method name modified (only if specific)
                search_terms.add(short_name)
                entity_map[short_name] = entity

            # 3. Associations
            if etype == "association" and len(short_name) >= 4 and short_name.lower() not in GENERIC_STOP_WORDS:
                search_terms.add(short_name)
                entity_map[short_name] = entity

        if not search_terms:
            return {
                "source_engine": source_engine,
                "total_impacted_files": 0,
                "impacted_engines_count": 0,
                "engine_impacts": {},
                "rg_installed": rg_installed
            }

        # Run scan (ripgrep or fallback python scanner)
        raw_matches, actual_rg_used = self._execute_scan(search_terms, source_engine, hide_db_migrations, impact_blacklist)

        # Process and filter matches based on Gemfile dependency graph
        engine_impacts = {}
        total_impacted_files_set = set()

        for match in raw_matches:
            target_engine = match["target_engine"]
            if target_engine == source_engine or target_engine == "watcher":
                continue # Ignore self

            file_path = match["file_path"]
            if hide_db_migrations and is_db_migration_file(file_path):
                continue
            if impact_blacklist and is_path_blacklisted(file_path, impact_blacklist):
                continue

            line_text = match["line_text"]
            matched_term = match["matched_term"]

            # Filter: Check if target_engine is a declared consumer of source_engine,
            # OR if the line explicitly references the source namespace (e.g. Cooperative:: or stock_)
            has_explicit_ns = (source_ns in line_text) or (f"{source_engine}_" in line_text.lower())
            is_declared_consumer = target_engine in allowed_consumers or target_engine == f"{source_engine}-front"

            if not is_declared_consumer and not has_explicit_ns:
                continue # Skip unrelated modules that don't import this engine!

            line_num = match["line_num"]

            total_impacted_files_set.add(f"{target_engine}:{file_path}")

            if target_engine not in engine_impacts:
                engine_impacts[target_engine] = {
                    "engine": target_engine,
                    "total_matches": 0,
                    "impacted_files_count": 0,
                    "file_impacts": {},
                    "categories": {
                        "model_usage": 0,
                        "service_builder": 0,
                        "association": 0,
                        "graphql": 0,
                        "spec_test": 0,
                        "frontend": 0,
                        "other": 0
                    }
                }

            eng_data = engine_impacts[target_engine]
            eng_data["total_matches"] += 1

            category = self._categorize_match(file_path, line_text, matched_term)
            eng_data["categories"][category] += 1

            if file_path not in eng_data["file_impacts"]:
                eng_data["file_impacts"][file_path] = {
                    "file_path": file_path,
                    "target_engine": target_engine,
                    "category": category,
                    "matches": []
                }

            eng_data["file_impacts"][file_path]["matches"].append({
                "line_num": line_num,
                "line_text": line_text.strip(),
                "matched_term": matched_term,
                "category": category,
                "entity": entity_map.get(matched_term, {})
            })

        # Calculate file counts
        for eng_name, eng_data in engine_impacts.items():
            eng_data["impacted_files_count"] = len(eng_data["file_impacts"])
            eng_data["file_impacts_list"] = list(eng_data["file_impacts"].values())

        return {
            "source_engine": source_engine,
            "searched_terms": list(search_terms),
            "allowed_consumers": list(allowed_consumers),
            "total_impacted_files": len(total_impacted_files_set),
            "impacted_engines_count": len(engine_impacts),
            "engine_impacts": engine_impacts,
            "rg_installed": actual_rg_used
        }

    def _execute_scan(self, search_terms: set, source_engine: str, hide_db_migrations: bool = True, impact_blacklist: list = None) -> tuple[List[Dict[str, Any]], bool]:
        """Executes search via ripgrep if available, seamlessly falling back to Python scanner."""
        if shutil.which('rg'):
            try:
                matches = self._run_ripgrep_scan(search_terms, source_engine, hide_db_migrations, impact_blacklist)
                return matches, True
            except (FileNotFoundError, OSError):
                pass

        return self._run_python_scan(search_terms, source_engine, hide_db_migrations, impact_blacklist), False

    def _run_ripgrep_scan(self, search_terms: set, source_engine: str, hide_db_migrations: bool = True, impact_blacklist: list = None) -> List[Dict[str, Any]]:
        """Constructs and executes ripgrep command for fast pattern matching."""
        escaped_terms = [re.escape(term) for term in search_terms]
        regex_pattern = "(" + "|".join(escaped_terms) + ")"

        cmd = [
            'rg',
            '--json',
            '--line-number',
            '-e', regex_pattern,
            self.root_dir,
            '-g', f'!{source_engine}/**',
            '-g', '!watcher/**',
            '-g', '!node_modules/**',
            '-g', '!log/**',
            '-g', '!tmp/**',
            '-g', '!coverage/**',
            '-g', '!.git/**'
        ]

        if hide_db_migrations:
            cmd.extend(['-g', '!**/db/**', '-g', '!*schema.rb', '-g', '!*structure.sql'])

        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        matches = []

        if proc.returncode != 0 and not proc.stdout.strip():
            return matches

        for line in proc.stdout.split('\n'):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if data.get('type') == 'match':
                    match_data = data['data']
                    abs_path = match_data['path']['text']
                    rel_path = os.path.relpath(abs_path, self.root_dir)

                    parts = rel_path.split(os.sep)
                    target_engine = parts[0] if parts else "unknown"

                    file_rel_engine = os.sep.join(parts[1:]) if len(parts) > 1 else rel_path
                    
                    if hide_db_migrations and is_db_migration_file(file_rel_engine):
                        continue
                    if impact_blacklist and (is_path_blacklisted(file_rel_engine, impact_blacklist) or is_path_blacklisted(rel_path, impact_blacklist)):
                        continue

                    line_num = match_data['line_number']
                    line_text = match_data['lines']['text']

                    matched_term = ""
                    for term in search_terms:
                        if term in line_text:
                            matched_term = term
                            break

                    matches.append({
                        "target_engine": target_engine,
                        "file_path": file_rel_engine,
                        "abs_path": abs_path,
                        "line_num": line_num,
                        "line_text": line_text,
                        "matched_term": matched_term or list(search_terms)[0]
                    })
            except Exception:
                continue

        return matches

    def _run_python_scan(self, search_terms: set, source_engine: str, hide_db_migrations: bool = True, impact_blacklist: list = None) -> List[Dict[str, Any]]:
        """Fallback pure-Python scanner when ripgrep ('rg') executable is missing in PATH."""
        matches = []
        escaped_terms = [re.escape(term) for term in search_terms]
        pattern = re.compile("(" + "|".join(escaped_terms) + ")")

        ignored_dirs = {
            source_engine, 'watcher', 'node_modules', 'log', 'tmp',
            'coverage', '.git', '.bundle', 'dist', 'build', '.idea', '.vscode', '__pycache__'
        }
        if hide_db_migrations:
            ignored_dirs.add('db')

        ignored_exts = {
            '.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.zip', '.gz',
            '.tar', '.mp4', '.sqlite3', '.db', '.pyc', '.so', '.dylib', '.dll',
            '.woff', '.woff2', '.ttf', '.eot', '.svg', '.map'
        }

        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith('.')]

            rel_root = os.path.relpath(root, self.root_dir)
            parts = rel_root.split(os.sep) if rel_root != '.' else []

            if parts and (parts[0] in ignored_dirs or parts[0].startswith('.')):
                continue

            for file_name in files:
                ext = os.path.splitext(file_name)[1].lower()
                if ext in ignored_exts or file_name.startswith('.'):
                    continue

                abs_path = os.path.join(root, file_name)
                rel_path = os.path.relpath(abs_path, self.root_dir)
                f_parts = rel_path.split(os.sep)

                f_target_engine = f_parts[0] if len(f_parts) > 1 else "root"
                if f_target_engine == source_engine or f_target_engine == "watcher":
                    continue

                file_rel_engine = os.sep.join(f_parts[1:]) if len(f_parts) > 1 else rel_path

                if hide_db_migrations and is_db_migration_file(file_rel_engine):
                    continue
                if impact_blacklist and (is_path_blacklisted(file_rel_engine, impact_blacklist) or is_path_blacklisted(rel_path, impact_blacklist)):
                    continue

                try:
                    with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_num, line_text in enumerate(f, 1):
                            if pattern.search(line_text):
                                matched_term = ""
                                for term in search_terms:
                                    if term in line_text:
                                        matched_term = term
                                        break

                                matches.append({
                                    "target_engine": f_target_engine,
                                    "file_path": file_rel_engine,
                                    "abs_path": abs_path,
                                    "line_num": line_num,
                                    "line_text": line_text,
                                    "matched_term": matched_term or list(search_terms)[0]
                                })
                except Exception:
                    continue

        return matches

    def _categorize_match(self, file_path: str, line_text: str, matched_term: str) -> str:
        p = file_path.lower()
        if 'spec/' in p or '_spec.rb' in p or '.spec.' in p:
            return 'spec_test'
        elif p.endswith('.ts') or p.endswith('.js') or p.endswith('.vue') or p.endswith('.jsx') or p.endswith('.tsx'):
            return 'frontend'
        elif 'app/graphql/' in p or p.endswith('.gql') or p.endswith('.graphql'):
            return 'graphql'
        elif 'builder' in p or 'service' in p or 'Builder' in line_text or 'Service' in line_text:
            return 'service_builder'
        elif 'class_name:' in line_text or 'has_many' in line_text or 'belongs_to' in line_text or 'has_one' in line_text:
            return 'association'
        elif 'app/models/' in p or 'Model' in line_text:
            return 'model_usage'
        else:
            return 'other'

    def _to_snake_case(self, name: str) -> str:
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def _to_camel_case(self, name: str) -> str:
        return ''.join(word.title() for word in name.split('_'))

if __name__ == '__main__':
    tracer = ImpactTracer()
    res = tracer.trace_impacts('cooperative', [{"full_name": "Cooperative::Member", "short_name": "Member", "type": "model"}])
    print(f"Impact scan for cooperative finished: {res['total_impacted_files']} files across {res['impacted_engines_count']} engines.")
    for eng, data in res['engine_impacts'].items():
        print(f"  [{eng}] {data['impacted_files_count']} files, {data['total_matches']} matches.")
