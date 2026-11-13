import hashlib,json,random
from sqlalchemy import func
from src.config.database import SessionLocal,Base,engine
from src.config.schema import ensure_schema
from src.models import User,Dataset,Observation,Experiment,AnalysisRun
from src.utils.security import hash_password
from src.services.statistics_service import analyze

STRATA=[25,55]

def _strata_row(subject, arm, pre_value, value):
    return dict(subject=subject,arm=arm,pre_value=round(pre_value,4),value=round(value,4))

def seed():
    Base.metadata.create_all(engine)
    ensure_schema()
    with SessionLocal() as db:
        for role,name in [("admin","林序 · 实验负责人"),("analyst","许禾 · 数据分析师"),("viewer","周澄 · 产品观察员")]:
            email=role+"@lanqiao.demo"
            if not db.query(User).filter_by(email=email).first(): db.add(User(email=email,name=name,role=role,password_hash=hash_password("Lanqiao2026!")))
        ds=db.query(Dataset).filter_by(name="付费入口 · 11月用户级实验").first()
        if not ds:
            rng=random.Random(42); rows=[]
            for i in range(2400):
                x=max(.1,rng.gauss(36,12)); arm="control" if i%2==0 else "treatment"
                y=max(0,7+.65*x+rng.gauss(0,7)+(2.8 if arm=="treatment" else 0))
                rows.append(dict(subject=f"LQ-{i+1:05}",arm=arm,pre_value=round(x,4),value=round(y,4)))
            ds=Dataset(name="付费入口 · 11月用户级实验",source="lanqiao-paywall-2026-11.csv",description="2400 位独立随机分桶用户；前置7日收入与后置7日收入，合成可复现数据。",checksum=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest())
            db.add(ds);db.flush()
            db.add_all([Observation(dataset_id=ds.id,**row) for row in rows]);db.flush()
        # 分层演示数据：两组的前置收入构成不同，整体差异为正而各层差异为负，
        # 用来验证“整体结论与分层结论相反”时结果页如何呈现。
        simpson=db.query(Dataset).filter_by(name="分层校验 · 前置收入构成失衡样本").first()
        if not simpson:
            rng=random.Random(2026); rows=[]
            def add(prefix,arm,pre,value,count):
                for i in range(count):
                    rows.append(_strata_row(f"{prefix}-{i+1:05}",arm,pre+rng.gauss(0,1),value+rng.gauss(0,1.5)))
            add("CL","control",12.,20.,1000); add("TL","treatment",12.,17.,300)
            add("CM","control",38.,35.,300); add("TM","treatment",38.,32.,300)
            add("CH","control",70.,50.,300); add("TH","treatment",70.,47.,1000)
            simpson=Dataset(name="分层校验 · 前置收入构成失衡样本",source="lanqiao-strata-check-2026-11.csv",description="3200 位独立用户；候选组更多集中在高前置收入层，整体差异为正、各层差异为负，用于验证分层口径。",checksum=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest())
            db.add(simpson);db.flush()
            db.add_all([Observation(dataset_id=simpson.id,**row) for row in rows]);db.flush()
        for name,hyp,dataset,strata,use_cuped in [
            ("短文付费入口 v3","以更清晰的阅读价值说明提高每用户7日收入。",ds,STRATA,True),
            ("精选内容预览长度","增加预览长度能提高付费入口收入，需独立新分桶验证。",ds,None,True),
            ("订阅权益说明顺序","将核心权益前置能提高每用户收入，当前复用数据仅作演示。",ds,None,True),
            ("分层校验 · 前置收入构成失衡","验证分层口径能在整体与分层结论相反时给出可追溯判断。",simpson,STRATA,False),
        ]:
            if not db.query(Experiment).filter_by(name=name).first():
                exp=Experiment(name=name,dataset_id=dataset.id,hypothesis=hyp,owner="许禾 · 数据分析师",alpha=.05,cuped=use_cuped,strata_bounds=strata)
                db.add(exp);db.flush()
                if name in ("短文付费入口 v3","分层校验 · 前置收入构成失衡"):
                    result=analyze(db.query(Observation).filter_by(dataset_id=dataset.id).all(),.05,use_cuped,strata)
                    db.add(AnalysisRun(experiment_id=exp.id,status="completed",result=result))
        db.commit()
        print(json.dumps({model.__tablename__:db.query(model).count() for model in [User,Dataset,Observation,Experiment,AnalysisRun]},ensure_ascii=False))
if __name__=="__main__": seed()
