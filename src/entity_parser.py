import os
import re
from typing import List, Dict, Any, Optional

class EntityParser:
    """Parses Ruby/GraphQL source files and git diff hunks to identify changed code entities."""

    def __init__(self, engine_name: str):
        self.engine_name = engine_name
        self.module_namespace = engine_name.capitalize()

    def parse_changed_files(self, diff_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Processes a list of diff files and extracts all changed entities."""
        entities = []
        parsed_files_count = 0

        for file_info in diff_files:
            file_path = file_info["file_path"]
            full_path = file_info["full_path"]
            status = file_info["status"]
            added_lines = file_info.get("added_lines", [])
            deleted_lines = file_info.get("deleted_lines", [])

            # Read full file content if file exists
            content = ""
            if os.path.exists(full_path) and status != "deleted":
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                except Exception:
                    content = ""

            file_entities = self.parse_single_file(file_path, content, added_lines, deleted_lines, status)
            if file_entities:
                entities.extend(file_entities)
                parsed_files_count += 1

        return {
            "engine": self.engine_name,
            "total_entities": len(entities),
            "entities": entities
        }

    def parse_single_file(
        self,
        file_path: str,
        content: str,
        added_lines: List[tuple],
        deleted_lines: List[tuple],
        status: str
    ) -> List[Dict[str, Any]]:
        """Parses a single file and its diff lines to extract entity definitions."""
        entities = []
        category = self._categorize_file(file_path)
        class_names = self._extract_class_names(file_path, content)

        # 1. Main Class / Module Entity
        for full_class_name in class_names:
            short_name = full_class_name.split('::')[-1]
            entities.append({
                "type": category, # model, service, builder, query, concern, etc.
                "full_name": full_class_name,
                "short_name": short_name,
                "file_path": file_path,
                "status": status,
                "engine": self.engine_name,
                "change_detail": f"{status.title()} {category} {full_class_name}"
            })

        # 2. Methods modified or deleted
        methods_added = self._extract_methods(added_lines)
        methods_deleted = self._extract_methods(deleted_lines)
        all_methods = set(methods_added + methods_deleted)

        for method in all_methods:
            is_deleted = method in methods_deleted and method not in methods_added
            is_added = method in methods_added and method not in methods_deleted
            method_status = "deleted" if is_deleted else ("added" if is_added else "modified")
            
            for full_class_name in class_names:
                entities.append({
                    "type": "method",
                    "full_name": f"{full_class_name}#{method}",
                    "parent_entity": full_class_name,
                    "short_name": method,
                    "file_path": file_path,
                    "status": method_status,
                    "engine": self.engine_name,
                    "change_detail": f"{method_status.title()} method `{method}` in `{full_class_name}`"
                })

        # 3. Associations modified/added/deleted in models/concerns
        if category in ["model", "concern"]:
            associations = self._extract_associations(added_lines, deleted_lines)
            for assoc in associations:
                for full_class_name in class_names:
                    entities.append({
                        "type": "association",
                        "full_name": f"{full_class_name}.{assoc['name']}",
                        "parent_entity": full_class_name,
                        "short_name": assoc["name"],
                        "assoc_type": assoc["assoc_type"],
                        "target_class": assoc.get("target_class"),
                        "file_path": file_path,
                        "status": assoc["status"],
                        "engine": self.engine_name,
                        "change_detail": f"{assoc['status'].title()} association `{assoc['assoc_type']} :{assoc['name']}`"
                    })

        # 4. Foreign key / schema column changes in migrations or models
        columns = self._extract_column_changes(added_lines, deleted_lines)
        for col in columns:
            entities.append({
                "type": "schema_column",
                "full_name": col["name"],
                "short_name": col["name"],
                "file_path": file_path,
                "status": col["status"],
                "engine": self.engine_name,
                "change_detail": f"{col['status'].title()} column `{col['name']}`"
            })

        return entities

    def _categorize_file(self, file_path: str) -> str:
        """Determines entity role from file path."""
        p = file_path.lower()
        if 'app/models/concerns/' in p or 'concerns/' in p:
            return 'concern'
        elif 'app/models/' in p:
            return 'model'
        elif 'app/services/' in p:
            return 'service'
        elif 'app/builders/' in p:
            return 'builder'
        elif 'app/queries/' in p:
            return 'query'
        elif 'app/graphql/' in p:
            return 'graphql'
        elif 'app/controllers/' in p:
            return 'controller'
        elif 'app/validators/' in p:
            return 'validator'
        elif 'app/jobs/' in p:
            return 'job'
        elif 'db/migrate/' in p or 'db/schema.rb' in p:
            return 'migration'
        elif 'spec/' in p:
            return 'spec'
        else:
            return 'code'

    def _extract_class_names(self, file_path: str, content: str) -> List[str]:
        """Deduces class/module names from file content and directory structure."""
        class_names = []
        if content:
            # Look for explicit module & class definitions
            modules = re.findall(r'(?:module|class)\s+([A-Z][A-Za-z0-9_:]+)', content)
            if modules:
                # Filter out standard base classes
                valid_mods = [m for m in modules if m not in ['ApplicationRecord', 'ApplicationJob', 'ApplicationController', 'StandardError', 'Base']]
                if valid_mods:
                    # Construct full namespaced name if module nesting occurs
                    main_class = valid_mods[0]
                    if '::' not in main_class:
                        # Try to prefix with engine namespace if missing
                        ns = self._get_engine_namespace()
                        if ns and not main_class.startswith(ns):
                            main_class = f"{ns}::{main_class}"
                    class_names.append(main_class)

        if not class_names:
            # Infer from file path if parsing didn't find explicit class
            # e.g., app/models/stock/batch.rb -> Stock::Batch
            parts = file_path.split('/')
            if len(parts) >= 2:
                filename = parts[-1].replace('.rb', '')
                if filename and not filename.startswith('.'):
                    camel_file = ''.join(word.title() for word in filename.split('_'))
                    ns = self._get_engine_namespace()
                    class_names.append(f"{ns}::{camel_file}")

        return list(set(class_names))

    def _get_engine_namespace(self) -> str:
        """Converts engine directory name to Ruby module name (e.g., 'stock' -> 'Stock')."""
        return ''.join(word.title() for word in self.engine_name.split('_'))

    def _extract_methods(self, lines: List[tuple]) -> List[str]:
        """Extracts def method names from diff lines."""
        methods = []
        for _, text in lines:
            m = re.search(r'def\s+(?:self\.)?([a-z0-9_!\?]+)', text.strip())
            if m:
                method_name = m.group(1)
                if method_name not in ['initialize', 'up', 'down', 'change']:
                    methods.append(method_name)
        return methods

    def _extract_associations(self, added_lines: List[tuple], deleted_lines: List[tuple]) -> List[Dict[str, Any]]:
        """Extracts ActiveRecord associations from model diff lines."""
        associations = []
        assoc_pattern = r'(has_many|belongs_to|has_one|has_and_belongs_to_many)\s+:([a-z0-9_]+)'

        added_map = {}
        for _, text in added_lines:
            m = re.search(assoc_pattern, text.strip())
            if m:
                target_cls = re.search(r"class_name:\s*['\"]([^'\"]+)['\"]", text)
                cls_val = target_cls.group(1) if target_cls else None
                added_map[m.group(2)] = (m.group(1), cls_val)

        deleted_map = {}
        for _, text in deleted_lines:
            m = re.search(assoc_pattern, text.strip())
            if m:
                target_cls = re.search(r"class_name:\s*['\"]([^'\"]+)['\"]", text)
                cls_val = target_cls.group(1) if target_cls else None
                deleted_map[m.group(2)] = (m.group(1), cls_val)

        all_names = set(list(added_map.keys()) + list(deleted_map.keys()))
        for name in all_names:
            if name in added_map and name in deleted_map:
                assoc_type, target_cls = added_map[name]
                associations.append({"name": name, "assoc_type": assoc_type, "target_class": target_cls, "status": "modified"})
            elif name in added_map:
                assoc_type, target_cls = added_map[name]
                associations.append({"name": name, "assoc_type": assoc_type, "target_class": target_cls, "status": "added"})
            else:
                assoc_type, target_cls = deleted_map[name]
                associations.append({"name": name, "assoc_type": assoc_type, "target_class": target_cls, "status": "deleted"})

        return associations

    def _extract_column_changes(self, added_lines: List[tuple], deleted_lines: List[tuple]) -> List[Dict[str, Any]]:
        """Extracts database column/field name changes."""
        cols = []
        col_pattern = r'(?:add_column|remove_column|t\.[a-z]+)\s+:([a-z0-9_]+)'
        for _, text in added_lines:
            m = re.search(col_pattern, text.strip())
            if m and m.group(1) not in ['id', 'created_at', 'updated_at']:
                cols.append({"name": m.group(1), "status": "added"})
        for _, text in deleted_lines:
            m = re.search(col_pattern, text.strip())
            if m and m.group(1) not in ['id', 'created_at', 'updated_at']:
                cols.append({"name": m.group(1), "status": "deleted"})
        return cols

if __name__ == '__main__':
    parser = EntityParser('stock')
    sample_diff = [{
        "file_path": "app/models/stock/batch.rb",
        "full_path": "/home/caetano/workspace/auriga_project/stock/app/models/stock/batch.rb",
        "status": "modified",
        "added_lines": [(10, "def reserve!(qty)")],
        "deleted_lines": [(10, "def reserve")]
    }]
    res = parser.parse_changed_files(sample_diff)
    print(f"Entities parsed: {res['total_entities']}")
    for e in res['entities']:
        print(" ", e)
