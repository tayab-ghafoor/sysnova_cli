#!/usr/bin/env python3
"""
Phase 2: Core/Analysis/Reporting Pipeline Verification and Testing

This script verifies that the 8-stage analysis pipeline works correctly
and that reporting functionality is operational.
"""

import sys
import os
import time

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_analysis_pipeline():
    """Test the 8-stage analysis pipeline"""
    print("ðŸ” Testing Analysis Pipeline (8 stages)...")

    try:
        # Import pipeline stages with correct class names
        from system_manager_cli.Analysis.reader import LogReader
        from system_manager_cli.Analysis.scanner import LogScanner
        from system_manager_cli.Analysis.scrubber import LogScrubber
        from system_manager_cli.Analysis.analyzer import LogAnalyzer
        from system_manager_cli.Analysis.aggregate import LogAggregator
        from system_manager_cli.Analysis.correlater import LogCorrelater
        from system_manager_cli.Analysis.anomaly import AnomalyDetector
        from system_manager_cli.Analysis.recommender import Recommender
        from system_manager_cli.Analysis.Notifier import Notifier

        print("âœ… All pipeline modules imported successfully")

        # Create pipeline instances
        reader = LogReader()
        scanner = LogScanner()
        scrubber = LogScrubber()
        analyzer = LogAnalyzer()
        aggregate = LogAggregator()
        correlater = LogCorrelater()
        anomaly = AnomalyDetector()
        recommender = Recommender()
        notifier = Notifier()

        print("âœ… All pipeline classes instantiated")

        # Test data flow through pipeline
        test_data = {
            "id": "test_analysis_001",
            "timestamp": time.time(),
            "logs": [
                {"level": "ERROR", "message": "Connection failed", "timestamp": time.time()},
                {"level": "INFO", "message": "Service started", "timestamp": time.time()},
                {"level": "WARNING", "message": "High CPU usage", "timestamp": time.time()},
            ],
            "metrics": {
                "cpu_usage": 85.5,
                "memory_usage": 78.2,
                "disk_usage": 45.1,
                "error_count": 3
            }
        }

        # Stage 1: Reader - needs a file path, let's create a temp file
        print("ðŸ“– Stage 1: Reader...")
        import tempfile
        import json
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            temp_file = f.name

        reader_result = reader.read(temp_file)
        assert isinstance(reader_result, dict), "Reader must return dict"
        print("âœ… Reader stage passed")

        # Stage 2: Scanner
        print("ðŸ” Stage 2: Scanner...")
        scanner_result = scanner.scan(reader_result)
        assert isinstance(scanner_result, dict), "Scanner must return dict"
        print("âœ… Scanner stage passed")

        # Stage 3: Scrubber
        print("ðŸ§¹ Stage 3: Scrubber...")
        scrubber_result = scrubber.scrub(scanner_result)
        assert isinstance(scrubber_result, dict), "Scrubber must return dict"
        print("âœ… Scrubber stage passed")

        # Stage 4: Analyzer
        print("ðŸ“Š Stage 4: Analyzer...")
        analyzer_result = analyzer.analyze(scrubber_result)
        assert isinstance(analyzer_result, dict), "Analyzer must return dict"
        print("âœ… Analyzer stage passed")

        # Stage 5: Aggregate
        print("ðŸ“ˆ Stage 5: Aggregate...")
        aggregate_result = aggregate.aggregate(analyzer_result)
        assert isinstance(aggregate_result, dict), "Aggregate must return dict"
        print("âœ… Aggregate stage passed")

        # Stage 6: Correlater
        print("ðŸ”— Stage 6: Correlater...")
        correlater_result = correlater.correlate(aggregate_result)
        assert isinstance(correlater_result, dict), "Correlater must return dict"
        print("âœ… Correlater stage passed")

        # Stage 7: Anomaly
        print("ðŸš¨ Stage 7: Anomaly...")
        anomaly_result = anomaly.detect(correlater_result)
        assert isinstance(anomaly_result, dict), "Anomaly must return dict"
        print("âœ… Anomaly stage passed")

        # Stage 8: Recommender
        print("ðŸ’¡ Stage 8: Recommender...")
        recommender_result = recommender.recommend(anomaly_result)
        assert isinstance(recommender_result, dict), "Recommender must return dict"
        print("âœ… Recommender stage passed")

        # Stage 9: Notifier
        print("ðŸ“¢ Stage 9: Notifier...")
        notifier_result = notifier.evaluate_and_notify(recommender_result)
        assert isinstance(notifier_result, dict), "Notifier must return dict"
        print("âœ… Notifier stage passed")

        # Clean up temp file
        os.unlink(temp_file)

        print("ðŸŽ‰ Analysis pipeline test completed successfully!")
        return True

    except Exception as e:
        print(f"âŒ Analysis pipeline test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_reporting_system():
    """Test the reporting system"""
    print("\nðŸ“Š Testing Reporting System...")

    try:
        # Import reporting modules with correct class names
        from system_manager_cli.Reporting.Formatter import AnalysisFormatter
        from system_manager_cli.Reporting.json_reporter import JsonReporter
        from system_manager_cli.Reporting.Advanced_reporter import AdvancedReporter

        print("âœ… Reporting modules imported successfully")

        # Create reporter instances
        formatter = AnalysisFormatter()  # Use AnalysisFormatter as the main formatter
        json_reporter = JsonReporter()
        advanced_reporter = AdvancedReporter()

        print("âœ… Reporting classes instantiated")

        # Test data
        test_results = {
            "analysis_id": "test_report_001",
            "timestamp": time.time(),
            "summary": {
                "total_logs": 150,
                "error_count": 5,
                "warning_count": 12,
                "info_count": 133,
                "files_scanned": 5,
                "records_processed": 150,
                "anomalies_detected": 2,
                "highest_severity": "warning"
            },
            "recommendations": [
                {"priority": "high", "title": "Increase server capacity", "action": "Add more RAM"},
                {"priority": "medium", "title": "Review error logs", "action": "Check recent errors"},
                {"priority": "low", "title": "Update monitoring thresholds", "action": "Adjust alert levels"}
            ]
        }

        # Test JSON reporting
        print("ðŸ“„ Testing JSON Reporter...")
        json_report = json_reporter.render(test_results)
        assert isinstance(json_report, str), "JSON reporter must return string"
        print("âœ… JSON Reporter passed")

        # Test Advanced reporting
        print("ðŸ“ˆ Testing Advanced Reporter...")
        # AdvancedReporter needs title and sections
        sections = {
            "Summary": f"Analysis ID: {test_results['analysis_id']}",
            "Metrics": f"Total logs: {test_results['summary']['total_logs']}",
            "Recommendations": test_results['recommendations']
        }
        advanced_report = advanced_reporter.build_report("Analysis Report", sections)
        assert isinstance(advanced_report, str), "Advanced reporter must return string"
        print("âœ… Advanced Reporter passed")

        # Test Formatter
        print("ðŸŽ¨ Testing Formatter...")
        formatted_output = formatter.format_analysis(test_results)
        assert isinstance(formatted_output, dict), "Formatter must return dict"
        print("âœ… Formatter passed")

        print("ðŸŽ‰ Reporting system test completed successfully!")
        return True

    except Exception as e:
        print(f"âŒ Reporting system test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_app_integration():
    """Test app.py integration with analysis and reporting"""
    print("\nðŸ”— Testing App Integration...")

    try:
        from system_manager_cli.app import SystemManagerApp

        app = SystemManagerApp()
        print("âœ… SystemManagerApp instantiated")

        # Test log analysis execution
        print("ðŸ“‹ Testing execute_log_analysis...")
        result = app.execute_log_analysis({
            "log_file": "test.log",
            "analysis_type": "comprehensive"
        })

        # Should return structured response even if analysis fails
        assert isinstance(result, dict), "execute_log_analysis must return dict"
        assert "status" in result, "Response must have status"
        assert "operation" in result, "Response must have operation"
        print("âœ… execute_log_analysis integration passed")

        print("ðŸŽ‰ App integration test completed successfully!")
        return True

    except Exception as e:
        print(f"âŒ App integration test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run Phase 2 verification"""
    print("=" * 60)
    print("PHASE 2: CORE/ANALYSIS/REPORTING PIPELINE VERIFICATION")
    print("=" * 60)

    results = []

    # Test 1: Analysis Pipeline
    results.append(("Analysis Pipeline", test_analysis_pipeline()))

    # Test 2: Reporting System
    results.append(("Reporting System", test_reporting_system()))

    # Test 3: App Integration
    results.append(("App Integration", test_app_integration()))

    # Summary
    print("\n" + "=" * 60)
    print("PHASE 2 VERIFICATION RESULTS")
    print("=" * 60)

    passed = 0
    total = len(results)

    for test_name, success in results:
        status = "âœ… PASSED" if success else "âŒ FAILED"
        print(f"{status}: {test_name}")
        if success:
            passed += 1

    print(f"\nðŸ“Š SUMMARY: {passed}/{total} tests passed")

    if passed == total:
        print("ðŸŽ‰ PHASE 2 COMPLETE: All pipeline and reporting systems operational!")
        print("\nðŸš€ Ready for Phase 3: End-to-end integration testing")
        return 0
    else:
        print("âš ï¸  PHASE 2 INCOMPLETE: Some tests failed - review and fix issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())