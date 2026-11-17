from datetime import date
from sqlalchemy import select
from fastapi import HTTPException
from .models import PrintJob
from .dispatch_models import PressMachine,PressInspection
from .paper_service import locked
from .services import audit

def record(s,b,u,key=None):
    locked(s,PrintJob,b.job_id);machine=locked(s,PressMachine,b.machine_id)
    row=locked(s,PressInspection,key) if key else PressInspection()
    if key and (row.state!='draft' or row.job_id!=b.job_id):raise HTTPException(409,'仅草稿点检可修订，关联工单不可改')
    for k,v in b.model_dump().items():setattr(row,k,v)
    s.add(row);audit(s,u,f'印机点检 工单{b.job_id} {machine.code}');s.commit();return row

def approve(s,key,u):
    ref=s.get(PressInspection,key)
    if not ref:raise HTTPException(404,'点检不存在')
    locked(s,PrintJob,ref.job_id);row=locked(s,PressInspection,key);machine=locked(s,PressMachine,row.machine_id)
    if row.state!='draft' or row.inspection_date!=date.today() or not row.lubricated or not row.guards_checked or machine.state!='ready':raise HTTPException(409,'须今日润滑及防护确认、印机非保养状态的草稿点检')
    row.state='approved';row.approved_by=u.email;audit(s,u,f'主管认可开机点检{key}');s.commit();return row

def ready(s,jid):
    row=s.scalar(select(PressInspection).where(PressInspection.job_id==jid).order_by(PressInspection.id.desc()).with_for_update().execution_options(populate_existing=True))
    if not row or row.state!='approved' or row.inspection_date!=date.today():raise HTTPException(409,'须最新一条为今日已认可点检，旧点检不能代替新草稿')
    machine=locked(s,PressMachine,row.machine_id)
    if machine.state!='ready':raise HTTPException(409,'印机处于保养状态，禁止新执行与抽检')
    return row
