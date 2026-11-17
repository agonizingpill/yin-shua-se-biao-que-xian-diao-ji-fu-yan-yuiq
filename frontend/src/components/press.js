import {esc,fixed} from '../utils/format.js';
import {STATES} from '../constants.js';
export const badge=(status,label)=>`<span class="status ${esc(status)}">${esc(label||STATES[status]||status)}</span>`;
export const jobLabel=(s,id)=>{const j=s.jobs.find(x=>x.id===id);return j?esc(j.code+' '+j.title):'#'+id};
export const proofPicker=s=>`<select id="proof-picker">${s.proofs.map(x=>`<option value="${x.id}" ${x.id===Number(s.proofId)?'selected':''}>${esc(x.code)} / ${esc(x.defect||STATES[x.classification_state])}</option>`).join('')}</select>`;
export const patches=p=>`<div class="cmyk">${['c','m','y','k'].map(k=>`<div class="patch">${fixed(p['density_'+k])}<small>${k.toUpperCase()} / 色标密度</small></div>`).join('')}</div>`;
export const empty=x=>`<div class="empty">${esc(x)}</div>`;
export function notify(x){const n=document.querySelector('#toast');n.textContent=x;n.classList.add('show');clearTimeout(window.nt);window.nt=setTimeout(()=>n.classList.remove('show'),4500)}
