from sqlalchemy import String,ForeignKey,JSON,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from .db import Base


class Complaint(Base):
    """客户退回成品箱的客诉。

    pack_id 是客户退回的原箱；proof_id 是从该箱登记的新色标。客诉受理后，
    以原箱封箱快照中的合格抽检依据确定同批箱，并冻结该批放行。
    """
    __tablename__='complaints'
    __table_args__=(UniqueConstraint('code'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(50))
    job_id:Mapped[int]=mapped_column(ForeignKey('print_jobs.id'))
    pack_id:Mapped[int]=mapped_column(ForeignKey('print_packs.id'))
    proof_id:Mapped[int]=mapped_column(ForeignKey('proof_sheets.id'),unique=True)
    state:Mapped[str]=mapped_column(String(24),default='registered')
    note:Mapped[str]=mapped_column(String(500),default='')
    basis_sample_id:Mapped[int|None]=mapped_column(nullable=True)
    basis_proof_code:Mapped[str|None]=mapped_column(String(40),nullable=True)
    basis_snapshot:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    created_by:Mapped[str]=mapped_column(String(100),default='')
    created_at:Mapped[str]=mapped_column(String(40),default='')
    accepted_by:Mapped[str]=mapped_column(String(100),default='')
    accepted_at:Mapped[str|None]=mapped_column(String(40),nullable=True)
    release_note:Mapped[str]=mapped_column(String(500),default='')
    released_by:Mapped[str]=mapped_column(String(100),default='')
    released_at:Mapped[str|None]=mapped_column(String(40),nullable=True)
    close_note:Mapped[str]=mapped_column(String(500),default='')
    closed_by:Mapped[str]=mapped_column(String(100),default='')
    closed_at:Mapped[str|None]=mapped_column(String(40),nullable=True)


class ComplaintBox(Base):
    """客诉受理时按原箱合格抽检依据追溯到的同批成品箱。

    kind=unshipped 的箱在库内未发出，状态为 quarantined；
    kind=shipped 的箱已经装运，登记待召回 recall_pending，原装运快照不改。
    """
    __tablename__='complaint_boxes'
    __table_args__=(UniqueConstraint('complaint_id','pack_id'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    complaint_id:Mapped[int]=mapped_column(ForeignKey('complaints.id'))
    pack_id:Mapped[int]=mapped_column(ForeignKey('print_packs.id'))
    shipment_id:Mapped[int|None]=mapped_column(ForeignKey('print_shipments.id'),nullable=True)
    kind:Mapped[str]=mapped_column(String(24))
    state:Mapped[str]=mapped_column(String(24))
    original_state:Mapped[str]=mapped_column(String(24),default='')
    pack_snapshot:Mapped[dict]=mapped_column(JSON)
    dispose_method:Mapped[str]=mapped_column(String(40),default='')
    dispose_note:Mapped[str]=mapped_column(String(300),default='')
    disposed_by:Mapped[str]=mapped_column(String(100),default='')
    disposed_at:Mapped[str|None]=mapped_column(String(40),nullable=True)


class ComplaintRecall(Base):
    """已发同批箱的待召回登记，按客诉+发货单唯一，重试不会重复建。"""
    __tablename__='complaint_recalls'
    __table_args__=(UniqueConstraint('complaint_id','shipment_id'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    complaint_id:Mapped[int]=mapped_column(ForeignKey('complaints.id'))
    shipment_id:Mapped[int]=mapped_column(ForeignKey('print_shipments.id'))
    state:Mapped[str]=mapped_column(String(24),default='pending')
    tracking:Mapped[str]=mapped_column(String(80),default='')
    customer:Mapped[str]=mapped_column(String(120),default='')
    shipment_snapshot:Mapped[dict]=mapped_column(JSON)
    created_at:Mapped[str]=mapped_column(String(40),default='')
    completed_at:Mapped[str|None]=mapped_column(String(40),nullable=True)
    note:Mapped[str]=mapped_column(String(300),default='')


class JobVerification(Base):
    """原箱旧封箱依据缺失时，拦住开机单待主管核实。"""
    __tablename__='job_verifications'
    id:Mapped[int]=mapped_column(primary_key=True)
    job_id:Mapped[int]=mapped_column(ForeignKey('print_jobs.id'))
    complaint_id:Mapped[int|None]=mapped_column(ForeignKey('complaints.id'),nullable=True)
    pack_id:Mapped[int|None]=mapped_column(ForeignKey('print_packs.id'),nullable=True)
    reason:Mapped[str]=mapped_column(String(300))
    prior_status:Mapped[str]=mapped_column(String(24),default='production')
    state:Mapped[str]=mapped_column(String(24),default='pending')
    verified_sample_id:Mapped[int|None]=mapped_column(nullable=True)
    verified_proof_code:Mapped[str|None]=mapped_column(String(40),nullable=True)
    resolved_by:Mapped[str]=mapped_column(String(100),default='')
    resolved_at:Mapped[str|None]=mapped_column(String(40),nullable=True)
    resolution:Mapped[str]=mapped_column(String(500),default='')
