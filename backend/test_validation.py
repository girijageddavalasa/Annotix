"""
Test script to run validation directly without starting the full server.
This tests the validation service logic.
"""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from services.validation_service import run_full_validation


def main():
    print("=" * 80)
    print("ANNOTIX SYSTEM VALIDATION / PIPELINE HEALTH CHECK")
    print("=" * 80)
    print()
    
    try:
        report = run_full_validation()
        
        print(f"Project ID: {report.project_id}")
        print(f"Timestamp: {report.timestamp}")
        print(f"Overall Status: {report.overall_status}")
        print()
        print("-" * 80)
        print()
        
        for category in report.categories:
            print(f"{category.category}: {category.status}")
            print()
            for check in category.checks:
                print(f"  [{check.status}] {check.name}")
                print(f"      {check.message}")
                if check.details:
                    print(f"      Details: {check.details}")
            if category.warnings:
                print()
                print("  Data Quality Warnings:")
                for warning in category.warnings:
                    print(f"    - {warning}")
            print()
            print("-" * 80)
            print()
        
        print("SUMMARY")
        print("-" * 80)
        for category_name, status in report.summary.items():
            print(f"{category_name}: {status}")
        print()
        
        return 0 if report.overall_status != "FAIL" else 1
        
    except Exception as e:
        print(f"ERROR: Validation failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
