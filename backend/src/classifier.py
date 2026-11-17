import numpy as np
from sqlalchemy import select
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.svm import SVC
from sklearn.metrics import confusion_matrix,accuracy_score
from .models import ReferenceSheet,PrintJob
from .constants import DEFECTS

def vector(p,target=1.4):return [p.density_c/target,p.density_m/target,p.density_y/target,p.density_k/target,p.dot_gain/100]
def classify(s,p):
    refs=s.scalars(select(ReferenceSheet).order_by(ReferenceSheet.id)).all()
    if len(refs)<60:raise ValueError('带标签参考色标不足60张')
    x=np.array([vector(r)for r in refs]);y=np.array([r.label for r in refs]);ids=np.arange(len(refs))
    train,test=train_test_split(ids,test_size=.2,stratify=y,random_state=42)
    model=make_pipeline(StandardScaler(),SVC(kernel='rbf',C=2,probability=True,random_state=42));model.fit(x[train],y[train])
    query=[vector(p,s.get(PrintJob,p.job_id).target_density)];label=str(model.predict(query)[0]);prob=model.predict_proba(query)[0];pred=model.predict(x[test])
    return label,{'probabilities':{str(c):round(float(v),5)for c,v in zip(model[-1].classes_,prob)},'labels':list(DEFECTS),'confusion_matrix':confusion_matrix(y[test],pred,labels=list(DEFECTS)).tolist(),'accuracy':round(float(accuracy_score(y[test],pred)),4),'train_rows':len(train),'holdout_rows':len(test),'seed':42,'reference_codes':[refs[i].code for i in train],'holdout_codes':[refs[i].code for i in test],'current_proof_code':p.code,'feature_names':['青密度比','品红密度比','黄密度比','黑密度比','网点扩大率'],'features':vector(p,s.get(PrintJob,p.job_id).target_density)}
