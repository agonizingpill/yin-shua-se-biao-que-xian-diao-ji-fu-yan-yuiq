import os,redis
from fastapi import APIRouter,Depends
from sqlalchemy import select
from .db import db_session
from .auth import current,writers,admin
from .schemas import ProofInput
from .production_models import PlateSet,PressSample,PressHold
from .production_schemas import PlateInput,MeasurementInput,SampleInput,HoldClose
from .services import pack
from . import plate_service,sampling_service
router=APIRouter();queue=redis.Redis.from_url(os.environ['REDIS_URL'],decode_responses=True)
@router.get('/plates')
def plates(s=Depends(db_session),u=Depends(current)):return [pack(x) for x in s.scalars(select(PlateSet).order_by(PlateSet.id.desc()))]
@router.post('/plates')
def create(p:PlateInput,s=Depends(db_session),u=Depends(writers)):return pack(plate_service.create(s,p,u))
@router.post('/plates/{key}/measure')
def measure(key:int,p:MeasurementInput,s=Depends(db_session),u=Depends(writers)):return pack(plate_service.measure(s,key,p,u))
@router.post('/plates/{key}/approve')
def approve(key:int,s=Depends(db_session),u=Depends(admin)):return pack(plate_service.approve(s,key,u))
@router.get('/press-samples')
def samples(s=Depends(db_session),u=Depends(current)):return [pack(x) for x in s.scalars(select(PressSample).order_by(PressSample.id.desc()))]
@router.post('/press-samples')
def sample(p:SampleInput,s=Depends(db_session),u=Depends(writers)):return pack(sampling_service.sample(s,p,u,queue))
@router.get('/press-holds')
def holds(s=Depends(db_session),u=Depends(current)):return [pack(x) for x in s.scalars(select(PressHold).order_by(PressHold.id.desc()))]
@router.post('/press-holds/{key}/recheck')
def recheck(key:int,p:ProofInput,s=Depends(db_session),u=Depends(writers)):return pack(sampling_service.recheck(s,key,p,u,queue))
@router.post('/press-holds/{key}/close')
def close(key:int,p:HoldClose,s=Depends(db_session),u=Depends(admin)):return pack(sampling_service.close(s,key,p,u))
