import {FormEvent,useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {ArrowRight} from 'lucide-react';
import {useResearchData} from '../hooks/useResearch';
import {createExperiment} from '../api/experiments';
import {enqueueRun} from '../api/runs';
import {useAction} from '../hooks/useAction';
import {useAuth} from '../stores/auth';
import {Notice} from '../components/common/Notice';

export function parseBounds(text:string):number[]|null|undefined{
  const trimmed=text.trim();
  if(!trimmed)return null;
  const parts=trimmed.split(/[,，\s]+/).filter(Boolean);
  const values=parts.map(p=>Number(p));
  if(values.some(v=>!Number.isFinite(v)))throw new Error('前置收入区间必须是数字，例如：25, 55');
  if(values.length>10)throw new Error('最多 10 个切点');
  for(let i=1;i<values.length;i++)if(values[i]<=values[i-1])throw new Error('前置收入切点必须严格递增，例如：25, 55');
  return values;
}

export function boundsHint(text:string){
  try{
    const values=parseBounds(text);
    if(!values||!values.length)return '留空表示沿用原方法，不按前置收入分层。';
    const fmt=(v:number)=>String(v);
    const labels=[`< ${fmt(values[0])}`];
    for(let i=1;i<values.length;i++)labels.push(`[${fmt(values[i-1])}, ${fmt(values[i])})`);
    labels.push(`≥ ${fmt(values[values.length-1])}`);
    return '将生成 '+labels.length+' 层：'+labels.join(' / ')+' 元';
  }catch(e){return (e as Error).message;}
}

export function Configure(){
  const s=useResearchData(),{user}=useAuth(),action=useAction(),navigate=useNavigate();
  const [name,setName]=useState(''),[hypothesis,setHypothesis]=useState(''),[alpha,setAlpha]=useState(.05),[cuped,setCuped]=useState(true),[did,setDid]=useState(0),[strata,setStrata]=useState('');
  function submit(e:FormEvent){
    e.preventDefault();
    action.execute(async()=>{
      const strata_bounds=parseBounds(strata);
      const exp=await createExperiment({name,hypothesis,dataset_id:did||s.datasets[0]?.id,alpha,cuped,strata_bounds});
      await enqueueRun(exp.id);
      navigate('/runs');
    });
  }
  return <div className="page">
    <div className="page-title"><div><p className="eyebrow">PRE-REGISTRATION / 03</p><h1>实验配置<span>先写假设，再看结果。</span></h1></div></div>
    <div className="editor-layout">
      <form className="research-form" onSubmit={submit}>
        <h2><span>01</span> 定义研究问题</h2>
        <label>实验名称<input aria-label="实验名称" value={name} onChange={e=>setName(e.target.value)} placeholder="例如：短文付费入口 v4" minLength={2} maxLength={120} required disabled={user?.role==='viewer'}/></label>
        <label>可检验的业务假设<textarea aria-label="业务假设" value={hypothesis} onChange={e=>setHypothesis(e.target.value)} placeholder="描述改动、预期影响与观测指标，至少8字。" minLength={8} required disabled={user?.role==='viewer'}/></label>
        <h2><span>02</span> 固定分析口径</h2>
        <label>观测数据<select value={did} onChange={e=>setDid(Number(e.target.value))}><option value="0">选择已冻结数据</option>{s.datasets.map(d=><option key={d.id} value={d.id}>{d.name} / {d.observations} 位用户</option>)}</select></label>
        <div className="form-pair">
          <label>显著性水平 α<select value={alpha} onChange={e=>setAlpha(Number(e.target.value))}><option value="0.05">0.05 / 95% 区间</option><option value="0.01">0.01 / 99% 区间</option><option value="0.1">0.10 / 90% 区间</option></select></label>
          <label>分析指标<input value="每用户7日收入 / revenue" readOnly/></label>
        </div>
        <label>前置收入分层切点 / 元
          <input aria-label="前置收入分层切点" value={strata} onChange={e=>setStrata(e.target.value)} placeholder="例如：25, 55（留空不分层）" disabled={user?.role==='viewer'}/>
          <small className="field-hint">{boundsHint(strata)}</small>
        </label>
        <label className="checkbox"><input type="checkbox" checked={cuped} onChange={e=>setCuped(e.target.checked)}/><span>使用前置收入执行 CUPED 方差校正<small>同时保留未经校正的 Welch 对照结果；启用分层时 θ 在层内分别估计。</small></span></label>
        <Notice message={action.error||s.error}/>
        {user?.role==='viewer'?<p className="notice">观察员可阅读配置；登记与运行需要分析师权限。</p>:<button className="primary" disabled={action.busy}>{action.busy?'提交中…':'登记并提交分析'}<ArrowRight size={17}/></button>}
      </form>
      <aside className="method-note">
        <span className="eyebrow">METHOD NOTE / 02</span>
        <h2>关于这次计算</h2>
        <ol>
          <li><b>Welch t 检验</b><p>允许两组方差不等，返回双侧 p 值、自由度与均值差区间。</p></li>
          <li><b>CUPED 校正</b><p>以分桶前收入作协变量，降低噪声；启用分层时在每层内估计 θ 并在层内校正。</p></li>
          <li><b>前置收入分层</b><p>切点在登记时固定。各层独立计算，按全体样本各层占比给两组相同权重汇总；每层结果都保留。</p></li>
          <li><b>何时不给结论</b><p>某层缺组或样本不足时说明原因，本次不给出放量结论；留空切点则沿用未分层原方法。</p></li>
        </ol>
      </aside>
    </div>
  </div>
}
