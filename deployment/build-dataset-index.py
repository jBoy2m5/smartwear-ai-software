"""Make participant-separated observation splits; refuse unreviewed/unlicensed data."""
import argparse
import hashlib
import json
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('manifests',type=Path,nargs='+')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
eligible=[];rejected=[]
for path in args.manifests:
    value=json.loads(path.read_text(encoding='utf-8'))
    context=value.get('context',{})
    reasons=[]
    if value.get('source_kind')!='measured':reasons.append('not_measured')
    if not value.get('quality_state',{}).get('learner_ready'):reasons.append('review_incomplete')
    if not context.get('participant_id') or not context.get('task_id'):reasons.append('participant_or_task_missing')
    if not context.get('consent_confirmed'):reasons.append('consent_missing')
    if value.get('license_status')!='approved_for_training':reasons.append('training_rights_missing')
    if reasons:rejected.append({'session_id':value.get('session_id'),'reasons':reasons})
    else:eligible.append({'session_id':value['session_id'],'episode_id':value['episode_id'],
                          'participant_id':context['participant_id'],'task_id':context['task_id'],
                          'manifest':str(path.resolve()),'manifest_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
people=sorted({e['participant_id'] for e in eligible},key=lambda p:hashlib.sha256(('smartwear-split-v1:'+p).encode()).hexdigest())
splits={'train':[],'validation':[],'test':[]}
if len(people)>=3:
    test_count=max(1,len(people)//5);validation_count=max(1,len(people)//5)
    owner={p:'test' if i<test_count else 'validation' if i<test_count+validation_count else 'train' for i,p in enumerate(people)}
    for entry in eligible:splits[owner[entry['participant_id']]].append(entry)
document={'schema':'smartwear.observation_dataset/1.0','purpose':'observation_and_reviewed_task_labels',
          'split_policy':'participant_group_hash_v1; no adjacent-frame split','splits':splits,
          'eligible_episodes':len(eligible),'independent_participants':len(people),'rejected':rejected,
          'status':'split_created_for_evaluation' if len(people)>=3 else 'insufficient_independent_participants',
          'representative_accuracy_established':False,'robot_policy_training_ready':False}
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(document,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'status':document['status'],'eligible':len(eligible),'participants':len(people),'rejected':len(rejected)}))
