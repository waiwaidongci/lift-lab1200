import {useState} from 'react';
import {Download,ArrowRight} from 'lucide-react';
import {Link} from 'react-router-dom';
import {useResearchData} from '../hooks/useResearch';
import {useAction} from '../hooks/useAction';
import {download} from '../api/client';
import {ExperimentSummary} from '../components/ExperimentSummary';
import {ConfidencePlot} from '../components/ConfidencePlot';
import {StrataPanel} from '../components/StrataPanel';
import {StatusBadge} from '../components/common/StatusBadge';
import {Notice} from '../components/common/Notice';
import {number,percent,time,probability} from '../utils/format';

const Basis:Record<string,string>={
  stratified:'结论依据：前置收入分层汇总',
  overall:'结论依据：整体样本',
  withheld:'分层不可汇总，未给放量结论',
};

export function Runs(){
  const s=useResearchData(true),[selected,setSelected]=useState(0),action=useAction();
  const run=s.runs.find(r=>r.id===selected)||s.runs[0],exp=s.experiments.find(e=>e.id===run?.experiment_id);
  const result=run?.result.cuped||run?.result.raw;
  const basis=run?.result.interpretation_basis||'overall';
  const stratified=run?.result.stratified;
  const headline=(basis==='stratified'&&stratified?.valid&&stratified.chosen_method&&stratified.combined
    ?stratified.combined[stratified.chosen_method as 'raw'|'cuped']
    :null)||result;
  const headlineLabel=basis==='stratified'?'分层汇总':'整体';
  return <div className="page runs-page">
    <div className="page-title">
      <div><p className="eyebrow">EVIDENCE REVIEW / 04</p><h1>分析结果<span>把不确定性一并呈上。</span></h1></div>
      {run?.status==='completed'&&<button className="outline" onClick={()=>action.execute(async()=>{await download(`/runs/${run.id}/export`,`lift-run-${run.id}.csv`)})}><Download size={16}/>导出分析</button>}
    </div>
    <Notice message={s.error||action.error} retry={s.refresh}/>
    <div className="run-picker">
      <label>运行档案 <select aria-label="运行档案" value={run?.id||''} onChange={e=>setSelected(Number(e.target.value))}>{s.runs.map(r=><option value={r.id} key={r.id}>RUN-{r.id} · {s.experiments.find(e=>e.id===r.experiment_id)?.name} · {r.status}</option>)}</select></label>
      {run&&<StatusBadge status={run.status}/>}
    </div>
    {run?<>
      <ExperimentSummary experiment={exp}/>
      {run.status==='completed'&&result&&run.result.raw?<>
        <div className="result-statement">
          <span className="eyebrow">RESEARCH FINDING / 双侧检验 · {Basis[basis]||Basis.overall}</span>
          <h2>{run.result.interpretation}</h2>
          <p>{headlineLabel} 控制组 {headline?.n_control} 位 · 候选组 {headline?.n_treatment} 位 · {time(run.created_at)}
            {run.result.conclusion_comparison&&<> · 整体与分层对比：{run.result.conclusion_comparison}</>}
          </p>
        </div>
        <div className="result-metrics">
          <div><span>整体均值差 / 元</span><b>+{number(result.difference)}</b></div>
          <div><span>整体双侧 p 值</span><b>{probability(result.p_value)}</b></div>
          <div><span>{basis==='stratified'?'分层汇总均值差':'整体均值差'} / 元</span><b>{headline===result?'+'+number(result.difference):number(headline?.difference)}</b></div>
          <div><span>{basis==='stratified'?'分层方差降低':'方差降低'}</span><b>{percent(basis==='stratified'?stratified?.variance_reduction:run.result.variance_reduction)}</b></div>
          <div><span>CUPED θ</span><b>{basis==='stratified'?'层内分别估计':number(run.result.theta,4)}</b></div>
        </div>
        <div className="plot-heading"><h3>{number((1-(exp?.alpha||.05))*100,0)}% 均值差置信区间</h3><span>横线为区间 · 圆点为点估计</span></div>
        <ConfidencePlot raw={run.result.raw} cuped={run.result.cuped}/>
        <StrataPanel stratified={run.result.stratified}/>
        <p className="assumptions">口径与假设：{run.result.assumptions}</p>
        <Link className="text-button" to="/decisions">把证据带入决策档案 <ArrowRight size={16}/></Link>
      </>:<div className="pending"><h2>{run.status==='failed'?'计算未能完成':'分析任务正在队列中执行'}</h2><p>{run.error||'后台 worker 将计算原始差异、CUPED 校正与分层结果；本页每2秒更新。'}</p></div>}
    </>:<div className="pending">还没有分析任务。先登记实验，再提交分析。<Link to="/configure">登记实验 →</Link></div>}
  </div>
}
