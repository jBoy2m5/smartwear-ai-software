"""Task knowledge/review and separate learner/observation downloads."""
import io
import json
import zipfile
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, FileResponse
from sqlalchemy.exc import IntegrityError
from backend.api.auth import require_api_key
from fastapi import Depends
from backend.schemas.knowledge import Procedure, SessionKnowledge
from backend.services.episode_products import inspect_source, quality
from backend.services.analysis_detail import source_archive_path
from backend.services.analysis_detail import analysis_directory
import re
import mimetypes
import logging

logger = logging.getLogger(__name__)

router=APIRouter(prefix='/knowledge',tags=['Knowledge'],dependencies=[Depends(require_api_key)])

def service(request):return request.app.state.knowledge_service

def product_directory(session_id, request):
    try:
        return service(request).products(session_id)
    except (ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        raise HTTPException(409, str(exc)) from exc
    except OSError as exc:
        logger.exception('Product storage unavailable for session %s', session_id)
        raise HTTPException(503, 'Product storage is unavailable; source data is preserved. Retry after checking storage.') from exc

@router.get('/procedures')
def procedures(request:Request):return service(request).procedures()

@router.post('/procedures')
def create_procedure(value:Procedure,request:Request):
    try:return service(request).append('procedure',value.task_id+':'+value.version,value.model_dump())
    except (ValueError,IntegrityError) as exc:raise HTTPException(409,str(exc)) from exc

@router.get('/references')
def references(request:Request,task_id:str|None=None,version:str|None=None):
    return service(request).references(task_id,version)

@router.get('/learning-trials')
def learning_trials(request: Request):
    return service(request).learning_trials()

@router.get('/learning-experiment')
def learning_experiment(request: Request, before_session_id: str, after_session_id: str):
    return service(request).learning_experiment(before_session_id, after_session_id)

@router.get('/sessions/{session_id}')
def knowledge(session_id:str,request:Request):return service(request).latest('session',session_id)

@router.put('/sessions/{session_id}')
def save(session_id:str,value:SessionKnowledge,request:Request):
    try:return service(request).save_session(session_id,value)
    except (ValueError,IntegrityError) as exc:raise HTTPException(409,str(exc)) from exc

@router.get('/sessions/{session_id}/quality')
def report(session_id:str,request:Request):
    service(request).sessions.get_session(session_id)
    try:return quality(inspect_source(source_archive_path(request.app.state.settings.keyframe_dir,session_id)))
    except ValueError as exc:raise HTTPException(409,str(exc)) from exc

@router.post('/sessions/{session_id}/products')
def generate(session_id:str,request:Request):
    directory=product_directory(session_id,request)
    return json.loads((directory/'episode_manifest.json').read_text(encoding='utf-8'))

@router.get('/sessions/{session_id}/products/{kind}')
def download(session_id:str,kind:str,request:Request):
    if kind=='robot':raise HTTPException(409,'Robot actions/calibration/clock evidence are missing; observation-only')
    if kind not in ('learner','observation','manifest'):raise HTTPException(404,'Unknown data product')
    directory=product_directory(session_id,request)
    if kind=='manifest':return FileResponse(directory/'episode_manifest.json',media_type='application/json')
    # Both portable products preserve the shared source/manifest and validity.
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.rglob('*')):
            if path.is_file():archive.write(path,path.relative_to(directory).as_posix())
    return Response(buffer.getvalue(),media_type='application/zip',headers={
        'Content-Disposition':f'attachment; filename="{kind}_{session_id}.zip"'})

@router.get('/sessions/{session_id}/products/files/{filename:path}')
def artifact(session_id:str,filename:str,request:Request,episode_id:str):
    service(request).sessions.get_session(session_id)
    if not re.fullmatch(r'[0-9a-f]{16}',episode_id):raise HTTPException(422,'Invalid episode ID')
    directory=analysis_directory(request.app.state.settings.keyframe_dir,session_id)/'products'/episode_id
    manifest=directory/'episode_manifest.json'
    if not manifest.is_file():raise HTTPException(404,'Product version not found')
    document=json.loads(manifest.read_text(encoding='utf-8'))
    allowed={a['path'] for a in document['artifacts']}
    path=(directory/filename).resolve()
    if filename not in allowed or not path.is_relative_to(directory.resolve()) or not path.is_file():
        raise HTTPException(404,'Artifact not declared in product manifest')
    return FileResponse(path,media_type=mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
