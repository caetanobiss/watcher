import os
import glob
import re
from typing import List, Dict, Set, Any

from src.config import get_default_root_dir

class DependencyGraph:
    """Parses Gemfiles, gemspecs, and package.json files to build a system dependency graph."""

    def __init__(self, root_dir: str = None):
        self.root_dir = get_default_root_dir(root_dir)
        self.modules = []
        self.deps_map = {}       # module -> set of modules it depends on (direct dependencies)
        self.consumers_map = {}  # module -> set of modules that depend on it (reverse dependencies)
        self._build_graph()

    def _build_graph(self):
        """Scans all subdirectories and parses dependency declarations."""
        if not os.path.exists(self.root_dir):
            return

        self.modules = [
            d for d in os.listdir(self.root_dir)
            if os.path.isdir(os.path.join(self.root_dir, d)) and d != 'watcher' and not d.startswith('.')
        ]

        for m in self.modules:
            self.deps_map[m] = set()
            self.consumers_map[m] = set()

        for m in self.modules:
            m_path = os.path.join(self.root_dir, m)
            deps = set()

            # 1. Check Gemfile & *.gemspec for Ruby engines
            gemfile = os.path.join(m_path, 'Gemfile')
            gemspec = glob.glob(os.path.join(m_path, '*.gemspec'))

            content = ''
            if os.path.exists(gemfile):
                try:
                    with open(gemfile, 'r', encoding='utf-8', errors='ignore') as f:
                        content += f.read() + '\n'
                except Exception:
                    pass

            if gemspec:
                try:
                    with open(gemspec[0], 'r', encoding='utf-8', errors='ignore') as f:
                        content += f.read() + '\n'
                except Exception:
                    pass

            for other in self.modules:
                if other == m:
                    continue
                # Match gem 'other' or add_dependency 'other' or path: '../other'
                pattern = r"gem\s+['\"]" + re.escape(other) + r"['\"]"
                dep_pattern = r"dependency\s+['\"]" + re.escape(other) + r"['\"]"
                path_pattern = f"path: '../{other}'"
                path_pattern2 = f'path: "../{other}"'

                if re.search(pattern, content) or re.search(dep_pattern, content) or path_pattern in content or path_pattern2 in content:
                    deps.add(other)

            # 2. Check package.json for Frontend apps
            package_json = os.path.join(m_path, 'package.json')
            if os.path.exists(package_json):
                try:
                    with open(package_json, 'r', encoding='utf-8', errors='ignore') as f:
                        pkg_content = f.read()
                    for other in self.modules:
                        if other != m and (f'"{other}"' in pkg_content or f"'{other}'" in pkg_content):
                            deps.add(other)
                except Exception:
                    pass

            # 3. Conventions for frontend matching (e.g. stock-front -> stock)
            if m.endswith('-front'):
                base = m[:-6]
                if base in self.modules:
                    deps.add(base)

            self.deps_map[m] = deps

        # Build reverse consumers map
        for m, deps in self.deps_map.items():
            for dep in deps:
                if dep in self.consumers_map:
                    self.consumers_map[dep].add(m)

    def get_consumers(self, engine_name: str) -> Set[str]:
        """Returns the set of modules that consume/depend on engine_name."""
        return self.consumers_map.get(engine_name, set())

    def get_dependencies(self, engine_name: str) -> Set[str]:
        """Returns the set of modules engine_name depends on."""
        return self.deps_map.get(engine_name, set())

if __name__ == '__main__':
    graph = DependencyGraph()
    print("Consumers of cooperative:", graph.get_consumers("cooperative"))
    print("Consumers of stock:", graph.get_consumers("stock"))
