import os
import subprocess
import json
import re
from typing import List, Dict, Any, Set

from src.config import get_default_root_dir
from src.dependency_graph import DependencyGraph

# Common generic words that should never be searched as un-scoped wildcards
GENERIC_STOP_WORDS = {
    'execute', 'call', 'load', 'setup', 'run', 'init', 'initialize',
    'id', 'name', 'type', 'status', 'value', 'code', 'data', 'params',
    'base', 'record', 'user', 'application', 'object', 'result'
}

class ImpactTracer:
    """Executes high-speed Ripgrep searches across monorepo engines to trace cross-module impacts,
    respecting Gemfile/gemspec dependencies to eliminate false positives."""

    def __init__(self, root_dir: str = None):
        self.root_dir = get_default_root_dir(root_dir)
        self.graph = DependencyGraph(self.root_dir)

    def trace_impacts(self, source_engine: str, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Traces references to all entities across modules that depend on source_engine."""
        if not entities:
            return {
                "source_engine": source_engine,
                "total_impacted_files": 0,
                "impacted_engines_count": 0,
                "engine_impacts": {}
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
                "engine_impacts": {}
            }

        # Run ripgrep scan
        raw_matches = self._run_ripgrep_scan(search_terms, source_engine)

        # Process and filter matches based on Gemfile dependency graph
        engine_impacts = {}
        total_impacted_files_set = set()

        for match in raw_matches:
            target_engine = match["target_engine"]
            if target_engine == source_engine or target_engine == "watcher":
                continue # Ignore self

            line_text = match["line_text"]
            matched_term = match["matched_term"]

            # Filter: Check if target_engine is a declared consumer of source_engine,
            # OR if the line explicitly references the source namespace (e.g. Cooperative:: or stock_)
            has_explicit_ns = (source_ns in line_text) or (f"{source_engine}_" in line_text.lower())
            is_declared_consumer = target_engine in allowed_consumers or target_engine == f"{source_engine}-front"

            if not is_declared_consumer and not has_explicit_ns:
                continue # Skip unrelated modules that don't import this engine!

            file_path = match["file_path"]
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
            "engine_impacts": engine_impacts
        }

    def _run_ripgrep_scan(self, search_terms: set, source_engine: str) -> List[Dict[str, Any]]:
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
