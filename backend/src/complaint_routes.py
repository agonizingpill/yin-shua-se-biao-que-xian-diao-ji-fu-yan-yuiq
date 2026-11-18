import os,redis
from fastapi import APIRouter,Depends
from sqlalchemy import select
from .db import db_session
from .auth import current,writers,admin
from .services import pack,get
from .complaint_models import Complaint,ComplaintBox,ComplaintRecall,JobVerification
from .complaint_schemas import ComplaintInput,ReleaseInput,DisposeInput,CloseInput,RecallDone,VerificationInput
from . import complaint_service
router=APIRouter();queue=redis.Redis.from_url(os.environ['REDIS_URL'],decode_responses=True)


def _case(s,x):
    row=pack(x)
    boxes=s.scalars(select(ComplaintBox).where(ComplaintBox.complaint_id==x.id).order_by(ComplaintBox.id)).all()
    recalls=s.scalars(select(ComplaintRecall).where(ComplaintRecall.complaint_id==x.id).order_by(ComplaintRecall.id)).all()
    row['boxes']=[pack(b) for b in boxes];row['recalls']=[pack(r) for r in recalls]
    return row


@router.get('/complaints')
def complaints(s=Depends(db_session),u=Depends(current)):return [_case(s,x) for x in s.scalars(select(Complaint).order_by(Complaint.id.desc()))]
@router.get('/complaints/{key}')
def complaint(key:int,s=Depends(db_session),u=Depends(current)):return _case(s,get(s,Complaint,key))
@router.post('/complaints')
def create(b:ComplaintInput,s=Depends(db_session),u=Depends(writers)):return _case(s,complaint_service.create(s,b,u,queue))
@router.post('/complaints/{key}/retest')
def retest(key:int,s=Depends(db_session),u=Depends(writers)):return _case(s,complaint_service.retest(s,key,queue,u))
@router.post('/complaints/{key}/accept')
def accept(key:int,s=Depends(db_session),u=Depends(writers)):return _case(s,complaint_service.accept(s,key,u))
@router.post('/complaints/{key}/release')
def release(key:int,b:ReleaseInput,s=Depends(db_session),u=Depends(admin)):return _case(s,complaint_service.release(s,key,b,u))
@router.post('/complaints/{key}/boxes/{box}/dispose')
def dispose(key:int,box:int,b:DisposeInput,s=Depends(db_session),u=Depends(writers)):return _case(s,complaint_service.dispose(s,key,box,b,u))
@router.post('/complaints/{key}/recalls/{recall}/complete')
def recall_done(key:int,recall:int,b:RecallDone,s=Depends(db_session),u=Depends(writers)):return _case(s,complaint_service.complete_recall(s,key,recall,b,u))
@router.post('/complaints/{key}/close')
def close(key:int,b:CloseInput,s=Depends(db_session),u=Depends(admin)):return _case(s,complaint_service.close(s,key,b,u))
@router.get('/job-verifications')
def verifications(s=Depends(db_session),u=Depends(current)):return [pack(x) for x in s.scalars(select(JobVerification).order_by(JobVerification.id.desc()))]
@router.post('/job-verifications/{key}/resolve')
def resolve(key:int,b:VerificationInput,s=Depends(db_session),u=Depends(admin)):return pack(complaint_service.resolve_verification(s,key,b,u))
