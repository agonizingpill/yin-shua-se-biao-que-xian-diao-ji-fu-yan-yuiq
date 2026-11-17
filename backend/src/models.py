from sqlalchemy import String,Integer,Float,Boolean,ForeignKey,JSON,CheckConstraint
from sqlalchemy.orm import Mapped,mapped_column
from .db import Base
class User(Base):
    __tablename__='users'
    id:Mapped[int]=mapped_column(primary_key=True)
    email:Mapped[str]=mapped_column(String(100),unique=True)
    password_hash:Mapped[str]=mapped_column(String(180))
    role:Mapped[str]=mapped_column(String(20))
class PrintJob(Base):
    __tablename__='print_jobs'
    __table_args__=(CheckConstraint('target_density > 0'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(40),unique=True)
    title:Mapped[str]=mapped_column(String(100))
    paper:Mapped[str]=mapped_column(String(80))
    target_density:Mapped[float]=mapped_column(Float)
    status:Mapped[str]=mapped_column(String(20),default='setup')
class ProofSheet(Base):
    __tablename__='proof_sheets'
    __table_args__=(CheckConstraint('density_c >= 0 AND density_m >= 0 AND density_y >= 0 AND density_k >= 0 AND dot_gain >= 0'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    job_id:Mapped[int]=mapped_column(ForeignKey('print_jobs.id'))
    code:Mapped[str]=mapped_column(String(40),unique=True)
    density_c:Mapped[float]=mapped_column(Float)
    density_m:Mapped[float]=mapped_column(Float)
    density_y:Mapped[float]=mapped_column(Float)
    density_k:Mapped[float]=mapped_column(Float)
    dot_gain:Mapped[float]=mapped_column(Float)
    defect:Mapped[str|None]=mapped_column(String(20),nullable=True)
    pass_flag:Mapped[bool]=mapped_column(Boolean,default=False)
    classification_state:Mapped[str]=mapped_column(String(20),default='unmeasured')
    classified_at:Mapped[str|None]=mapped_column(String(40),nullable=True)
    evidence:Mapped[dict|None]=mapped_column(JSON,nullable=True)
class Adjustment(Base):
    __tablename__='adjustments'
    id:Mapped[int]=mapped_column(primary_key=True)
    job_id:Mapped[int]=mapped_column(ForeignKey('print_jobs.id'))
    proof_id:Mapped[int]=mapped_column(ForeignKey('proof_sheets.id'),unique=True)
    ink_delta:Mapped[float]=mapped_column(Float)
    water_delta:Mapped[float]=mapped_column(Float)
    status:Mapped[str]=mapped_column(String(20),default='issued')
    executed_at:Mapped[str|None]=mapped_column(String(40),nullable=True)
    reproof_id:Mapped[int|None]=mapped_column(ForeignKey('proof_sheets.id'),nullable=True)
    signed_by:Mapped[str|None]=mapped_column(String(100),nullable=True)
class ReferenceSheet(Base):
    __tablename__='reference_sheets'
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(40),unique=True)
    density_c:Mapped[float]=mapped_column(Float)
    density_m:Mapped[float]=mapped_column(Float)
    density_y:Mapped[float]=mapped_column(Float)
    density_k:Mapped[float]=mapped_column(Float)
    dot_gain:Mapped[float]=mapped_column(Float)
    label:Mapped[str]=mapped_column(String(20))
class Audit(Base):
    __tablename__='audits'
    id:Mapped[int]=mapped_column(primary_key=True)
    actor:Mapped[str]=mapped_column(String(100))
    action:Mapped[str]=mapped_column(String(200))
    stamp:Mapped[str]=mapped_column(String(40))
