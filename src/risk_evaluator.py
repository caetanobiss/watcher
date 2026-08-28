from typing import List, Dict, Any

class RiskEvaluator:
    """Evaluates risk levels (High, Medium, Low) for cross-module code impacts."""

    def evaluate_impacts(self, impact_report: Dict[str, Any], entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Enriches the impact report with risk ratings, severity counts, and actionable summary recommendations."""
        source_engine = impact_report.get("source_engine", "unknown")
        engine_impacts = impact_report.get("engine_impacts", {})

        deleted_or_breaking_entities = {
            e.get("full_name"): e for e in entities if e.get("status") in ["deleted", "renamed"] or e.get("type") == "method" and e.get("status") == "deleted"
        }

        high_risk_count = 0
        medium_risk_count = 0
        low_risk_count = 0

        for eng_name, eng_data in engine_impacts.items():
            eng_high = 0
            eng_medium = 0
            eng_low = 0

            file_impacts = eng_data.get("file_impacts_list", [])
            for file_obj in file_impacts:
                file_path = file_obj.get("file_path", "")
                category = file_obj.get("category", "")
                matches = file_obj.get("matches", [])

                file_risk = "LOW"

                for match in matches:
                    matched_term = match.get("matched_term", "")
                    line_text = match.get("line_text", "")
                    
                    # 1. High risk if entity was deleted/renamed or method signature broke
                    if matched_term in deleted_or_breaking_entities:
                        match["severity"] = "HIGH"
                        match["risk_reason"] = f"Entity `{matched_term}` was deleted or renamed in source!"
                        file_risk = "HIGH"
                    elif category in ["model_usage", "service_builder"] and ("call(" in line_text or ".new" in line_text or "build(" in line_text):
                        match["severity"] = "HIGH"
                        match["risk_reason"] = "Direct transactional service/builder or method execution."
                        if file_risk != "HIGH":
                            file_risk = "HIGH"
                    elif category == "association" and ("class_name" in line_text or "has_many" in line_text or "belongs_to" in line_text):
                        match["severity"] = "MEDIUM"
                        match["risk_reason"] = "ActiveRecord association reference."
                        if file_risk not in ["HIGH"]:
                            file_risk = "MEDIUM"
                    elif category in ["graphql", "frontend"]:
                        match["severity"] = "MEDIUM"
                        match["risk_reason"] = "API contract / GraphQL type schema dependency."
                        if file_risk not in ["HIGH"]:
                            file_risk = "MEDIUM"
                    elif category == "spec_test":
                        match["severity"] = "LOW"
                        match["risk_reason"] = "RSpec test file coverage."
                    else:
                        match["severity"] = "LOW"
                        match["risk_reason"] = "General reference or helper code."

                file_obj["overall_severity"] = file_risk
                if file_risk == "HIGH":
                    eng_high += 1
                    high_risk_count += 1
                elif file_risk == "MEDIUM":
                    eng_medium += 1
                    medium_risk_count += 1
                else:
                    eng_low += 1
                    low_risk_count += 1

            # Engine-level overall severity rating
            eng_data["severity_summary"] = {
                "HIGH": eng_high,
                "MEDIUM": eng_medium,
                "LOW": eng_low,
                "overall": "HIGH" if eng_high > 0 else ("MEDIUM" if eng_medium > 0 else "LOW")
            }

        overall_system_risk = "HIGH" if high_risk_count > 0 else ("MEDIUM" if medium_risk_count > 0 else "LOW")

        impact_report["risk_summary"] = {
            "overall_system_risk": overall_system_risk,
            "high_risk_files": high_risk_count,
            "medium_risk_files": medium_risk_count,
            "low_risk_files": low_risk_count
        }

        return impact_report

if __name__ == '__main__':
    evaluator = RiskEvaluator()
    sample_report = {
        "source_engine": "stock",
        "engine_impacts": {
            "fiscal": {
                "file_impacts_list": [{
                    "file_path": "app/services/fiscal/invoice_service.rb",
                    "category": "service_builder",
                    "matches": [{
                        "matched_term": "Stock::Batch",
                        "line_text": "Stock::BatchBuilder.call(params)"
                    }]
                }]
            }
        }
    }
    res = evaluator.evaluate_impacts(sample_report, [])
    print("Risk evaluation:", res["risk_summary"])
