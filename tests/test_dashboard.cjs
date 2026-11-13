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
 const timers=[];
 const context=vm.createContext({document,console,Date,setInterval:(callback,ms)=>timers.push({callback,ms})});
 // Drive rendering directly with deterministic fixture data, without network.
 vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/load\(\);(?:loadPER\(\);)?\s*$/,''),context);
 vm.runInContext('loadPER=()=>{}',context);
 return {nodes,timers,document,run:s=>vm.runInContext(s,context)};
}
const fixture=(market,signal)=>({market,theme:'테스트',ticker:market==='한국'?'KR':'US',
 cycle_score:70,transition_strength:60,confirmation_score:75,score_change_5d:5,
 cycle_stage:'관찰',asof:'2025-08-29',cycle_metrics:{rs_20d_pct:2,volume_ratio:1.1},
 etf_trend:{signal,bullish_score:50,advanced_bullish_score:50,last_changed:'2025-08-28',asof:'2025-08-29',timeframes:{
 monthly:{state:'up',asof:'2025-07-31',close:120,actual_open:108,actual_close:120,actual_change_pct:11.11,ha_open:110,ha_close:118},
 weekly:{state:'down',asof:'2025-08-22'},daily:{state:'mixed',asof:'2025-08-29'}}}});

test('visible dashboard reloads published data every ten minutes',()=>{
 const {nodes,timers,document,run}=setup();
 assert.equal(timers.length,1);assert.equal(timers[0].ms,600000);
 run('let reloads=0,shortReloads=0;load=()=>reloads++;loadShort=()=>shortReloads++');
 document.getElementById('short-view').hidden=true;timers[0].callback();
 assert.equal(run('reloads'),1);assert.equal(run('shortReloads'),0);
 nodes.get('short-view').hidden=false;timers[0].callback();
 assert.equal(run('reloads'),2);assert.equal(run('shortReloads'),1);
 document.hidden=true;timers[0].callback();assert.equal(run('reloads'),2);
});
test('cycle sections are removed and aggregate traffic light is the first column',()=>{
 const {nodes,run}=setup();run('data='+JSON.stringify({themes:[fixture('한국','yellow')]})+';render()');
 assert.ok(!html.includes('id="themes"'));assert.ok(!html.includes('id="history"'));assert.ok(!html.includes('<h2>테마별 사이클'));assert.ok(!html.includes('<h2>사이클 전환'));assert.ok(!html.includes('Cycle Detector'));
 assert.ok(html.includes('<tr><th>종합 신호등</th><th>시장</th><th>테마 ETF</th>'));
 assert.ok(nodes.get('theme-scores').children[0].children[0].text.includes('노랑'));
 assert.ok(nodes.get('theme-scores').children[0].children[3].text.includes('판정 근거'));
 assert.ok(nodes.get('theme-scores').children[0].children[3].text.includes('실제 시가 108 / 종가 120 / 등락률 11.11%'));
 assert.ok(nodes.get('theme-scores').children[0].children[3].text.includes('HA 시가 110 / 종가 118'));
});
test('securities ETF is first panel and remains visible for every market filter',()=>{
 const {nodes,run}=setup();
 assert.ok(html.indexOf('id="securities-heading"')<html.indexOf('id="status"'));
 const guide=fixture('한국','green');
 run('data='+JSON.stringify({securities_etf:guide,themes:[fixture('미국','red')]})+';market="미국";render()');
 assert.ok(nodes.get('securities-signal').text.includes('초록 · 3개 상승'));
 assert.equal(nodes.get('securities-frames').children.length,3);
 assert.ok(nodes.get('securities-dates').text.includes('2025-08-28'));
 assert.ok(nodes.get('securities-frames').text.includes('HA 시가'));
});
test('missing securities ETF data stays gray rather than using theme signals',()=>{
 const {nodes,run}=setup();run('data={themes:[]};render()');
 assert.ok(nodes.get('securities-signal').text.includes('회색 · 데이터 부족'));
 assert.equal(nodes.get('securities-frames').children.length,3);
});

const historyFixture=(active=false)=>({window_start:'2022-08-29',asof:'2025-08-29',complete:true,latest_date:active?'2025-08-29':'2025-08-27',latest_run:{start_date:'2025-08-20',end_date:active?'2025-08-29':'2025-08-27',active},runs:[{start_date:'2025-08-20',end_date:active?'2025-08-29':'2025-08-27',active}]});
test('green history shows latest date, full interval and active state for all filters',()=>{
 for(const active of [true,false])for(const market of ['전체','한국','미국']){
  const {nodes,run}=setup();const guide=fixture('한국',active?'green':'yellow');guide.etf_trend.green_history=historyFixture(active);
  run('data='+JSON.stringify({securities_etf:guide,themes:[]})+';market='+JSON.stringify(market)+';render()');
  const text=nodes.get('securities-green-history').text;
  assert.ok(text.includes('가장 최근 모두 초록: '+(active?'2025-08-29':'2025-08-27')));
  assert.ok(text.includes('해당 연속 구간: 2025-08-20 ~ '+(active?'2025-08-29':'2025-08-27')));
  assert.ok(text.includes('현재 유지 여부: '+(active?'유지 중':'종료')));
  assert.ok(text.includes('연속 구간 전체 (1개)'));
 }
});
test('no green in three complete years is explicit, missing data never claims none',()=>{
 for(const complete of [true,false]){
  const {nodes,run}=setup();const guide=fixture('한국','yellow');guide.etf_trend.green_history={...historyFixture(),complete,latest_date:null,latest_run:null,runs:[]};
  run('data='+JSON.stringify({securities_etf:guide,themes:[]})+';render()');
  const text=nodes.get('securities-green-history').text;
  assert.ok(text.includes(complete?'최근 3년간 없음':'데이터 부족 · 최근 3년간 없음 여부 확인 불가'));
 }
 const {nodes,run}=setup();run('data={themes:[]};render()');
 assert.ok(nodes.get('securities-green-history').text.includes('데이터 부족'));
 assert.ok(!nodes.get('securities-green-history').text.includes('최근 3년간 없음'));
});

test('weighted theme scores sort descending, show contributions and honor market filter',()=>{
 const {nodes,run}=setup();const low=fixture('한국','yellow'),high=fixture('미국','green');
 low.etf_trend.bullish_score=50;high.etf_trend.bullish_score=100;low.etf_trend.advanced_bullish_score=50;high.etf_trend.advanced_bullish_score=100;
 high.etf_trend.timeframes.weekly.state='up';high.etf_trend.timeframes.daily.state='up';
 run('data='+JSON.stringify({themes:[low,high]})+';render()');
 const rows=nodes.get('theme-scores').children;
 assert.ok(rows[0].text.includes('US'));assert.equal(rows[0].children[3].textContent,'100 / 100점');
 assert.ok(rows[0].children[5].text.includes('+50점'));assert.ok(rows[0].children[6].text.includes('+30점'));assert.ok(rows[0].children[7].text.includes('+20점'));
 assert.equal(rows[1].children[3].textContent,'50 / 100점');assert.ok(rows[1].children[6].text.includes('+0점'));
 run('market="한국";render()');assert.equal(nodes.get('theme-scores').children.length,1);assert.ok(nodes.get('theme-scores').text.includes('KR'));
});
test('zero is a real score and unavailable scores are not zero',()=>{
 const {nodes,run}=setup();const zero=fixture('한국','red'),missing=fixture('미국','gray');
 zero.etf_trend.bullish_score=0;missing.etf_trend.bullish_score=null;zero.etf_trend.advanced_bullish_score=0;missing.etf_trend.advanced_bullish_score=null;
 for(const f of Object.values(zero.etf_trend.timeframes))f.state='down';
 run('data='+JSON.stringify({themes:[missing,zero]})+';render()');
 const rows=nodes.get('theme-scores').children;
 assert.equal(rows[0].children[3].textContent,'0 / 100점');assert.equal(rows[1].children[3].text,'데이터 부족');
 assert.ok(!rows[1].text.includes('+50점'));
 assert.ok(!html.includes('새로운 사이클'));assert.ok(!html.includes('조기 징후'));assert.ok(!html.includes('watch_active'));assert.ok(!html.includes('id="top"'));
 assert.ok(html.includes('실제 상승 확률(%)은 아닙니다'));
});

test('intraday MA1 score takes precedence and completed history remains separate',()=>{
 const {nodes,run}=setup();const x=fixture('한국','red');x.etf_trend.bullish_score=0;x.etf_trend.advanced_bullish_score=0;x.etf_trend.green_history=historyFixture();
 x.etf_trend.intraday={signal:'yellow',bullish_score:20,advanced_bullish_score:20,asof:'2025-09-01',provisional:true,timeframes:{monthly:{state:'down',ma1:105,previous_ma1:150},weekly:{state:'down',ma1:105,previous_ma1:120},daily:{state:'up',ma1:105,previous_ma1:100}}};
 run('data='+JSON.stringify({securities_etf:x,themes:[x]})+';render()');
 const row=nodes.get('theme-scores').children[0];assert.equal(row.children[3].textContent,'20 / 100점 (장중·미확정)');
 assert.ok(row.children[7].text.includes('상승 · +20점'));assert.ok(row.children[8].text.includes('2025-09-01'));
 assert.ok(nodes.get('securities-dates').text.includes('장중·미확정'));assert.ok(nodes.get('securities-green-history').text.includes('2025-08-29'));
 assert.ok(!html.slice(html.indexOf('id="securities-heading"'),html.indexOf('id="short-view"')).includes('MA5'));
});
