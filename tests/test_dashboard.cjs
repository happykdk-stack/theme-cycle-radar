const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../site/index.html'),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/);
test('dashboard JavaScript compiles',()=>{assert.ok(script);new vm.Script(script[1]);});
test('main navigation includes independent PER analysis',()=>{
 assert.match(html,/id="long-tab"/);
 assert.match(html,/id="short-tab"/);
 assert.match(html,/id="per-tab"/);
 assert.match(html,/id="per-view"/);
});
test('ETF PER overview and daily slope list replace country analysis',()=>{
 assert.match(html,/id="per-only-rows"/);
 assert.match(html,/ETF별 PER · 15거래일 기울기/);
 assert.match(html,/id="per-daily-rows"/);
 assert.match(html,/id="per-etf-select"/);
 assert.doesNotMatch(html,/국가별 주가지수 · PER/);
 assert.match(html,/location.hash==='#per'/);
});
test('missing PER values are explicit',()=>{
 assert.match(html,/PER 자료 없음/);
 assert.match(html,/15거래일 전 관측값 없음/);
});

class Element{
 constructor(){this.children=[];this.textContent='';this.handlers={};this.value='';this.classList={toggle(){}};}
 append(...items){this.children.push(...items);}
 appendChild(item){this.append(item);}
 replaceChildren(...items){this.children=items;this.textContent='';}
 addEventListener(name,fn){this.handlers[name]=fn;}
 setAttribute(){}
 get text(){return this.textContent+this.children.map(x=>x.text).join(' ');}
}
function setup(){
 const nodes=new Map();const document={createElement:()=>new Element(),querySelectorAll:()=>[],getElementById:id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);}};
 const context=vm.createContext({document,Date,console,location:{hash:''},setInterval(){}});
 vm.runInContext(script[1].replace(/load\(\);loadPER\(\);\s*$/,''),context);
 return {nodes,run:text=>vm.runInContext(text,context)};
}
const fixture={generated_at_utc:'2026-11-25T22:30Z',etfs:{
 KR:{ticker:'KR',market:'한국',theme:'반도체',pe:null,history:[],status:'unavailable'},
 SOXX:{ticker:'SOXX',market:'미국',theme:'반도체',pe:20,asof:'2026-11-25',history:[{date:'2026-11-24',pe:20},{date:'2026-11-25',pe:20}],per_slope_history:[
  {date:'2026-11-24',pe:20,status:'missing_baseline',baseline_date:'2026-11-03'},
  {date:'2026-11-25',pe:20,status:'ok',baseline_date:'2026-11-04',baseline_pe:20,change_pct:0,slope_per_session:0}
 ]},
 USO:{ticker:'USO',market:'미국',theme:'원유',pe:null,history:[],status:'not_applicable'}
}};
test('PER date list shows zero slopes, missing baselines and newest dates first',()=>{
 const {nodes,run}=setup();run('perData='+JSON.stringify(fixture)+';renderPER()');
 const rows=nodes.get('per-daily-rows').children;
 assert.match(nodes.get('per-daily-heading').text,/SOXX/);
 assert.match(rows[0].text,/2026-11-25/);assert.equal(rows[0].children[5].textContent,'0.0000');
 assert.equal(rows[1].children[5].textContent,'—');assert.match(rows[1].text,/15거래일 전 관측값 없음/);
 assert.match(nodes.get('per-only-status').text,/3개 ETF 중 1개/);
});
test('ETF selection and market filters expose distinct missing and non-applicable states',()=>{
 const {nodes,run}=setup();run('perData='+JSON.stringify(fixture)+';renderPER()');
 nodes.get('per-etf-select').handlers.change({target:{value:'USO'}});
 assert.match(nodes.get('per-daily-rows').text,/PER 적용 대상/);
 nodes.get('per-only-kr').handlers.click();
 assert.match(nodes.get('per-daily-heading').text,/KR/);
 assert.match(nodes.get('per-daily-rows').text,/PER 자료가 없습니다/);
 assert.equal(nodes.get('per-only-rows').children.length,1);
});
test('PER load failures and legacy snapshots do not invent slopes',()=>{
 const {nodes,run}=setup();run('renderPER()');assert.match(nodes.get('per-only-rows').text,/조회 실패/);
 const legacy=JSON.parse(JSON.stringify(fixture));delete legacy.etfs.SOXX.per_slope_history;
 run('perData='+JSON.stringify(legacy)+';renderPER()');
 assert.match(nodes.get('per-daily-rows').text,/갱신 대기/);
 assert.equal(nodes.get('per-daily-rows').children[0].children[5].textContent,'—');
});
test('market traffic lights and refresh remain available',()=>{
 assert.match(html,/id="theme-scores"/);
 assert.match(html,/id="securities-signal"/);
 assert.match(html,/setInterval/);
 assert.match(html,/loadPER\(\)/);
});

const monthlyFixture=JSON.parse(fs.readFileSync(path.join(__dirname,'../site/per_monthly.json'),'utf8'));
test('published monthly evidence has sourced observations and two adjacent-month comparisons',()=>{
 const {run}=setup();
 assert.equal(monthlyFixture.observations.length,17);
 for(const p of monthlyFixture.observations){
  assert.ok(p.date<=monthlyFixture.verified_on);
  assert.ok(p.pe>0&&p.basis&&p.series&&p.source_title);
  assert.equal(new URL(p.source_url).protocol,'https:');
 }
 const rows=run('monthlyPERRows('+JSON.stringify(monthlyFixture.observations)+')');
 const skyy=rows.find(p=>p.ticker==='SKYY'&&p.date==='2026-10-30');
 assert.equal(skyy.previous_pe,29.71);
 assert.ok(Math.abs(skyy.change_pct-(-9.390777515988))<1e-9);
 assert.equal(rows.filter(p=>p.change_pct!==null).length,2);
 assert.ok(rows.filter(p=>p.ticker==='CIBR').every(p=>p.change_pct===null));
});
test('monthly comparisons handle year boundaries and zero changes, and reject differing methods or ambiguous baselines',()=>{
 const {run}=setup();
 const p={ticker:'TEST',series:'trailing',publisher:'Issuer',basis:'TTM',date:'2025-12-31',pe:20};
 const current={...p,date:'2026-01-30'};
 const calculate=points=>run('monthlyPERRows('+JSON.stringify(points)+')')[0];
 assert.equal(calculate([p,current]).change_pct,0);
 assert.equal(calculate([p,{...current,pe:30}]).change_pct,50);
 for(const mismatch of [{series:'forward'},{publisher:'Other'},{basis:'FY1'}])assert.equal(calculate([p,{...current,...mismatch}]).change_pct,null);
 assert.equal(calculate([p,{...p,date:'2025-12-30'},current]).change_pct,null);
 assert.equal(calculate([{...p,pe:0},current]).change_pct,null);
});
test('monthly table filters independently, exposes sources, and preserves gaps',()=>{
 const {nodes,run}=setup();
 run('monthlyPERData='+JSON.stringify(monthlyFixture)+';renderMonthlyPER()');
 assert.equal(nodes.get('per-monthly-rows').children.length,17);
 assert.match(nodes.get('per-monthly-highlight').text,/-9.39%/);
 nodes.get('per-monthly-select').handlers.change({target:{value:'CIBR'}});
 const rows=nodes.get('per-monthly-rows').children;
 assert.equal(rows.length,2);
 assert.ok(rows.every(row=>row.children[5].textContent==='—'));
 assert.match(rows[0].text,/2023-10 비교 자료 없음/);
 assert.match(rows[0].children[7].children[0].href,/ftportfolios.com/);
 assert.match(rows[0].text,/선행 PER/);
 run('monthlyPERData=null;monthlyPERError=true;renderMonthlyPER()');
 assert.match(nodes.get('per-monthly-status').text,/조회 실패/);
 assert.doesNotMatch(nodes.get('per-monthly-rows').text,/23.30/);
});

test('archived LIT months use the same earnings year and SOXX gaps remain explicit',()=>{
 const {nodes,run}=setup();
 run('monthlyPERData='+JSON.stringify(monthlyFixture)+';renderMonthlyPER()');
 nodes.get('per-monthly-select').handlers.change({target:{value:'LIT'}});
 assert.equal(nodes.get('per-monthly-rows').children.length,7);
 assert.match(nodes.get('per-monthly-highlight').text,/2016-09.*23.46.*23.20.*\+1.12%/);
 const rows=run('monthlyPERRows(monthlyPERData.observations)');
 const lit=rows.find(p=>p.ticker==='LIT'&&p.date==='2016-09-30');
 assert.equal(lit.earnings_year,2016);
 assert.ok(Math.abs(lit.change_pct-1.12068965517)<1e-9);
 assert.equal(rows.filter(p=>p.ticker==='LIT'&&p.change_pct!==null).length,1);
 nodes.get('per-monthly-select').handlers.change({target:{value:'SOXX'}});
 assert.equal(nodes.get('per-monthly-rows').children.length,4);
 assert.match(nodes.get('per-monthly-highlight').text,/연속 월말 자료가 없어/);
 assert.ok(nodes.get('per-monthly-rows').children.every(p=>p.children[5].textContent==='—'));
 assert.equal(rows.find(p=>p.ticker==='SOXX'&&p.date==='2025-04-30').pe,26.5);
 assert.equal(rows.find(p=>p.ticker==='SOXX'&&p.date==='2025-06-30').pe,33.78);
 assert.equal(rows.filter(p=>p.ticker==='SOXX'&&p.date==='2026-09-30').length,0,'inconsistent 60x cap disclosure is not treated as validated data');
});
