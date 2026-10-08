"""Portable, checksummed learner/observation bundles; never synthesize robot actions."""
import hashlib
import html
import io
import json
import math
import os
import shutil
import statistics
import subprocess
import tempfile
import threading
import time
import zipfile
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from backend.services.analysis_detail import analysis_directory, source_archive_path, recording_path

LOCK = threading.Lock()
EXPORT_VERSION = '1'
EXPORTER_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def remove_build_directory(path, parent):
    path, parent = Path(path).resolve(), Path(parent).resolve()
    if path.parent != parent or not (path.name.startswith('build_') or path.name == 'frame_work'):
        raise ValueError('Refusing to remove a directory outside the product build root')
    if path.exists():
        shutil.rmtree(path)


def run_ffmpeg(command, timeout):
    try:
        subprocess.run(command, check=True, timeout=timeout, capture_output=True,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError('Video export failed or timed out; source data is preserved') from exc


def verify_product(directory):
    manifest = json.loads((directory/'episode_manifest.json').read_text(encoding='utf-8'))
    for item in manifest['artifacts']:
        path = (directory/item['path']).resolve()
        if (not path.is_relative_to(directory.resolve()) or not path.is_file()
                or path.stat().st_size != item['size_bytes'] or sha(path) != item['sha256']):
            raise ValueError('Product artifact is missing or has changed: ' + item['path'])
    return manifest


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def source_documents(path):
    if not path.is_file():
        raise ValueError('Source archive has not been published')
    with zipfile.ZipFile(path) as archive:
        result = {'raw_jpeg_in_archive': 'camera_raw.mjpeg' in archive.namelist()}
        for name in ('camera.jsonl', 'camera_packets.jsonl', 'wrist_raw.jsonl', 'real_sensors.jsonl',
                     'real_sensors.meta.json', 'hardware_capture.json', 'action_segments.json',
                     'capture_manifest.json', 'camera.video.json', 'analysis_result.json', 'session_role.json'):
            if name in archive.namelist():
                text = archive.read(name).decode('utf-8')
                result[name] = ([json.loads(line) for line in text.splitlines() if line.strip()]
                                if name.endswith('.jsonl') else json.loads(text))
    return result


def inspect_source(path):
    docs = source_documents(path)
    frames = docs.get('camera.jsonl', [])
    if not frames:
        raise ValueError('Source archive has no camera observations')
    timestamps = [frame['timestamp'] for frame in frames]
    if any(b <= a for a, b in zip(timestamps, timestamps[1:])):
        raise ValueError('Camera timeline must increase')
    return {**docs, 'duration_s': timestamps[-1]/1000, 'frame_count': len(frames)}


def quality(info):
    capture = info.get('hardware_capture.json', {})
    aligned = info.get('real_sensors.meta.json', {})
    wrist = info.get('wrist_raw.jsonl', [])
    frames = info['camera.jsonl']
    n = len(frames)
    ranges = []
    for i in range(4):
        values = [row['force'][i] for row in wrist if isinstance(row.get('force'), list)]
        ranges.append({'channel': i, 'gpio': [32,33,34,35][i], 'side': 'right',
                       'min': min(values) if values else None, 'max': max(values) if values else None,
                       'std': statistics.pstdev(values) if values else None,
                       'flatline': len(set(values)) <= 1 if values else None,
                       'saturation_fraction': sum(v in (0,4095) for v in values)/len(values) if values else None,
                       'unit': 'adc_count', 'calibrated': False, 'source_kind': 'measured' if wrist else 'missing'})
    intervals = [b['t_ms']-a['t_ms'] for a,b in zip(wrist,wrist[1:])]
    gaps = sum(max(0,b['seq']-a['seq']-1) for a,b in zip(wrist,wrist[1:]))
    expected = len(wrist)+gaps
    rate = (1000*(len(wrist)-1)/(wrist[-1]['t_ms']-wrist[0]['t_ms'])
            if len(wrist)>1 and wrist[-1]['t_ms']>wrist[0]['t_ms'] else None)
    imu_count = sum(r.get('acc') is not None and r.get('gyro') is not None for r in wrist)
    tracking = {side: {status: sum(f.get('hand_actions', {}).get(side, {}).get('tracking_status')==status for f in frames)
                       for status in ('detected','missing','ambiguous')} for side in ('left','right')}
    scores = [h.get('handedness_score') for f in frames for h in f.get('hands', [])
              if isinstance(h.get('handedness_score'), (int,float))]
    video = frames[0]['camera']
    fps = capture.get('average_received_fps')
    if fps is None and info['duration_s']>0:
        fps=(n-1)/info['duration_s']
    warnings = ['FSR chưa hiệu chuẩn Newton', 'Vị trí tay chỉ là tọa độ ảnh; chưa hiệu chuẩn mm',
                'Clock offset/drift chưa đo độc lập', 'Không có robot action/teleoperation']
    if not imu_count:
        warnings.append('IMU SmartWrist không có dữ liệu')
    if video['frame_width']<800 or video['frame_height']<480 or fps is None or fps<30:
        warnings.append('Camera chưa đạt WVGA/720p @30 FPS')
    if any(r['flatline'] for r in ranges):
        warnings.append('Có kênh FSR đứng giá trị; cần kiểm tra riêng')
    return {'schema_version':'smartwear.quality/1.0', 'camera':{**video,'fps_measured':fps},
            'target_checks': {'video_WVGA_30fps': 'pass' if video['frame_width']>=800 and video['frame_height']>=480 and fps is not None and fps>=30 else 'fail',
                              'wrist_50hz': 'pass' if rate is not None and rate>=50 else 'fail' if rate is not None else 'unknown',
                              'clock_offset_below_2ms':'unknown','spatial_below_2mm':'unknown',
                              'fsr_newton_calibration':'missing','robot_actions':'missing'},
            'wrist':{'samples':len(wrist),'device_rate_hz':rate,'receive_rate_hz':capture.get('average_wrist_hz'),
                     'seq_gaps':gaps,'expected_samples':expected,'gap_fraction':gaps/expected if expected else None,
                     'interval_min_ms':min(intervals) if intervals else None,
                     'interval_max_ms':max(intervals) if intervals else None,
                     'interval_std_ms':statistics.pstdev(intervals) if intervals else None,
                     'imu_available_samples':imu_count,'fsr':ranges},
            'alignment':{**aligned,'coverage':aligned.get('matched_count',0)/n},
            'tracking':tracking, 'handedness_score_mean':statistics.fmean(scores) if scores else None,
            'handedness_ground_truth_status':'unknown', 'clock_accuracy_status':'unknown',
            'warnings':warnings, 'calibrated':False,'robot_ready':False}


def arrays(info, path, steps=None, labels_reviewed=False):
    import numpy as np
    import h5py
    frames=info['camera.jsonl']
    sensors=info.get('real_sensors.jsonl', [])
    if len(sensors)!=len(frames):
        raise ValueError('Aligned sensor/frame counts differ')
    n=len(frames)
    landmarks=np.full((n,2,21,3),np.nan,dtype=np.float32)
    hands_valid=np.zeros((n,2),dtype=bool)
    confidence=np.full((n,2),np.nan,dtype=np.float32)
    adc=np.full((n,4),np.nan,dtype=np.float32)
    imu=np.full((n,6),np.nan,dtype=np.float32)
    seq=np.full(n,-1,dtype=np.int64)
    delta=np.full(n,np.nan,dtype=np.float64)
    for i,(frame,sensor) in enumerate(zip(frames,sensors)):
        for side_index,side in enumerate(('left','right')):
            action=frame.get('hand_actions',{}).get(side,{})
            if action.get('tracking_status')=='detected':
                hand=next((h for h in frame['hands'] if h['hand_index']==action['hand_index']),None)
                if hand:
                    landmarks[i,side_index]=[[p['x'],p['y'],p['z']] for p in sorted(hand['landmarks'],key=lambda p:p['id'])]
                    hands_valid[i,side_index]=True
                    if hand.get('handedness_score') is not None:
                        confidence[i,side_index]=hand['handedness_score']
        right=sensor['hand_sensors']['right']
        if right.get('force_adc') is not None:
            adc[i]=right['force_adc'];seq[i]=right['source_seq'];delta[i]=right['alignment_offset_ms']*1_000_000
        if right.get('imu_wrist') is not None:
            imu[i]=[right['imu_wrist'][a] for a in ('ax','ay','az','gx','gy','gz')]
    packets={p['seq']:p for p in info.get('camera_packets.jsonl',[])}
    host=[packets.get(f.get('source_frame_seq'),{}).get('received_monotonic_ns') for f in frames]
    monotonic=all(isinstance(t,int) for t in host)
    times=np.array([t-host[0] for t in host] if monotonic else [f['timestamp']*1_000_000 for f in frames],dtype=np.int64)
    clock='recorder_receive_monotonic' if monotonic else 'legacy_camera_device_relative'
    with h5py.File(path,'w') as output:
        output.attrs['schema']='smartwear.observation/1.0'
        output.attrs['timebase']=clock
        output.attrs['robot_action_available']=False
        output.attrs['imu_units']='firmware_g_and_deg_s_unverified; no SI conversion'
        output.attrs['landmark_units']='normalized_image_xy; model_relative_z_not_metric'
        output.attrs['fsr_units']='adc_count'
        for name,data in {'timestamps/t_episode_ns':times,'timestamps/camera_relative_ns':np.array([f['timestamp']*1_000_000 for f in frames]),
                          'timestamps/camera_device_epoch_ms':np.array([f.get('source_epoch_ms',-1) for f in frames]),
                          'timestamps/camera_receive_epoch_ms':np.array([f.get('received_epoch_ms',-1) for f in frames]),
                          'timestamps/alignment_delta_ns':delta,'observations/hand/landmarks':landmarks,
                          'observations/hand/handedness_score':confidence,'observations/wrist/fsr_adc':adc,
                          'observations/wrist/imu_raw':imu,'observations/wrist/seq':seq,
                          'validity/hand':hands_valid,'validity/fsr':np.isfinite(adc),'validity/imu':np.isfinite(imu)}.items():
            output.create_dataset(name,data=data,compression='gzip')
        output.create_group('actions').attrs['status']='unavailable; no robot commands recorded'
        task_labels=[]
        for f in frames:
            matches=[s['step_id'] for s in (steps or []) if s.get('start_s') is not None
                     and s['start_s']<=f['timestamp']/1000<s['end_s']]
            task_labels.append(matches[0] if len(matches)==1 else '')
        output.create_dataset('labels/task_step_id',data=np.array(task_labels,dtype='S64'),compression='gzip')
        output['labels'].attrs['source_kind']='human_label'
        output['labels'].attrs['review_status']='approved' if labels_reviewed else 'draft'
        output['labels'].attrs['timebase']='camera_device_relative_seconds'
        output.create_dataset('validity/task_label',data=np.array([labels_reviewed and bool(label) for label in task_labels]),compression='gzip')
    with h5py.File(path,'r') as reader:
        if not np.array_equal(reader['timestamps/t_episode_ns'][:],times) or reader['observations/hand/landmarks'].shape[0]!=n:
            raise ValueError('HDF5 round-trip validation failed')
        if not np.array_equal(reader['validity/fsr'][:],np.isfinite(adc)):
            raise ValueError('HDF5 validity round-trip failed')
    return clock


def encode_video(info, directory, annotated=False):
    """Preserve source frame durations instead of trusting AVI's encoding FPS."""
    with ExitStack() as resources:
        return _encode_video(info, directory, annotated, resources)


def _encode_video(info, directory, annotated, resources):
    import imageio_ffmpeg
    frames=info['camera.jsonl']
    with zipfile.ZipFile(directory/'raw/ai_source_data.zip') as archive:
        raw=archive.read('camera_raw.mjpeg') if 'camera_raw.mjpeg' in archive.namelist() else None
    capture=None
    if raw is None:
        import cv2
        capture=cv2.VideoCapture(str(directory/'raw/camera.avi'))
        resources.callback(capture.release)
        if not capture.isOpened():
            capture.release()
            return None
    packets={p['seq']:p for p in info.get('camera_packets.jsonl',[])}
    images=directory/'frame_work'
    images.mkdir()
    resources.callback(remove_build_directory, images, directory)
    lines=[]
    trails={'left':[],'right':[]}
    for i,f in enumerate(frames):
        jpg=images/f'{i:08d}.jpg'
        if raw is not None:
            packet=packets.get(f.get('source_frame_seq'))
            if not packet:raise ValueError('Video frame does not have a raw JPEG packet')
            content=raw[packet['offset']:packet['offset']+packet['length']]
        else:
            if f.get('video_frame_index')!=i:
                capture.release();raise ValueError('AVI frame/index map is incomplete')
            success,image=capture.read()
            if not success:
                capture.release();raise ValueError('AVI has fewer frames than observations')
            success,encoded=cv2.imencode('.jpg',image)
            if not success:
                capture.release();raise ValueError('Cannot decode AVI frame')
            content=encoded.tobytes()
        if annotated:
            import cv2
            import numpy as np
            image=cv2.imdecode(np.frombuffer(content,np.uint8),cv2.IMREAD_COLOR)
            if image is None:raise ValueError('JPEG decode failed during overlay export')
            if raw is not None:image=cv2.flip(image,1)
            height,width=image.shape[:2]
            for side,color in [('left',(80,200,255)),('right',(255,220,0))]:
                action=f.get('hand_actions',{}).get(side,{})
                hand=next((h for h in f.get('hands',[]) if h['hand_index']==action.get('hand_index')),None)
                if hand and action.get('tracking_status')=='detected':
                    points=[(round(p['x']*width),round(p['y']*height)) for p in hand['landmarks']]
                    trails[side]=(trails[side]+[points[0]])[-30:]
                    if len(trails[side])>1:cv2.polylines(image,[np.array(trails[side],np.int32)],False,color,1)
                    for point in points:cv2.circle(image,point,2,color,-1)
                    cv2.putText(image,side.upper(),points[0],cv2.FONT_HERSHEY_SIMPLEX,.35,color,1)
                else:trails[side]=[]
            cv2.putText(image,'2D IMAGE TRACK / ADC UNCALIBRATED',(4,height-6),cv2.FONT_HERSHEY_SIMPLEX,.3,(255,255,255),1)
            if not cv2.imwrite(str(jpg),image):raise ValueError('Cannot write overlay frame')
        else:jpg.write_bytes(content)
        lines.append(f"file '{jpg.name}'\noption framerate 1000\n")
        duration=((frames[i+1]['timestamp']-f['timestamp'])/1000 if i+1<len(frames)
                  else ((f['timestamp']-frames[i-1]['timestamp'])/1000 if i else 1/30))
        lines.append(f'duration {duration:.9f}\n')
    lines.append(f"file '{len(frames)-1:08d}.jpg'\noption framerate 1000\n")
    if capture is not None:capture.release()
    listing=images/'frames.txt'
    listing.write_text(''.join(lines),encoding='utf-8')
    target=directory/('video/fpv_annotated.mp4' if annotated else 'video/fpv.mp4')
    target.parent.mkdir(exist_ok=True)
    command=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-f','concat','-safe','0',
             '-i',str(listing),'-vf','hflip' if raw is not None and not annotated else 'null','-fps_mode','vfr','-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(target)]
    run_ffmpeg(command, timeout=300)
    return target


def mcap_observations(info, path):
    from mcap.writer import Writer
    from mcap.reader import make_reader
    expected=Counter()
    digests=[]
    with path.open('wb') as stream:
        writer=Writer(stream);writer.start(profile='smartwear-observation-json')
        schema=writer.register_schema('smartwear.observation/1.0','jsonschema',json.dumps({
            'type':'object','required':['source_kind','valid','clock_domain','observation'],
            'properties':{'source_kind':{'enum':['measured','inferred']},'valid':{'type':'boolean'},
                          'clock_domain':{'type':'string'},'observation':{'type':'object'}}}).encode())
        channels={topic:writer.register_channel(topic=topic,message_encoding='json',schema_id=schema)
                  for topic in ('/smartwear/camera/frame','/smartwear/hand/observations','/smartwear/wrist/fsr_raw','/smartwear/wrist/imu')}
        records=[]
        packets={p['seq']:p for p in info.get('camera_packets.jsonl',[])}
        for f in info['camera.jsonl']:
            epoch=f.get('source_epoch_ms');received=f.get('received_epoch_ms')
            if epoch is None or received is None:
                raise ValueError('MCAP requires recorded device and receive epochs; no invented clocks')
            records.append(('/smartwear/camera/frame',received*1_000_000,epoch*1_000_000,f.get('source_frame_seq',0),
                            {'source_kind':'measured','valid':True,'clock_domain':'camera_device_NTP_epoch','observation':{
                                'frame_index':f['video_frame_index'],'camera':f['camera'],
                                'received_monotonic_ns':packets.get(f.get('source_frame_seq'),{}).get('received_monotonic_ns')}}))
            records.append(('/smartwear/hand/observations',received*1_000_000,epoch*1_000_000,f.get('source_frame_seq',0),
                            {'source_kind':'inferred','valid':True,'clock_domain':'camera_device_NTP_epoch','observation':{
                                'hands':f.get('hands',[]),'hand_actions':f.get('hand_actions',{}),'units':'normalized_image_not_meters'}}))
        for r in info.get('wrist_raw.jsonl',[]):
            epoch=r['t_ms'];received=r.get('received_epoch_ms')
            if received is None:
                raise ValueError('MCAP wrist records require recorded receive epoch')
            records.append(('/smartwear/wrist/fsr_raw',received*1_000_000,epoch*1_000_000,r['seq'],
                            {'source_kind':'measured','valid':True,'clock_domain':'wrist_device_NTP_epoch','observation':{
                                'force':r['force'],'unit':'adc_count','side':'right','received_monotonic_ns':r.get('received_monotonic_ns')}}))
            records.append(('/smartwear/wrist/imu',received*1_000_000,epoch*1_000_000,r['seq'],
                            {'source_kind':'measured','valid':r.get('acc') is not None and r.get('gyro') is not None,
                             'clock_domain':'wrist_device_NTP_epoch','observation':{'acc':r.get('acc'),'gyro':r.get('gyro'),
                              'units':'firmware_g_and_deg_s_unverified','imu_status':r.get('imu_status','unknown')}}))
        for topic,log,publish,seq,value in sorted(records,key=lambda item:item[1]):
            data=json.dumps(value,allow_nan=False).encode()
            writer.add_message(channels[topic],log_time=log,publish_time=publish,sequence=seq,data=data)
            expected[topic]+=1;digests.append(hashlib.sha256(data).hexdigest())
        writer.finish()
    actual=Counter();decoded=[]
    with path.open('rb') as stream:
        for _,channel,message in make_reader(stream,validate_crcs=True).iter_messages():
            actual[channel.topic]+=1;decoded.append(hashlib.sha256(message.data).hexdigest())
    if actual!=expected or sorted(decoded)!=sorted(digests):
        raise ValueError('MCAP round-trip count/payload validation failed')
    return dict(expected)


def build_products(settings,session_id,knowledge,reference,reference_directory=None):
    root=analysis_directory(settings.keyframe_dir,session_id)
    source=source_archive_path(settings.keyframe_dir,session_id)
    recording=recording_path(settings.keyframe_dir,session_id)
    source_hash=sha(source)
    recording_hash=sha(recording) if recording.is_file() else None
    reference_manifest=verify_product(reference_directory) if reference_directory else None
    lineage={'source_archive_sha256':source_hash,'recording_sha256':recording_hash,
             'reference_manifest_sha256':sha(reference_directory/'episode_manifest.json') if reference_directory else None,
             'exporter_sha256':EXPORTER_SHA256}
    fingerprint=hashlib.sha256(json.dumps({'lineage':lineage,'knowledge':knowledge,'reference':reference},sort_keys=True).encode()).hexdigest()[:16]
    target=root/'products'/fingerprint
    with LOCK:
        if (target/'episode_manifest.json').is_file():
            verify_product(target)
            return target
        info=inspect_source(source)
        q=quality(info)
        role=knowledge['context']['role']
        ready=knowledge['review_status']=='approved' if role=='expert' else bool(reference and reference['review_status']=='approved' and knowledge['review_status']=='approved')
        media_available=info['raw_jpeg_in_archive'] or recording.is_file()
        reference_media_available=not reference or bool(reference_directory and (
            (reference_directory/'video/fpv.mp4').is_file()))
        ready=ready and media_available and reference_media_available
        q['learner_ready']=ready
        q['learner_reasons']=[] if ready else ['SOP/reference và evidence chưa được người hướng dẫn duyệt']
        if not media_available or not reference_media_available:
            q['learner_reasons'].append('Thiếu video/JPEG nguồn để phát bài học')
        target.parent.mkdir(parents=True,exist_ok=True)
        temp=Path(tempfile.mkdtemp(prefix='build_',dir=target.parent))
        started=time.monotonic()
        try:
            (temp/'raw').mkdir();shutil.copyfile(source,temp/'raw/ai_source_data.zip')
            if recording.is_file():shutil.copyfile(recording,temp/'raw/camera.avi')
            if sha(temp/'raw/ai_source_data.zip') != source_hash or (recording_hash and sha(temp/'raw/camera.avi') != recording_hash):
                raise ValueError('Source changed during product generation; retry with stable published data')
            (temp/'reports').mkdir();(temp/'labels').mkdir();(temp/'arrays').mkdir();(temp/'learner').mkdir()
            def write(relative,value):
                (temp/relative).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
            write('reports/quality.json',q)
            write('labels/task_steps.json',{'source_kind':'human_label','knowledge':knowledge,'reference':reference})
            write('labels/heuristic_phases.json',info.get('action_segments.json',{}))
            clock=arrays(info,temp/'arrays/episode.h5',knowledge['steps'],knowledge['review_status']=='approved')
            mcap_counts=mcap_observations(info,temp/'arrays/episode.mcap')
            video=encode_video(info,temp)
            annotated_video=encode_video(info,temp,annotated=True) if video else None
            if media_available and video is None:
                raise ValueError('Published video could not be decoded')
            source_start_s=info['camera.jsonl'][0]['timestamp']/1000
            video_timebase={'source_start_s':source_start_s,
                            'reference_source_start_s':reference_manifest['video_timebase']['source_start_s'] if reference_manifest else None}
            reference_video=None
            if reference_directory and (reference_directory/'video/fpv.mp4').is_file():
                reference_video=temp/'video/reference.mp4'
                reference_video.parent.mkdir(exist_ok=True)
                shutil.copyfile(reference_directory/'video/fpv.mp4',reference_video)
            gap_report=[]
            if reference:
                for current,expert in zip(knowledge['steps'],reference['steps']):
                    w,e=current.get('start_s'),expert.get('start_s')
                    gap_report.append({'step_id':current['step_id'],'source_kind':'human_label',
                                       'worker_range_s':[w,current.get('end_s')],
                                       'expert_range_s':[e,expert.get('end_s')],
                                       'duration_delta_s':(current['end_s']-w)-(expert['end_s']-e)
                                       if w is not None and e is not None else None})
            write('reports/motion_gap.json',{'steps':gap_report,'note':'Step timings are human annotations; heuristic DTW is a separate source.'})
            lesson=reference if role=='worker' and reference else knowledge
            clips=[]
            for step in knowledge['steps']:
                if video and step.get('start_s') is not None and step.get('end_s') is not None:
                    import imageio_ffmpeg
                    clip=temp/'learner'/f"{step['step_id']}.mp4"
                    if step['start_s'] < source_start_s or step['end_s'] > info['duration_s'] + .05:
                        raise ValueError('Clip time is outside the recorded source timeline')
                    run_ffmpeg([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-ss',str(step['start_s']-source_start_s),'-i',str(annotated_video or video),'-t',str(step['end_s']-step['start_s']),'-c:v','libx264','-pix_fmt','yuv420p','-an',str(clip)],timeout=120)
                    sidecar={'schema':'smartwear.micro_clip/1.0','step_id':step['step_id'],'time_range_s':[step['start_s'],step['end_s']],
                             'source_kind':'measured_with_inferred_overlay','coordinate_units':'normalized_image',
                             'overlay':bool(annotated_video),'overlay_version':'2d-trail-1','sha256':sha(clip),
                             'source_archive_sha256':sha(source),'camera':q['camera']}
                    sidecar['video_time_range_s']=[step['start_s']-source_start_s,step['end_s']-source_start_s]
                    write(f"learner/{step['step_id']}.json",sidecar);clips.append(sidecar)
            sections=[]
            for step in lesson['steps']:
                fields=''.join(f'<p><b>{html.escape(label)}:</b> {html.escape(str(step.get(field,"")))}</p>'
                               for field,label in [('instruction','Hướng dẫn'),('why','Vì sao'),('tips','Mẹo'),('common_errors','Lỗi cần tránh'),('safety','Khi nào dừng'),('acceptable_variation','Biến thể chấp nhận')])
                links=[]
                current=next((s for s in knowledge['steps'] if s['step_id']==step['step_id']),None)
                if current and current.get('start_s') is not None and video:
                    at=current['start_s']-source_start_s
                    links.append(f'<button type="button" data-video="session-video" data-time="{at}">Mở bước trong phiên này</button>')
                    links.append(f'<a href="{html.escape(current["step_id"])}.mp4">Xem clip bước</a>')
                if reference_video and step.get('start_s') is not None:
                    at=step['start_s']-video_timebase['reference_source_start_s']
                    links.append(f'<button type="button" data-video="reference-video" data-time="{at}">Mở bước mẫu</button>')
                sections.append(f'<section><h2>{html.escape(step["step_id"]+" · "+step["title"])}</h2>{fields}<p>Mốc video nguồn: {step.get("start_s")}–{step.get("end_s")} s</p>{" · ".join(links)}</section>')
            banner='ĐÃ DUYỆT' if ready else 'BẢN NHÁP — CHƯA DUYỆT'
            document=f'<!doctype html><html lang="vi"><meta charset="utf-8"><title>SmartWear SOP</title><style>body{{font:16px system-ui;max-width:1000px;margin:40px auto;padding:20px}}section{{border-top:1px solid #aaa;padding:12px}}video{{width:100%}}</style><h1>{banner}</h1><p>Session: {html.escape(session_id)}</p><p>Reference: {html.escape(str(knowledge["context"].get("reference_session_id")))}</p><p>ADC chưa hiệu chuẩn; thiếu robot action.</p>'
            if reference:
                document+='<h2>Mẫu chuyên gia đã chọn</h2>'
                if reference_video:document+='<video id="reference-video" controls src="../video/reference.mp4"></video>'
                else:document+='<p>Video mẫu chưa có MP4; xem video nguồn ở dashboard.</p>'
                document+='<h2>Phiên học viên</h2>'
            if video:document+='<video id="session-video" controls src="../video/fpv.mp4"></video>'
            elif (temp/'raw/camera.avi').is_file():document+='<p><a href="../raw/camera.avi">Video AVI nguồn (mốc bước bên dưới; dùng trình phát hỗ trợ AVI)</a></p>'
            document+=''.join(sections)+'''<script>
document.querySelectorAll('button[data-video]').forEach(button => {
  button.addEventListener('click', () => {
    const video = document.getElementById(button.dataset.video);
    const seek = () => { video.currentTime = Number(button.dataset.time); video.scrollIntoView({block: 'center'}); };
    if (video.readyState >= 1) seek(); else video.addEventListener('loadedmetadata', seek, {once: true});
  });
});
</script></html>'''
            (temp/'learner/sop.html').write_text(document,encoding='utf-8')
            write('learner/manifest.json',{'schema':'smartwear.learner/1.0','session_id':session_id,'ready':ready,
                                        'review_status':knowledge['review_status'],'clips':clips,'quality':q})
            artifacts=[{'path':str(p.relative_to(temp)).replace('\\','/'),'sha256':sha(p),'size_bytes':p.stat().st_size}
                       for p in sorted(temp.rglob('*')) if p.is_file()]
            manifest={'schema':'smartwear.episode/1.0','session_id':session_id,'episode_id':fingerprint,
                      'exporter_version':EXPORT_VERSION,'exporter_sha256':EXPORTER_SHA256,'role':role,
                      'lineage':lineage,'video_timebase':video_timebase,
                      'learner_steps':lesson['steps'],'worker_steps':knowledge['steps'],
                      'context':knowledge['context'],'review_revision':knowledge['revision'],
                      'source_archive_sha256':sha(source),'source_kind':'measured' if 'hardware_capture.json' in info else 'simulated',
                      'timebase':{'clock':clock,'unit':'ns','note':'Receive monotonic clock is not capture time or clock-accuracy evidence'},
                      'pipeline':info.get('capture_manifest.json',{}),'quality_state':q,
                      'robot_action_available':False,'robot_policy_training_ready':False,
                      'mcap_message_counts':mcap_counts,
                      'calibration_ids':{'camera':None,'fsr':None,'hand_to_robot':None},
                      'license_status':knowledge['license_status'],'retention_policy':knowledge['retention_policy'],
                      'generation_elapsed_ms':round((time.monotonic()-started)*1000), 'artifacts':artifacts}
            write('episode_manifest.json',manifest)
            hashes=[f'{sha(p)}  {str(p.relative_to(temp)).replace(chr(92),"/")}' for p in sorted(temp.rglob('*')) if p.is_file()]
            (temp/'checksums.sha256').write_text('\n'.join(hashes)+'\n',encoding='utf-8')
            # Validate every artifact after generation, before publishing the directory.
            for artifact in artifacts:
                if sha(temp/artifact['path'])!=artifact['sha256']:raise ValueError('Artifact checksum mismatch')
            os.rename(temp,target)
        except Exception:
            remove_build_directory(temp,target.parent)
            raise
    return target
