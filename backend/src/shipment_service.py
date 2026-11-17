from sqlalchemy import select,func
from fastapi import HTTPException
from .models import PrintJob,ProofSheet
from .production_models import PressSample,PressHold
from .dispatch_models import PrintPack,PrintShipment,ShipmentPack
from .paper_service import locked,net_paper
from .services import audit

def gate(s,j):
    if j.status!='production' or s.scalar(select(PressHold.id).where(PressHold.job_id==j.id,PressHold.state=='active')):raise HTTPException(409,'须无活动停机单的量产工单')
    if s.scalar(select(PressSample.id).where(PressSample.job_id==j.id,PressSample.state=='classifying')):raise HTTPException(409,'抽检待判读，不能封箱或发货')
    sample=s.scalar(select(PressSample).where(PressSample.job_id==j.id,PressSample.state=='passed').order_by(PressSample.sequence.desc()))
    if not sample:raise HTTPException(409,'须有合格量产抽检才可装箱发货')
    proof=s.get(ProofSheet,sample.proof_id)
    return {'sample_id':sample.id,'sequence':sample.sequence,'quantity':sample.quantity,'proof_code':proof.code,'plate':sample.plate_snapshot,'net_paper':net_paper(s,j.id)}
def sealed(s,jid):return int(s.scalar(select(func.coalesce(func.sum(PrintPack.sheets),0)).where(PrintPack.job_id==jid,PrintPack.state.in_(['sealed','shipped']))))

def create_pack(s,b,u):
    j=locked(s,PrintJob,b.job_id);e=gate(s,j)
    if b.sheets>min(e['quantity'],e['net_paper']):raise HTTPException(409,'单箱张数超最后合格抽检或净领纸')
    row=PrintPack(**b.model_dump());s.add(row);audit(s,u,f'登记待封箱 {b.code} {b.sheets}张');s.commit();return row

def pack_action(s,key,u,action):
    ref=s.get(PrintPack,key)
    if not ref:raise HTTPException(404,'箱码不存在')
    j=locked(s,PrintJob,ref.job_id);row=locked(s,PrintPack,key)
    if row.state!='open':raise HTTPException(409,'仅未封箱可封签或取消；封签后数量冻结')
    if action=='cancel':row.state='cancelled'
    else:
        e=gate(s,j)
        if sealed(s,j.id)+row.sheets>min(e['quantity'],e['net_paper']):raise HTTPException(409,'封箱累计张数超最后合格抽检或净领纸')
        row.state='sealed';row.sample_snapshot=e
    audit(s,u,f'成品箱{key} {action}');s.commit();return row

def create_shipment(s,b,u):
    j=locked(s,PrintJob,b.job_id);gate(s,j)
    if len(set(b.pack_ids))!=len(b.pack_ids):raise HTTPException(409,'箱单包含重复箱码')
    boxes=[locked(s,PrintPack,k) for k in sorted(b.pack_ids)]
    for box in boxes:
        if box.job_id!=j.id or box.state!='sealed' or s.scalar(select(ShipmentPack.id).where(ShipmentPack.pack_id==box.id)):raise HTTPException(409,'箱码须同工单、已封且未被其他发货单占用')
    row=PrintShipment(job_id=j.id,tracking=b.tracking,customer=b.customer);s.add(row);s.flush()
    for box in boxes:s.add(ShipmentPack(shipment_id=row.id,pack_id=box.id))
    audit(s,u,f'编制发货单{b.tracking} {len(boxes)}箱');s.commit();return row

def dispatch(s,key,u):
    ref=s.get(PrintShipment,key)
    if not ref:raise HTTPException(404,'发货单不存在')
    j=locked(s,PrintJob,ref.job_id);row=locked(s,PrintShipment,key)
    if row.state!='draft':raise HTTPException(409,'发货已出库，不得重复装运')
    e=gate(s,j);ids=s.scalars(select(ShipmentPack.pack_id).where(ShipmentPack.shipment_id==row.id)).all();boxes=[locked(s,PrintPack,k) for k in sorted(ids)]
    if not boxes or any(x.job_id!=j.id or x.state!='sealed' for x in boxes):raise HTTPException(409,'箱单不完整或未封箱')
    if sealed(s,j.id)>min(e['quantity'],e['net_paper']):raise HTTPException(409,'已封总量超过合格数量/净领纸，禁止发货')
    row.snapshot={'job_code':j.code,'paper':j.paper,'customer':row.customer,'tracking':row.tracking,'quality':e,'boxes':[{'id':x.id,'code':x.code,'sheets':x.sheets,'sample_snapshot':x.sample_snapshot} for x in boxes],'total_sheets':sum(x.sheets for x in boxes)}
    for box in boxes:box.state='shipped'
    row.state='dispatched';row.dispatched_by=u.email;audit(s,u,f'主管装运{row.tracking} 冻结{len(boxes)}箱');s.commit();return row

def receive(s,key,b,u):
    ref=s.get(PrintShipment,key)
    if not ref:raise HTTPException(404,'发货单不存在')
    locked(s,PrintJob,ref.job_id);row=locked(s,PrintShipment,key)
    if row.state!='dispatched':raise HTTPException(409,'须主管装运后客户签收，不得重复')
    if len(b.received_by.strip())<2:raise HTTPException(409,'签收人不能为空')
    row.state='received';row.received_by=b.received_by.strip();audit(s,u,f'客户签收{row.tracking} {row.received_by}');s.commit();return row
