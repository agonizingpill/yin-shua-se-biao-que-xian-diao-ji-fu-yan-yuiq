from sqlalchemy import select,func
from fastapi import HTTPException
from .models import PrintJob,ProofSheet
from .production_models import PressSample,PressHold
from .services import get,audit,now,pack
from .plate_service import require_ready

def queue(s,proof,r):
    # Save before enqueue so the worker can see the new proof. A failed queue write
    # is converted into a persistent stop record instead of allowing silent production.
    s.commit()
    try:r.rpush('press-classify',proof.id)
    except Exception:
        proof.classification_state='failed';proof.evidence={'error':'判读队列暂不可用'};finish(s,proof);s.commit();raise HTTPException(503,'判读队列暂不可用，已保留待处置记录')

def sample(s,p,u,r):
    job=s.scalar(select(PrintJob).where(PrintJob.id==p.job_id).with_for_update())
    if not job:raise HTTPException(404,'工单不存在')
    if job.status!='production' or s.scalar(select(PressHold).where(PressHold.job_id==job.id,PressHold.state=='active')):raise HTTPException(409,'仅无停机单的量产工单可以抽检，须先复验并主管复机')
    plate=require_ready(s,job.id)
    from .inspection_service import ready
    from .paper_service import sample_guard
    ready(s,job.id);sample_guard(s,job.id,p.quantity)
    if s.scalar(select(PressSample).where(PressSample.job_id==job.id,PressSample.state=='classifying')):raise HTTPException(409,'上一张量产抽检尚在判读，请等待结果')
    last=s.scalar(select(func.max(PressSample.sequence)).where(PressSample.job_id==job.id)) or 0
    if p.sequence<=last:raise HTTPException(409,'抽检序号须递增，不得重复或倒序')
    if s.scalar(select(ProofSheet).where(ProofSheet.code==p.code)):raise HTTPException(409,'量产抽检必须使用新的唯一色标编号')
    values=p.model_dump();seq=values.pop('sequence');qty=values.pop('quantity')
    proof=ProofSheet(**values,classification_state='classifying');s.add(proof);s.flush()
    item=PressSample(job_id=job.id,proof_id=proof.id,plate_id=plate.id,sequence=seq,quantity=qty,plate_snapshot={'version':plate.version,'registration_error_mm':plate.registration_error_mm,'source_note':plate.source_note,'approved_by':plate.approved_by});s.add(item)
    audit(s,u,f'量产抽检 工单{job.code} 序{seq} 已印{qty}张 色标{proof.code}');queue(s,proof,r);return item

def finish(s,proof):
    item=s.scalar(select(PressSample).where(PressSample.proof_id==proof.id).with_for_update())
    if not item or item.state!='classifying':return
    job=s.scalar(select(PrintJob).where(PrintJob.id==item.job_id).with_for_update())
    if proof.classification_state=='classified' and proof.pass_flag and proof.defect=='合格':item.state='passed';return
    item.state='held';job.status='hold'
    hold=PressHold(job_id=job.id,sample_id=item.id,reason='量产抽检 '+proof.code+' / '+(proof.defect or '判读失败'),created_at=now(),reproof_ids=[]);s.add(hold)

def recheck(s,key,p,u,r):
    current=get(s,PressHold,key)
    job=s.scalar(select(PrintJob).where(PrintJob.id==current.job_id).with_for_update())
    hold=s.scalar(select(PressHold).where(PressHold.id==key).with_for_update())
    if hold.state!='active' or job.status!='hold':raise HTTPException(409,'仅活动停机单可以登记复机复验')
    if p.job_id!=job.id:raise HTTPException(409,'复机色标必须来自停机单同一工单')
    if hold.reproof_id and get(s,ProofSheet,hold.reproof_id).classification_state=='classifying':raise HTTPException(409,'上一张复验仍在判读，请等待')
    if s.scalar(select(ProofSheet).where(ProofSheet.code==p.code)):raise HTTPException(409,'停机后须重新取样，不能复用已有色标')
    proof=ProofSheet(**p.model_dump(),classification_state='classifying');s.add(proof);s.flush();hold.reproof_id=proof.id;hold.reproof_ids=[*(hold.reproof_ids or []),proof.id]
    audit(s,u,f'停机复验 {key} 新色标{p.code}');queue(s,proof,r);return hold

def close(s,key,p,u):
    current=get(s,PressHold,key);job=s.scalar(select(PrintJob).where(PrintJob.id==current.job_id).with_for_update());hold=s.scalar(select(PressHold).where(PressHold.id==key).with_for_update())
    if hold.state!='active' or job.status!='hold':raise HTTPException(409,'停机单已关闭，不能重复复机')
    require_ready(s,job.id)
    if not hold.reproof_id:raise HTTPException(409,'须登记停机后的新色标复验')
    proof=get(s,ProofSheet,hold.reproof_id)
    if proof.job_id!=job.id or proof.classification_state!='classified' or not proof.pass_flag or proof.defect!='合格' or not proof.classified_at or proof.classified_at<hold.created_at:raise HTTPException(409,'停机后新色标未判为合格，不能复机')
    hold.state='closed';hold.resolution=p.resolution;hold.closed_by=u.email;hold.closed_at=now();job.status='production'
    audit(s,u,f'主管复机 停机单{key} 依据{p.resolution}');s.commit();return hold
