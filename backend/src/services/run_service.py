import csv, io
from fastapi import HTTPException
from redis import Redis
from ..config.settings import REDIS_URL
from ..models import AnalysisRun, Experiment
from ..utils.serialize import record
from .audit_service import log
queue=Redis.from_url(REDIS_URL,decode_responses=True)
METRICS=["n_control","n_treatment","difference","p_value","ci_low","ci_high"]

def list_runs(db):
    return [record(x) for x in db.query(AnalysisRun).order_by(AnalysisRun.id.desc())]
def get_run(db,rid):
    row=db.get(AnalysisRun,rid)
    if not row: raise HTTPException(404,"运行记录不存在")
    return row
def enqueue(db,eid,user):
    if not db.get(Experiment,eid): raise HTTPException(404,"实验不存在")
    row=AnalysisRun(experiment_id=eid,status="queued")
    db.add(row); db.flush(); log(db,user.email,"analysis.enqueue",row.id); db.commit()
    try: queue.rpush("lift:jobs",row.id)
    except Exception:
        row.status="failed"; row.error="队列不可用，请稍后重新运行"; db.commit(); raise HTTPException(503,row.error)
    return record(row)

def export_run(db,rid):
    row=get_run(db,rid)
    if row.status!="completed": raise HTTPException(409,"运行尚未完成")
    result=row.result or {}
    stratified=result.get("stratified") or {}
    out=io.StringIO(); w=csv.writer(out)
    w.writerow(["method","n_control","n_treatment","difference","p_value","ci_low","ci_high"])
    for method in ("raw","cuped"):
        item=result.get(method)
        if item: w.writerow([method]+[item[k] for k in METRICS])
    w.writerow([])
    if stratified.get("enabled"):
        w.writerow(["strata_bounds","/".join(f"{float(b):g}" for b in stratified["bounds"])])
        w.writerow(["strata_weight_basis",stratified.get("weight_basis","")])
        w.writerow(["strata_aggregation_basis",stratified.get("aggregation_basis","")])
        w.writerow(["strata_weight_total",sum(stratified.get("weights") or [])])
        w.writerow(["strata_conclusion_withheld",stratified.get("conclusion_withheld")])
        for reason in stratified.get("blocked_reasons") or []: w.writerow(["strata_blocked_reason",reason])
        for reason in stratified.get("cuped_blocked_reasons") or []: w.writerow(["strata_cuped_blocked_reason",reason])
        w.writerow([])
        w.writerow(["stratum","method","n","n_control","n_treatment","weight","difference","p_value","ci_low","ci_high","theta","valid","reason"])
        for item in stratified.get("strata",[]):
            for method in ("raw","cuped"):
                sub=item.get(method)
                if sub:
                    w.writerow([item["label"],method,item["n"],sub["n_control"],sub["n_treatment"],item["weight"],
                                sub["difference"],sub["p_value"],sub["ci_low"],sub["ci_high"],
                                "" if item.get("theta") is None else item["theta"],item["valid"],item.get("reason") or item.get("cuped_reason") or ""])
                elif method=="raw":
                    w.writerow([item["label"],method,item["n"],item["n_control"],item["n_treatment"],item["weight"],
                                "","","","","","",item.get("reason","")])
        combined=stratified.get("combined") or {}
        for method in ("raw","cuped"):
            sub=combined.get(method)
            if sub: w.writerow(["strata_combined",method,"",sub["n_control"],sub["n_treatment"],1.0,
                                sub["difference"],sub["p_value"],sub["ci_low"],sub["ci_high"],"","",""])
        w.writerow(["strata_variance_reduction",stratified.get("variance_reduction")])
        w.writerow(["conclusion_comparison",result.get("conclusion_comparison") or ""])
    else:
        w.writerow(["strata_enabled",False])
        w.writerow(["strata_note",stratified.get("reason") if stratified else "旧运行记录未包含分层信息，按原方法复算"])
    w.writerow(["interpretation_basis",result.get("interpretation_basis","overall")])
    w.writerow(["interpretation",result.get("interpretation","")])
    w.writerow(["assumptions",result.get("assumptions","")])
    return out.getvalue()
