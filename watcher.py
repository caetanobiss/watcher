#!/usr/bin/env python3
import sys
import os
import argparse
import json

from src.engine_scanner import EngineScanner
from src.git_diff_extractor import GitDiffExtractor
from src.entity_parser import EntityParser
from src.impact_tracer import ImpactTracer
from src.risk_evaluator import RiskEvaluator
from src.server import run_server

def main():
    parser = argparse.ArgumentParser(
        description="Watcher - Multi-Engine Code Impact Analyzer for Rails Monorepos"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: server
    server_parser = subparsers.add_parser("server", help="Start interactive Web Dashboard server")
    server_parser.add_argument("--port", type=int, default=3019, help="Server port (default: 3019)")

    # Command: analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analyze cross-module code impacts for an engine")
    analyze_parser.add_argument("--engine", "-e", type=str, required=True, help="Target engine name (e.g. stock, fiscal)")
    analyze_parser.add_argument("--target", "-t", type=str, default="working", choices=["working", "staged", "branch", "last_commit"], help="Git diff target mode")
    analyze_parser.add_argument("--format", "-f", type=str, default="text", choices=["text", "json", "markdown"], help="Output format")

    # Command: engines
    engines_parser = subparsers.add_parser("engines", help="List all system modules and git status")

    # Command: update
    update_parser = subparsers.add_parser("update", help="Check and install Watcher updates automatically from GitHub master branch")
    update_parser.add_argument("--check", action="store_true", help="Only check for available updates without installing")

    args = parser.parse_args()

    if args.command == "server":
        run_server(args.port)

    elif args.command == "update":
        from src.updater import WatcherUpdater
        updater = WatcherUpdater()
        print("\n🔍 Verificando atualizações do Watcher no repositório remoto...")
        check_res = updater.check_for_updates()
        if check_res.get("status") == "error":
            print(f"❌ {check_res.get('message')}\n")
            sys.exit(1)

        curr_v = check_res.get("current_version")
        latest_v = check_res.get("latest_version")
        has_upd = check_res.get("has_update")

        if not has_upd:
            print(f"✅ O Watcher já está na versão mais recente! (v{curr_v})\n")
        else:
            print(f"🎉 Nova versão disponível: v{latest_v} (Versão atual: v{curr_v})")
            if args.check:
                print("Execute `watcher update` (sem --check) para instalar a atualização.\n")
            else:
                print("📦 Baixando e instalando a versão mais recente do GitHub...")
                upd_res = updater.perform_update()
                if upd_res.get("status") == "success":
                    print(f"✨ {upd_res.get('message')}\n")
                else:
                    print(f"❌ {upd_res.get('message')}\n")

    elif args.command == "engines":
        scanner = EngineScanner()
        engines = scanner.discover_engines()
        print(f"\nDiscovered {len(engines)} system modules:\n")
        print(f"{'Engine Name':<30} | {'Type':<15} | {'Git Status':<12} | {'Branch':<15} | {'Changed Files'}")
        print("-" * 90)
        for eng in engines:
            git = eng.get("git", {})
            status_str = "DIRTY" if git.get("dirty") else "CLEAN"
            print(f"{eng['name']:<30} | {eng['type']:<15} | {status_str:<12} | {git.get('branch', 'N/A'):<15} | {git.get('total_changed', 0)}")
        print()

    elif args.command == "analyze":
        print(f"\n🔍 Analyzing impact for engine `{args.engine}` (diff mode: `{args.target}`)...")
        
        # 1. Diff
        diff_extractor = GitDiffExtractor()
        diff_data = diff_extractor.get_engine_diff(args.engine, args.target)
        diff_files = diff_data.get("files", [])

        # 2. Entity Parsing
        parser_inst = EntityParser(args.engine)
        parsed_entities = parser_inst.parse_changed_files(diff_files)
        entities_list = parsed_entities.get("entities", [])

        # Fallback if working tree clean
        if not entities_list:
            scanner = EngineScanner()
            engine_path = os.path.join(scanner.root_dir, args.engine)
            sample_files = []
            for sub in ['app/models', 'app/services', 'app/builders']:
                p = os.path.join(engine_path, sub)
                if os.path.exists(p):
                    for root, _, files in os.walk(p):
                        for f in files:
                            if f.endswith('.rb'):
                                rel = os.path.relpath(os.path.join(root, f), engine_path)
                                sample_files.append({"file_path": rel, "full_path": os.path.join(root, f), "status": "modified"})
            parsed_entities = parser_inst.parse_changed_files(sample_files[:10])
            entities_list = parsed_entities.get("entities", [])

        # 3. Cross-Module Tracer
        tracer = ImpactTracer()
        raw_impact_report = tracer.trace_impacts(args.engine, entities_list)

        # 4. Risk Evaluator
        evaluator = RiskEvaluator()
        final_report = evaluator.evaluate_impacts(raw_impact_report, entities_list)

        if args.format == "json":
            print(json.dumps({
                "engine": args.engine,
                "target": args.target,
                "entities": entities_list,
                "report": final_report
            }, indent=2))

        elif args.format == "markdown":
            risk = final_report.get("risk_summary", {})
            engine_impacts = final_report.get("engine_impacts", {})
            print(f"# 🛡️ Watcher - Impact Analysis Report")
            print(f"- **Source Engine:** `{args.engine}`")
            print(f"- **Overall System Risk:** **{risk.get('overall_system_risk', 'LOW')}**")
            print(f"- **Entities Changed:** {len(entities_list)}")
            print(f"- **Total Impacted Files:** {final_report.get('total_impacted_files', 0)} across {final_report.get('impacted_engines_count', 0)} modules\n")
            print("## Impact Summary by Target Module")
            for eng_name, eng_data in engine_impacts.items():
                print(f"- **[{eng_name}]** {eng_data['impacted_files_count']} files ({eng_data['total_matches']} matches)")

        else:
            # Text output
            risk = final_report.get("risk_summary", {})
            engine_impacts = final_report.get("engine_impacts", {})
            print(f"\n=======================================================")
            print(f" 🛡️  AURIGA WATCHER IMPACT REPORT")
            print(f"=======================================================")
            print(f" Source Engine        : {args.engine}")
            print(f" Overall Risk Rating  : {risk.get('overall_system_risk', 'LOW')}")
            print(f" Entities Analyzed    : {len(entities_list)}")
            print(f" Impacted Files       : {final_report.get('total_impacted_files', 0)}")
            print(f" Impacted Modules     : {final_report.get('impacted_engines_count', 0)}")
            print(f"=======================================================\n")

            if not engine_impacts:
                print("No cross-module impacts found.\n")
            else:
                for eng_name, eng_data in engine_impacts.items():
                    print(f"📦 TARGET MODULE: [{eng_name.upper()}] ({eng_data['impacted_files_count']} files, {eng_data['total_matches']} matches)")
                    print("-" * 65)
                    for file_obj in eng_data.get("file_impacts_list", [])[:5]:
                        print(f"  📄 {file_obj['file_path']} [{file_obj['overall_severity']}]")
                        for match in file_obj.get("matches", [])[:2]:
                            print(f"     └─ L{match['line_num']}: {match['line_text'].strip()}")
                    print()

    else:
        parser.print_help()

if __name__ == '__main__':
    main()
