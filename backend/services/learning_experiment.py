"""Compare explicitly selected, human-reviewed before/after trials."""
def compare_trials(before_id, before, after_id, after):
    reasons = []
    if before_id == after_id:
        reasons.append('Hai lượt phải là hai phiên khác nhau.')
    for sid, value, stage in ((before_id, before, 'before_learning'), (after_id, after, 'after_learning')):
        context = value['context']
        if not sid.startswith('MEASURED_') or context.get('role') != 'worker':
            reasons.append(f'{sid}: cần phiên người học đo thật.')
        if context.get('trial_stage') != stage:
            reasons.append(f'{sid}: sai lượt trước/sau học.')
        if value.get('review_status') != 'approved' or not value.get('clarity_confirmed'):
            reasons.append(f'{sid}: chưa duyệt bằng chứng rõ hình.')
        if not context.get('consent_confirmed'):
            reasons.append(f'{sid}: thiếu xác nhận tham gia.')
        if value.get('outcome') not in ('passed', 'failed') or value.get('prompt_count') is None or value.get('confirmed_error_count') is None:
            reasons.append(f'{sid}: cần đánh giá đầu ra, số gợi ý và số lỗi; ghi 0 khi đã kiểm và không có.')
    a, b = before['context'], after['context']
    for field in ('participant_id', 'task_id', 'procedure_version', 'reference_session_id'):
        if not a.get(field) or a.get(field) != b.get(field):
            reasons.append(f'Hai lượt phải cùng {field}.')
    if not before.get('reference_revision') or before.get('reference_revision') != after.get('reference_revision'):
        reasons.append('Hai lượt phải dùng cùng bản duyệt mẫu hướng dẫn.')
    condition = before.get('conditions_note', '').strip()
    if not condition or condition != after.get('conditions_note', '').strip():
        reasons.append('Người đánh giá cần xác nhận cùng vật dụng, gá, bố trí và điều kiện trong ghi chú hai lượt.')
    if not after.get('sop_viewed_confirmed'):
        reasons.append('Chưa xác nhận người học đã xem SOP trước lượt sau.')

    def trial(sid, value):
        steps = value.get('steps', [])
        complete = bool(steps) and all(s.get('start_s') is not None and s.get('end_s') is not None
                                             and s['end_s'] > s['start_s'] for s in steps)
        if not complete:
            reasons.append(f'{sid}: thiếu mốc thao tác được duyệt.')
        elif any(x['end_s'] > y['start_s'] for x, y in zip(steps, steps[1:])):
            reasons.append(f'{sid}: mốc các bước chồng lấn hoặc sai thứ tự.')
            complete = False
        duration = round(steps[-1]['end_s']-steps[0]['start_s'], 3) if complete else None
        return {'session_id': sid, 'knowledge_revision': value.get('revision'),
                'source_session_name': value.get('source_session_name'), 'reviewer': value.get('reviewer'),
                'review_rationale': value.get('review_rationale'), 'outcome': value.get('outcome'),
                'duration_s': duration, 'prompt_count': value.get('prompt_count'),
                'confirmed_error_count': value.get('confirmed_error_count'),
                'confirmed_errors': value.get('confirmed_errors'),
                'steps': [{k: s.get(k) for k in ('step_id','start_s','end_s','keyframe')} for s in steps]}
    left, right = trial(before_id, before), trial(after_id, after)
    ready = not reasons
    deltas = None
    if ready:
        duration_delta = round(right['duration_s']-left['duration_s'], 3)
        deltas = {'duration_delta_s': duration_delta,
                  'duration_reduction_pct': round(-100*duration_delta/left['duration_s'], 2),
                  'prompt_delta': right['prompt_count']-left['prompt_count'],
                  'error_delta': right['confirmed_error_count']-left['confirmed_error_count']}
    return {'schema': 'smartwear.learning_experiment/1', 'evidence_ready': ready,
            'reasons': reasons, 'participant_id': a.get('participant_id'),
            'task_id': a.get('task_id'), 'procedure_version': a.get('procedure_version'),
            'reference_session_id': a.get('reference_session_id'),
            'reference_revision': before.get('reference_revision'), 'conditions_note': condition,
            'before': left, 'after': right, 'deltas': deltas,
            'limitations': ['Một cặp trước/sau là trường hợp thực nghiệm; việc quen bài có thể ảnh hưởng kết quả.',
                            'Thời gian lấy từ mốc thao tác đã duyệt, đầu ra và lỗi do người đánh giá xác nhận.']}
