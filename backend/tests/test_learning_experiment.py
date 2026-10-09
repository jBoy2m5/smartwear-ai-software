import copy
import unittest
from backend.services.learning_experiment import compare_trials


def trial(stage, end=10):
    return {'revision': 2, 'source_session_name': stage, 'reference_revision': 3,
            'context': {'role': 'worker', 'participant_id': 'learner_01', 'task_id': 'LOG_KIT',
                        'procedure_version': '1', 'reference_session_id': 'MEASURED_guide',
                        'trial_stage': stage, 'consent_confirmed': True},
            'review_status': 'approved', 'clarity_confirmed': True, 'reviewer': 'observer',
            'review_rationale': 'Checked video and product', 'outcome': 'passed',
            'prompt_count': 2, 'confirmed_error_count': 1, 'conditions_note': 'Same fixture and BOM',
            'sop_viewed_confirmed': stage == 'after_learning',
            'steps': [{'step_id': 'A1', 'start_s': 2., 'end_s': 5.},
                      {'step_id': 'A2', 'start_s': 5., 'end_s': float(end)}]}


class LearningExperimentTests(unittest.TestCase):
    def test_report_uses_reviewed_action_times_and_preserves_failed_outcome(self):
        before, after = trial('before_learning'), trial('after_learning', 8)
        before['outcome'] = 'failed'
        after['prompt_count'] = 0
        after['confirmed_error_count'] = 0
        result = compare_trials('MEASURED_before', before, 'MEASURED_after', after)
        self.assertTrue(result['evidence_ready'])
        self.assertEqual(result['before']['duration_s'], 8)
        self.assertEqual(result['deltas']['duration_reduction_pct'], 25)
        self.assertEqual(result['deltas']['error_delta'], -1)
        self.assertEqual(result['before']['outcome'], 'failed')

    def test_never_reports_improvement_with_missing_or_incompatible_evidence(self):
        for field, value in [('conditions_note','different fixture'), ('prompt_count',None),
                             ('confirmed_error_count',None), ('review_status','draft'),
                             ('sop_viewed_confirmed',False), ('reference_revision',4)]:
            with self.subTest(field=field):
                before, after = trial('before_learning'), trial('after_learning')
                after[field] = value
                result = compare_trials('MEASURED_before', before, 'MEASURED_after', after)
                self.assertFalse(result['evidence_ready'])
                self.assertIsNone(result['deltas'])
        for field in ('participant_id','task_id','procedure_version','reference_session_id'):
            before, after = trial('before_learning'), trial('after_learning')
            after['context'][field] = 'different'
            self.assertFalse(compare_trials('MEASURED_before', before, 'MEASURED_after', after)['evidence_ready'])

    def test_rejects_overlapping_and_missing_step_times(self):
        before, after = trial('before_learning'), trial('after_learning')
        after['steps'][1]['start_s'] = 4
        self.assertIsNone(compare_trials('MEASURED_before', before, 'MEASURED_after', after)['deltas'])
        after['steps'][1]['start_s'] = None
        self.assertFalse(compare_trials('MEASURED_before', before, 'MEASURED_after', after)['evidence_ready'])
