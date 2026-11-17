from fastapi import APIRouter,Depends
from sqlalchemy import select
from .db import db_session
from .auth import current,writers,admin
from .services import pack,audit
from .dispatch_models import PaperLot,PaperIssue,PressMachine,PressInspection,PrintPack,PrintShipment,ShipmentPack
from .dispatch_schemas import PaperLotInput,PaperState,PaperIssueInput,PaperReturn,MachineInput,MachineState,InspectionInput,PackInput,ShipmentInput,ReceiptInput
from .paper_service import locked
from . import paper_service,inspection_service,shipment_service
router=APIRouter()
@router.get('/paper-lots')
def lots(s=Depends(db_session),u=Depends(current)):return [pack(x) for x in s.scalars(select(PaperLot).order_by(PaperLot.id))]
@router.post('/paper-lots')
def lot(b:PaperLotInput,s=Depends(db_session),u=Depends(writers)):
    row=PaperLot(**b.model_dump());s.add(row);audit(s,u,'纸张入库');s.commit();return pack(row)
@router.put('/paper-lots/{key}/state')
def lot_state(key:int,b:PaperState,s=Depends(db_session),u=Depends(admin)):
    row=locked(s,PaperLot,key);row.state=b.state;audit(s,u,'纸张批次隔离');s.commit();return pack(row)
@router.get('/paper-issues')
def issues(s=Depends(db_session),u=Depends(current)):return [pack(x) for x in s.scalars(select(PaperIssue).order_by(PaperIssue.id.desc()))]
@router.post('/paper-issues')
def issue(b:PaperIssueInput,s=Depends(db_session),u=Depends(writers)):return pack(paper_service.issue(s,b,u))
@router.post('/paper-issues/{key}/return')
def return_paper(key:int,b:PaperReturn,s=Depends(db_session),u=Depends(writers)):return pack(paper_service.return_unused(s,key,b,u))
@router.get('/press-machines')
def machines(s=Depends(db_session),u=Depends(current)):return [pack(x) for x in s.scalars(select(PressMachine).order_by(PressMachine.id))]
@router.post('/press-machines')
def machine(b:MachineInput,s=Depends(db_session),u=Depends(admin)):
    row=PressMachine(**b.model_dump());s.add(row);audit(s,u,'登记印机');s.commit();return pack(row)
@router.put('/press-machines/{key}/state')
def machine_state(key:int,b:MachineState,s=Depends(db_session),u=Depends(admin)):
    row=locked(s,PressMachine,key);row.state=b.state;audit(s,u,'印机保养状态');s.commit();return pack(row)
@router.get('/press-inspections')
def inspections(s=Depends(db_session),u=Depends(current)):return [pack(x) for x in s.scalars(select(PressInspection).order_by(PressInspection.id.desc()))]
@router.post('/press-inspections')
def inspect(b:InspectionInput,s=Depends(db_session),u=Depends(writers)):return pack(inspection_service.record(s,b,u))
@router.put('/press-inspections/{key}')
def revise(key:int,b:InspectionInput,s=Depends(db_session),u=Depends(writers)):return pack(inspection_service.record(s,b,u,key))
@router.post('/press-inspections/{key}/approve')
def inspect_approve(key:int,s=Depends(db_session),u=Depends(admin)):return pack(inspection_service.approve(s,key,u))
@router.get('/print-packs')
def packs(s=Depends(db_session),u=Depends(current)):return [pack(x) for x in s.scalars(select(PrintPack).order_by(PrintPack.id.desc()))]
@router.post('/print-packs')
def create_pack(b:PackInput,s=Depends(db_session),u=Depends(writers)):return pack(shipment_service.create_pack(s,b,u))
@router.post('/print-packs/{key}/seal')
def seal(key:int,s=Depends(db_session),u=Depends(writers)):return pack(shipment_service.pack_action(s,key,u,'seal'))
@router.post('/print-packs/{key}/cancel')
def cancel(key:int,s=Depends(db_session),u=Depends(writers)):return pack(shipment_service.pack_action(s,key,u,'cancel'))
@router.get('/print-shipments')
def shipments(s=Depends(db_session),u=Depends(current)):
    result=[]
    for x in s.scalars(select(PrintShipment).order_by(PrintShipment.id.desc())):
        row=pack(x);row['pack_ids']=s.scalars(select(ShipmentPack.pack_id).where(ShipmentPack.shipment_id==x.id)).all();result.append(row)
    return result
@router.post('/print-shipments')
def shipment(b:ShipmentInput,s=Depends(db_session),u=Depends(writers)):return pack(shipment_service.create_shipment(s,b,u))
@router.post('/print-shipments/{key}/dispatch')
def dispatch(key:int,s=Depends(db_session),u=Depends(admin)):return pack(shipment_service.dispatch(s,key,u))
@router.post('/print-shipments/{key}/receive')
def receive(key:int,b:ReceiptInput,s=Depends(db_session),u=Depends(writers)):return pack(shipment_service.receive(s,key,b,u))
