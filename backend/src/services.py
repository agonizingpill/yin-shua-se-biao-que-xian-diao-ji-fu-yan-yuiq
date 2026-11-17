from datetime import datetime,timezone
from sqlalchemy import select,or_
from fastapi import HTTPException
from .models import PrintJob,ProofSheet,Adjustment,Audit

def now():return datetime.now(timezone.utc).isoformat()
def get(s,cls,id):
    v=s.get(cls,id)
    if not v:raise HTTPException(404,'记录不存在')
    return v
def pack(v):return {c.name:getattr(v,c.name)for c in v.__table__.columns}
def audit(s,u,action):s.add(Audit(actor=u.email,action=action,stamp=now()))
def editable_proof(s,p):
    if p.classification_state=='classifying':raise HTTPException(409,'判读进行中，色标暂不可修改')
    if get(s,PrintJob,p.job_id).status in ['production','hold']:raise HTTPException(409,'已签印量产工单，色标已冻结')
    if s.scalar(select(Adjustment.id).where(or_(Adjustment.proof_id==p.id,Adjustment.reproof_id==p.id))):raise HTTPException(409,'已关联调机或签印，源色标冻结')
def issue(s,proof_id):
    p=get(s,ProofSheet,proof_id);job=get(s,PrintJob,p.job_id)
    if job.status in ['production','hold']:raise HTTPException(409,'量产或停机工单须使用抽检/停机复验流程')
    if p.classification_state!='classified' or p.defect not in ('乳化','偏色'):raise HTTPException(409,'仅已判读的不合格色标可生成调机指令')
    if s.scalar(select(Adjustment.id).where(Adjustment.job_id==job.id,Adjustment.status!='signed')):raise HTTPException(409,'本工单已有未闭合调机，请先完成复验')
    ink,water=(0,-8)if p.defect=='乳化'else(-6,0)
    a=Adjustment(job_id=job.id,proof_id=p.id,ink_delta=ink,water_delta=water,status='issued');s.add(a);job.status='adjusting';return a

def change_instruction(s,a,data):
    if a.status!='issued':raise HTTPException(409,'已执行调机指令不可修改')
    p=get(s,ProofSheet,a.proof_id)
    if p.defect=='乳化'and data.water_delta>=0:raise HTTPException(409,'乳化须减供水，调水量必须为负')
    if p.defect=='偏色'and data.ink_delta==0:raise HTTPException(409,'偏色调机须有非零供墨修订')
    a.ink_delta=data.ink_delta;a.water_delta=data.water_delta

def sign(s,aid,reproof_id,user):
    a=s.query(Adjustment).filter_by(id=aid).with_for_update().one_or_none()
    if not a:raise HTTPException(404,'调机指令不存在')
    if a.status!='executed':raise HTTPException(409,'请先登记调机执行；已签印不能重复签印')
    job=s.query(PrintJob).filter_by(id=a.job_id).with_for_update().one()
    if job.status!='adjusting':raise HTTPException(409,'工单不在待复验状态')
    p=get(s,ProofSheet,reproof_id)
    if p.id==a.proof_id or p.job_id!=job.id:raise HTTPException(409,'复验张必须来自同一工单且不同于首张')
    if p.classification_state!='classified'or not p.pass_flag or p.defect!='合格':raise HTTPException(409,'复验张未判为合格，禁止恢复量产')
    if not p.classified_at or p.classified_at<a.executed_at:raise HTTPException(409,'复验判读必须在调机执行之后完成')
    from .plate_service import require_ready
    require_ready(s,job.id)
    a.reproof_id=p.id;a.status='signed';a.signed_by=user.email;job.status='production';return a
