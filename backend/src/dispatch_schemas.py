from datetime import date
from typing import Literal
from pydantic import Field
from .production_schemas import Inputs
class PaperLotInput(Inputs):
    code:str=Field(min_length=2,max_length=50)
    gsm:int=Field(ge=40,le=1000)
    available_sheets:int=Field(ge=1,le=10000000)
class PaperState(Inputs):
    state:Literal['active','quarantine']
class PaperIssueInput(Inputs):
    job_id:int
    lot_id:int
    sheets:int=Field(ge=1,le=10000000)
class PaperReturn(Inputs):
    sheets:int=Field(ge=1,le=10000000)
    note:str=Field(min_length=5,max_length=300)
class MachineInput(Inputs):
    code:str=Field(min_length=2,max_length=40)
class MachineState(Inputs):
    state:Literal['ready','maintenance']
class InspectionInput(Inputs):
    job_id:int
    machine_id:int
    inspection_date:date
    lubricated:bool
    guards_checked:bool
class PackInput(Inputs):
    job_id:int
    code:str=Field(min_length=2,max_length=50)
    sheets:int=Field(ge=1,le=10000000)
class ShipmentInput(Inputs):
    job_id:int
    tracking:str=Field(min_length=2,max_length=80)
    customer:str=Field(min_length=2,max_length=120)
    pack_ids:list[int]=Field(min_length=1,max_length=100)
class ReceiptInput(Inputs):
    received_by:str=Field(min_length=2,max_length=100)
