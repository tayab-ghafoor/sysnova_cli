import shutil
import unittest
import uuid
from pathlib import Path

from system_manager_cli.logs_analysis.Analysis.aggregate import LogAggregator
from system_manager_cli.logs_analysis.Analysis.analyzer import LogAnalyzer
from system_manager_cli.logs_analysis.Analysis.anomaly import AnomalyDetector
from system_manager_cli.logs_analysis.Analysis.correlater import LogCorrelater
from system_manager_cli.logs_analysis.Analysis.reader import LogReader
from system_manager_cli.logs_analysis.Analysis.recommender import Recommender
from system_manager_cli.logs_analysis.Analysis.scanner import LogScanner
from system_manager_cli.logs_analysis.Analysis.scrubber import LogScrubber


TEST_TMP_ROOT = Path(__file__).resolve().parent / '_tmp'
TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)

APP_LOG = '''
[2026-04-22 10:00:00] INFO Service started
[2026-04-22 10:01:00] WARN Retry scheduled for worker 17 from 192.168.1.10
[2026-04-22 10:02:00] ERROR Connection refused for admin@example.com token=abc123
[2026-04-22 10:02:30] ERROR Connection refused for admin@example.com token=abc123
[2026-04-22 10:03:00] CRITICAL Payment processor unavailable
'''.strip()

WORKER_LOG = '''
[2026-04-22 10:02:10] ERROR Connection refused for admin@example.com token=abc123
[2026-04-22 10:02:40] ERROR Connection refused for admin@example.com token=abc123
[2026-04-22 10:03:10] ERROR Connection refused for admin@example.com token=abc123
[2026-04-22 10:03:40] ERROR Connection refused for admin@example.com token=abc123
[2026-04-22 10:04:00] INFO Worker recovered
'''.strip()


class AnalysisPipelineStageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TEST_TMP_ROOT / f"pipeline_{uuid.uuid4().hex}"
        self.temp_dir.mkdir(parents=True, exist_ok=False)
        (self.temp_dir / 'app.log').write_text(APP_LOG + '\n', encoding='utf-8')
        (self.temp_dir / 'worker.log').write_text(WORKER_LOG + '\n', encoding='utf-8')

        self.reader = LogReader()
        self.scanner = LogScanner()
        self.scrubber = LogScrubber()
        self.analyzer = LogAnalyzer()
        self.aggregator = LogAggregator()
        self.correlater = LogCorrelater()
        self.anomaly_detector = AnomalyDetector()
        self.recommender = Recommender()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _raw(self):
        return self.reader.read(str(self.temp_dir))

    def _scanned(self):
        return self.scanner.scan(self._raw())

    def _scrubbed(self):
        return self.scrubber.scrub(self._scanned())

    def _analyzed(self):
        return self.analyzer.analyze(self._scrubbed())

    def _aggregated(self):
        return self.aggregator.aggregate(self._analyzed())

    def _correlated(self):
        return self.correlater.correlate(self._aggregated())

    def _anomalies(self):
        return self.anomaly_detector.detect(self._correlated())

    def test_reader_reads_records_from_directory(self) -> None:
        raw_data = self._raw()

        self.assertEqual(2, len(raw_data['files']))
        self.assertEqual(10, len(raw_data['records']))
        self.assertFalse(raw_data['truncated'])

    def test_scanner_adds_source_metadata_and_levels(self) -> None:
        scanned_data = self._scanned()
        first_record = scanned_data['records'][0]

        self.assertIn('source_name', first_record)
        self.assertIn('extension', first_record)
        self.assertIn('level', first_record)
        self.assertIn('message', first_record)
        self.assertIn('ERROR', scanned_data['scan_summary']['levels_detected'])

    def test_scrubber_redacts_sensitive_data(self) -> None:
        scrubbed_data = self._scrubbed()
        joined_text = ' '.join(record['clean_text'] for record in scrubbed_data['records'])

        self.assertIn('<email>', joined_text)
        self.assertIn('<ip>', joined_text)
        self.assertIn('token=<redacted>', joined_text)

    def test_analyzer_computes_metrics_and_patterns(self) -> None:
        analyzed_data = self._analyzed()

        self.assertEqual(10, analyzed_data['metrics']['records_processed'])
        self.assertGreaterEqual(analyzed_data['metrics']['error_count'], 1)
        self.assertTrue(analyzed_data['patterns'])
        self.assertIn('error_examples', analyzed_data['samples'])

    def test_aggregator_groups_records(self) -> None:
        aggregated_data = self._aggregated()
        groups = aggregated_data['groups']

        self.assertIn('by_level', groups)
        self.assertIn('by_source', groups)
        self.assertIn('timeline', groups)
        self.assertEqual(2, len(groups['by_source']))

    def test_correlater_finds_multi_source_relationships(self) -> None:
        correlated_data = self._correlated()
        relationship_types = {item['type'] for item in correlated_data['relationships']}

        self.assertIn('multi_source_pattern', relationship_types)
        self.assertGreaterEqual(correlated_data['correlation_summary']['relationship_count'], 1)

    def test_anomaly_detector_flags_risky_patterns(self) -> None:
        anomaly_data = self._anomalies()
        anomaly_types = {item['type'] for item in anomaly_data['anomalies']}

        self.assertIn('critical_events', anomaly_types)
        self.assertIn('high_error_rate', anomaly_types)
        self.assertIn('cross_source_issue', anomaly_types)

    def test_recommender_returns_actionable_summary(self) -> None:
        recommendations = self.recommender.recommend(self._anomalies())
        titles = {item['title'] for item in recommendations['recommendations']}

        self.assertGreater(recommendations['summary']['anomalies_detected'], 0)
        self.assertIn('Investigate critical events', titles)
        self.assertIn('Reduce the error rate', titles)


if __name__ == '__main__':
    unittest.main()
