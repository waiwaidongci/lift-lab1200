import {Experiment} from '../types/domain';
import {edge} from '../utils/format';

export function strataLabel(bounds?:number[]|null){
  return bounds&&bounds.length?bounds.map(b=>edge(b)).join(' / ')+' 元':'未设置分层';
}

export function ExperimentSummary({experiment}:{experiment?:Experiment}){
  return <div className="experiment-summary">
    <span className="eyebrow">REGISTERED HYPOTHESIS / 预注册假设</span>
    <h3>{experiment?.name||'请先选择实验'}</h3>
    <p>{experiment?.hypothesis||'建立实验后即可提交独立的分析任务。'}</p>
    {experiment&&<small>负责人 {experiment.owner} · α {experiment.alpha} · {experiment.cuped?'CUPED 校正':'原始指标'} · 前置收入区间 {strataLabel(experiment.strata_bounds)}</small>}
  </div>
}
