import {Stratified,Stratum,Comparison} from '../types/domain';
import {number,percent,probability,edge} from '../utils/format';

function Cell({result}:{result?:Comparison|null}){
  if(!result) return <td>—</td>;
  return <td><b>{number(result.difference)}</b><small>[{number(result.ci_low)}, {number(result.ci_high)}] · p {probability(result.p_value)}</small></td>;
}

function Row({stratum}:{stratum:Stratum}){
  return <tr className={stratum.valid?'':'invalid'}>
    <td><b>{stratum.label}</b><small className="mono">第 {stratum.index+1} 层 / 元</small></td>
    <td>{number(stratum.weight*100,1)}%</td>
    <td>{stratum.n.toLocaleString()}<small>对照 {stratum.n_control} · 候选 {stratum.n_treatment}</small></td>
    <Cell result={stratum.raw}/>
    <Cell result={stratifiedMethod(stratum)}/>
    <td className="mono">{stratum.theta===null||stratum.theta===undefined?'—':number(stratum.theta,4)}</td>
    <td>{stratum.valid?'保留':(stratumReason(stratum)||'该层不可用')}</td>
  </tr>;
}

function stratifiedMethod(stratum:Stratum){return stratum.cuped;}

function stratumReason(stratum:Stratum){
  if(stratum.cuped_reason&&!stratum.valid)return stratum.reason?`${stratum.reason}；${stratum.cuped_reason}`:stratum.cuped_reason;
  return stratum.reason;
}

export function StrataPanel({stratified}:{stratified?:Stratified}){
  if(!stratified){
    // 升级前已归档的运行没有分层字段，原值照旧显示；重新提交分析才会按现行口径复算。
    return <section className="strata-panel">
      <div className="plot-heading"><h3>按前置收入分层</h3><span>STRATA / 旧运行记录</span></div>
      <p className="strata-note">该运行产生于分层功能之前，保留原始结果；重新提交分析会按登记的区间与当前口径复算。</p>
    </section>;
  }
  if(!stratified.enabled){
    return <section className="strata-panel">
      <div className="plot-heading"><h3>按前置收入分层</h3><span>STRATA / 未启用</span></div>
      <p className="strata-note">{stratified.reason||'登记时未设置前置收入区间，按原方法复算。'}</p>
    </section>;
  }
  const strata=stratified.strata||[];
  const combinedRaw=stratified.combined?.raw||null;
  const combinedCuped=stratified.combined?.cuped||null;
  const withheld=!!stratified.conclusion_withheld||!stratified.valid;
  const weightSum=(stratified.weights||[]).reduce((a,b)=>a+b,0);
  return <section className="strata-panel">
    <div className="plot-heading">
      <h3>按前置收入分层</h3>
      <span>STRATA / {stratified.bounds&&stratified.bounds.length?stratified.bounds.map(b=>edge(b)).join(' / ')+' 元':'未设置'}</span>
    </div>
    <p className="strata-note">
      区间在登记实验时固定；按全体样本各层占比给两组相同权重。
      {stratified.weight_basis&&<>权重依据：{stratified.weight_basis}。</>}
      {stratified.aggregation_basis&&<>汇总依据：{stratified.aggregation_basis}。</>}
    </p>
    {withheld&&<div className="strata-blocked" role="status">
      <strong>本次不给出放量结论</strong>
      <p>{(stratified.blocked_reasons&&stratified.blocked_reasons.length?stratified.blocked_reasons.join('；'):null)
        ||(stratified.cuped_blocked_reasons&&stratified.cuped_blocked_reasons.length?'层内 CUPED：'+stratified.cuped_blocked_reasons.join('；'):null)
        ||stratified.interpretation||'部分层缺组或样本不足。'}</p>
      {(stratified.blocked_reasons&&stratified.blocked_reasons.length>0&&stratified.cuped_blocked_reasons&&stratified.cuped_blocked_reasons.length>0)&&
        <p>层内 CUPED：{stratified.cuped_blocked_reasons.join('；')}</p>}
      <small>整体结果仍保留在上方供追溯，不作为放量依据。</small>
    </div>}
    <div className="table-wrap">
      <table className="strata-table">
        <thead><tr><th>前置收入层</th><th>权重</th><th>样本量</th><th>原始差异 [区间]</th><th>CUPED 差异 [区间]</th><th>层内 θ</th><th>状态</th></tr></thead>
        <tbody>
          {strata.map(s=><Row key={s.index} stratum={s}/>)}
          {(combinedRaw||combinedCuped)&&<tr className="strata-total">
            <td><b>分层汇总</b><small>权重和 {number(weightSum,4)}</small></td>
            <td>100.0%</td>
            <td>{stratified.n_total?.toLocaleString()}</td>
            <Cell result={combinedRaw}/>
            <Cell result={combinedCuped}/>
            <td className="mono">层内</td>
            <td>{stratified.chosen_method==='cuped'?'采用 CUPED 汇总':'采用原始汇总'}</td>
          </tr>}
        </tbody>
      </table>
    </div>
    {strata.filter(s=>!s.valid).map(s=><p key={s.index} className="strata-reason">{s.label}：{s.reason||s.cuped_reason}</p>)}
    {strata.filter(s=>s.valid&&s.cuped_reason).map(s=><p key={s.index} className="strata-reason">{s.label}：{s.cuped_reason}</p>)}
    {stratified.variance_reduction!==null&&stratified.variance_reduction!==undefined&&
      <p className="strata-foot">分层汇总方差降低 {percent(stratified.variance_reduction)}（层内分别估计 θ，层间按 w²·SE² 合成）。</p>}
  </section>;
}
