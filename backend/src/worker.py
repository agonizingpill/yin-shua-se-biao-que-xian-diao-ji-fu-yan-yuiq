import os,json,logging
from pathlib import Path
import redis
from .db import Session
from .models import ProofSheet
from .classifier import classify
from .services import now
from .sampling_service import finish
from .complaint_service import finish as finish_complaint
r=redis.Redis.from_url(os.environ['REDIS_URL'],decode_responses=True);Path('/artifacts').mkdir(exist_ok=True)

def complaint_trace(pid):
    # 客诉追溯单独提交：追溯失败不能回滚已经得到并持久化的判读结果。
    with Session()as s:
        p=s.get(ProofSheet,pid)
        try:finish_complaint(s,p);s.commit()
        except Exception:s.rollback();logging.exception('complaint trace failed')

while True:
    Path('/tmp/worker-heartbeat').touch();entry=r.blpop('press-classify',timeout=2)
    if not entry:continue
    with Session()as s:
        p=s.get(ProofSheet,int(entry[1]))
        if not p or p.classification_state!='classifying':continue
        try:
            p.defect,p.evidence=classify(s,p);p.pass_flag=p.defect=='合格';p.classification_state='classified';p.classified_at=now();finish(s,p);s.commit();Path(f'/artifacts/proof-{p.id}.json').write_text(json.dumps(p.evidence,ensure_ascii=False))
        except Exception as ex:
            s.rollback();p=s.get(ProofSheet,int(entry[1]));p.classification_state='failed';p.evidence={'error':str(ex)};finish(s,p);s.commit();logging.exception('classification failed')
    complaint_trace(int(entry[1]))
