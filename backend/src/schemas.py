from pydantic import BaseModel,Field
class Login(BaseModel):
    email:str
    password:str
class JobInput(BaseModel):
    code:str=Field(min_length=1,max_length=40)
    title:str=Field(min_length=1,max_length=100)
    paper:str=Field(min_length=1,max_length=80)
    target_density:float=Field(ge=.8,le=2.5)
class ProofInput(BaseModel):
    job_id:int
    code:str=Field(min_length=1,max_length=40)
    density_c:float=Field(ge=0,le=3)
    density_m:float=Field(ge=0,le=3)
    density_y:float=Field(ge=0,le=3)
    density_k:float=Field(ge=0,le=3)
    dot_gain:float=Field(ge=0,le=50)
class AdjustmentInput(BaseModel):
    proof_id:int
class InstructionInput(BaseModel):
    ink_delta:float=Field(ge=-15,le=15)
    water_delta:float=Field(ge=-15,le=15)
class ReproofInput(BaseModel):
    reproof_id:int
