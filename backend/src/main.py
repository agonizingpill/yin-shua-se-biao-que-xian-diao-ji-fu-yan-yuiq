import os,logging
from contextlib import asynccontextmanager
import redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import FastAPI,Depends,HTTPException
from fastapi.responses import JSONResponse
from .db import Base,engine,db_session
from .models import User,PrintJob,ProofSheet,Adjustment,Audit
from .auth import current,writers,admin,verify,token
from .schemas import Login,JobInput,ProofInput,AdjustmentInput,InstructionInput,ReproofInput
from .services import get,pack,audit,editable_proof,issue,change_instruction,sign,now
from .middlewares import RequestTrace,BurstGuard
from .production_routes import router as production
from .dispatch_routes import router as dispatches
from .plate_service import require_ready
from .paper_service import locked
from .constants import ROLES,DEFECTS,JOB_STATES,ADJUSTMENT_STATES
r=redis.Redis.from_url(os.environ['REDIS_URL'],decode_responses=True)
@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    if os.getenv('SEED_DEMO','true')=='true':
        try:
            from scripts.seed_demo import seed
            seed()
        except Exception:logging.exception('seed failed')
    yield
app=FastAPI(title='铅叶 · 色标缺陷与调机复验',lifespan=lifespan);app.add_middleware(RequestTrace);app.add_middleware(BurstGuard)
@app.exception_handler(IntegrityError)
async def conflict(req,exc):return JSONResponse({'detail':'工单、色标编号或首张调机指令重复，请核对'},409)
app.include_router(production);app.include_router(dispatches)
@app.get('/health')
def health(s=Depends(db_session)):s.execute(select(1));r.ping();return {'status':'ok'}
@app.post('/auth/login')
def login(p:Login,s=Depends(db_session)):
    u=s.scalar(select(User).where(User.email==p.email))
    if not u or not verify(p.password,u.password_hash):raise HTTPException(401,'邮箱或口令不正确')
    return {'token':token(u),'user':{'email':u.email,'role':u.role}}
@app.get('/me')
def me(u=Depends(current)):return {'email':u.email,'role':u.role}
@app.get('/enums')
def enums(u=Depends(current)):return {'roles':ROLES,'defects':DEFECTS,'job_states':JOB_STATES,'adjustment_states':ADJUSTMENT_STATES}
@app.get('/jobs')
def jobs(s=Depends(db_session),u=Depends(current)):return [pack(x)for x in s.scalars(select(PrintJob).order_by(PrintJob.id))]
@app.post('/jobs')
def add_job(p:JobInput,s=Depends(db_session),u=Depends(writers)):
    j=PrintJob(**p.model_dump(),status='setup');s.add(j);audit(s,u,'登记开机单 '+p.code);s.commit();return pack(j)
@app.put('/jobs/{jid}')
def edit_job(jid:int,p:JobInput,s=Depends(db_session),u=Depends(writers)):
    j=locked(s,PrintJob,jid)
    if j.status!='setup'or s.scalar(select(ProofSheet.id).where(ProofSheet.job_id==jid,ProofSheet.classification_state.in_(['classifying','classified']))):raise HTTPException(409,'已有判读或调机，工单纸张与目标密度冻结')
    from .dispatch_models import PaperIssue
    if p.paper!=j.paper and s.scalar(select(PaperIssue.id).where(PaperIssue.job_id==jid)):raise HTTPException(409,'已有领纸，工单纸张冻结')
    for k,value in p.model_dump().items():setattr(j,k,value)
    audit(s,u,'修订开机单 '+j.code);s.commit();return pack(j)
@app.get('/proofs')
def proofs(s=Depends(db_session),u=Depends(current)):return [pack(x)for x in s.scalars(select(ProofSheet).order_by(ProofSheet.id))]
@app.post('/proofs')
def add_proof(p:ProofInput,s=Depends(db_session),u=Depends(writers)):
    j=get(s,PrintJob,p.job_id)
    if j.status in ['production','hold']:raise HTTPException(409,'量产或停机工单请通过量产抽检/停机复验录入新色标')
    x=ProofSheet(**p.model_dump());s.add(x);audit(s,u,'登记色标 '+p.code);s.commit();return pack(x)
@app.put('/proofs/{pid}')
def edit_proof(pid:int,p:ProofInput,s=Depends(db_session),u=Depends(writers)):
    x=get(s,ProofSheet,pid);editable_proof(s,x)
    if p.job_id!=x.job_id:raise HTTPException(409,'色标不得转移到其他工单')
    for k,value in p.model_dump().items():setattr(x,k,value)
    x.defect=None;x.pass_flag=False;x.evidence=None;x.classification_state='unmeasured';x.classified_at=None;audit(s,u,'修订色标 '+x.code);s.commit();return pack(x)
@app.post('/proofs/{pid}/classify')
def classify(pid:int,s=Depends(db_session),u=Depends(writers)):
    x=get(s,ProofSheet,pid);editable_proof(s,x);x.classification_state='classifying';x.defect=None;x.pass_flag=False;x.evidence=None;x.classified_at=None;audit(s,u,'色标判读入队 '+x.code);s.commit()
    try:r.rpush('press-classify',pid)
    except Exception:x.classification_state='failed';s.commit();raise HTTPException(503,'判读队列暂不可用，请重试')
    return pack(x)
@app.get('/adjustments')
def adjustments(s=Depends(db_session),u=Depends(current)):return [pack(x)for x in s.scalars(select(Adjustment).order_by(Adjustment.id))]
@app.post('/adjustments')
def create_adjustment(p:AdjustmentInput,s=Depends(db_session),u=Depends(writers)):
    x=issue(s,p.proof_id);audit(s,u,'生成调机指令 色标#'+str(p.proof_id));s.commit();return pack(x)
@app.patch('/adjustments/{aid}')
def patch_instruction(aid:int,p:InstructionInput,s=Depends(db_session),u=Depends(writers)):
    x=get(s,Adjustment,aid);change_instruction(s,x,p);audit(s,u,'修订调机指令#'+str(aid));s.commit();return pack(x)
@app.post('/adjustments/{aid}/execute')
def execute(aid:int,s=Depends(db_session),u=Depends(writers)):
    x=s.query(Adjustment).filter_by(id=aid).with_for_update().one_or_none()
    if not x:raise HTTPException(404,'调机指令不存在')
    if x.status!='issued':raise HTTPException(409,'仅待执行指令可登记执行')
    s.query(PrintJob).filter_by(id=x.job_id).with_for_update().one()
    require_ready(s,x.job_id)
    from .inspection_service import ready
    ready(s,x.job_id)
    x.status='executed';x.executed_at=now();audit(s,u,'登记调机执行#'+str(aid));s.commit();return pack(x)
@app.post('/adjustments/{aid}/sign')
def approve(aid:int,p:ReproofInput,s=Depends(db_session),u=Depends(admin)):
    x=sign(s,aid,p.reproof_id,u);audit(s,u,'主管签印#'+str(aid));s.commit();return pack(x)
@app.get('/audits')
def audits(s=Depends(db_session),u=Depends(current)):return [pack(x)for x in s.scalars(select(Audit).order_by(Audit.id.desc()).limit(30))]
