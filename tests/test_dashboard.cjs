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
test('all colors and dates render alongside unchanged V4.2 metrics',()=>{
 const {nodes,run}=setup();
 run('data='+JSON.stringify({themes:['green','yellow','red','gray'].map(c=>fixture('미국',c))})+'; render()');
 const rows=nodes.get('etf-signals').children;
 assert.equal(rows.length,4);
 for(const [i,color] of ['green','yellow','red','gray'].entries()){
  assert.equal(rows[i].children[5].children[0].className,'signal '+color);
  assert.ok(rows[i].text.includes('2025-08-28'));
 }
 assert.equal(nodes.get('themes').children[0].children[5].text,'70');
 assert.equal(nodes.get('themes').children[0].children[6].text,'60');
 assert.equal(nodes.get('themes').children[0].children[8].text,'75/100');
 assert.ok(rows[0].text.includes('MA5 110'));
});
test('market filter updates signals, counts, and legacy table together',()=>{
 const {nodes,run}=setup();
 run('data='+JSON.stringify({themes:[fixture('한국','green'),fixture('미국','red')]})+'; market="한국"; render()');
 assert.equal(nodes.get('etf-signals').children.length,1);
 assert.ok(nodes.get('etf-signals').text.includes('KR'));
 assert.ok(!nodes.get('etf-signals').text.includes('US'));
 assert.equal(nodes.get('themes').children.length,1);
 assert.ok(nodes.get('signal-summary').text.includes('3개 상승 1개'));
});
test('missing ETF data is gray and initial availability is not a change',()=>{
 const {nodes,run}=setup();const x=fixture('미국','green');delete x.etf_trend;
 run('data='+JSON.stringify({themes:[x]})+';render()');
 assert.ok(nodes.get('etf-signals').text.includes('회색 · 데이터 부족'));
 assert.ok(nodes.get('etf-signals').text.includes('산출 전'));
 run('data.themes[0].etf_trend={signal:"green",initial_since:"2025-06-30"};render()');
 assert.ok(nodes.get('etf-signals').text.includes('변경 없음 (최초 2025-06-30)'));
});
test('empty market renders an explicit empty state',()=>{
 const {nodes,run}=setup();run('data={themes:[]};render()');
 assert.ok(nodes.get('etf-signals').text.includes('표시할 ETF 없음'));
});
