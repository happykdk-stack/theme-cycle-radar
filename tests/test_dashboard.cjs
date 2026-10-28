const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../site/index.html'),'utf8');
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.textContent='';this.className=''}
 append(...items){this.children.push(...items)}
 appendChild(item){this.append(item)}
 replaceChildren(...items){this.children=items;this.textContent=''}
 addEventListener(){}
 get text(){return this.textContent+this.children.map(c=>c.text).join(' ')}
}
function setup(){
 const nodes=new Map();
 const document={createElement:t=>new Element(t),getElementById:id=>{
  if(!nodes.has(id))nodes.set(id,new Element('div'));return nodes.get(id);
 },querySelectorAll:()=>[]};
 const context=vm.createContext({document,console,Date});
 // Drive rendering directly with deterministic fixture data, without network.
 vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/load\(\);\s*$/,''),context);
 return {nodes,run:s=>vm.runInContext(s,context)};
}
const fixture=(market,signal)=>({market,theme:'테스트',ticker:market==='한국'?'KR':'US',
 cycle_score:70,transition_strength:60,confirmation_score:75,score_change_5d:5,
 cycle_stage:'관찰',asof:'2025-08-29',cycle_metrics:{rs_20d_pct:2,volume_ratio:1.1},
 etf_trend:{signal,last_changed:'2025-08-28',asof:'2025-08-29',timeframes:{
 monthly:{state:'up',asof:'2025-07-31',close:120,ma5:110,previous_ma5:108},
 weekly:{state:'down',asof:'2025-08-22'},daily:{state:'mixed',asof:'2025-08-29'}}}});
test('theme table displays active expansion date and return with sign',()=>{
 const {nodes,run}=setup();const x=fixture('한국','green');x.cycle_stage='상승 확산';x.strength_since='2025-08-20';x.strength_return_pct=4.25;
 run('data='+JSON.stringify({themes:[x]})+';render()');
 const row=nodes.get('themes').children[0];assert.equal(row.children[3].text,'2025-08-20');assert.equal(row.children[4].text,'+4.25%');assert.equal(row.children[4].className,'ok');
 assert.equal(row.children[7].text,'70');assert.equal(row.children[8].text,'60');
 assert.ok(!html.includes('id="etf-signals"'));
});
test('strength below 60 hides date and return',()=>{
 const {nodes,run}=setup();const x=fixture('미국','red');x.cycle_score=55;run('data='+JSON.stringify({themes:[x]})+';render()');
 const row=nodes.get('themes').children[0];assert.equal(row.children[3].text,'없음');assert.equal(row.children[4].text,'N/A');
});
test('market filter preserves theme table',()=>{
 const {nodes,run}=setup();run('data='+JSON.stringify({themes:[fixture('한국','green'),fixture('미국','red')]})+';market="한국";render()');
 assert.equal(nodes.get('themes').children.length,1);assert.ok(nodes.get('themes').text.includes('KR'));assert.ok(!nodes.get('themes').text.includes('US'));
});
test('securities ETF is first panel and remains visible for every market filter',()=>{
 const {nodes,run}=setup();
 assert.ok(html.indexOf('id="securities-heading"')<html.indexOf('id="status"'));
 const guide=fixture('한국','green');
 run('data='+JSON.stringify({securities_etf:guide,themes:[fixture('미국','red')]})+';market="미국";render()');
 assert.ok(nodes.get('securities-signal').text.includes('초록 · 3개 상승'));
 assert.equal(nodes.get('securities-frames').children.length,3);
 assert.ok(nodes.get('securities-dates').text.includes('2025-08-28'));
 assert.ok(nodes.get('securities-frames').text.includes('MA5 110'));
});
test('missing securities ETF data stays gray rather than using theme signals',()=>{
 const {nodes,run}=setup();run('data={themes:[]};render()');
 assert.ok(nodes.get('securities-signal').text.includes('회색 · 데이터 부족'));
 assert.equal(nodes.get('securities-frames').children.length,3);
});
