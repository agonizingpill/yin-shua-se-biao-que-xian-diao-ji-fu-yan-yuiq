from sqlalchemy import String,Float,ForeignKey,JSON,UniqueConstraint,CheckConstraint
from sqlalchemy.orm import Mapped,mapped_column
from .db import Base
class PlateSet(Base):
    __tablename__='plate_sets'
    __table_args__=(UniqueConstraint('job_id','version'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    job_id:Mapped[int]=mapped_column(ForeignKey('print_jobs.id'))
    version:Mapped[str]=mapped_column(String(40))
    source_note:Mapped[str]=mapped_column(String(300))
    registration_error_mm:Mapped[float|None]=mapped_column(Float,nullable=True)
    state:Mapped[str]=mapped_column(String(24),default='registered')
    approved_by:Mapped[str]=mapped_column(String(100),default='')
class PressSample(Base):
    __tablename__='press_samples'
    __table_args__=(UniqueConstraint('job_id','sequence'),CheckConstraint('quantity>0 AND sequence>0'))
    id:Mapped[int]=mapped_column(primary_key=True)
    job_id:Mapped[int]=mapped_column(ForeignKey('print_jobs.id'))
    proof_id:Mapped[int]=mapped_column(ForeignKey('proof_sheets.id'),unique=True)
    plate_id:Mapped[int]=mapped_column(ForeignKey('plate_sets.id'))
    sequence:Mapped[int]=mapped_column()
    quantity:Mapped[int]=mapped_column()
    state:Mapped[str]=mapped_column(String(24),default='classifying')
    plate_snapshot:Mapped[dict]=mapped_column(JSON)
class PressHold(Base):
    __tablename__='press_holds'
    id:Mapped[int]=mapped_column(primary_key=True)
    job_id:Mapped[int]=mapped_column(ForeignKey('print_jobs.id'))
    sample_id:Mapped[int]=mapped_column(ForeignKey('press_samples.id'),unique=True)
    reason:Mapped[str]=mapped_column(String(300))
    state:Mapped[str]=mapped_column(String(24),default='active')
    created_at:Mapped[str]=mapped_column(String(40))
    reproof_id:Mapped[int|None]=mapped_column(ForeignKey('proof_sheets.id'),nullable=True)
    reproof_ids:Mapped[list]=mapped_column(JSON,default=list)
    resolution:Mapped[str]=mapped_column(String(500),default='')
    closed_by:Mapped[str]=mapped_column(String(100),default='')
    closed_at:Mapped[str|None]=mapped_column(String(40),nullable=True)
