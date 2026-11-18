import {esc,formData,fixed,localStamp} from '../utils/format.js';
import {notify,jobLabel,empty,patches} from '../components/press.js';
import {send} from '../api.js';

const inputs=()=>`<div class="cmykfields">${['c','m','y','k'].map(k=>`<div class="tone"><label>${k.toUpperCase()} / 实地密度</label><input name="density_${k}" type="number" min="0" max="3" step=".01" value="1.4" required></div>`).join('')}</div><label>网点扩大率 / %</label><input name="dot_gain" type="number" min="0" max="50" step=".1" value="14" required>`;
const labels={registered:'已登记待受理',accepted:'受理·复测合格待解除',blocked:'依据缺失待核实',defect:'复测缺陷待逐箱处置',released:'主管已解除',closed:'已结案'};
const boxState={returned:'客户退回原箱',quarantined:'未发隔离',recall_pending:'已发待召回',disposed:'已处置',released:'已解除'};
const methodLabel={scrap:'报废',rework:'返修',return_supplier:'退回供应商'};

export function render(s){const c=s.complaints.find(x=>x.id===Number(s.complaintId))||s.complaints[0];
 const activePacks=s.packs.filter(p=>p.state==='sealed'||p.state==='shipped');
 const pendingVer=s.verifications.filter(v=>v.state==='pending');
 const done=c?c.boxes.filter(b=>b.state==='disposed'||b.state==='released').length:0;
 return `<div class="head"><div><div class="eyebrow">COMPLAINT / RETEST / TRACE / 10</div><h1>退回来的一箱，牵出同一批。</h1><p>从客户退回的原箱登记客诉新色标，沿用训练判别。按原箱封箱时的合格抽检依据追溯同批箱：未发隔离、已发登记待召回，原装运证据不改。客诉受理后先冻结该批放行，合格由主管解除，缺陷须逐箱处置后结案；生产复机不解除箱隔离。</p></div><div class="picker"><select id="complaint-picker">${s.complaints.map(x=>`<option value="${x.id}" ${x.id===c?.id?'selected':''}>${esc(x.code)} · ${esc(labels[x.state]||x.state)}</option>`).join('')||'<option>暂无客诉</option>'}</select></div></div>
 <div class="production-layout"><div>
 ${c?`<section class="instruction"><div class="instruction-head"><div><div class="eyebrow">CASE / ${String(c.id).padStart(3,'0')} / ${esc(c.code)}</div><h2>${jobLabel(s,c.job_id)}</h2><p class="muted">原箱 ${esc(s.packs.find(p=>p.id===c.pack_id)?.code||'#'+c.pack_id)} · 受理人 ${esc(c.accepted_by||'待受理')} · 复测色标 ${esc(s.proofs.find(p=>p.id===c.proof_id)?.code)}</p></div><span class="status ${c.state==='released'?'pass':c.state==='defect'||c.state==='blocked'?'fail':''}">${esc(labels[c.state]||c.state)}</span></div>
 <p class="note">${esc(c.note)}</p>
 <div class="checkline"><span>追溯依据（原箱封箱合格抽检）</span><b>${c.basis_sample_id?`抽检#${c.basis_sample_id} / ${esc(c.basis_proof_code||'')}`:'缺失，待核实'}</b></div>
 <div class="checkline"><span>放行冻结</span><b>${['accepted','blocked','defect'].includes(c.state)?'冻结中':'已解除'}</b></div>
 <div class="checkline"><span>受影响箱处置进度</span><b>${done} / ${c.boxes.length}</b></div>
 <div class="actions">
 <button id="retest" ${s.user.role==='viewer'||c.state==='closed'||c.state==='released'?'disabled':''}>重试客诉复测判读</button>
 <button id="accept" ${s.user.role==='viewer'||!['registered'].includes(c.state)?'disabled':''}>受理客诉并冻结该批</button>
 </div>
 <form id="release-form"><label>主管解除依据（复测判合格后）</label><textarea name="release_note" minlength="5" required placeholder="复测色标四色密度与目标一致，判为合格，解除同批箱隔离"></textarea><div class="actions"><button class="magenta" ${s.user.role!=='admin'||c.state!=='accepted'?'disabled':''}>主管解除该批放行冻结</button></div></form>
 <form id="close-form"><label>结案说明（逐箱处置完成后）</label><textarea name="close_note" minlength="5" required placeholder="同批箱已全部隔离、召回并处置完毕"></textarea><div class="actions"><button class="primary" ${s.user.role!=='admin'||c.state!=='defect'?'disabled':''}>主管结案</button></div></form>
 </section>
 <section class="section"><h2>受影响箱与处置</h2><div class="tablewrap"><table><thead><tr><th>箱码</th><th>来源</th><th>张数</th><th>封箱依据</th><th>状态</th><th>处置</th></tr></thead><tbody>${c.boxes.map(b=>`<tr><td><b class="mono">${esc(b.pack_snapshot.pack_code)}</b></td><td>${b.kind==='returned'?'客户退回':b.kind==='shipped'?`已发 ${esc(s.shipments.find(x=>x.id===b.shipment_id)?.tracking||'')}`:'未发'}</td><td class="mono">${b.pack_snapshot.sheets}</td><td class="mono">抽检#${b.pack_snapshot.sample_id||'—'} / ${esc(b.pack_snapshot.proof_code||'')}</td><td><span class="status ${b.state==='disposed'||b.state==='released'?'pass':b.state==='recall_pending'?'hold':''}">${esc(boxState[b.state]||b.state)}</span></td><td>${b.state==='disposed'?`${esc(methodLabel[b.dispose_method]||b.dispose_method)} · ${esc(b.dispose_note)}`:b.state==='released'?'随合格复测解除':`<form class="dispose-form" data-box="${b.id}"><select name="method"><option value="scrap">报废</option><option value="rework">返修</option><option value="return_supplier">退回供应商</option></select><input name="note" minlength="5" placeholder="处置说明" required><button ${s.user.role==='viewer'||c.state!=='defect'?'disabled':''}>登记处置</button></form>`}</td></tr>`).join('')}</tbody></table></div>${c.boxes.length?'':'<p class="note">尚无追溯箱。先受理客诉，系统按原箱封箱的合格抽检依据追溯同批箱。</p>'}</section>
 <section class="section"><h2>已发箱召回登记</h2>${c.recalls.map(r=>`<article class="section" data-recall="${r.id}"><div class="eyebrow">RECALL-${r.id} / ${esc(r.tracking)}</div><h3>${esc(r.customer)} <span class="status ${r.state==='completed'?'pass':'fail'}">${r.state==='completed'?'召回完成':r.state==='cancelled'?'已取消':'待召回'}</span></h3><p class="muted">原装运证据 ${esc(r.shipment_snapshot?.dispatched_by||'—')} · 发货单状态 ${esc(r.shipment_snapshot?.state||'')}（不改写）</p>${r.state==='pending'?`<form class="recall-form" data-recall="${r.id}"><label>召回完成说明</label><input name="note" minlength="5" required placeholder="物流已拦截并退回工厂"><button ${s.user.role==='viewer'||c.state!=='defect'?'disabled':''}>登记召回完成</button></form>`:`<p class="note">${esc(r.note||'')} ${r.completed_at?'· '+esc(localStamp(r.completed_at)):''}</p>`}</article>`).join('')||'<p class="note">本客诉无已发同批箱，或尚未受理。</p>'}</section>`:empty('暂无客诉。请在右侧从已封/已发原箱登记客诉新色标。')}
 <section class="section"><h2>旧箱依据核实</h2>${pendingVer.map(v=>`<article class="section" data-verification="${v.id}"><div class="eyebrow">VERIFY-${v.id} / ${jobLabel(s,v.job_id)}</div><h3 class="status fail">已拦住开机单待核实</h3><p class="muted">${esc(v.reason)}</p><form class="verify-form" data-key="${v.id}"><label>核实所依据的同工单合格抽检</label><select name="sample_id">${s.samples.filter(x=>x.job_id===v.job_id&&x.state==='passed').map(x=>`<option value="${x.id}">抽检#${x.id} / 序${x.sequence} / 已印${x.quantity}张</option>`).join('')||'<option value="">暂无合格抽检</option>'}</select><label>核实依据</label><textarea name="resolution" minlength="5" required placeholder="查原始封箱记录，确认同批合格抽检依据"></textarea><button class="magenta" ${s.user.role!=='admin'?'disabled':''}>主管核实并解除拦截</button></form></article>`).join('')||'<p class="note">无待核实旧箱依据。</p>'}</section>
 </div>
 <aside class="section"><h2>登记客诉复测</h2><form id="complaint-form"><label>客户退回原箱（已封/已发）</label><select name="pack_id">${activePacks.map(p=>`<option value="${p.id}">${esc(p.code)} · ${p.sheets}张 · ${jobLabel(s,p.job_id)} · ${p.state}</option>`).join('')||'<option value="">暂无可登记原箱</option>'}</select><label>客诉编号</label><input name="code" value="CC-${Date.now().toString().slice(-6)}" required><label>客诉说明</label><textarea name="note" minlength="5" required placeholder="客户反馈画册封套整体偏红，退回原箱"></textarea><label>新色标编号</label><input name="proof_code" value="PS-CC-${Date.now().toString().slice(-5)}" required>${inputs()}<div class="actions"><button class="primary" ${s.user.role==='viewer'||!activePacks.length?'disabled':''}>登记客诉并判读新色标</button></div></form><p class="note">新色标沿用ReferenceSheet训练判别，当前样张不入训练。旧箱封箱依据缺失时，系统登记待核实并拦住该开机单。</p>
 <h2>复测结果</h2>${c?patches(s.proofs.find(p=>p.id===c.proof_id)||{}):''}${c?`<p class="muted">判读 ${esc(s.proofs.find(p=>p.id===c.proof_id)?.defect||'待判读')} · ${esc(localStamp(s.proofs.find(p=>p.id===c.proof_id)?.classified_at))}</p>`:''}</aside></div>`;}

export function bind(s,reload){const save=async(path,body,msg)=>{try{await send(path,body);await reload();notify(msg);}catch(e){notify(e.message)}};
 const picker=document.querySelector('#complaint-picker');if(picker)picker.onchange=async e=>{s.complaintId=Number(e.target.value);await reload()};
 const c=s.complaints.find(x=>x.id===Number(s.complaintId))||s.complaints[0];
 const cv=document.querySelector('#complaint-form');
 if(cv)cv.onsubmit=async e=>{e.preventDefault();const b=formData(e.target);for(const k of ['pack_id','density_c','density_m','density_y','density_k','dot_gain'])b[k]=Number(b[k]);try{const x=await send('/complaints',b);s.complaintId=x.id;await reload();notify('客诉已登记，新色标入队判读')}catch(err){notify(err.message)}};
 const retest=document.querySelector('#retest'),accept=document.querySelector('#accept'),releaseForm=document.querySelector('#release-form'),closeForm=document.querySelector('#close-form');
 if(c){
  const base='/complaints/'+c.id;
  if(retest)retest.onclick=()=>save(base+'/retest',{},'客诉复测已重新入队');
  if(accept)accept.onclick=()=>save(base+'/accept',{},'客诉已受理，该批放行冻结');
  if(releaseForm)releaseForm.onsubmit=e=>{e.preventDefault();save(base+'/release',formData(e.target),'主管已解除该批放行冻结');};
  if(closeForm)closeForm.onsubmit=e=>{e.preventDefault();save(base+'/close',formData(e.target),'客诉已结案');};
  document.querySelectorAll('.dispose-form').forEach(f=>f.onsubmit=e=>{e.preventDefault();save(base+'/boxes/'+f.dataset.box+'/dispose',formData(f),'受影响箱已处置');});
  document.querySelectorAll('.recall-form').forEach(f=>f.onsubmit=e=>{e.preventDefault();save(base+'/recalls/'+f.dataset.recall+'/complete',formData(f),'召回已完成');});
 }
 document.querySelectorAll('.verify-form').forEach(f=>f.onsubmit=e=>{e.preventDefault();const b=formData(f);b.sample_id=Number(b.sample_id);save('/job-verifications/'+f.dataset.key+'/resolve',b,'旧箱依据已核实');});}
