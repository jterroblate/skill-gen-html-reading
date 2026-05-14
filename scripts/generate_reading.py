#!/usr/bin/env python3
"""Generate standalone IELTS reading practice HTML from structured JSON."""
import argparse
import html
import json
import os
import re
import sys
from typing import Any


def h(value: Any) -> str:
    return html.escape(str(value), quote=False)


def a(value: Any) -> str:
    return html.escape(str(value), quote=True)


SUPPORTED_QTYPES = {"mcq", "tfng", "true_false", "ynng", "yes_no", "match", "fill", "summary", "heading_info"}


def normalize_heading(item):
    if isinstance(item, dict):
        return str(item.get("key", "")), str(item.get("text", ""))
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        return str(item[0]), str(item[1])
    return "", ""


def validate_data(data: dict) -> None:
    errors = []
    if not isinstance(data, dict):
        raise ValueError("root must be an object")
    if not isinstance(data.get("title"), str) or not data["title"].strip():
        errors.append("title is required")
    passages = data.get("passages")
    if not isinstance(passages, list) or len(passages) not in (1, 3, 5):
        errors.append("passages must contain 1, 3, or 5 passage objects")
        passages = passages if isinstance(passages, list) else []
    seen_nums = set()
    for i, p in enumerate(passages, 1):
        base = f"passages[{i}]"
        if not isinstance(p, dict):
            errors.append(f"{base} must be an object")
            continue
        for field in ("num", "title", "paras", "questions"):
            if field not in p:
                errors.append(f"{base}.{field} is required")
        num = p.get("num")
        if not isinstance(num, int) or num < 1:
            errors.append(f"{base}.num must be a positive integer")
        elif num in seen_nums:
            errors.append(f"{base}.num duplicates {num}")
        else:
            seen_nums.add(num)
        if not isinstance(p.get("title"), str) or not p.get("title", "").strip():
            errors.append(f"{base}.title must be a non-empty string")
        paras = p.get("paras")
        if not isinstance(paras, list) or not paras:
            errors.append(f"{base}.paras must be a non-empty array")
            paras = []
        labels = []
        for j, para in enumerate(paras, 1):
            if not isinstance(para, dict):
                errors.append(f"{base}.paras[{j}] must be an object")
                continue
            if not isinstance(para.get("label"), str) or not para.get("label"):
                errors.append(f"{base}.paras[{j}].label is required")
            if not isinstance(para.get("text"), str) or not para.get("text"):
                errors.append(f"{base}.paras[{j}].text is required")
            labels.append(para.get("label"))
        qdata = p.get("questions")
        if not isinstance(qdata, dict):
            errors.append(f"{base}.questions must be an object")
            continue
        q_group_type = qdata.get("type")
        if q_group_type not in ("regular", "heading"):
            errors.append(f"{base}.questions.type must be regular or heading")
        blocks = qdata.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            errors.append(f"{base}.questions.blocks must be a non-empty array")
            blocks = []
        if q_group_type == "heading":
            headings = qdata.get("headings")
            answers = qdata.get("answers")
            if not isinstance(headings, list) or not headings:
                errors.append(f"{base}.questions.headings is required for heading passages")
                heading_keys = set()
            else:
                heading_keys = {normalize_heading(x)[0] for x in headings if normalize_heading(x)[0]}
            if not isinstance(answers, dict) or not answers:
                errors.append(f"{base}.questions.answers is required for heading passages")
            else:
                for label in labels:
                    if label not in answers:
                        errors.append(f"{base}.questions.answers missing paragraph {label}")
                    elif heading_keys and answers[label] not in heading_keys:
                        errors.append(f"{base}.questions.answers.{label} must be a heading key")
        for j, blk in enumerate(blocks, 1):
            b = f"{base}.questions.blocks[{j}]"
            if not isinstance(blk, dict):
                errors.append(f"{b} must be an object")
                continue
            if not isinstance(blk.get("q"), int):
                errors.append(f"{b}.q is required and must be integer")
            typ = blk.get("type")
            if typ not in SUPPORTED_QTYPES:
                errors.append(f"{b}.type unsupported: {typ}")
                continue
            if typ == "mcq":
                if not isinstance(blk.get("stem"), str): errors.append(f"{b}.stem is required")
                opts = blk.get("options")
                if not isinstance(opts, list) or len(opts) < 2: errors.append(f"{b}.options must contain at least 2 strings")
                if not isinstance(blk.get("answer"), str) or not blk.get("answer"): errors.append(f"{b}.answer is required")
            elif typ in ("tfng", "true_false", "ynng", "yes_no"):
                if not isinstance(blk.get("statement"), str): errors.append(f"{b}.statement is required")
                allowed = {"TRUE", "FALSE", "NOT GIVEN"} if typ in ("tfng", "true_false") else {"YES", "NO", "NOT GIVEN"}
                if blk.get("answer") not in allowed: errors.append(f"{b}.answer must be one of {sorted(allowed)}")
            elif typ == "match":
                if not isinstance(blk.get("text"), str): errors.append(f"{b}.text is required")
                if not isinstance(blk.get("options"), list) or not blk.get("options"): errors.append(f"{b}.options is required")
                if not isinstance(blk.get("answer"), str) or not blk.get("answer"): errors.append(f"{b}.answer is required")
            elif typ == "fill":
                if not isinstance(blk.get("answer"), str) or not blk.get("answer"): errors.append(f"{b}.answer is required")
            elif typ == "summary":
                pairs = blk.get("pairs")
                if not isinstance(pairs, list) or not pairs: errors.append(f"{b}.pairs is required")
                else:
                    for k, pair in enumerate(pairs, 1):
                        if not isinstance(pair, list) or len(pair) < 4:
                            errors.append(f"{b}.pairs[{k}] must be [q,before,answer,after]")
            elif typ == "heading_info":
                # q + optional reveal only; answer is stored in heading slots.
                pass
    if errors:
        raise ValueError("Schema validation failed:\n  - " + "\n  - ".join(errors))


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
<meta charset=\"UTF-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
<title>{{PAGE_TITLE}}</title>
<script src=\"https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js\"></script>
<script src=\"https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js\"></script>
<style>
{{STYLES}}
</style>
</head>
<body>

<div class=\"tab-bar\">
{{TAB_BUTTONS}}
</div>

<div class=\"action-bar\">
  <button class=\"btn btn-primary\" id=\"submitBtn\" onclick=\"submitAnswers()\">✍ 提交答案</button>
  <button class=\"btn btn-secondary\" onclick=\"resetAll()\">🔄 重置本篇</button>
  <span class=\"score-badge\" id=\"scoreBadge\"></span>
</div>

<div class=\"pdf-section\" id=\"pdfSection\">
  <strong>📄 导出本篇成绩报告</strong><br>
  <input id=\"studentName\" placeholder=\"学生姓名\" style=\"width:160px\">
  <input id=\"reportDate\" type=\"date\" style=\"width:150px\">
  <button class=\"btn btn-success\" onclick=\"exportPDF()\">📥 下载 PDF</button>
</div>

<div class=\"header\">
  <h1>{{HEADER_TITLE}}</h1>
  <div class=\"sub\" id=\"headerSub\">{{HEADER_SUB}}</div>
</div>

<div class=\"layout\" id=\"layout\">
{{PASSAGE_SECTIONS}}
</div><!-- /layout -->

<script>
{{JAVASCRIPT}}
</script>
</body>
</html>
"""

DEFAULT_STYLES = r""":root{--bg:#faf8f7;--card:#fffcf9;--sidebar:#f5f0eb;--text:#3a3a3a;--text2:#7a7a7a;--accent:#d97757;--accent-light:#fef0e8;--success:#2d8659;--error:#c0392b;--border:#e8ddd5;--radius:8px;--font:'Georgia','Times New Roman',serif;--ui-font:-apple-system,'Helvetica Neue','PingFang SC',sans-serif}
*{box-sizing:border-box;margin:0;padding:0}body{background:var(--bg);color:var(--text);font-family:var(--font);line-height:1.7;height:100vh;overflow:hidden}.tab-bar{background:var(--card);border-bottom:1px solid var(--border);display:flex;position:sticky;top:0;z-index:20;overflow-x:auto}.tab-btn{flex:1;min-width:70px;padding:12px 6px;border:none;background:none;cursor:pointer;font-size:11px;font-family:var(--ui-font);color:var(--text2);border-bottom:3px solid transparent}.tab-btn:hover{color:var(--accent)}.tab-btn.active{color:var(--accent);border-bottom-color:var(--accent);font-weight:600}.tab-badge{display:inline-block;background:var(--accent);color:#fff;border-radius:10px;padding:1px 7px;font-size:10px;margin-left:4px}.action-bar{display:flex;gap:6px;flex-wrap:wrap;align-items:center;justify-content:center;padding:4px 16px;background:var(--card);border-bottom:1px solid var(--border)}.action-bar .btn{padding:4px 12px;font-size:11px}.pdf-section{padding:4px 16px;background:var(--sidebar);border-bottom:1px solid var(--border);display:none;font-size:12px;text-align:center}.pdf-section.show{display:block}.pdf-section input{padding:3px 8px;border:1px solid var(--border);border-radius:var(--radius);font-size:11px;font-family:var(--ui-font);margin-right:4px;margin-bottom:2px}.header{background:var(--card);border-bottom:1px solid var(--border);padding:12px 32px}.header h1{font-size:16px;font-weight:600;color:var(--accent)}.header .sub{font-size:12px;color:var(--text2);font-family:var(--ui-font);margin-top:2px}.layout{display:flex;min-height:calc(100vh - 144px)}.passage-col{flex:1.1;padding:28px;overflow-y:auto;height:calc(100vh - 144px);position:sticky;top:0;background:var(--card);border-right:1px solid var(--border)}.questions-col{flex:.9;padding:28px;overflow-y:auto;height:calc(100vh - 144px);position:sticky;top:0;background:var(--sidebar)}.p-title{font-size:18px;font-weight:600;margin-bottom:4px;color:var(--accent)}.p-meta{font-size:12px;color:var(--text2);font-family:var(--ui-font);margin-bottom:20px}.para{margin-bottom:14px;font-size:14px;text-align:justify;line-height:1.85}.para .label{font-weight:700;color:var(--accent);margin-right:2px}.q-block{margin-bottom:16px}.q-text{font-size:13.5px;margin-bottom:5px;font-family:var(--ui-font)}.q-text .num{font-weight:600;color:var(--text)}.q-inst{font-size:12px;color:var(--text2);font-family:var(--ui-font);margin-bottom:12px;font-style:italic}.mcq-group{display:flex;flex-direction:column;gap:4px}.mcq-opt{padding:7px 10px;border:1.5px solid var(--border);border-radius:var(--radius);cursor:pointer;font-size:12.5px;font-family:var(--ui-font);background:var(--card)}.mcq-opt:hover{border-color:var(--accent)}.mcq-opt.selected{border-color:var(--accent);background:var(--accent-light)}.mcq-opt.wrong-only{border-color:var(--error);background:#fef2f2}.mcq-opt.correct{border-color:var(--success);background:#e6f4ea}.tfng-group,.ynng-group{display:flex;gap:4px;flex-wrap:wrap}.tfng-btn,.ynng-btn{padding:7px 12px;border:1.5px solid var(--border);border-radius:var(--radius);cursor:pointer;font-size:12px;font-family:var(--ui-font);background:var(--card)}.tfng-btn:hover,.ynng-btn:hover{border-color:var(--accent)}.tfng-btn.selected,.ynng-btn.selected{border-color:var(--accent);background:var(--accent-light)}.tfng-btn.wrong-only,.ynng-btn.wrong-only{border-color:var(--error);background:#fef2f2}.tfng-btn.correct,.ynng-btn.correct{border-color:var(--success);background:#e6f4ea}.match-select{width:100%;padding:6px 10px;border:1.5px solid var(--border);border-radius:var(--radius);font-size:12px;font-family:var(--ui-font);margin-top:2px;background:var(--card)}.match-select.wrong-only{border-color:var(--error);background:#fef2f2}.match-select.correct{border-color:var(--success);background:#e6f4ea}.fill-input{width:220px;padding:6px 10px;border:1.5px solid var(--border);border-radius:var(--radius);font-size:12.5px;font-family:var(--ui-font);background:var(--card);margin-top:4px}.fill-input.wrong-only{border-color:var(--error);background:#fef2f2}.fill-input.correct{border-color:var(--success);background:#e6f4ea}.heading-pool{display:flex;flex-direction:column;gap:6px;margin-bottom:14px;padding:12px;background:var(--card);border:1.5px solid var(--border);border-radius:var(--radius);max-height:42vh;overflow-y:auto}.heading-item{display:block;padding:7px 10px;border:1.5px solid var(--accent);border-radius:var(--radius);cursor:grab;font-size:12px;line-height:1.35;background:var(--accent-light);color:var(--text);user-select:none;white-space:normal}.heading-item:hover{border-color:#c0664a;background:#fde4d4}.heading-item.dragging{opacity:.4}.heading-item.selected{outline:2px solid var(--accent);background:#fde4d4}.heading-item.used{opacity:.35;cursor:default;border-style:dashed;background:var(--sidebar)}.heading-drop-row{margin:16px 0 6px;padding:10px 12px;background:#fff8f3;border:1px solid var(--border);border-radius:var(--radius);font-family:var(--ui-font)}.heading-drop-label{font-size:12px;font-weight:700;color:var(--accent);margin-bottom:6px}.heading-slot{display:flex;align-items:center;justify-content:flex-start;width:100%;min-height:42px;border:2px dashed var(--border);border-radius:var(--radius);background:var(--card);font-size:12.5px;font-weight:600;color:var(--text);font-family:var(--ui-font);padding:8px 10px;cursor:pointer;line-height:1.4}.heading-slot.dragover{border-color:var(--accent);background:var(--accent-light)}.heading-slot.filled{border-style:solid;border-color:var(--accent);background:var(--accent-light)}.heading-slot.wrong-only{border-color:var(--error);background:#fef2f2}.heading-slot.correct{border-color:var(--success);background:#e6f4ea}.heading-slot.revealed{border-color:var(--success);background:#e6f4ea}.heading-slot .slot-placeholder{font-size:12px;color:var(--text2);font-weight:400}.heading-slot b{white-space:normal}.heading-slot .correct-prefix{color:var(--success);font-weight:700;margin-right:4px}.answer-reveal{display:none;margin-top:4px;padding:6px 10px;border-radius:var(--radius);font-size:12px;font-family:var(--ui-font)}.answer-reveal.show{display:block;background:#e6f4ea;color:var(--success);border:1px solid var(--success)}.reveal-btn-single{display:inline-block;margin-top:4px;padding:3px 10px;border:1px solid var(--border);border-radius:var(--radius);cursor:pointer;font-size:11px;font-family:var(--ui-font);background:var(--card);color:var(--text2)}.reveal-btn-single:hover{border-color:var(--accent);color:var(--accent)}.reveal-btn-single:disabled{opacity:.4;cursor:default}.reveal-btn-single.enabled{border-color:var(--accent);color:var(--accent)}.passage-panel{display:none}.passage-panel.active{display:flex;flex:1;overflow:hidden}.btn{padding:7px 16px;border:none;border-radius:var(--radius);cursor:pointer;font-size:12.5px;font-family:var(--ui-font);font-weight:500}.btn-primary{background:var(--accent);color:#fff}.btn-primary:hover{opacity:.85}.btn-secondary{background:var(--sidebar);color:var(--text);border:1px solid var(--border)}.btn-success{background:var(--success);color:#fff}.btn:disabled{opacity:.4;cursor:default}.score-badge{font-size:13px;font-family:var(--ui-font);color:var(--text2);margin-left:auto}.score-badge strong{color:var(--text)}@media(max-width:900px){.layout{flex-direction:column}.passage-col,.questions-col{flex:1;padding:16px;border-right:none;height:auto;position:static;overflow-y:visible}.tab-btn{font-size:10px;padding:8px 4px}.heading-pool{max-height:none}.heading-drop-row{margin:14px 0 6px}.heading-slot{min-height:46px}}
"""

DEFAULT_JS = r"""
let currentPassage = PASSAGE_NUMS[0];
let selectedHeading = null;
const passageNums = PASSAGE_NUMS;
const pState = Object.fromEntries(passageNums.map(p => [p, {submitted:false, results:null}]));
const passageInfo = PASSAGE_INFO;

function switchPassage(p){
  currentPassage=p;
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.toggle('active',Number(b.dataset.p)===p));
  document.querySelectorAll('.passage-panel').forEach(pan=>pan.classList.remove('active'));
  const panel=document.querySelector(`.passage-panel[data-p="${p}"]`); if(panel) panel.classList.add('active');
  const info=passageInfo[p];
  document.getElementById('headerSub').textContent=info.num+' "'+info.title+'" · Band '+info.band+' · '+info.genre;
  restorePassageUI(p);
}
function restorePassageUI(p){
  const s=pState[p],badge=document.getElementById('scoreBadge'),submitBtn=document.getElementById('submitBtn'),pdfSec=document.getElementById('pdfSection');
  if(s.submitted){submitBtn.disabled=true;if(s.results) badge.innerHTML='得分: <strong>'+s.results.correct+'/'+s.results.total+'</strong> ('+s.results.pct+'%)';pdfSec.classList.add('show');document.getElementById('reportDate').value=new Date().toISOString().slice(0,10);const panel=document.querySelector(`.passage-panel[data-p="${p}"]`);panel.querySelectorAll('.reveal-btn-single').forEach(btn=>{const qNum=btn.dataset.qnum,reveal=panel.querySelector(`.answer-reveal[data-reveal="${qNum}"]`);if(reveal&&reveal.classList.contains('show')){btn.disabled=true;btn.textContent='✅ 已显示';btn.style.opacity='0.5'}else{btn.disabled=false;btn.classList.add('enabled')}})}
  else{submitBtn.disabled=false;pdfSec.classList.remove('show');badge.innerHTML=''}
}
function selectMCQ(el){if(pState[currentPassage].submitted)return;const g=el.parentElement;g.querySelectorAll('.mcq-opt').forEach(o=>o.classList.remove('selected'));el.classList.add('selected')}
function selectTFNG(el){if(pState[currentPassage].submitted)return;const g=el.parentElement;g.querySelectorAll('.tfng-btn,.ynng-btn').forEach(b=>b.classList.remove('selected'));el.classList.add('selected')}
function gradePanel(panel){
  const qCol=panel.querySelector('[id^="qcol"]')||panel.querySelector('.questions-col');if(!qCol)return{correct:0,total:0,wrongs:[]};let correct=0,total=0;const wrongs=[];panel.querySelectorAll('.wrong-only,.correct').forEach(e=>e.classList.remove('wrong-only','correct'));
  qCol.querySelectorAll('.mcq-group').forEach(g=>{total++;const q=g.dataset.q,ca=g.dataset.ans,s=g.querySelector('.selected');if(s){const l=s.textContent.trim().charAt(0);if(l===ca){correct++;s.classList.add('correct')}else{s.classList.add('wrong-only');wrongs.push({q:'Q'+q,userAns:l,correctAns:ca})}}else{wrongs.push({q:'Q'+q,userAns:'(未选)',correctAns:ca})}});
  qCol.querySelectorAll('.tfng-group,.ynng-group').forEach(g=>{total++;const q=g.dataset.q,ca=g.dataset.ans,s=g.querySelector('.selected');if(s){if(s.textContent.trim()===ca){correct++;s.classList.add('correct')}else{s.classList.add('wrong-only');wrongs.push({q:'Q'+q,userAns:s.textContent.trim(),correctAns:ca})}}else{wrongs.push({q:'Q'+q,userAns:'(未选)',correctAns:ca})}});
  qCol.querySelectorAll('.match-select').forEach(s=>{total++;const q=s.dataset.q,ca=s.dataset.ans,v=s.value;if(v===ca){correct++;s.classList.add('correct')}else{s.classList.add('wrong-only');wrongs.push({q:'Q'+q,userAns:v||'(未选)',correctAns:ca})}});
  qCol.querySelectorAll('.fill-input').forEach(inp=>{total++;const q=inp.dataset.q,ca=inp.dataset.ans,ua=inp.value.trim().toLowerCase();if(ua===ca.toLowerCase()){correct++;inp.classList.add('correct')}else{inp.classList.add('wrong-only');wrongs.push({q:'Q'+q,userAns:inp.value||'(未填)',correctAns:ca})}});
  panel.querySelectorAll('.passage-col .heading-slot').forEach(slot=>{total++;const q=slot.dataset.q,ca=slot.dataset.ans,va=slot.dataset.val||'';if(va===ca){correct++;slot.classList.add('correct')}else{slot.classList.add('wrong-only');wrongs.push({q:'Q'+q,userAns:va||'(未拖)',correctAns:ca})}});
  return{correct,total,wrongs,pct:total>0?Math.round(correct/total*100):0};
}
function submitAnswers(){const p=currentPassage,panel=document.querySelector(`.passage-panel[data-p="${p}"]`);if(!panel)return;const r=gradePanel(panel);pState[p].submitted=true;pState[p].results=r;document.getElementById('scoreBadge').innerHTML='得分: <strong>'+r.correct+'/'+r.total+'</strong> ('+r.pct+'%)';document.getElementById('submitBtn').disabled=true;document.getElementById('pdfSection').classList.add('show');document.getElementById('reportDate').value=new Date().toISOString().slice(0,10);panel.querySelectorAll('.reveal-btn-single').forEach(b=>{b.disabled=false;b.classList.add('enabled')})}
function revealHeadingSlot(panel,qNum){const slot=panel.querySelector(`.passage-col .heading-slot[data-q="${qNum}"]`);if(!slot)return;const text=slot.dataset.answerText||slot.dataset.ans||'';slot.innerHTML='';const prefix=document.createElement('span');prefix.className='correct-prefix';prefix.textContent='正确答案：';const b=document.createElement('b');b.textContent=text;slot.appendChild(prefix);slot.appendChild(b);slot.dataset.val=slot.dataset.ans;slot.classList.add('filled','revealed','correct');slot.classList.remove('wrong-only');}
function toggleReveal(btn,qNum){const panel=btn.closest('.passage-panel'),reveal=panel.querySelector(`.answer-reveal[data-reveal="${qNum}"]`);revealHeadingSlot(panel,qNum);if(reveal){reveal.classList.add('show');btn.disabled=true;btn.textContent='✅ 已显示';btn.style.opacity='0.5'}}
function resetAll(){const p=currentPassage;pState[p]={submitted:false,results:null};selectedHeading=null;const panel=document.querySelector(`.passage-panel[data-p="${p}"]`);panel.querySelectorAll('.wrong-only,.correct,.revealed').forEach(e=>e.classList.remove('wrong-only','correct','revealed'));panel.querySelectorAll('.selected').forEach(e=>e.classList.remove('selected'));panel.querySelectorAll('.fill-input').forEach(inp=>inp.value='');panel.querySelectorAll('.match-select').forEach(s=>s.value='');panel.querySelectorAll('.heading-slot').forEach(slot=>{slot.innerHTML='<span class="slot-placeholder">拖拽或点选右侧 heading 后放到这里</span>';slot.classList.remove('wrong-only','correct','filled','revealed');delete slot.dataset.val;});const pool=panel.querySelector('.heading-pool');if(pool){pool.querySelectorAll('.heading-item').forEach(it=>{it.classList.remove('used','selected');it.draggable=true;});}panel.querySelectorAll('.answer-reveal').forEach(el=>el.classList.remove('show'));panel.querySelectorAll('.reveal-btn-single').forEach(btn=>{btn.disabled=true;btn.classList.remove('enabled');btn.textContent='💡 显示解析';btn.style.opacity=''});document.getElementById('scoreBadge').innerHTML='';document.getElementById('submitBtn').disabled=false;document.getElementById('pdfSection').classList.remove('show');}
function exportPDF(){const p=currentPassage,name=document.getElementById('studentName').value||'未填写',date=document.getElementById('reportDate').value||new Date().toISOString().slice(0,10),r=pState[p].results;if(!r){alert('请先提交本篇答案');return}const info=passageInfo[p],{jsPDF}=window.jspdf,doc=new jsPDF('p','mm','a4');let y=25;doc.setFontSize(16);doc.setTextColor(217,119,87);doc.text('IELTS Reading · 成绩报告',105,y,{align:'center'});y+=10;doc.setTextColor(58,58,58);doc.setFontSize(11);doc.text('姓名: '+name+'    日期: '+date,20,y);y+=7;doc.text('文章: '+info.num+' '+info.title,20,y);y+=7;doc.setFontSize(14);doc.text('得分: '+r.correct+'/'+r.total+' ('+r.pct+'%)',20,y);y+=12;if(r.wrongs.length===0){doc.setFontSize(12);doc.text('全部正确! 没有错题。',20,y)}else{doc.setFontSize(13);doc.text('错题记录 ('+r.wrongs.length+'题):',20,y);y+=8;doc.setFontSize(10);r.wrongs.forEach(w=>{if(y>275){doc.addPage();y=20}doc.text(w.q,20,y);doc.text('你的答案: '+w.userAns+'    正确答案: '+w.correctAns,30,y+5);y+=12})}doc.save('IELTS_Reading_'+info.num+'_'+name+'_'+date+'.pdf');}
function dragHeading(e){selectedHeading=e.target.dataset.heading;e.dataTransfer.setData('text/plain',selectedHeading);e.target.classList.add('dragging');}
function dragEnd(e){e.target.classList.remove('dragging');}
function selectHeadingItem(item){if(item.classList.contains('used'))return;const panel=item.closest('.passage-panel');if(panel){panel.querySelectorAll('.heading-item.selected').forEach(i=>i.classList.remove('selected'));}selectedHeading=item.dataset.heading;item.classList.add('selected');}
function allowDrop(e){e.preventDefault();e.currentTarget.classList.add('dragover');}
function dropHeading(e){e.preventDefault();var slot=e.currentTarget;slot.classList.remove('dragover');var heading=e.dataTransfer.getData('text/plain')||selectedHeading;if(!heading)return;placeHeading(slot,heading);}
function clearHeadingSlot(slot){if(!slot.dataset.val)return;var heading=slot.dataset.val;slot.innerHTML='<span class="slot-placeholder">拖拽或点选右侧 heading 后放到这里</span>';slot.classList.remove('filled','wrong-only','correct','revealed');delete slot.dataset.val;var panel=slot.closest('.passage-panel');var pool=panel?panel.querySelector('.heading-pool'):null;if(pool){var item=pool.querySelector('.heading-item[data-heading="'+CSS.escape(heading)+'"]');if(item){item.classList.remove('used','selected');item.draggable=true;}}}
function clickSlot(slot){if(pState[currentPassage].submitted)return;if(selectedHeading){placeHeading(slot,selectedHeading);return;}clearHeadingSlot(slot);}
function placeHeading(slot,heading){if(pState[currentPassage].submitted)return;var panel=slot.closest('.passage-panel');var pool=panel?panel.querySelector('.heading-pool'):null;var fullText=heading;if(slot.dataset.val&&slot.dataset.val!==heading)clearHeadingSlot(slot);if(pool){var item=pool.querySelector('.heading-item[data-heading="'+CSS.escape(heading)+'"]');if(item&&item.classList.contains('used'))return;if(item){item.classList.add('used');item.classList.remove('selected');item.draggable=false;fullText=item.textContent.trim();}}slot.textContent='';var b=document.createElement('b');b.textContent=fullText;slot.appendChild(b);slot.dataset.val=heading;slot.classList.add('filled');slot.classList.remove('wrong-only','correct','revealed');selectedHeading=null;}
document.addEventListener('DOMContentLoaded',function(){document.querySelectorAll('.answer-reveal').forEach(reveal=>{const qNum=reveal.dataset.reveal,btn=document.createElement('button');btn.className='reveal-btn-single';btn.dataset.qnum=qNum;btn.textContent='💡 显示解析';btn.disabled=true;btn.onclick=function(){toggleReveal(this,qNum)};reveal.parentNode.insertBefore(btn,reveal);});switchPassage(currentPassage);});
"""


def build_summary(num_pairs, reveals=None):
    sentences, reveal_list = [], []
    for i, pair in enumerate(num_pairs):
        q_num, before, answer, after = pair[:4]
        inp = (f'<span class="summary-q"><span class="num">{h(q_num)}.</span> '
               f'<input class="fill-input" data-q="{a(q_num)}" data-ans="{a(answer)}" '
               f'placeholder="输入答案" style="display:inline;width:160px;vertical-align:middle"></span>')
        sentences.append(f'{h(before)} {inp} {h(after)}')
        r = reveals[i] if reveals and i < len(reveals) else answer
        reveal_list.append(build_reveal(q_num, r))
    return '<div class="summary-paragraph">\n<p>' + ' '.join(sentences) + '</p>\n</div>\n' + '\n'.join(reveal_list)


def build_heading_slot(p_num, label, q_num, answer, answer_text=''):
    full_answer = f'{answer}. {answer_text}' if answer_text else str(answer)
    return (f'<div class="heading-drop-row" data-para="{a(label)}" data-q="{a(q_num)}">'
            f'<div class="heading-drop-label">Q{h(q_num)} · Paragraph {h(label)} heading</div>'
            f'<div class="heading-slot" data-p="{a(p_num)}" data-para="{a(label)}" data-q="{a(q_num)}" '
            f'data-ans="{a(answer)}" data-answer-text="{a(full_answer)}" '
            f'ondragover="allowDrop(event)" ondrop="dropHeading(event)" onclick="clickSlot(this)">'
            f'<span class="slot-placeholder">拖拽或点选右侧 heading 后放到这里</span></div></div>')


def build_reveal(q_num, text):
    return f'<div class="answer-reveal" data-reveal="{a(q_num)}">{h(text)}</div>'


def build_heading_pool(p_num, headings):
    items = []
    for item in headings:
        key, text = normalize_heading(item)
        items.append(f'<span class="heading-item" draggable="true" data-heading="{a(key)}" onclick="selectHeadingItem(this)" ondragstart="dragHeading(event)" ondragend="dragEnd(event)">{h(key)}. {h(text)}</span>')
    return f'<div class="heading-pool" id="p{a(p_num)}-heading-pool">\n' + '\n'.join(items) + '\n</div>\n'


def build_para(label, text):
    return f'<p class="para"><span class="label">[{h(label)}]</span> {h(text)}</p>'


def build_mcq(num, stem, options, answer, reveal=None):
    opts = '\n'.join(f'<div class="mcq-opt" onclick="selectMCQ(this)">{h(opt)}</div>' for opt in options)
    return f'<div class="q-block"><div class="q-text"><span class="num">{h(num)}.</span> {h(stem)}</div>\n<div class="mcq-group" data-q="{a(num)}" data-ans="{a(answer)}">{opts}</div>\n{build_reveal(num, reveal or answer)}</div>'


def build_tfng(num, statement, answer, reveal=None):
    btns = ''.join(f'<div class="tfng-btn" onclick="selectTFNG(this)">{v}</div>' for v in ['TRUE', 'FALSE', 'NOT GIVEN'])
    return f'<div class="q-block"><div class="q-text"><span class="num">{h(num)}.</span> {h(statement)}</div>\n<div class="tfng-group" data-q="{a(num)}" data-ans="{a(answer)}">{btns}</div>\n{build_reveal(num, reveal or answer)}</div>'


def build_ynng(num, statement, answer, reveal=None):
    btns = ''.join(f'<div class="ynng-btn" onclick="selectTFNG(this)">{v}</div>' for v in ['YES', 'NO', 'NOT GIVEN'])
    return f'<div class="q-block"><div class="q-text"><span class="num">{h(num)}.</span> {h(statement)}</div>\n<div class="ynng-group" data-q="{a(num)}" data-ans="{a(answer)}">{btns}</div>\n{build_reveal(num, reveal or answer)}</div>'


def build_match_select(num, text, options, answer, reveal=None):
    opts = ''.join(f'<option value="{a(v)}">{h(v)}</option>' for v in options)
    return f'<div class="q-block"><div class="q-text"><span class="num">{h(num)}.</span> {h(text)}</div>\n<select class="match-select" data-q="{a(num)}" data-ans="{a(answer)}"><option value="">— 选择 —</option>{opts}</select>\n{build_reveal(num, reveal or answer)}</div>'


def build_fill(num, text_before, text_after, answer, width=140, reveal=None):
    width = int(width) if str(width).isdigit() else 140
    inp = f'<input class="fill-input" data-q="{a(num)}" data-ans="{a(answer)}" placeholder="输入答案" style="display:inline;width:{width}px;vertical-align:middle">'
    return f'<div class="q-block"><div class="q-text"><span class="num">{h(num)}.</span> {h(text_before)} {inp} {h(text_after)}</div>\n{build_reveal(num, reveal or answer)}</div>'


def build_passage(p_num, pc_html, qc_html, active=False):
    cls = 'passage-panel active' if active else 'passage-panel'
    return f'<!-- ==================== PASSAGE {h(p_num)} ==================== -->\n<div class="{cls}" data-p="{a(p_num)}">\n<div class="passage-col">\n{pc_html}\n</div>\n\n<div class="questions-col" id="qcol{a(p_num)}">\n{qc_html}\n</div>\n</div>'


def max_question_number(blocks, minimum=0):
    max_q = minimum
    for blk in blocks:
        if blk.get('type') == 'summary':
            for pair in blk.get('pairs', []):
                if pair:
                    try:
                        max_q = max(max_q, int(pair[0]))
                    except Exception:
                        pass
        else:
            try:
                max_q = max(max_q, int(blk.get('q', 0)))
            except Exception:
                pass
    return max_q


def build_question_blocks(blocks):
    lines = []
    for blk in blocks:
        typ, q, answer, reveal = blk.get('type', ''), blk['q'], blk.get('answer', ''), blk.get('reveal')
        if typ == 'mcq': lines.append(build_mcq(q, blk.get('stem', ''), blk.get('options', []), answer, reveal))
        elif typ in ('tfng', 'true_false'): lines.append(build_tfng(q, blk.get('statement', ''), answer, reveal))
        elif typ in ('ynng', 'yes_no'): lines.append(build_ynng(q, blk.get('statement', ''), answer, reveal))
        elif typ == 'match': lines.append(build_match_select(q, blk.get('text', ''), blk.get('options', []), answer, reveal))
        elif typ == 'summary': lines.append(build_summary(blk.get('pairs', []), blk.get('reveals')))
        elif typ == 'fill': lines.append(build_fill(q, blk.get('before', ''), blk.get('after', ''), answer, blk.get('width', 140), reveal))
        elif typ == 'heading_info':
            label = blk.get('label') or chr(64 + int(q)) if isinstance(q, int) and q > 0 else ''
            lines.append(f'<div class="q-block"><div class="q-text"><span class="num">{h(q)}.</span> Paragraph {h(label)}</div>\n{build_reveal(q, reveal or "✅")}\n</div>')
    return lines


def generate(data, output_path):
    validate_data(data)
    page_title = data.get('title', 'IELTS Reading Practice')
    header_title = data.get('header_title', 'IELTS Academic Reading')
    passages_data = data.get('passages', [])
    first = passages_data[0]
    header_sub = data.get('header_sub') or f'P{first["num"]} "{first["title"]}" · Band {first.get("band", "")} · {first.get("genre", "")}'
    all_sections = []
    passage_info = {}
    tab_buttons = []

    for idx, p in enumerate(passages_data):
        p_num = p['num']
        passage_info[p_num] = {"title": p['title'], "num": f"P{p_num}", "band": p.get('band', ''), "genre": p.get('genre', '')}
        tab_buttons.append(f'<button class="tab-btn {"active" if idx == 0 else ""}" data-p="{a(p_num)}" onclick="switchPassage({int(p_num)})">P{h(p_num)}<span class="tab-badge">{h(p.get("band", ""))}</span></button>')
        qdata = p['questions']
        paras = p.get('paras', [])
        pc_lines = [f'<div class="p-title">{h(p["title"])}</div>', f'<div class="p-meta">{h(p.get("meta", ""))}</div>']
        blocks = qdata.get('blocks', [])
        if qdata.get('type') == 'heading':
            headings_data = qdata.get('headings', [])
            ans_map = qdata.get('answers', {})
            heading_text = dict(normalize_heading(x) for x in headings_data)
            for i, para in enumerate(paras, 1):
                label = para['label']; ans = ans_map.get(label, ''); q_num = i
                reveal_text = f'✅ {ans} — {heading_text.get(ans, "")}'.strip()
                pc_lines.append(build_heading_slot(p_num, label, q_num, ans, heading_text.get(ans, "")))
                pc_lines.append(build_reveal(q_num, reveal_text))
                pc_lines.append(build_para(label, para['text']))
            non_heading_blocks = [b for b in blocks if b.get('type') != 'heading_info']
            q_end = max_question_number(non_heading_blocks, minimum=len(paras))
            qc_lines = [
                f'<div style="font-size:15px;font-weight:600;margin-bottom:12px;color:var(--accent);font-family:var(--ui-font)">Questions 1–{q_end}</div>',
                '<div class="q-inst">将 headings 拖到左侧对应段落前；也可以先点击一个 heading，再点击左侧段落前的答题框。</div>',
                '<div class="q-block heading-pool-block"><div class="q-text"><b>List of Headings</b></div>',
                build_heading_pool(p_num, headings_data),
                '</div>',
            ]
            qc_lines.extend(build_question_blocks(non_heading_blocks))
        else:
            for para in paras:
                pc_lines.append(build_para(para['label'], para['text']))
            q_end = max_question_number(blocks, minimum=len(blocks))
            qc_lines = [f'<div style="font-size:15px;font-weight:600;margin-bottom:12px;color:var(--accent);font-family:var(--ui-font)">Questions 1–{q_end}</div>']
            qc_lines.extend(build_question_blocks(blocks))
        all_sections.append(build_passage(p_num, '\n'.join(pc_lines), '\n'.join(qc_lines), active=(idx == 0)))

    passage_nums_js = json.dumps([p['num'] for p in passages_data]).replace('</', '<\\/')
    passage_info_js = json.dumps(passage_info, ensure_ascii=False).replace('</', '<\\/')
    js = DEFAULT_JS.replace('PASSAGE_NUMS', passage_nums_js).replace('PASSAGE_INFO', passage_info_js)
    replacements = {
        '{{PAGE_TITLE}}': h(page_title), '{{HEADER_TITLE}}': h(header_title), '{{HEADER_SUB}}': h(header_sub),
        '{{TAB_BUTTONS}}': '\n'.join(tab_buttons), '{{PASSAGE_SECTIONS}}': '\n'.join(all_sections), '{{STYLES}}': DEFAULT_STYLES,
        '{{JAVASCRIPT}}': js,
    }
    out = HTML_TEMPLATE
    for k, v in replacements.items():
        out = out.replace(k, v)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(out)
    print(f'Generated reading practice: {output_path}')
    print(f'  {len(passages_data)} passages')


def main():
    parser = argparse.ArgumentParser(description='Generate IELTS reading practice HTML')
    parser.add_argument('--title', default=None, help='Optional page title override')
    parser.add_argument('--output', '-o', required=True)
    parser.add_argument('--data', '-d', required=True)
    args = parser.parse_args()
    with open(args.data, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if args.title:
        data['title'] = args.title
    try:
        generate(data, args.output)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
