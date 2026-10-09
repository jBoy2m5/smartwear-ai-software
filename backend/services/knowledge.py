"""Versioned task/reference registry with explicit human review and provenance."""
import copy
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select
from backend.models.knowledge import KnowledgeRevision
from backend.schemas.knowledge import Procedure, SessionKnowledge, CaptureContext
from backend.services.analysis_detail import source_archive_path
from backend.core.exceptions import ResourceNotFoundError
from backend.services.episode_products import inspect_source, build_products

ROOT = Path(__file__).resolve().parents[2]


def seed_procedures():
    common = {'version': '1', 'tools': 'Bulông, long đen, đai ốc, gá/tấm lỗ và ba vùng khay; cần người hướng dẫn xác nhận vật dụng thực tế.'}
    def steps(prefix, items):
        return [{'step_id': f'{prefix}{i+1}', 'title': title, 'instruction': instruction}
                for i, (title, instruction) in enumerate(items)]
    return [
        {**common, 'task_id': 'LOG_KIT', 'department': 'LOG', 'title': 'Soạn và kiểm đủ bộ',
         'success_criteria': 'Đúng loại, đủ số lượng, đúng ô; vật không chắc chắn nằm trong vùng chờ kiểm. Bài mẫu cần được người hướng dẫn duyệt.',
         'steps': steps('A', [('Đọc phiếu và mẫu', 'Đối chiếu phiên bản phiếu với mẫu trước khi lấy.'),
                              ('Soạn từng loại', 'Lấy từng loại theo thứ tự và đặt vào ô riêng.'),
                              ('Kiểm đủ bộ', 'Đối chiếu từng ô với phiếu và mẫu đã xác nhận.'),
                              ('Tách bất thường', 'Đặt vật nghi ngờ vào vùng chờ; kiểm lại bộ trước bàn giao.')])},
        {**common, 'task_id': 'HAND_ASSEMBLY', 'department': 'Sản xuất', 'title': 'Lắp bộ bằng tay',
         'success_criteria': 'Đủ chi tiết đúng vị trí, không bắt chéo ren; gá ổn định. Không nghiệm thu mô-men/lực siết.',
         'steps': steps('B', [('Bố trí và giữ gá', 'Bố trí bộ đã kiểm và giữ gá trong vùng thao tác.'),
                              ('Đưa bulông', 'Một tay giữ gá, tay kia đưa bulông qua lỗ.'),
                              ('Đặt long đen, bắt ren', 'Đặt long đen và đai ốc đúng trục; bắt ren nhẹ bằng tay.'),
                              ('Hoàn thành và kiểm', 'Vặn bằng tay đến tiêu chí bài mẫu rồi kiểm đầu ra.')])}]


class KnowledgeService:
    def __init__(self, database, settings, session_service):
        self.database, self.settings, self.sessions = database, settings, session_service

    def latest(self, kind, key, revision=None):
        with self.database.transaction() as db:
            query = select(KnowledgeRevision).where(
                KnowledgeRevision.kind == kind, KnowledgeRevision.key == key
            )
            if revision is not None:
                query = query.where(KnowledgeRevision.revision == revision)
            row = db.scalars(query.order_by(KnowledgeRevision.revision.desc()).limit(1)).first()
            if row is None:
                raise ResourceNotFoundError(f'{kind}: {key} not found')
            return copy.deepcopy(row.document)

    def learning_trials(self):
        with self.database.transaction() as db:
            rows = db.scalars(select(KnowledgeRevision).where(KnowledgeRevision.kind == 'session')
                              .order_by(KnowledgeRevision.revision.desc())).all()
            latest = {}
            for row in rows:
                latest.setdefault(row.key, row.document)
        return [{'session_id': key, **value} for key, value in latest.items()
                if value['context']['role'] == 'worker' and value['context'].get('trial_stage') in ('before_learning', 'after_learning')]

    def learning_experiment(self, before_id, after_id):
        import hashlib
        from backend.services.learning_experiment import compare_trials
        before, after = self.latest('session', before_id), self.latest('session', after_id)
        result = compare_trials(before_id, before, after_id, after)
        evidence = []
        reference_id = before['context'].get('reference_session_id')
        reference = {}
        if reference_id and before.get('reference_revision'):
            reference = self.latest('session', reference_id, before['reference_revision'])
            if reference.get('review_status') != 'approved' or reference['context'].get('role') != 'expert':
                result['reasons'].append('Bản mẫu hướng dẫn được pin chưa duyệt hợp lệ.')
        for sid in dict.fromkeys([before_id, after_id] + ([reference_id] if reference_id else [])):
            self.sessions.get_session(sid)
            path = source_archive_path(self.settings.keyframe_dir, sid)
            if not path.is_file():
                result['reasons'].append(f'{sid}: không tìm thấy archive bằng chứng.')
                continue
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024*1024), b''):
                    digest.update(chunk)
            reviewed = before if sid == before_id else after if sid == after_id else reference
            if digest.hexdigest() != reviewed.get('source_archive_sha256'):
                result['reasons'].append(f'{sid}: archive chưa được pin hash trong bản duyệt hoặc đã thay đổi; cần người đánh giá kiểm tra.')
            evidence.append({'session_id': sid, 'archive_sha256': digest.hexdigest(),
                             'archive_bytes': path.stat().st_size,
                             'source_url': f'/api/v1/sessions/{sid}/source-data'})
        if result['reasons']:
            result['evidence_ready'] = False
            result['deltas'] = None
        result['source_evidence'] = evidence
        result['generated_at'] = datetime.now(timezone.utc).isoformat()
        return result

    def append(self, kind, key, document, expected=0):
        with self.database.transaction() as db:
            previous = db.scalars(select(KnowledgeRevision).where(
                KnowledgeRevision.kind == kind, KnowledgeRevision.key == key
            ).order_by(KnowledgeRevision.revision.desc()).limit(1)).first()
            actual = previous.revision if previous else 0
            if actual != expected:
                raise ValueError('Revision conflict: reload before editing')
            value = {**copy.deepcopy(document), 'revision': actual+1,
                     'updated_at': datetime.now(timezone.utc).isoformat()}
            db.add(KnowledgeRevision(kind=kind, key=key, revision=actual+1, document=value))
            return value

    def seed(self):
        for value in seed_procedures():
            key = value['task_id'] + ':' + value['version']
            try:
                self.latest('procedure', key)
            except ResourceNotFoundError:
                self.append('procedure', key, Procedure.model_validate(value).model_dump())

    def procedures(self):
        with self.database.transaction() as db:
            rows = db.scalars(select(KnowledgeRevision).where(KnowledgeRevision.kind == 'procedure')
                              .order_by(KnowledgeRevision.revision.desc())).all()
            latest = {}
            for row in rows:
                latest.setdefault(row.key, row.document)
            return list(latest.values())

    def references(self, task_id=None, version=None):
        with self.database.transaction() as db:
            rows = db.scalars(select(KnowledgeRevision).where(KnowledgeRevision.kind == 'session')
                              .order_by(KnowledgeRevision.revision.desc())).all()
            latest = {}
            for row in rows:
                latest.setdefault(row.key, row.document)
        return [{'session_id': key, **value} for key, value in latest.items()
                if value['review_status'] == 'approved' and value['context']['role'] == 'expert'
                and (not task_id or value['context']['task_id'] == task_id)
                and (not version or value['context']['procedure_version'] == version)]

    def capture_context(self, context):
        value = context.model_dump()
        if context.role == 'demo':
            return value
        procedure = self.latest('procedure', context.task_id + ':' + context.procedure_version)
        value['procedure_snapshot'] = procedure
        if context.role == 'worker':
            reference = self.latest('session', context.reference_session_id)
            c = reference['context']
            if (reference['review_status'] != 'approved' or c['role'] != 'expert'
                    or c['task_id'] != context.task_id or c['procedure_version'] != context.procedure_version):
                raise ValueError('Reference must be approved and match the task/version')
            path = ROOT / 'ai/generated_data/sessions' / reference['source_session_name']
            if not path.resolve().is_relative_to((ROOT / 'ai/generated_data/sessions').resolve()) or not path.is_dir():
                raise ValueError('Reference source is not available on this AI host')
            value['expert_session_path'] = str(path.resolve())
            value['reference_revision'] = reference['revision']
        return value

    def save_session(self, session_id, knowledge):
        from backend.services.episode_products import sha
        detail = self.sessions.get_session(session_id)
        data = knowledge.model_dump()
        expected_role = 'EXPERT' if knowledge.context.role == 'expert' else 'TRAINEE'
        if knowledge.context.role != 'demo' and detail.worker_type != expected_role:
            raise ValueError('Capture role does not match the ingested session')
        if knowledge.context.role != 'demo' and not session_id.startswith('MEASURED_'):
            raise ValueError('Reviewed references must use measured hardware')
        from ai.integration.backend_bridge import measured_id, demo_id
        expected_id = (measured_id if session_id.startswith('MEASURED_') else demo_id)(knowledge.source_session_name)
        if expected_id != session_id:
            raise ValueError('Source session identity does not match')
        info = inspect_source(source_archive_path(self.settings.keyframe_dir, session_id))
        archive_hash = sha(source_archive_path(self.settings.keyframe_dir, session_id))
        data['source_archive_sha256'] = archive_hash
        source_role = info.get('capture_manifest.json', {}).get('context', {})
        if source_role and any(value != data['context'].get(key) for key, value in source_role.items()):
            raise ValueError('Context does not match the recorded manifest')
        if knowledge.context.role == 'worker':
            if knowledge.reference_revision is None:
                raise ValueError('Worker requires a pinned expert review revision')
            ref = self.latest('session', knowledge.context.reference_session_id, knowledge.reference_revision)
            if (ref['review_status'] != 'approved' or ref['context']['role'] != 'expert'
                    or ref['context']['task_id'] != knowledge.context.task_id
                    or ref['context']['procedure_version'] != knowledge.context.procedure_version):
                raise ValueError('Reference revision must be approved for the same task/version')
        try:
            previous = self.latest('session', session_id)
        except ResourceNotFoundError:
            previous = None
        if previous and previous.get('source_archive_sha256') and previous['source_archive_sha256'] != archive_hash:
            raise ValueError('Reviewed source archive changed; preserve the original and create a new session')
        if previous and (CaptureContext.model_validate(previous['context']).model_dump() != data['context'] or previous['source_session_name'] != data['source_session_name']
                         or previous.get('reference_revision') != data['reference_revision']):
            raise ValueError('Capture context is immutable')
        if knowledge.context.role != 'demo':
            procedure = self.latest('procedure', knowledge.context.task_id + ':' + knowledge.context.procedure_version)
            if not knowledge.steps:
                data['steps'] = ([{**s, 'start_s': None, 'end_s': None, 'keyframe': None} for s in ref['steps']]
                                 if knowledge.context.role == 'worker' else procedure['steps'])
            if [s['step_id'] for s in data['steps']] != [s['step_id'] for s in procedure['steps']]:
                raise ValueError('Steps must match the task procedure')
        if knowledge.review_status == 'approved':
            if knowledge.outcome == 'unknown' or (knowledge.context.role == 'expert' and knowledge.outcome != 'passed'):
                raise ValueError('Approval needs a reviewed outcome; expert reference must pass the task')
            if not knowledge.reviewer.strip() or not knowledge.review_rationale.strip() or not knowledge.clarity_confirmed:
                raise ValueError('Approval requires reviewer, rationale and confirmed video clarity')
            for step in data['steps']:
                if not step['why'].strip() or step['start_s'] is None or step['end_s'] is None:
                    raise ValueError('Each approved step needs rationale and video evidence times')
                if step['end_s'] > info['duration_s'] + 0.05:
                    raise ValueError('Step time exceeds the recorded source timeline')
                if step['start_s'] < info['camera.jsonl'][0]['timestamp']/1000:
                    raise ValueError('Step time precedes the recorded source timeline')
                if step['keyframe'] and step['keyframe'] not in detail.key_frames:
                    raise ValueError('Step keyframe is not declared by this session')
            if not data['steps'] or not knowledge.context.consent_confirmed:
                raise ValueError('Approval requires steps and confirmed consent')
        return self.append('session', session_id, data, knowledge.revision)

    def products(self, session_id):
        self.sessions.get_session(session_id)
        try:
            knowledge = self.latest('session', session_id)
        except ResourceNotFoundError:
            info = inspect_source(source_archive_path(self.settings.keyframe_dir, session_id))
            # Portable technical draft for legacy data; never invent task, consent or approval.
            knowledge = {'revision': 0, 'context': {'role': info.get('session_role.json', {}).get('role', 'unknown'),
                         'task_id': None, 'procedure_version': None, 'participant_id': None,
                         'reference_session_id': None, 'consent_confirmed': False, 'purpose': 'legacy_technical_export'},
                         'steps': [], 'review_status': 'draft', 'license_status': 'unknown',
                         'retention_policy': 'local_project_review_required'}
        reference = None
        ref_id = knowledge['context']['reference_session_id']
        if ref_id:
            reference = self.latest('session', ref_id, knowledge.get('reference_revision'))
        reference_directory = None
        if reference:
            reference_directory = build_products(self.settings, ref_id, reference, None)
        return build_products(self.settings, session_id, knowledge, reference, reference_directory)
