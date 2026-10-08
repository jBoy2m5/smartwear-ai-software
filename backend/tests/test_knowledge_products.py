"""Review gates, pinned references and observation export round trips."""
import io
import json
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile
from pathlib import Path
from types import SimpleNamespace
from PIL import Image

import h5py
import numpy as np
from backend.core.config import Settings
from backend.db.session import Database
from backend.schemas.knowledge import CaptureContext, SessionKnowledge
from backend.services.knowledge import KnowledgeService
from backend.services.analysis_detail import source_archive_path
from backend.services.analysis_detail import recording_path
from backend.services.episode_products import inspect_source, quality, arrays, build_products, sha


def write_fixture(path, *, raw_jpeg=True, start_ms=0):
    frames=[];sensors=[];wrist=[];packets=[];raw=bytearray()
    for i in range(11):
        frames.append({'timestamp':start_ms+i*100,'video_frame_index':i,'source_frame_seq':i,
                       'source_epoch_ms':1790000000000+i*100,'received_epoch_ms':1790000000010+i*100,
                       'camera':{'frame_width':320,'frame_height':240},'hands':[],
                       'hand_actions':{side:{'tracking_status':'missing','hand_index':None} for side in ('left','right')}})
        image=io.BytesIO();Image.new('RGB',(320,240),(i*15,20,30)).save(image,format='JPEG')
        jpeg=image.getvalue()
        packets.append({'seq':i,'received_monotonic_ns':1_000_000_000+i*100_000_000,
                        'offset':len(raw),'length':len(jpeg)})
        raw.extend(jpeg)
        sensors.append({'hand_sensors':{'right':{'force_adc':None if i==2 else [i,20,30,0],
                       'source_seq':i,'alignment_offset_ms':5,'imu_wrist':None}}})
        wrist.append({'seq':i,'t_ms':1790000000000+i*100,'received_epoch_ms':1790000000010+i*100,
                      'force':[i,20,30,0],'acc':None,'gyro':None})
    path.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(path,'w') as archive:
        if raw_jpeg:archive.writestr('camera_raw.mjpeg',raw)
        for name,rows in [('camera.jsonl',frames),('real_sensors.jsonl',sensors),('wrist_raw.jsonl',wrist),('camera_packets.jsonl',packets)]:
            archive.writestr(name,'\n'.join(json.dumps(r) for r in rows))
        archive.writestr('hardware_capture.json',json.dumps({'status':'complete','average_received_fps':10,'average_wrist_hz':10}))
        archive.writestr('real_sensors.meta.json',json.dumps({'matched_count':10,'max_abs_alignment_offset_ms':5}))


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.settings=Settings(environment='test',static_dir=self.root/'static',keyframe_dir=self.root/'static/images')
        self.db=Database('sqlite:///:memory:');self.db.create_schema()
        self.sessions=SimpleNamespace(get_session=lambda sid:SimpleNamespace(worker_type='EXPERT',key_frames=[]))
        self.service=KnowledgeService(self.db,self.settings,self.sessions);self.service.seed()
        self.sid='MEASURED_expert_test'
        write_fixture(source_archive_path(self.settings.keyframe_dir,self.sid))
        self.context=CaptureContext(role='expert',task_id='LOG_KIT',procedure_version='1',participant_id='guide_01',consent_confirmed=True)

    def tearDown(self):
        self.db.dispose();self.temp.cleanup()

    def value(self,revision=0):
        return SessionKnowledge(context=self.context,source_session_name='expert_test',revision=revision)

    def test_approval_requires_evidence_and_does_not_invent_notes(self):
        draft=self.service.save_session(self.sid,self.value())
        self.assertEqual(draft['review_status'],'draft');self.assertEqual(self.service.references(),[])
        value=self.value(1);value.review_status='approved'
        value.outcome='passed'
        with self.assertRaisesRegex(ValueError,'Approval requires'):
            self.service.save_session(self.sid,value)
        value.reviewer='reviewer';value.review_rationale='Viewed all steps';value.clarity_confirmed=True
        with self.assertRaisesRegex(ValueError,'Each approved step'):
            self.service.save_session(self.sid,value)
        from backend.schemas.knowledge import Step
        value.steps=[Step.model_validate({**s,'why':'Human reviewer rationale','start_s':i*.25,'end_s':(i+1)*.25}) for i,s in enumerate(draft['steps'])]
        approved=self.service.save_session(self.sid,value)
        self.assertEqual(len(self.service.references('LOG_KIT','1')),1)
        self.assertEqual(self.service.latest('session',self.sid,1)['review_status'],'draft')
        with self.assertRaisesRegex(ValueError,'Revision conflict'):
            self.service.save_session(self.sid,value)
        ready=build_products(self.settings,self.sid,approved,None)
        manifest=json.loads((ready/'episode_manifest.json').read_text(encoding='utf-8'))
        self.assertTrue(manifest['quality_state']['learner_ready'])
        self.assertFalse(manifest['robot_policy_training_ready'])
        self.assertTrue((ready/'learner/A1.mp4').is_file())
        self.assertTrue((ready/'video/fpv_annotated.mp4').is_file())
        sop=(ready/'learner/sop.html').read_text(encoding='utf-8')
        self.assertIn('data-video="session-video" data-time="0.0"',sop)
        self.assertIn('href="A1.mp4"',sop)
        for item in manifest['artifacts']:
            self.assertEqual(item['sha256'],sha(ready/item['path']))
        self.assertEqual(build_products(self.settings,self.sid,approved,None),ready)
        (ready/'learner/A1.mp4').write_bytes(b'corrupted artifact')
        with self.assertRaisesRegex(ValueError,'has changed'):
            build_products(self.settings,self.sid,approved,None)

    def test_avi_fallback_timing_and_cache_lineage(self):
        import cv2
        path=source_archive_path(self.settings.keyframe_dir,self.sid)
        write_fixture(path,raw_jpeg=False,start_ms=500)
        recording=recording_path(self.settings.keyframe_dir,self.sid)
        def write_avi(color):
            writer=cv2.VideoWriter(str(recording),cv2.VideoWriter_fourcc(*'MJPG'),30,(320,240))
            self.assertTrue(writer.isOpened())
            try:
                for _ in range(11):writer.write(np.full((240,320,3),color,dtype=np.uint8))
            finally:writer.release()
        write_avi(40)
        draft=self.service.save_session(self.sid,self.value())
        draft['steps'][0].update(start_s=.6,end_s=.8)
        first=build_products(self.settings,self.sid,draft,None)
        manifest=json.loads((first/'episode_manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['video_timebase']['source_start_s'],.5)
        self.assertEqual(manifest['lineage']['recording_sha256'],sha(recording))
        sidecar=json.loads((first/'learner/A1.json').read_text())
        np.testing.assert_allclose(sidecar['video_time_range_s'],[.1,.3])
        reader=cv2.VideoCapture(str(first/'video/fpv.mp4'))
        try:
            self.assertTrue(reader.isOpened())
            self.assertGreater(reader.get(cv2.CAP_PROP_FRAME_COUNT)/reader.get(cv2.CAP_PROP_FPS),1)
        finally:reader.release()
        write_avi(80)
        second=build_products(self.settings,self.sid,draft,None)
        self.assertNotEqual(first,second)
        self.assertTrue(first.is_dir())

    def test_export_failure_cleans_only_temporary_build_and_keeps_source(self):
        import subprocess
        draft=self.service.save_session(self.sid,self.value())
        source=source_archive_path(self.settings.keyframe_dir,self.sid)
        original=sha(source)
        with patch('backend.services.episode_products.subprocess.run',side_effect=subprocess.CalledProcessError(1,['ffmpeg'])):
            with self.assertRaisesRegex(RuntimeError,'Video export failed'):
                build_products(self.settings,self.sid,draft,None)
        self.assertEqual(sha(source),original)
        self.assertEqual(list((source.parent/'products').glob('build_*')),[])

    def test_worker_bundle_pins_reference_media_and_offline_links(self):
        import copy
        expert=self.service.save_session(self.sid,self.value())
        for i,step in enumerate(expert['steps']):
            step.update(start_s=i*.25,end_s=(i+1)*.25)
        reference=build_products(self.settings,self.sid,expert,None)
        worker_id='MEASURED_worker_test'
        write_fixture(source_archive_path(self.settings.keyframe_dir,worker_id),start_ms=500)
        worker=copy.deepcopy(expert)
        worker['context'].update(role='worker',reference_session_id=self.sid)
        for step in worker['steps']:
            step['start_s']+=.5;step['end_s']+=.5
        product=build_products(self.settings,worker_id,worker,expert,reference)
        manifest=json.loads((product/'episode_manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['lineage']['reference_manifest_sha256'],sha(reference/'episode_manifest.json'))
        self.assertEqual(sha(product/'video/reference.mp4'),sha(reference/'video/fpv.mp4'))
        sop=(product/'learner/sop.html').read_text(encoding='utf-8')
        self.assertIn('data-video="reference-video" data-time="0.0"',sop)
        self.assertIn('data-video="session-video" data-time="0.0"',sop)
        self.assertFalse(manifest['quality_state']['learner_ready'])
        # New reference annotation revision must create a new worker bundle.
        expert['revision']+=1
        reference2=build_products(self.settings,self.sid,expert,None)
        product2=build_products(self.settings,worker_id,worker,expert,reference2)
        self.assertNotEqual(product,product2)

    def test_retirement_preserves_pinned_history_and_excludes_new_captures(self):
        draft=self.service.save_session(self.sid,self.value())
        from backend.schemas.knowledge import Step
        value=self.value(1)
        value.review_status='approved';value.outcome='passed';value.reviewer='reviewer'
        value.review_rationale='Reviewed fixture';value.clarity_confirmed=True
        value.steps=[Step.model_validate({**s,'why':'Reviewed reason','start_s':i*.25,'end_s':(i+1)*.25}) for i,s in enumerate(draft['steps'])]
        self.service.save_session(self.sid,value)
        value.revision=2;value.review_status='retired'
        self.service.save_session(self.sid,value)
        self.assertEqual(self.service.references(),[])
        self.assertEqual(self.service.latest('session',self.sid,2)['review_status'],'approved')
        context=CaptureContext(role='worker',task_id='LOG_KIT',procedure_version='1',participant_id='learner',consent_confirmed=True,reference_session_id=self.sid)
        with self.assertRaisesRegex(ValueError,'approved'):
            self.service.capture_context(context)

    def test_role_identity_and_context_are_immutable(self):
        self.service.save_session(self.sid,self.value())
        changed=self.value(1);changed.context.participant_id='someone_else'
        with self.assertRaisesRegex(ValueError,'immutable'):
            self.service.save_session(self.sid,changed)
        with self.assertRaisesRegex(ValueError,'identity'):
            self.service.save_session('MEASURED_other',self.value())

    def test_missing_values_round_trip_without_zero_imputation(self):
        info=inspect_source(source_archive_path(self.settings.keyframe_dir,self.sid))
        report=quality(info)
        self.assertEqual(report['clock_accuracy_status'],'unknown')
        self.assertTrue(report['wrist']['fsr'][3]['flatline'])
        self.assertFalse(report['robot_ready'])
        clock=arrays(info,self.root/'episode.h5')
        self.assertEqual(clock,'recorder_receive_monotonic')
        with h5py.File(self.root/'episode.h5') as episode:
            self.assertTrue(np.isnan(episode['observations/wrist/fsr_adc'][2]).all())
            self.assertFalse(episode['validity/fsr'][2].any())
            self.assertFalse(episode['validity/imu'][:].any())
            self.assertEqual(len(episode['actions']),0)

    def test_worker_rejects_unapproved_and_wrong_task_reference(self):
        self.service.save_session(self.sid,self.value())
        context=CaptureContext(role='worker',task_id='LOG_KIT',procedure_version='1',participant_id='learner_01',
                               consent_confirmed=True,reference_session_id=self.sid)
        with self.assertRaisesRegex(ValueError,'approved'):
            self.service.capture_context(context)

    def test_nonincreasing_camera_time_rejected(self):
        archive=source_archive_path(self.settings.keyframe_dir,self.sid)
        with zipfile.ZipFile(archive) as reader:
            entries={name:reader.read(name) for name in reader.namelist()}
        rows=[json.loads(line) for line in entries['camera.jsonl'].splitlines()]
        rows[2]['timestamp']=rows[1]['timestamp']
        entries['camera.jsonl']='\n'.join(json.dumps(r) for r in rows).encode()
        with zipfile.ZipFile(archive,'w') as writer:
            for name,content in entries.items():writer.writestr(name,content)
        with self.assertRaisesRegex(ValueError,'increase'):inspect_source(archive)

    def test_capture_api_passes_explicit_role_and_context_to_ai(self):
        from fastapi.testclient import TestClient
        from backend.main import create_app
        settings=Settings(environment='test',database_url='sqlite:///:memory:',static_dir=self.root/'static',
                          pdf_dir=self.root/'pdf',keyframe_dir=self.root/'images',dataset_dir=self.root/'dataset')
        with TestClient(create_app(settings,serve_frontend=False)) as client:
            self.assertEqual(len(client.get('/api/v1/knowledge/procedures').json()),2)
            self.assertEqual(client.post('/api/v1/capture/',json={'role':'worker'}).status_code,422)
            manager=client.app.state.capture_manager
            process=Mock();process.poll.return_value=None
            with patch.object(manager,'_hardware_preflight'),patch.object(manager,'_ai_python',return_value='python'),patch('backend.services.capture.subprocess.Popen',return_value=process) as launch:
                response=client.post('/api/v1/capture/',json=self.context.model_dump())
            self.assertEqual(response.status_code,201)
            job=manager.directory(response.json()['job_id'])
            context=json.loads((job/'context.json').read_text(encoding='utf-8'))
            self.assertEqual(context['role'],'expert')
            self.assertEqual(context['procedure_snapshot']['task_id'],'LOG_KIT')
            self.assertIn('--context',launch.call_args.args[0])
            self.assertEqual(client.post('/api/v1/capture/',json=self.context.model_dump()).status_code,409)
            self.assertEqual(client.get('/api/v1/knowledge/sessions/no_such_session/products/robot').status_code,409)
            with patch.object(client.app.state.knowledge_service,'products',side_effect=OSError('disk failed')):
                self.assertEqual(client.post('/api/v1/knowledge/sessions/test/products').status_code,503)
                self.assertEqual(client.get('/api/v1/knowledge/sessions/test/products/observation').status_code,503)
