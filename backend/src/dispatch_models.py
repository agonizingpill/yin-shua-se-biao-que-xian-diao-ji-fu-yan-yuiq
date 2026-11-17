from datetime import date
from sqlalchemy import String,ForeignKey,JSON,CheckConstraint,Date
from sqlalchemy.orm import Mapped,mapped_column
from .db import Base
class PaperLot(Base):
    __tablename__='paper_lots'
    __table_args__=(CheckConstraint('gsm>0 AND available_sheets>=0'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(50),unique=True)
    gsm:Mapped[int]=mapped_column()
    available_sheets:Mapped[int]=mapped_column()
    state:Mapped[str]=mapped_column(String(24),default='active')
class PaperIssue(Base):
    __tablename__='paper_issues'
    __table_args__=(CheckConstraint('sheets>0 AND returned_sheets>=0 AND returned_sheets<=sheets'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    job_id:Mapped[int]=mapped_column(ForeignKey('print_jobs.id'))
    lot_id:Mapped[int]=mapped_column(ForeignKey('paper_lots.id'))
    sheets:Mapped[int]=mapped_column()
    returned_sheets:Mapped[int]=mapped_column(default=0)
    paper_snapshot:Mapped[str]=mapped_column(String(80))
    issued_by:Mapped[str]=mapped_column(String(100))
    returned_by:Mapped[str]=mapped_column(String(100),default='')
    return_note:Mapped[str]=mapped_column(String(300),default='')
class PressMachine(Base):
    __tablename__='press_machines'
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(40),unique=True)
    state:Mapped[str]=mapped_column(String(24),default='ready')
class PressInspection(Base):
    __tablename__='press_inspections'
    id:Mapped[int]=mapped_column(primary_key=True)
    job_id:Mapped[int]=mapped_column(ForeignKey('print_jobs.id'))
    machine_id:Mapped[int]=mapped_column(ForeignKey('press_machines.id'))
    inspection_date:Mapped[date]=mapped_column(Date)
    lubricated:Mapped[bool]=mapped_column()
    guards_checked:Mapped[bool]=mapped_column()
    state:Mapped[str]=mapped_column(String(24),default='draft')
    approved_by:Mapped[str]=mapped_column(String(100),default='')
class PrintPack(Base):
    __tablename__='print_packs'
    __table_args__=(CheckConstraint('sheets>0'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    job_id:Mapped[int]=mapped_column(ForeignKey('print_jobs.id'))
    code:Mapped[str]=mapped_column(String(50),unique=True)
    sheets:Mapped[int]=mapped_column()
    state:Mapped[str]=mapped_column(String(24),default='open')
    sample_snapshot:Mapped[dict|None]=mapped_column(JSON,nullable=True)
class PrintShipment(Base):
    __tablename__='print_shipments'
    id:Mapped[int]=mapped_column(primary_key=True)
    job_id:Mapped[int]=mapped_column(ForeignKey('print_jobs.id'))
    tracking:Mapped[str]=mapped_column(String(80),unique=True)
    customer:Mapped[str]=mapped_column(String(120))
    state:Mapped[str]=mapped_column(String(24),default='draft')
    snapshot:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    dispatched_by:Mapped[str]=mapped_column(String(100),default='')
    received_by:Mapped[str]=mapped_column(String(100),default='')
class ShipmentPack(Base):
    __tablename__='shipment_packs'
    id:Mapped[int]=mapped_column(primary_key=True)
    shipment_id:Mapped[int]=mapped_column(ForeignKey('print_shipments.id'))
    pack_id:Mapped[int]=mapped_column(ForeignKey('print_packs.id'),unique=True)
