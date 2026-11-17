import re
from sqlalchemy import select,func
from fastapi import HTTPException
from .models import PrintJob
from .production_models import PressSample
from .dispatch_models import PaperLot,PaperIssue
from .services import audit

def locked(s,cls,key):
    row=s.scalar(select(cls).where(cls.id==key).with_for_update().execution_options(populate_existing=True))
    if not row:raise HTTPException(404,'记录不存在')
    return row

def net_paper(s,jid):return int(s.scalar(select(func.coalesce(func.sum(PaperIssue.sheets-PaperIssue.returned_sheets),0)).where(PaperIssue.job_id==jid)))
def printed(s,jid):return int(s.scalar(select(func.coalesce(func.max(PressSample.quantity),0)).where(PressSample.job_id==jid)))

def issue(s,b,u):
    j=locked(s,PrintJob,b.job_id)
    if j.status not in ['setup','adjusting','production']:raise HTTPException(409,'仅计划、调机或量产工单可领纸')
    lot=locked(s,PaperLot,b.lot_id);match=re.search(r'(\d+)\s*g',j.paper,re.I)
    if not match or int(match.group(1))!=lot.gsm:raise HTTPException(409,'纸张克重须匹配工单paper中的g数')
    if lot.state!='active' or lot.available_sheets<b.sheets:raise HTTPException(409,'纸张隔离或库存不足')
    lot.available_sheets-=b.sheets;row=PaperIssue(**b.model_dump(),paper_snapshot=j.paper,issued_by=u.email);s.add(row);audit(s,u,f'上机领纸 {j.code} {b.sheets}张');s.commit();return row

def return_unused(s,key,b,u):
    ref=s.get(PaperIssue,key)
    if not ref:raise HTTPException(404,'领料不存在')
    j=locked(s,PrintJob,ref.job_id);row=locked(s,PaperIssue,key)
    if row.returned_by:raise HTTPException(409,'该领料已办理一次余纸退回')
    if b.sheets>row.sheets or net_paper(s,j.id)-b.sheets<printed(s,j.id):raise HTTPException(409,'只能退未使用余纸，净领纸不得低于累计已印张数')
    if len(b.note.strip())<5:raise HTTPException(409,'退纸依据至少5字')
    lot=locked(s,PaperLot,row.lot_id);lot.available_sheets+=b.sheets;row.returned_sheets=b.sheets;row.returned_by=u.email;row.return_note=b.note.strip();audit(s,u,f'余纸退回 {j.code} {b.sheets}张');s.commit();return row

def sample_guard(s,jid,quantity):
    last=printed(s,jid)
    if quantity<last:raise HTTPException(409,'已印数量为累计读数，不得低于历史累计已印张数')
    if quantity>net_paper(s,jid):raise HTTPException(409,'累计已印张数超过净领纸数，请先补领纸')
