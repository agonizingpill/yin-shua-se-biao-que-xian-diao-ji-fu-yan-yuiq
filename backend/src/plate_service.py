from sqlalchemy import select
from fastapi import HTTPException
from .models import PrintJob
from .production_models import PlateSet
from .services import get,audit

def require_ready(s,job_id):
    plate=s.scalar(select(PlateSet).where(PlateSet.job_id==job_id).order_by(PlateSet.id.desc()).with_for_update())
    if not plate or plate.state!='ready' or plate.registration_error_mm is None or plate.registration_error_mm>.15:raise HTTPException(409,'当前印版版本尚未主管认可就绪，不能执行调机或量产')
    return plate

def create(s,p,u):
    if not s.scalar(select(PrintJob).where(PrintJob.id==p.job_id).with_for_update()):raise HTTPException(404,'工单不存在')
    if s.scalar(select(PlateSet).where(PlateSet.job_id==p.job_id,PlateSet.version==p.version)):raise HTTPException(409,'该工单印版版本已存在')
    plate=PlateSet(**p.model_dump());s.add(plate);audit(s,u,f'登记印版 {p.version} 工单{p.job_id} 来源{p.source_note}');s.commit();return plate

def measure(s,key,p,u):
    plate=s.scalar(select(PlateSet).where(PlateSet.id==key).with_for_update())
    if not plate:raise HTTPException(404,'印版不存在')
    if plate.state=='ready':raise HTTPException(409,'就绪印版套准证据已冻结，请建立新版本')
    plate.registration_error_mm=p.registration_error_mm;plate.state='measured'
    audit(s,u,f'印版套准测量 {plate.version} {p.registration_error_mm}mm');s.commit();return plate

def approve(s,key,u):
    plate=s.scalar(select(PlateSet).where(PlateSet.id==key).with_for_update())
    if not plate:raise HTTPException(404,'印版不存在')
    if plate.state!='measured' or plate.registration_error_mm is None:raise HTTPException(409,'须先测量套准，且不能重复认可')
    if plate.registration_error_mm>.15:raise HTTPException(409,'套准误差超过0.15mm，不能认可就绪')
    plate.state='ready';plate.approved_by=u.email;audit(s,u,f'主管认可印版 {plate.version} 就绪');s.commit();return plate
