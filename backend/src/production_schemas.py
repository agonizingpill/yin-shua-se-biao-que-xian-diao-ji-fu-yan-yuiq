from pydantic import BaseModel,Field,ConfigDict,field_validator
from .schemas import ProofInput
class Inputs(BaseModel):
    model_config=ConfigDict(allow_inf_nan=False)
class PlateInput(Inputs):
    job_id:int
    version:str=Field(min_length=1,max_length=40)
    source_note:str=Field(min_length=5,max_length=300)
    @field_validator('version','source_note')
    @classmethod
    def required(cls,v):
        if not v.strip():raise ValueError('不能为空')
        return v.strip()
class MeasurementInput(Inputs):
    registration_error_mm:float=Field(ge=0,le=5)
class SampleInput(ProofInput):
    model_config=ConfigDict(allow_inf_nan=False)
    sequence:int=Field(ge=1,le=1000000)
    quantity:int=Field(ge=1,le=10000000)
class HoldClose(Inputs):
    resolution:str=Field(min_length=5,max_length=500)
    @field_validator('resolution')
    @classmethod
    def reason(cls,v):
        if len(v.strip())<5:raise ValueError('处置依据至少5字')
        return v.strip()
