#!/usr/bin/env python3
"""
Generate IELTS reading practice HTML with heading-matching drag-and-drop.

Takes a JSON file with passage content and question data, produces a standalone
HTML file with the full interactive UI.

Usage:
  python generate_reading.py \
    --title "IELTS Reading · U01 Daily Rhythm" \
    --output /path/to/刷题.html \
    --data /path/to/passage_data.json
"""

import json, sys, os, argparse, re, textwrap

# =============================================================================
# TEMPLATE: the complete reading player HTML, with {{PLACEHOLDERS}}
# =============================================================================

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{PAGE_TITLE}}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<style>
{{STYLES}}
</style>
</head>
<body>

<div class="tab-bar">
  <button class="tab-btn active" onclick="switchPassage(1)">P1<span class="tab-badge">{{BAND1}}</span></button>
  <button class="tab-btn" onclick="switchPassage(2)">P2<span class="tab-badge">{{BAND2}}</span></button>
  <button class="tab-btn" onclick="switchPassage(3)">P3<span class="tab-badge">{{BAND3}}</span></button>
  <button class="tab-btn" onclick="switchPassage(4)">P4<span class="tab-badge">{{BAND4}}</span></button>
  <button class="tab-btn" onclick="switchPassage(5)">P5<span class="tab-badge">{{BAND5}}</span></button>
</div>

<div class="action-bar">
  <button class="btn btn-primary" id="submitBtn" onclick="submitAnswers()">{{SUBMIT_TEXT}}</button>
  <button class="btn btn-secondary" onclick="resetAll()">{{RESET_TEXT}}</button>
  <span class="score-badge" id="scoreBadge"></span>
</div>

<div class="pdf-section" id="pdfSection">
  <strong>{{PDF_TITLE}}</strong><br>
  <input id="studentName" placeholder="{{PDF_NAME_PLACEHOLDER}}" style="width:160px">
  <input id="reportDate" type="date" style="width:150px">
  <button class="btn btn-success" onclick="exportPDF()">{{PDF_DOWNLOAD}}</button>
</div>

<div class="header">
  <h1>{{HEADER_TITLE}}</h1>
  <div class="sub" id="headerSub">{{HEADER_SUB}}</div>
</div>

<div class="layout" id="layout">

{{PASSAGE_SECTIONS}}

</div><!-- /layout -->

<script>
{{JAVASCRIPT}}
</script>
</body>
</html>"""

# =============================================================================
# DEFAULT STYLES (minified, matching the working U01 file)
# =============================================================================

DEFAULT_STYLES = r""":root{--bg:#faf8f7;--card:#fffcf9;--sidebar:#f5f0eb;--text:#3a3a3a;--text2:#7a7a7a;--accent:#d97757;--accent-light:#fef0e8;--success:#2d8659;--error:#c0392b;--border:#e8ddd5;--radius:8px;--font:'Georgia','Times New Roman',serif;--ui-font:-apple-system,'Helvetica Neue','PingFang SC',sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--font);line-height:1.7;height:100vh;overflow:hidden}
.tab-bar{background:var(--card);border-bottom:1px solid var(--border);display:flex;position:sticky;top:0;z-index:20;overflow-x:auto}
.tab-btn{flex:1;min-width:0;padding:12px 6px;border:none;background:none;cursor:pointer;font-size:11px;font-family:var(--ui-font);color:var(--text2);border-bottom:3px solid transparent}.tab-btn:hover{color:var(--accent)}.tab-btn.active{color:var(--accent);border-bottom-color:var(--accent);font-weight:600}
.tab-badge{display:inline-block;background:var(--accent);color:#fff;border-radius:10px;padding:1px 7px;font-size:10px;margin-left:4px}
.action-bar{display:flex;gap:6px;flex-wrap:wrap;align-items:center;justify-content:center;padding:4px 16px;background:var(--card);border-bottom:1px solid var(--border)}.action-bar .btn{padding:4px 12px;font-size:11px}
.pdf-section{padding:4px 16px;background:var(--sidebar);border-bottom:1px solid var(--border);display:none;font-size:12px;text-align:center}.pdf-section.show{display:block}.pdf-section input{padding:3px 8px;border:1px solid var(--border);border-radius:var(--radius);font-size:11px;font-family:var(--ui-font);margin-right:4px;margin-bottom:2px}.pdf-section strong{font-size:12px}
.header{background:var(--card);border-bottom:1px solid var(--border);padding:12px 32px}
.header h1{font-size:16px;font-weight:600;color:var(--accent)}.header .sub{font-size:12px;color:var(--text2);font-family:var(--ui-font);margin-top:2px}
.layout{display:flex;min-height:calc(100vh - 144px)}
.passage-col{flex:1.1;padding:28px;overflow-y:auto;height:calc(100vh - 144px);position:sticky;top:0;background:var(--card);border-right:1px solid var(--border)}
.questions-col{flex:0.9;padding:28px;overflow-y:auto;height:calc(100vh - 144px);position:sticky;top:0;background:var(--sidebar)}
.p-title{font-size:18px;font-weight:600;margin-bottom:4px;color:var(--accent)}
.p-meta{font-size:12px;color:var(--text2);font-family:var(--ui-font);margin-bottom:20px}
.para{margin-bottom:14px;font-size:14px;text-align:justify;line-height:1.85}
.para .label{font-weight:700;color:var(--accent);margin-right:2px}
.q-block{margin-bottom:16px}.q-text{font-size:13.5px;margin-bottom:5px;font-family:var(--ui-font)}.q-text .num{font-weight:600;color:var(--text)}
.q-inst{font-size:12px;color:var(--text2);font-family:var(--ui-font);margin-bottom:12px;font-style:italic}
.mcq-group{display:flex;flex-direction:column;gap:4px}
.mcq-opt{padding:7px 10px;border:1.5px solid var(--border);border-radius:var(--radius);cursor:pointer;font-size:12.5px;font-family:var(--ui-font);background:var(--card)}.mcq-opt:hover{border-color:var(--accent)}.mcq-opt.selected{border-color:var(--accent);background:var(--accent-light)}
.mcq-opt.wrong-only{border-color:var(--error);background:#fef2f2}.mcq-opt.correct{border-color:var(--success);background:#e6f4ea}
.tfng-group,.ynng-group{display:flex;gap:4px;flex-wrap:wrap}
.tfng-btn,.ynng-btn{padding:7px 12px;border:1.5px solid var(--border);border-radius:var(--radius);cursor:pointer;font-size:12px;font-family:var(--ui-font);background:var(--card)}.tfng-btn:hover,.ynng-btn:hover{border-color:var(--accent)}
.tfng-btn.selected,.ynng-btn.selected{border-color:var(--accent);background:var(--accent-light)}
.tfng-btn.wrong-only,.ynng-btn.wrong-only{border-color:var(--error);background:#fef2f2}
.tfng-btn.correct,.ynng-btn.correct{border-color:var(--success);background:#e6f4ea}
.match-select{width:100%;padding:6px 10px;border:1.5px solid var(--border);border-radius:var(--radius);font-size:12px;font-family:var(--ui-font);margin-top:2px;background:var(--card)}
.match-select.wrong-only{border-color:var(--error);background:#fef2f2}
.match-select.correct{border-color:var(--success);background:#e6f4ea}
.fill-input{width:220px;padding:6px 10px;border:1.5px solid var(--border);border-radius:var(--radius);font-size:12.5px;font-family:var(--ui-font);background:var(--card);margin-top:4px}
.fill-input.wrong-only{border-color:var(--error);background:#fef2f2}.fill-input.correct{border-color:var(--success);background:#e6f4ea}
.heading-pool{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:14px;padding:10px;background:var(--card);border:1.5px solid var(--border);border-radius:var(--radius)}
.heading-item{padding:5px 10px;border:1.5px solid var(--accent);border-radius:var(--radius);cursor:grab;font-size:11.5px;background:var(--accent-light);color:var(--text);user-select:none;white-space:nowrap}.heading-item:hover{border-color:#c0664a;background:#fde4d4}.heading-item.dragging{opacity:.4}.heading-item.used{opacity:.35;cursor:default;border-style:dashed;background:var(--sidebar)}
.heading-slot{display:inline-flex;align-items:center;justify-content:center;min-width:40px;height:32px;border:2px dashed var(--border);border-radius:var(--radius);background:var(--card);font-size:13px;font-weight:600;color:var(--text);font-family:var(--ui-font);margin-top:4px;padding:0 8px;cursor:default}.heading-slot.dragover{border-color:var(--accent);background:var(--accent-light)}.heading-slot.filled{border-style:solid;border-color:var(--accent);background:var(--accent-light)}.heading-slot.wrong-only{border-color:var(--error);background:#fef2f2}.heading-slot.correct{border-color:var(--success);background:#e6f4ea}.heading-slot .slot-placeholder{font-size:10px;color:var(--text2);font-weight:400}
.answer-reveal{display:none;margin-top:4px;padding:6px 10px;border-radius:var(--radius);font-size:12px;font-family:var(--ui-font)}
.answer-reveal.show{display:block;background:#e6f4ea;color:var(--success);border:1px solid var(--success)}
.reveal-btn-single{display:inline-block;margin-top:4px;padding:3px 10px;border:1px solid var(--border);border-radius:var(--radius);cursor:pointer;font-size:11px;font-family:var(--ui-font);background:var(--card);color:var(--text2)}.reveal-btn-single:hover{border-color:var(--accent);color:var(--accent)}.reveal-btn-single:disabled{opacity:.4;cursor:default}
.reveal-btn-single.enabled{border-color:var(--accent);color:var(--accent)}
.passage-panel{display:none}.passage-panel.active{display:flex;flex:1;overflow:hidden}
.btn{padding:7px 16px;border:none;border-radius:var(--radius);cursor:pointer;font-size:12.5px;font-family:var(--ui-font);font-weight:500}
.btn-primary{background:var(--accent);color:#fff}.btn-primary:hover{opacity:.85}
.btn-secondary{background:var(--sidebar);color:var(--text);border:1px solid var(--border)}
.btn-success{background:var(--success);color:#fff}.btn:disabled{opacity:.4;cursor:default}
.score-badge{font-size:13px;font-family:var(--ui-font);color:var(--text2);margin-left:auto}.score-badge strong{color:var(--text)}
@media(max-width:900px){.layout{flex-direction:column}.passage-col,.questions-col{flex:1;padding:16px;border-right:none;height:auto;position:static;overflow-y:visible}.tab-btn{font-size:10px;padding:8px 4px}}
"""

# =============================================================================
# DEFAULT JAVASCRIPT
# =============================================================================

DEFAULT_JS = r"""
let currentPassage = 1;
const pState = {1:{submitted:false,results:null},2:{submitted:false,results:null},3:{submitted:false,results:null},4:{submitted:false,results:null},5:{submitted:false,results:null}};

const passageInfo = """ + '{{PASSAGE_INFO}}' + r""";

function switchPassage(p){
  currentPassage=p;
  document.querySelectorAll('.tab-btn').forEach((b,i)=>b.classList.toggle('active',i+1===p));
  document.querySelectorAll('.passage-panel').forEach(pan=>pan.classList.remove('active'));
  document.querySelector(`[data-p="${p}"]`).classList.add('active');
  const info=passageInfo[p];
  document.getElementById('headerSub').textContent=info.num+' "'+info.title+'" · Band '+info.band+' · '+info.genre;
  restorePassageUI(p);
}

function restorePassageUI(p){
  const s=pState[p],badge=document.getElementById('scoreBadge'),submitBtn=document.getElementById('submitBtn'),pdfSec=document.getElementById('pdfSection');
  if(s.submitted){
    submitBtn.disabled=true;
    if(s.results) badge.innerHTML='\u5f97\u5206: <strong>'+s.results.correct+'/'+s.results.total+'</strong> ('+s.results.pct+'%)';
    pdfSec.classList.add('show');
    document.getElementById('reportDate').value=new Date().toISOString().slice(0,10);
    const panel=document.querySelector(`[data-p="${p}"]`);
    panel.querySelectorAll('.reveal-btn-single').forEach(btn=>{
      const qNum=btn.dataset.qnum,reveal=panel.querySelector(`.answer-reveal[data-reveal="${qNum}"]`);
      if(reveal&&reveal.classList.contains('show')){btn.disabled=true;btn.textContent='✅ \u5df2\u663e\u793a';btn.style.opacity='0.5'}
      else{btn.disabled=false;btn.classList.add('enabled')}
    });
  }else{submitBtn.disabled=false;pdfSec.classList.remove('show');badge.innerHTML=''}
}

function selectMCQ(el){if(pState[currentPassage].submitted)return;const g=el.parentElement;g.querySelectorAll('.mcq-opt').forEach(o=>o.classList.remove('selected'));el.classList.add('selected')}
function selectTFNG(el){if(pState[currentPassage].submitted)return;const g=el.parentElement;g.querySelectorAll('.tfng-btn,.ynng-btn').forEach(b=>b.classList.remove('selected'));el.classList.add('selected')}

function gradePanel(panel){
  const qCol=panel.querySelector('[id^="qcol"]')||panel.querySelector('.questions-col');
  if(!qCol)return{correct:0,total:0,wrongs:[]};
  let correct=0,total=0;const wrongs=[];
  panel.querySelectorAll('.wrong-only,.correct').forEach(e=>e.classList.remove('wrong-only','correct'));
  qCol.querySelectorAll('.mcq-group').forEach(g=>{total++;const q=g.dataset.q,ca=g.dataset.ans,s=g.querySelector('.selected');if(s){const l=s.textContent.trim().charAt(0);if(l===ca){correct++;s.classList.add('correct')}else{s.classList.add('wrong-only');wrongs.push({q:'Q'+q,userAns:l,correctAns:ca})}}else{wrongs.push({q:'Q'+q,userAns:'(\u672a\u9009)',correctAns:ca})}});
  qCol.querySelectorAll('.tfng-group,.ynng-group').forEach(g=>{total++;const q=g.dataset.q,ca=g.dataset.ans,s=g.querySelector('.selected');if(s){if(s.textContent.trim()===ca){correct++;s.classList.add('correct')}else{s.classList.add('wrong-only');wrongs.push({q:'Q'+q,userAns:s.textContent.trim(),correctAns:ca})}}else{wrongs.push({q:'Q'+q,userAns:'(\u672a\u9009)',correctAns:ca})}});
  qCol.querySelectorAll('.match-select').forEach(s=>{total++;const q=s.dataset.q,ca=s.dataset.ans,v=s.value;if(v===ca){correct++;s.classList.add('correct')}else{s.classList.add('wrong-only');wrongs.push({q:'Q'+q,userAns:v||'(\u672a\u9009)',correctAns:ca})}});
  qCol.querySelectorAll('.fill-input').forEach(inp=>{total++;const q=inp.dataset.q,ca=inp.dataset.ans,ua=inp.value.trim().toLowerCase();if(ua===ca.toLowerCase()){correct++;inp.classList.add('correct')}else{inp.classList.add('wrong-only');wrongs.push({q:'Q'+q,userAns:inp.value||'(\u672a\u586b)',correctAns:ca})}});
  qCol.querySelectorAll('.heading-slot').forEach(slot=>{total++;const q=slot.dataset.q,ca=slot.dataset.ans,va=slot.dataset.val||'';if(va===ca){correct++;slot.classList.add('correct')}else{slot.classList.add('wrong-only');wrongs.push({q:'Q'+q,userAns:va||'(\u672a\u62d6)',correctAns:ca})}});
  panel.querySelectorAll('.passage-col .heading-slot').forEach(slot=>{total++;const q=slot.dataset.q,ca=slot.dataset.ans,va=slot.dataset.val||'';if(va===ca){correct++;slot.classList.add('correct')}else{slot.classList.add('wrong-only');wrongs.push({q:'Q'+q,userAns:va||'(\u672a\u62d6)',correctAns:ca})}});
  return{correct,total,wrongs,pct:total>0?Math.round(correct/total*100):0};
}

function submitAnswers(){
  const p=currentPassage,panel=document.querySelector(`[data-p="${p}"]`);
  if(!panel)return;
  const r=gradePanel(panel);pState[p].submitted=true;pState[p].results=r;
  document.getElementById('scoreBadge').innerHTML='\u5f97\u5206: <strong>'+r.correct+'/'+r.total+'</strong> ('+r.pct+'%)';
  document.getElementById('submitBtn').disabled=true;document.getElementById('pdfSection').classList.add('show');
  document.getElementById('reportDate').value=new Date().toISOString().slice(0,10);
  panel.querySelectorAll('.reveal-btn-single').forEach(b=>{b.disabled=false;b.classList.add('enabled')});
}

function toggleReveal(btn,qNum){
  const panel=btn.closest('.passage-panel'),reveal=panel.querySelector(`.answer-reveal[data-reveal="${qNum}"]`);
  if(reveal){reveal.classList.add('show');btn.disabled=true;btn.textContent='✅ \u5df2\u663e\u793a';btn.style.opacity='0.5'}
}

function resetAll(){
  const p=currentPassage;pState[p]={submitted:false,results:null};
  const panel=document.querySelector(`[data-p="${p}"]`);
  panel.querySelectorAll('.wrong-only,.correct').forEach(e=>e.classList.remove('wrong-only','correct'));
  panel.querySelectorAll('.selected').forEach(e=>e.classList.remove('selected'));
  panel.querySelectorAll('.fill-input').forEach(inp=>inp.value='');
  panel.querySelectorAll('.match-select').forEach(s=>s.value='');
  panel.querySelectorAll('.heading-slot').forEach(slot=>{slot.innerHTML='<span class="slot-placeholder">\u62d6\u62fd\u6807\u9898\u81f3\u6b64</span>';slot.classList.remove('wrong-only','correct','filled');delete slot.dataset.val;});
  var poolSuffix=(p===2?'p2':p===3?'p3':p===4?'p4':p===5?'p5':'')+'-heading-pool';var pool=document.getElementById(poolSuffix);if(pool){pool.querySelectorAll('.heading-item.used').forEach(function(it){it.classList.remove('used');it.draggable=true;});}
  panel.querySelectorAll('.answer-reveal').forEach(el=>el.classList.remove('show'));
  panel.querySelectorAll('.reveal-btn-single').forEach(btn=>{btn.disabled=true;btn.classList.remove('enabled');btn.textContent='💡 \u663e\u793a\u89e3\u6790';btn.style.opacity=''});
  document.getElementById('scoreBadge').innerHTML='';document.getElementById('submitBtn').disabled=false;document.getElementById('pdfSection').classList.remove('show');
}

function exportPDF(){
  const p=currentPassage,name=document.getElementById('studentName').value||'\u672a\u586b\u5199',date=document.getElementById('reportDate').value||new Date().toISOString().slice(0,10),r=pState[p].results;
  if(!r){alert('\u8bf7\u5148\u63d0\u4ea4\u672c\u7bc7\u7b54\u6848');return}
  const info=passageInfo[p],{jsPDF}=window.jspdf,doc=new jsPDF('p','mm','a4');let y=25;
  doc.setFontSize(16);doc.setTextColor(217,119,87);doc.text('IELTS Reading \u00b7 \u6210\u7ee9\u62a5\u544a',105,y,{align:'center'});y+=10;
  doc.setTextColor(58,58,58);doc.setFontSize(11);doc.text('\u59d3\u540d: '+name+'    \u65e5\u671f: '+date,20,y);y+=7;
  doc.text('\u6587\u7ae0: '+info.num+' '+info.title,20,y);y+=7;
  doc.setFontSize(14);doc.text('\u5f97\u5206: '+r.correct+'/'+r.total+' ('+r.pct+'%)',20,y);y+=12;
  if(r.wrongs.length===0){doc.setFontSize(12);doc.text('🎉 \u5168\u90e8\u6b63\u786e!\u6ca1\u6709\u9519\u9898\u3002',20,y)}
  else{doc.setFontSize(13);doc.text('\u9519\u9898\u8bb0\u5f55 ('+r.wrongs.length+'\u9898):',20,y);y+=8;doc.setFontSize(10);r.wrongs.forEach(w=>{if(y>275){doc.addPage();y=20}doc.text(w.q,20,y);doc.text('\u4f60\u7684\u7b54\u6848: '+w.userAns+'    \u6b63\u786e\u7b54\u6848: '+w.correctAns,30,y+5);y+=12})}
  doc.save('IELTS_Reading_'+info.num+'_'+name+'_'+date+'.pdf');
}

/* ===== Drag & Drop for Matching Headings ===== */
function dragHeading(e){
  e.dataTransfer.setData('text/plain',e.target.dataset.heading);
  e.target.classList.add('dragging');
}
function dragEnd(e){e.target.classList.remove('dragging');}
function allowDrop(e){e.preventDefault();e.currentTarget.classList.add('dragover');}
function dropHeading(e){
  e.preventDefault();
  var slot=e.currentTarget;slot.classList.remove('dragover');
  var heading=e.dataTransfer.getData('text/plain');
  if(!heading)return;
  placeHeading(slot,heading);
}
function clickSlot(slot){
  if(slot.dataset.val){
    var heading=slot.dataset.val;
    slot.innerHTML='<span class="slot-placeholder">\u62d6\u62fd\u6807\u9898\u81f3\u6b64</span>';
    slot.classList.remove('filled','wrong-only','correct');
    delete slot.dataset.val;
    var panel=slot.closest('.passage-panel');
    var pool=panel?panel.querySelector('.heading-pool'):null;
    if(pool){
      var item=pool.querySelector('.heading-item[data-heading="'+heading+'"]');
      if(item){item.classList.remove('used');item.draggable=true;}
    }
  }
}
function placeHeading(slot,heading){
  var panel=slot.closest('.passage-panel');
  var pool=panel?panel.querySelector('.heading-pool'):null;
  var fullText=heading;
  if(pool){
    var item=pool.querySelector('.heading-item[data-heading="'+heading+'"]');
    if(item&&item.classList.contains('used'))return;
    if(item){item.classList.add('used');item.draggable=false;fullText=item.textContent.trim();}
  }
  slot.innerHTML='<b>'+fullText+'</b>';
  slot.dataset.val=heading;
  slot.classList.add('filled');
  slot.classList.remove('wrong-only','correct');
}
document.addEventListener('DOMContentLoaded',function(){
  document.querySelectorAll('.answer-reveal').forEach(reveal=>{
    const qNum=reveal.dataset.reveal,btn=document.createElement('button');
    btn.className='reveal-btn-single';btn.dataset.qnum=qNum;btn.textContent='💡 \u663e\u793a\u89e3\u6790';btn.disabled=true;
    btn.onclick=function(){toggleReveal(this,qNum)};reveal.parentNode.insertBefore(btn,reveal);
  });
});
""" + '\n</script>\n</body>\n</html>'

# =============================================================================
# BUILDERS
# =============================================================================



def build_summary(num_pairs, reveals=None):
    """Build a flowing summary paragraph with inline inputs.
    num_pairs: list of (q_num, before_text, answer, after_text) tuples
    """
    sentences = []
    reveal_list = []
    for i, (q_num, before, answer, after) in enumerate(num_pairs):
        inp = (f'<span class="summary-q"><span class="num">{q_num}.</span> '
               f'<input class="fill-input" data-q="{q_num}" data-ans="{answer}" '
               f'placeholder="输入答案" '
               f'style="display:inline;width:160px;vertical-align:middle"></span>')
        sentences.append(f'{before} {inp} {after}')
        r = reveals[i] if reveals and i < len(reveals) else answer
        reveal_list.append(f'<div class="answer-reveal" data-reveal="{q_num}">{r}</div>')
    
    full_para = ' '.join(sentences)
    return (f'<div class="summary-paragraph">\n<p>{full_para}</p>\n</div>\n'
            + '\n'.join(reveal_list))

def build_heading_slot(p_num, label, q_num, answer):
    return (
        f'<div class="heading-slot" data-p="{p_num}" data-para="{label}" '
        f'data-q="{q_num}" data-ans="{answer}" '
        f'ondragover="allowDrop(event)" ondrop="dropHeading(event)" onclick="clickSlot(this)">'
        f'<span class="slot-placeholder">\u62d6\u62fd\u6807\u9898\u81f3\u6b64</span></div>'
    )

def build_reveal(q_num, text):
    return f'<div class="answer-reveal" data-reveal="{q_num}">{text}</div>'

def build_heading_pool(p_num, headings):
    """headings: list of (key, text) tuples"""
    items = '\n'.join(
        f'<span class="heading-item" draggable="true" data-heading="{h}" '
        f'ondragstart="dragHeading(event)" ondragend="dragEnd(event)">{h}. {t}</span>'
        for h, t in headings
    )
    return f'<div class="heading-pool" id="p{p_num}-heading-pool">\n{items}\n</div>\n'

def build_para(label, text):
    return f'<p class="para"><span class="label">[{label}]</span> {text}</p>'

def build_mcq(num, stem, options, answer, reveal=None):
    opts = '\n'.join(f'<div class="mcq-opt" onclick="selectMCQ(this)">{opt}</div>' for opt in options)
    reveal_html = build_reveal(num, reveal or answer)
    return f'''<div class="q-block"><div class="q-text"><span class="num">{num}.</span> {stem}</div>
<div class="mcq-group" data-q="{num}" data-ans="{answer}">{opts}</div>
{reveal_html}</div>'''

def build_tfng(num, statement, answer, reveal=None):
    reveal_html = build_reveal(num, reveal or answer)
    btns = ''.join(f'<div class="tfng-btn" onclick="selectTFNG(this)">{v}</div>' for v in ['TRUE', 'FALSE', 'NOT GIVEN'])
    return f'''<div class="q-block"><div class="q-text"><span class="num">{num}.</span> {statement}</div>
<div class="tfng-group" data-q="{num}" data-ans="{answer}">{btns}</div>
{reveal_html}</div>'''

def build_ynng(num, statement, answer, reveal=None):
    reveal_html = build_reveal(num, reveal or answer)
    btns = ''.join(f'<div class="tfng-btn" onclick="selectTFNG(this)">{v}</div>' for v in ['YES', 'NO', 'NOT GIVEN'])
    return f'''<div class="q-block"><div class="q-text"><span class="num">{num}.</span> {statement}</div>
<div class="ynng-group" data-q="{num}" data-ans="{answer}">{btns}</div>
{reveal_html}</div>'''

def build_match_select(num, text, options, answer, reveal=None):
    opts = ''.join(f'<option value="{v}">{v}</option>' for v in options)
    reveal_html = build_reveal(num, reveal or answer)
    return f'''<div class="q-block"><div class="q-text"><span class="num">{num}.</span> {text}</div>
<select class="match-select" data-q="{num}" data-ans="{answer}"><option value="">\u2014 \u9009\u62e9 \u2014</option>{opts}</select>
{reveal_html}</div>'''

def build_fill(num, text_before, text_after, answer, width=140, reveal=None):
    inp = f'<input class="fill-input" data-q="{num}" data-ans="{answer}" placeholder="\u8f93\u5165\u7b54\u6848" style="display:inline;width:{width}px;vertical-align:middle">'
    reveal_html = build_reveal(num, reveal or answer)
    return f'''<div class="q-block"><div class="q-text"><span class="num">{num}.</span> {text_before} {inp} {text_after}</div>
{reveal_html}</div>'''

def build_passage(p_num, pc_html, qc_html, heading_pool=None, heading_questions=None):
    """Build complete passage section."""
    return (
        f'<!-- ==================== PASSAGE {p_num} ==================== -->\n'
        f'<div class="passage-panel" data-p="{p_num}">\n'
        f'<div class="passage-col">\n{pc_html}\n</div>\n\n'
        f'<div class="questions-col" id="qcol{p_num}">\n{qc_html}\n</div>\n</div>'
    )

# =============================================================================
# MAIN GENERATOR
# =============================================================================

def generate(data, output_path):
    """Generate the reading practice HTML from input data."""
    
    # Extract data
    page_title = data.get('title', 'IELTS Reading Practice')
    header_title = data.get('header_title', 'IELTS Academic Reading')
    header_sub = data.get('header_sub', 'P1 "Reading"')
    passages_data = data.get('passages', [])
    
    # Build passage sections
    all_sections = []
    passage_info_lines = []
    
    for p in passages_data:
        p_num = p['num']
        title = p['title']
        meta = p.get('meta', '')
        paras = p.get('paras', [])
        qdata = p.get('questions', {})
        qtype = qdata.get('type', 'regular')
        blocks = qdata.get('blocks', [])
        
        # Passage info for JS
        band = p.get('band', '?.?-?.?')
        genre = p.get('genre', '')
        passage_info_lines.append(
            f'  {p_num}: {{ title:\'{title}\', num:\'P{p_num}\', band:\'{band}\', genre:\'{genre}\' }}'
        )
        
        # Build passage-col HTML
        pc_lines = [
            f'<div class="p-title">{title}</div>',
            f'<div class="p-meta">{meta}</div>'
        ]
        
        heading_slots = []  # (label, q_num, answer)
        heading_reveals = {}  # q_num -> reveal text
        
        if qtype == 'heading':
            headings_data = qdata.get('headings', [])
            ans_map = qdata.get('answers', {})
            
            for label in [chr(65+i) for i in range(len(paras))]:  # A, B, C...
                ans = ans_map.get(label, '')
                # Extract reveal from heading answer blocks
                q_num = len(heading_slots) + 1
                heading_item_text = ''
                for hk, ht in headings_data:
                    if hk == ans:
                        heading_item_text = ht
                        break
                reveal_text = f'✅ {ans} \u2014 {heading_item_text}' if heading_item_text else f'✅ {ans}'
                heading_slots.append((label, q_num, ans))
                heading_reveals[q_num] = reveal_text
            
            # Group non-heading blocks
            heading_blocks = []
            other_blocks = []
            for blk in blocks:
                if blk.get('q', 0) <= len(paras):
                    heading_blocks.append(blk)
                else:
                    other_blocks.append(blk)
            
            # Add heading slots + reveals before paragraphs
            for i, para in enumerate(paras):
                label = para['label']
                text = para['text']
                slot_info = [s for s in heading_slots if s[0] == label]
                if slot_info:
                    _, q_num, ans = slot_info[0]
                    pc_lines.append(build_heading_slot(p_num, label, q_num, ans))
                    pc_lines.append(build_reveal(q_num, heading_reveals[q_num]))
                pc_lines.append(build_para(label, text))
            
            # Build questions-col for heading passage
            qc_lines = [
                f'<div style="font-size:15px;font-weight:600;margin-bottom:12px;color:var(--accent);font-family:var(--ui-font)">Questions 1\u2013{len(blocks)}</div>',
                f'<div class="q-inst">\u5c06\u53f3\u4fa7\u6807\u9898\u62d6\u62fd\u81f3\u6587\u7ae0\u6bb5\u843d\u524d\u3002</div>\n',
                build_heading_pool(p_num, headings_data),
            ]
            # Add heading q-blocks (just paragraph label + reveal)
            for blk in heading_blocks:
                q = blk['q']
                label = chr(64 + q)  # A=1, B=2...
                reveal_text = heading_reveals.get(q, '✅')
                qc_lines.append(
                    f'<div class="q-block"><div class="q-text"><span class="num">{q}.</span> Paragraph {label}</div>\n'
                    f'{build_reveal(q, reveal_text)}\n</div>'
                )
            # Add other blocks (MCQ, etc.)
            qc_lines.extend(build_question_blocks(other_blocks, headings_data))
            
        else:
            # Regular passage - no heading matching
            for para in paras:
                pc_lines.append(build_para(para['label'], para['text']))
            qc_lines = build_regular_questions(p_num, blocks)
        
        # Assemble passage section
        pc_html = '\n'.join(pc_lines)
        
        # For heading passages, include heading pool in qc
        if qtype == 'heading':
            qc_html = '\n'.join(qc_lines)
        else:
            qc_lines = [
                f'<div style="font-size:15px;font-weight:600;margin-bottom:12px;color:var(--accent);font-family:var(--ui-font)">Questions 1\u2013{len(blocks)}</div>',
            ]
            qc_lines.extend(build_question_blocks(blocks))
            qc_html = '\n'.join(qc_lines)
        
        all_sections.append(build_passage(p_num, pc_html, qc_html))
    
    # Build passageInfo JS
    passage_info_js = '{\n' + ',\n'.join(passage_info_lines) + '\n}'
    
    # Fill template
    html = HTML_TEMPLATE
    
    # Simple placeholder replacement
    replacements = {
        '{{PAGE_TITLE}}': page_title,
        '{{HEADER_TITLE}}': header_title,
        '{{HEADER_SUB}}': header_sub,
        '{{PASSAGE_INFO}}': passage_info_js,
        '{{PASSAGE_SECTIONS}}': '\n'.join(all_sections),
        '{{SUBMIT_TEXT}}': '✍ \u63d0\u4ea4\u7b54\u6848',
        '{{RESET_TEXT}}': '🔄 \u91cd\u7f6e\u672c\u7bc7',
        '{{PDF_TITLE}}': '📄 \u5bfc\u51fa\u672c\u7bc7\u6210\u7ee9\u62a5\u544a',
        '{{PDF_NAME_PLACEHOLDER}}': '\u5b66\u751f\u59d3\u540d',
        '{{PDF_DOWNLOAD}}': '📥 \u4e0b\u8f7d PDF',
        '{{BAND1}}': passages_data[0].get('band', '') if passages_data else '',
        '{{BAND2}}': passages_data[1].get('band', '') if len(passages_data) > 1 else '',
        '{{BAND3}}': passages_data[2].get('band', '') if len(passages_data) > 2 else '',
        '{{BAND4}}': passages_data[3].get('band', '') if len(passages_data) > 3 else '',
        '{{BAND5}}': passages_data[4].get('band', '') if len(passages_data) > 4 else '',
        '{{STYLES}}': DEFAULT_STYLES,
    }
    
    for k, v in replacements.items():
        html = html.replace(k, v)
    
    # Build the complete HTML: template without the JS placeholder, then append JS
    # Actually, the JS {{PASSAGE_INFO}} is inside DEFAULT_JS which uses '{{PASSAGE_INFO}}'
    # Let me fix this by doing the replacement before inserting into the template
    
    # The JS template uses '{{PASSAGE_INFO}}' as a placeholder within the string
    # We need to replace it
    full_js = DEFAULT_JS.replace('{{PASSAGE_INFO}}', passage_info_js)
    
    # Replace the entire JAVASCRIPT block
    html = html.replace('{{JAVASCRIPT}}', full_js)
    
    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f'Generated reading practice: {output_path}')
    print(f'  {len(passages_data)} passages')

def build_question_blocks(blocks, headings_data=None):
    """Convert question blocks to HTML."""
    lines = []
    for blk in blocks:
        qtype = blk.get('type', '')
        q = blk['q']
        answer = blk.get('answer', '')
        reveal = blk.get('reveal', None)
        
        if qtype == 'mcq':
            stem = blk.get('stem', '')
            opts = blk.get('options', [])
            lines.append(build_mcq(q, stem, opts, answer, reveal))
        elif qtype in ('tfng', 'true_false'):
            stmt = blk.get('statement', '')
            lines.append(build_tfng(q, stmt, answer, reveal))
        elif qtype in ('ynng', 'yes_no'):
            stmt = blk.get('statement', '')
            lines.append(build_ynng(q, stmt, answer, reveal))
        elif qtype == 'match':
            text = blk.get('text', '')
            opts = blk.get('options', [])
            lines.append(build_match_select(q, text, opts, answer, reveal))
        elif qtype == 'summary':
            pairs = blk.get('pairs', [])
            reveals = blk.get('reveals', None)
            lines.append(build_summary(pairs, reveals))
        elif qtype == 'fill':
            before = blk.get('before', '')
            after = blk.get('after', '')
            width = blk.get('width', 140)
            lines.append(build_fill(q, before, after, answer, width, reveal))
        elif qtype == 'heading_info':
            # Just paragraph label + reveal for heading question
            label = chr(64 + q)
            reveal_text = reveal or '✅'
            lines.append(
                f'<div class="q-block"><div class="q-text"><span class="num">{q}.</span> Paragraph {label}</div>\n'
                f'{build_reveal(q, reveal_text)}\n</div>'
            )
    
    return lines

def build_regular_questions(p_num, blocks):
    """Build regular (non-heading) questions. Returns HTML string."""
    lines = [
        f'<div style="font-size:15px;font-weight:600;margin-bottom:12px;color:var(--accent);font-family:var(--ui-font)">Questions 1\u2013{len(blocks)}</div>'
    ]
    lines.extend(build_question_blocks(blocks))
    return '\n'.join(lines)

# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Generate IELTS reading practice HTML')
    parser.add_argument('--title', help='Page title', default='IELTS Reading Practice')
    parser.add_argument('--output', '-o', help='Output HTML path', required=True)
    parser.add_argument('--data', '-d', help='JSON data file path', required=True)
    args = parser.parse_args()
    
    with open(args.data, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    generate(data, args.output)

if __name__ == '__main__':
    main()
