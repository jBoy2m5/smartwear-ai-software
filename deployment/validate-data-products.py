"""Download/read a portable product and verify artifacts, arrays and MCAP counts."""
import argparse
import collections
import hashlib
import io
import json
import tempfile
import urllib.request
import zipfile
from pathlib import Path
import h5py
import numpy as np
from mcap.reader import make_reader

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url',required=True)
parser.add_argument('--output',type=Path)
args=parser.parse_args()
with urllib.request.urlopen(args.url,timeout=300) as response:
    content=response.read()
with zipfile.ZipFile(io.BytesIO(content)) as archive:
    manifest=json.loads(archive.read('episode_manifest.json'))
    checksums={}
    for line in archive.read('checksums.sha256').decode('utf-8').splitlines():
        digest,name=line.split('  ',1)
        if name in checksums:raise ValueError('Duplicate checksum entry: '+name)
        checksums[name]=digest
        if hashlib.sha256(archive.read(name)).hexdigest()!=digest:
            raise ValueError('Checksum mismatch: '+name)
    if set(checksums)!=set(archive.namelist())-{'checksums.sha256'}:
        raise ValueError('Checksum file does not cover the complete archive')
    for entry in manifest['artifacts']:
        data=archive.read(entry['path'])
        if hashlib.sha256(data).hexdigest()!=entry['sha256'] or len(data)!=entry['size_bytes']:
            raise ValueError('Artifact hash/size does not match: '+entry['path'])
    with tempfile.TemporaryDirectory() as directory:
        h5=Path(directory)/'episode.h5'
        h5.write_bytes(archive.read('arrays/episode.h5'))
        with h5py.File(h5) as dataset:
            count=len(dataset['timestamps/t_episode_ns'])
            for name in ('observations/wrist/fsr_adc','observations/wrist/imu_raw','validity/fsr','validity/imu'):
                if dataset[name].shape[0]!=count:raise ValueError('Array length mismatch')
            if np.any(np.diff(dataset['timestamps/t_episode_ns'][:])<=0):
                raise ValueError('Episode timeline must increase')
            for feature,mask in [('fsr_adc','fsr'),('imu_raw','imu')]:
                if not np.array_equal(np.isfinite(dataset['observations/wrist/'+feature][:]),dataset['validity/'+mask][:]):
                    raise ValueError('Missing-value mask mismatch: '+feature)
            if len(dataset['labels/task_step_id'])!=count or len(dataset['validity/task_label'])!=count:
                raise ValueError('Task label length mismatch')
            if len(dataset['actions']):raise ValueError('Unexpected robot actions in observation export')
    counts=collections.Counter()
    for _,channel,message in make_reader(io.BytesIO(archive.read('arrays/episode.mcap')),validate_crcs=True).iter_messages():
        counts[channel.topic]+=1
        value=json.loads(message.data)
        if not isinstance(value.get('valid'),bool) or not value.get('clock_domain'):
            raise ValueError('Missing MCAP validity/clock metadata')
        if channel.topic=='/smartwear/wrist/imu':
            observation=value['observation']
            if value['valid'] != (observation.get('acc') is not None and observation.get('gyro') is not None):
                raise ValueError('MCAP IMU validity mismatch')
    if dict(counts)!=manifest['mcap_message_counts']:raise ValueError('MCAP count mismatch')
    if manifest['robot_action_available'] or manifest['robot_policy_training_ready']:
        raise ValueError('Unexpected robot-ready claim')
report={'session_id':manifest['session_id'],'episode_id':manifest['episode_id'],
        'verified_artifacts':len(manifest['artifacts']),'frames':count,'mcap_counts':dict(counts),
        'archive_sha256':hashlib.sha256(content).hexdigest(),'archive_bytes':len(content),
        'robot_ready':False,'learner_ready':manifest['quality_state']['learner_ready'],
        'generation_elapsed_ms':manifest['generation_elapsed_ms'],'status':'validated'}
report['exporter_sha256']=manifest['exporter_sha256']
report['lineage']=manifest.get('lineage')
report['verified_checksum_entries']=len(checksums)
if args.output:
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
