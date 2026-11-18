from pydantic import Field,field_validator
from .production_schemas import Inputs


class ComplaintInput(Inputs):
    pack_id:int
    code:str=Field(min_length=2,max_length=50)
    note:str=Field(min_length=5,max_length=500)
    proof_code:str=Field(min_length=1,max_length=40)
    density_c:float=Field(ge=0,le=3)
    density_m:float=Field(ge=0,le=3)
    density_y:float=Field(ge=0,le=3)
    density_k:float=Field(ge=0,le=3)
    dot_gain:float=Field(ge=0,le=50)

    @field_validator('code','proof_code')
    @classmethod
    def required(cls,v):
        if not v.strip():raise ValueError('不能为空')
        return v.strip()


class ReleaseInput(Inputs):
    release_note:str=Field(min_length=5,max_length=500)

    @field_validator('release_note')
    @classmethod
    def reason(cls,v):
        if len(v.strip())<5:raise ValueError('解除依据至少5字')
        return v.strip()


class DisposeInput(Inputs):
    method:str=Field(pattern='^(scrap|rework|return_supplier)$')
    note:str=Field(min_length=5,max_length=300)

    @field_validator('note')
    @classmethod
    def reason(cls,v):
        if len(v.strip())<5:raise ValueError('处置说明至少5字')
        return v.strip()


class CloseInput(Inputs):
    close_note:str=Field(min_length=5,max_length=500)

    @field_validator('close_note')
    @classmethod
    def reason(cls,v):
        if len(v.strip())<5:raise ValueError('结案说明至少5字')
        return v.strip()


class RecallDone(Inputs):
    note:str=Field(min_length=5,max_length=300)

    @field_validator('note')
    @classmethod
    def reason(cls,v):
        if len(v.strip())<5:raise ValueError('召回说明至少5字')
        return v.strip()


class VerificationInput(Inputs):
    sample_id:int
    resolution:str=Field(min_length=5,max_length=500)

    @field_validator('resolution')
    @classmethod
    def reason(cls,v):
        if len(v.strip())<5:raise ValueError('核实依据至少5字')
        return v.strip()
