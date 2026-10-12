"""Upload boundary and real file-decoder/MediaPipe/publish regression checks."""
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from backend.core.config import Settings
from backend.main import create_app


class VideoUploadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.settings = Settings(environment='test', database_url=f"sqlite:///{(self.root/'db.sqlite').as_posix()}",
            static_dir=self.root/'static', keyframe_dir=self.root/'static/images',
            pdf_dir=self.root/'static/pdf', dataset_dir=self.root/'static/dataset')
        self.app = create_app(self.settings, serve_frontend=False)
        self.client = TestClient(self.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temporary.cleanup()

    def upload(self, content=b'video', filename='test.mp4', consent='true'):
        return self.client.post('/api/v1/capture/upload', params={'filename':filename,'consent':consent}, content=content)

    def test_upload_limits_consent_and_stream_cleanup(self):
        self.assertEqual(self.upload(consent='false').status_code, 422)
        self.assertEqual(self.upload(filename='test.exe').status_code, 415)
        self.assertEqual(self.upload(content=b'').status_code, 422)
        with patch('backend.api.routes.capture.MAX_UPLOAD_BYTES', 3):
            self.assertEqual(self.upload(content=b'abcd').status_code, 413)
            # Exercise the streaming limit without a declared Content-Length.
            response = self.client.post('/api/v1/capture/upload?filename=x.mp4&consent=true',
                                        content=iter([b'ab', b'cd']))
            self.assertEqual(response.status_code, 413)
        self.assertEqual(list(self.app.state.capture_manager.root.iterdir()), [])

    def test_upload_uses_file_worker_without_devices_and_serializes_jobs(self):
        manager = self.app.state.capture_manager
        process = Mock()
        process.poll.return_value = None
        with patch.object(manager, '_ai_python', return_value='python'), \
             patch.object(manager, '_hardware_preflight', side_effect=AssertionError('no hardware')), \
             patch('backend.services.capture.subprocess.Popen', return_value=process) as launch:
            response = self.upload(filename='../../outside.mp4')
            self.assertEqual(response.status_code, 201, response.text)
            job = response.json()
            directory = manager.directory(job['job_id'])
            self.assertEqual((directory/'input.mp4').read_bytes(), b'video')
            self.assertEqual(job['capture_mode'], 'upload')
            self.assertIn('uploaded_video.py', launch.call_args.args[0][2])
            self.assertEqual(launch.call_args.kwargs['env']['SMARTWEAR_CAPTURE_MODE'], 'upload')
            self.assertEqual(self.upload().status_code, 409)
            self.client.post(f"/api/v1/capture/{job['job_id']}/stop")
            self.assertTrue((directory/'stop.flag').exists())

    def test_real_video_without_hands_publishes_null_sensors_and_original(self):
        import cv2
        import numpy as np
        from ai.integration import uploaded_video as worker
        from integration import backend_bridge as bridge

        job = self.root / ('a'*32)
        job.mkdir()
        source = job/'input.avi'
        writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'MJPG'), 20., (160,120))
        self.assertTrue(writer.isOpened())
        for _ in range(20):
            writer.write(np.zeros((120,160,3), dtype=np.uint8))
        writer.release()
        original = source.read_bytes()

        def transport(url, method, data, api_key=None, content_type='application/json', extra_headers=None, timeout=30):
            response = self.client.request(method, url.removeprefix('http://testserver'), content=data,
                headers={'Content-Type': content_type, **(extra_headers or {})})
            self.assertLess(response.status_code, 300, response.text)
            return response.json()

        with patch.dict(os.environ, {'SMARTWEAR_CAPTURE_MODE':'upload'}), \
             patch.object(worker, 'request_json', side_effect=transport), \
             patch.object(bridge, 'request_json', side_effect=transport):
            result = worker.main(['--job-dir',str(job),'--input',str(source),'--backend-url','http://testserver'])
        self.assertEqual(result, 0, (job/'status.json').read_text(encoding='utf-8'))
        status = json.loads((job/'status.json').read_text(encoding='utf-8'))
        self.assertEqual(status['stage'], 'completed')
        sid = status['session_id']
        self.assertTrue(sid.startswith('VIDEO_'))
        detail = self.client.get('/api/v1/sessions/'+sid).json()
        self.assertEqual(detail['robot_trajectory_points'], [])
        self.assertIsNone(detail['robot_export_url'])
        self.assertIsNone(detail['robot_json_url'])
        self.assertEqual(detail['action_phases'], [])  # Black fixture must not invent hands.
        html = self.client.get(detail['sop_download_url']+'?format=html').text
        self.assertIn('Unavailable (no reference)', html)
        archive = self.client.get(detail['source_data_url']).content
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            self.assertEqual(z.read('source_video.avi'), original)
            manifest = json.loads(z.read('uploaded_video.json'))
            self.assertEqual(manifest['decoded_frames'], 20)
            self.assertEqual(manifest['analyzed_frames'], 10)
            frames = [json.loads(line) for line in z.read('multimodal.jsonl').splitlines()]
            self.assertTrue(all(f['provenance']['sensors'] == worker.SENSOR_SOURCE for f in frames))
            self.assertTrue(all(not f['provenance']['simulated_fields'] for f in frames))
            self.assertTrue(all(f['hand_sensors']['right']['force_adc'] is None for f in frames))
        self.assertEqual(self.client.get(detail['recording_url']).status_code, 200)
        cancelled = self.root / ('b'*32)
        cancelled.mkdir()
        (cancelled/'stop.flag').touch()
        with patch.dict(os.environ, {'SMARTWEAR_CAPTURE_MODE':'upload'}), \
             patch.object(worker, 'publish_video', side_effect=AssertionError('cancelled job must not publish')):
            self.assertEqual(worker.main(['--job-dir',str(cancelled),'--input',str(source)]), 1)
        stopped = json.loads((cancelled/'status.json').read_text(encoding='utf-8'))
        self.assertEqual(stopped['stage'], 'failed')
        self.assertIn('hủy', stopped['message'])

    def test_rejects_long_video_before_inference(self):
        from ai.integration import uploaded_video as worker
        capture = Mock()
        capture.isOpened.return_value = True
        capture.get.side_effect = [30., 6000.]
        with patch('cv2.VideoCapture', return_value=capture):
            with self.assertRaisesRegex(ValueError, '3 phút'):
                worker.process_video(self.root/'long.mp4', self.root/'session', self.root)
        capture.release.assert_called_once()
        self.assertFalse((self.root/'session').exists())

    def test_invalid_video_fails_without_session(self):
        from ai.integration import uploaded_video as worker
        for name, content in [('invalid', b'not a video')]:
            job = self.root/name
            job.mkdir()
            source = job/'input.mp4'
            source.write_bytes(content)
            with patch.dict(os.environ, {'SMARTWEAR_CAPTURE_MODE':'upload'}):
                self.assertEqual(worker.main(['--job-dir',str(job),'--input',str(source)]), 1)
            document = json.loads((job/'status.json').read_text(encoding='utf-8'))
            self.assertEqual(document['stage'], 'failed')
            self.assertIsNone(document['session_id'])


if __name__ == '__main__':
    unittest.main()
