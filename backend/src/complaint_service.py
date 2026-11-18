from sqlalchemy import select
from fastapi import HTTPException
from .models import PrintJob,ProofSheet
from .production_models import PressSample
from .dispatch_models import PrintPack,PrintShipment,ShipmentPack
from .complaint_models import Complaint,ComplaintBox,ComplaintRecall,JobVerification
from .paper_service import locked
from .services import get,audit,now

FREEZING=('accepted','blocked','defect')
FINAL=('released','closed')

def frozen_samples(s,job_id):
    """当前被客诉冻结的同批合格抽检依据。"""
    return set(s.scalars(select(Complaint.basis_sample_id).where(Complaint.job_id==job_id,Complaint.state.in_(FREEZING),Complaint.basis_sample_id.is_not(None))))

def release_guard(s,job_id,sample_id=None,boxes=None):
    """封箱、发货前统一检查客诉冻结与待核实旧箱依据。

    客诉冻结只作用于按原箱合格抽检依据追溯出的同批箱；后续以新合格抽检
    封箱的产品不属于该批。待核实旧箱依据则拦住整个开机单。
    """
    v=s.scalar(select(JobVerification).where(JobVerification.job_id==job_id,JobVerification.state=='pending').order_by(JobVerification.id))
    if v:raise HTTPException(409,'开机单存在缺失封箱依据的旧箱，须主管核实后才能封箱发货')
    frozen=frozen_samples(s,job_id)
    if sample_id in frozen:raise HTTPException(409,'该批已因客诉冻结放行，须主管解除或逐箱处置后才能封箱发货；生产复机不解除箱隔离')
    for b in boxes or []:
        snap=b.sample_snapshot or {}
        if snap.get('sample_id') in frozen:raise HTTPException(409,f'箱{b.code}属于客诉冻结批次，不能装运；须主管解除或逐箱处置')

def verification_pending(s,job_id):
    return s.scalar(select(JobVerification.id).where(JobVerification.job_id==job_id,JobVerification.state=='pending')) is not None

def _shipment_for(s,pack_id):
    return s.scalar(select(ShipmentPack.shipment_id).where(ShipmentPack.pack_id==pack_id))

def _sample_for_snapshot(s,snap):
    """按封箱快照中的合格抽检依据找回 PressSample，并校验证据仍为合格。"""
    if not snap:return None
    sample=s.get(PressSample,int(snap['sample_id'])) if snap.get('sample_id') else None
    if not sample and snap.get('proof_code'):
        proof=s.scalar(select(ProofSheet).where(ProofSheet.code==snap['proof_code']))
        if proof:sample=s.scalar(select(PressSample).where(PressSample.proof_id==proof.id))
    if not sample:return None
    proof=s.get(ProofSheet,sample.proof_id)
    if not proof or sample.state!='passed' or proof.classification_state!='classified' or not proof.pass_flag or proof.defect!='合格':return None
    return sample

def _scan(s,job,ignore=None):
    """锁定并分拣同工单已封/已发箱；依据缺失或证据失效的箱独立列出，绝不静默漏箱。"""
    rows=s.scalars(select(PrintPack).where(PrintPack.job_id==job.id,PrintPack.state.in_(['sealed','shipped'])).order_by(PrintPack.id).with_for_update()).all()
    groups={};missing=[]
    for p in rows:
        if ignore and p.id==ignore:continue
        sample=_sample_for_snapshot(s,p.sample_snapshot)
        if not sample or (p.state=='shipped' and not _shipment_for(s,p.id)):missing.append(p);continue
        groups.setdefault(sample.id,[]).append((p,sample))
    return groups,missing

def _snap(s,p,sample):
    return {'pack_code':p.code,'pack_state':p.state,'sheets':p.sheets,'sample_id':sample.id,'sequence':sample.sequence,'quantity':sample.quantity,'proof_code':s.get(ProofSheet,sample.proof_id).code}

def _recall(s,c,shipment_id):
    row=s.scalar(select(ComplaintRecall).where(ComplaintRecall.complaint_id==c.id,ComplaintRecall.shipment_id==shipment_id).with_for_update())
    if row:return row
    ship=s.get(PrintShipment,shipment_id)
    row=ComplaintRecall(complaint_id=c.id,shipment_id=shipment_id,state='pending',tracking=ship.tracking if ship else '',customer=ship.customer if ship else '',shipment_snapshot={'tracking':ship.tracking,'customer':ship.customer,'state':ship.state,'dispatched_by':ship.dispatched_by,'snapshot':ship.snapshot} if ship else {},created_at=now())
    s.add(row);s.flush();return row

def _apply(s,c,returned,basis,group):
    """建立受影响箱记录：退回箱 + 同批未发箱隔离 + 同批已发箱登记待召回。

    客诉+箱唯一，重复追溯（受理/缺陷补齐/重试）不会重复建箱或重复召回。
    """
    for p,sample in [(returned,basis)]+group:
        p=locked(s,PrintPack,p.id)
        existing=s.scalar(select(ComplaintBox).where(ComplaintBox.complaint_id==c.id,ComplaintBox.pack_id==p.id).with_for_update())
        if existing:continue
        shipment_id=_shipment_for(s,p.id)
        original=p.state
        snap=_snap(s,p,sample)
        if p.id==returned.id:
            kind,state='returned','returned';p.state='returned'
        elif p.state=='sealed':
            kind,state='unshipped','quarantined';p.state='quarantined'
        else:
            kind,state='shipped','recall_pending'
            if not shipment_id:raise HTTPException(409,f'已发箱{p.code}缺少装运记录，不能登记召回')
            _recall(s,c,shipment_id)
        s.add(ComplaintBox(complaint_id=c.id,pack_id=p.id,shipment_id=shipment_id,kind=kind,state=state,original_state=original,pack_snapshot=snap))

def _verification(s,c,job,reason):
    prior=s.scalar(select(JobVerification).where(JobVerification.job_id==job.id,JobVerification.state=='pending').with_for_update())
    if not prior:
        prior=JobVerification(job_id=job.id,complaint_id=c.id,pack_id=c.pack_id,reason=reason[:300],prior_status=job.status,state='pending')
        s.add(prior)
    return prior

def _block(s,c,job,reason,u):
    _verification(s,c,job,reason);c.state='blocked';audit(s,u,f'客诉{c.code}原箱依据缺失，拦住开机单{job.code}待核实');s.commit()
    raise HTTPException(409,reason+'；已拦住该开机单，须主管核实后才可放行')

def _is_defect(proof):
    return proof.classification_state=='classified' and proof.defect in ('乳化','偏色') and not proof.pass_flag

def create(s,p,u,r):
    ref=s.get(PrintPack,p.pack_id)
    if not ref:raise HTTPException(404,'成品箱不存在')
    job=locked(s,PrintJob,ref.job_id);row=locked(s,PrintPack,p.pack_id)
    if row.state not in ('sealed','shipped'):raise HTTPException(409,'客诉须从已封箱或已装运的原箱登记')
    open_case=s.scalar(select(Complaint).where(Complaint.pack_id==row.id,Complaint.state.not_in(FINAL)))
    if open_case:raise HTTPException(409,f'该箱已有未结案客诉 {open_case.code}')
    if s.scalar(select(ProofSheet.id).where(ProofSheet.code==p.proof_code)):raise HTTPException(409,'客诉复测色标编号已存在')
    proof=ProofSheet(job_id=job.id,code=p.proof_code,density_c=p.density_c,density_m=p.density_m,density_y=p.density_y,density_k=p.density_k,dot_gain=p.dot_gain,classification_state='classifying')
    s.add(proof);s.flush()
    c=Complaint(code=p.code,job_id=job.id,pack_id=row.id,proof_id=proof.id,state='registered',note=p.note.strip(),created_by=u.email,created_at=now())
    s.add(c);s.flush()
    if not _sample_for_snapshot(s,row.sample_snapshot):
        _verification(s,c,job,'原箱封箱时的合格抽检依据缺失，待主管核实')
        audit(s,u,f'客诉{c.code}原箱{row.code}依据缺失，拦住开机单{job.code}待核实')
    audit(s,u,f'客诉登记 {p.code} 原箱{row.code} 复测色标{p.proof_code}');s.commit()
    try:r.rpush('press-classify',proof.id)
    except Exception:
        proof.classification_state='failed';proof.evidence={'error':'判读队列暂不可用'};s.commit();raise HTTPException(503,'判读队列暂不可用，客诉已登记，可稍后重试复测')
    return c

def retest(s,key,r,u):
    ref=get(s,Complaint,key);locked(s,PrintJob,ref.job_id);c=locked(s,Complaint,key)
    if c.state in FINAL:raise HTTPException(409,'客诉已结案，不能重测')
    proof=get(s,ProofSheet,c.proof_id)
    if proof.classification_state=='classifying':raise HTTPException(409,'复测色标仍在判读，请等待结果')
    if proof.classification_state=='classified':raise HTTPException(409,'复测色标已有判读结果，不能重复判读')
    proof.classification_state='classifying';proof.defect=None;proof.pass_flag=False;proof.evidence=None;proof.classified_at=None
    audit(s,u,f'客诉复测重试 {c.code} 色标{proof.code}');s.commit()
    try:r.rpush('press-classify',proof.id)
    except Exception:
        proof.classification_state='failed';s.commit();raise HTTPException(503,'判读队列暂不可用，请稍后重试')
    return c

def accept(s,key,u):
    ref=get(s,Complaint,key);job=locked(s,PrintJob,ref.job_id);c=locked(s,Complaint,key)
    if c.state in ('accepted','defect'):return c
    if c.state in FINAL:raise HTTPException(409,'客诉已解除或结案，不能重复受理')
    if c.state=='blocked':raise HTTPException(409,'原箱封箱依据缺失，已拦住开机单，须先完成核实')
    row=locked(s,PrintPack,c.pack_id)
    if row.job_id!=job.id:raise HTTPException(409,'退回箱不属于该开机单')
    if row.state not in ('sealed','shipped'):raise HTTPException(409,'退回箱当前状态不能受理客诉')
    basis=_sample_for_snapshot(s,row.sample_snapshot)
    groups,missing=_scan(s,job,ignore=row.id)
    if basis:
        dup=s.scalar(select(Complaint).where(Complaint.job_id==job.id,Complaint.id!=c.id,Complaint.basis_sample_id==basis.id,Complaint.state.in_(FREEZING)))
        if dup:raise HTTPException(409,f'同批已由客诉 {dup.code} 冻结，不能重复受理同一批箱')
    if not basis or missing:
        reason='原箱封箱时的合格抽检依据缺失'+('：'+'、'.join(p.code for p in missing) if missing else '')
        _block(s,c,job,reason,u)
    _apply(s,c,row,basis,groups.get(basis.id,[]))
    proof=get(s,ProofSheet,c.proof_id)
    c.basis_sample_id=basis.id;c.basis_proof_code=s.get(ProofSheet,basis.proof_id).code;c.basis_snapshot=row.sample_snapshot
    c.accepted_by=u.email;c.accepted_at=now();c.state='defect' if _is_defect(proof) else 'accepted'
    audit(s,u,f'客诉受理 {c.code} 冻结同批箱{len(groups.get(basis.id,[]))}只+退回箱 依据合格抽检#{basis.id}')
    s.commit();return c

def finish(s,proof):
    """worker判读完成后驱动客诉状态；只对已受理客诉生效，并补齐缺陷追溯。

    这里运行在worker事务内，不抛HTTP异常：依据缺失只落待核实并拦住开机单。
    先取工单锁再取客诉锁，与受理/解除等入口保持一致的加锁顺序。
    """
    cid=s.scalar(select(Complaint.id).where(Complaint.proof_id==proof.id))
    if not cid:return
    c0=s.get(Complaint,cid);locked(s,PrintJob,c0.job_id);c=locked(s,Complaint,cid)
    if c.state not in ('accepted','defect'):return
    if proof.classification_state!='classified':return
    if not _is_defect(proof):
        c.state='accepted';return
    c.state='defect'
    if not _trace(s,c):c.state='blocked'

def _trace(s,c):
    """复测判为缺陷后，按原箱合格抽检依据追溯同批箱：未发隔离、已发登记待召回。

    返回 False 表示依据缺失，已登记待核实并拦截开机单。已追溯过的客诉不重扫，
    避免主管核实后又被旧箱快照重新拦住。
    """
    if s.scalar(select(ComplaintBox.id).where(ComplaintBox.complaint_id==c.id).with_for_update()):return True
    job=locked(s,PrintJob,c.job_id)
    basis=_sample_for_snapshot(s,c.basis_snapshot) if c.basis_snapshot else None
    if not basis and c.basis_sample_id:
        cand=s.get(PressSample,c.basis_sample_id);basis=_sample_for_snapshot(s,{'sample_id':cand.id}) if cand else None
    if not basis:
        _verification(s,c,job,'客诉复测缺陷，但原箱封箱依据缺失，待主管核实')
        return False
    if c.basis_sample_id is None:
        c.basis_sample_id=basis.id;c.basis_proof_code=s.get(ProofSheet,basis.proof_id).code
    returned=locked(s,PrintPack,c.pack_id)
    groups,missing=_scan(s,job,ignore=returned.id)
    if missing:
        _verification(s,c,job,'客诉复测缺陷，同批箱'+'、'.join(p.code for p in missing)+'封箱依据缺失，待主管核实')
        return False
    _apply(s,c,returned,basis,groups.get(basis.id,[]))
    return True

def release(s,key,p,u):
    ref=get(s,Complaint,key);job=locked(s,PrintJob,ref.job_id);c=locked(s,Complaint,key)
    if c.state=='released':return c
    if c.state!='accepted':raise HTTPException(409,'仅已受理且复测合格的客诉可由主管解除；缺陷须逐箱处置后结案')
    if verification_pending(s,job.id):raise HTTPException(409,'开机单仍有待核实依据，不能解除放行冻结')
    proof=get(s,ProofSheet,c.proof_id)
    if proof.classification_state!='classified' or not proof.pass_flag or proof.defect!='合格':raise HTTPException(409,'客诉复测未判为合格，不能解除冻结')
    boxes=s.scalars(select(ComplaintBox).where(ComplaintBox.complaint_id==c.id).order_by(ComplaintBox.id).with_for_update()).all()
    for b in boxes:
        if b.kind=='unshipped' and b.state=='quarantined':
            pk=locked(s,PrintPack,b.pack_id)
            if b.original_state=='sealed' and pk.state=='quarantined':pk.state='sealed'
        if b.state!='returned':b.state='released'
    for rec in s.scalars(select(ComplaintRecall).where(ComplaintRecall.complaint_id==c.id).with_for_update()):
        if rec.state=='pending':rec.state='cancelled'
    c.state='released';c.release_note=p.release_note.strip();c.released_by=u.email;c.released_at=now()
    audit(s,u,f'主管解除客诉冻结 {c.code} 依据合格复测{proof.code} {p.release_note.strip()}');s.commit();return c

def dispose(s,key,box_key,p,u):
    ref=get(s,Complaint,key);locked(s,PrintJob,ref.job_id);c=locked(s,Complaint,key);box=locked(s,ComplaintBox,box_key)
    if box.complaint_id!=c.id:raise HTTPException(404,'受影响箱不属于该客诉')
    if c.state!='defect':raise HTTPException(409,'仅复测判为缺陷的客诉须逐箱处置')
    if not _is_defect(get(s,ProofSheet,c.proof_id)):raise HTTPException(409,'客诉复测未判为缺陷，不能按缺陷处置')
    if box.state=='disposed':raise HTTPException(409,'该箱已处置，不能重复')
    if box.state=='released':raise HTTPException(409,'该箱已随合格复测解除隔离')
    if box.kind=='shipped':
        rec=s.scalar(select(ComplaintRecall).where(ComplaintRecall.complaint_id==c.id,ComplaintRecall.shipment_id==box.shipment_id))
        if not rec or rec.state!='completed':raise HTTPException(409,'已发箱须先完成召回登记，才能逐箱处置')
    box.state='disposed';box.dispose_method=p.method;box.dispose_note=p.note.strip();box.disposed_by=u.email;box.disposed_at=now()
    pk=locked(s,PrintPack,box.pack_id)
    if pk.state in ('quarantined','returned','shipped'):pk.state='disposed'
    audit(s,u,f'客诉箱处置 {c.code} {box.pack_snapshot.get("pack_code")} {p.method} {p.note.strip()}');s.commit();return box

def complete_recall(s,key,recall_key,p,u):
    ref=get(s,Complaint,key);locked(s,PrintJob,ref.job_id);c=locked(s,Complaint,key);rec=locked(s,ComplaintRecall,recall_key)
    if rec.complaint_id!=c.id:raise HTTPException(404,'召回记录不属于该客诉')
    if rec.state=='completed':return rec
    if rec.state!='pending':raise HTTPException(409,'召回已取消，不能重复完成')
    if c.state not in ('accepted','defect'):raise HTTPException(409,'客诉当前状态不需要登记召回')
    rec.state='completed';rec.completed_at=now();rec.note=p.note.strip()
    audit(s,u,f'客诉召回完成 {c.code} 发货单{rec.tracking} {p.note.strip()}');s.commit();return rec

def close(s,key,p,u):
    ref=get(s,Complaint,key);locked(s,PrintJob,ref.job_id);c=locked(s,Complaint,key)
    if c.state=='closed':return c
    if c.state!='defect':raise HTTPException(409,'仅复测缺陷的客诉须逐箱处置后结案；复测合格由主管解除')
    if not _is_defect(get(s,ProofSheet,c.proof_id)):raise HTTPException(409,'客诉复测未判为缺陷，不能结案')
    boxes=s.scalars(select(ComplaintBox).where(ComplaintBox.complaint_id==c.id).order_by(ComplaintBox.id).with_for_update()).all()
    if not boxes:raise HTTPException(409,'客诉未登记受影响箱，不能结案')
    if any(b.state!='disposed' for b in boxes):raise HTTPException(409,'仍有未处置箱，不能结案')
    if s.scalar(select(ComplaintRecall.id).where(ComplaintRecall.complaint_id==c.id,ComplaintRecall.state=='pending')):raise HTTPException(409,'仍有待完成召回，不能结案')
    c.state='closed';c.close_note=p.close_note.strip();c.closed_by=u.email;c.closed_at=now()
    audit(s,u,f'客诉结案 {c.code} 逐箱处置完成 {p.close_note.strip()}');s.commit();return c

def resolve_verification(s,key,p,u):
    ref=s.get(JobVerification,key)
    if not ref:raise HTTPException(404,'核实记录不存在')
    job=locked(s,PrintJob,ref.job_id);v=locked(s,JobVerification,key)
    if v.state!='pending':return v
    sample=s.get(PressSample,p.sample_id)
    proof=s.get(ProofSheet,sample.proof_id) if sample else None
    if not sample or sample.job_id!=job.id or sample.state!='passed' or not proof or proof.classification_state!='classified' or not proof.pass_flag or proof.defect!='合格':
        raise HTTPException(409,'核实依据须是同工单已判合格的量产抽检')
    groups,missing=_scan(s,job,ignore=v.pack_id)
    c=s.scalar(select(Complaint).where(Complaint.id==v.complaint_id).with_for_update()) if v.complaint_id else None
    if c and c.state=='defect':raise HTTPException(409,'客诉已按缺陷处置，不能重复核实')
    if c:
        returned=locked(s,PrintPack,c.pack_id)
        if returned.job_id!=job.id:raise HTTPException(409,'退回箱不属于该开机单')
        if returned.state not in ('sealed','shipped'):raise HTTPException(409,'退回箱当前状态不能追溯')
        # 主管核实的合格抽检同时作为缺失依据旧箱的依据，缺失箱一并纳入受影响范围，避免漏箱。
        _apply(s,c,returned,sample,groups.get(sample.id,[])+[(p,sample) for p in missing])
        c.basis_sample_id=sample.id;c.basis_proof_code=proof.code
        c.basis_snapshot={'sample_id':sample.id,'sequence':sample.sequence,'quantity':sample.quantity,'proof_code':proof.code,'verified':True,'verified_missing':[p.code for p in missing]}
        c.accepted_by=u.email;c.accepted_at=now()
        retest_proof=get(s,ProofSheet,c.proof_id)
        c.state='defect' if _is_defect(retest_proof) else 'accepted'
    v.state='resolved';v.verified_sample_id=sample.id;v.verified_proof_code=proof.code;v.resolved_by=u.email;v.resolved_at=now();v.resolution=p.resolution.strip()
    audit(s,u,f'主管核实旧箱依据 {job.code} 采用抽检#{sample.id}/{proof.code} {p.resolution.strip()}');s.commit();return v
