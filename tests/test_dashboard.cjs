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
 constructor(){this.children=[];this.textContent='';this.handlers={};this.attributes={};this.value='';this.classList={toggle(){}};}
 append(...items){this.children.push(...items);}
 appendChild(item){this.append(item);}
 replaceChildren(...items){this.children=items;this.textContent='';}
 addEventListener(name,fn){this.handlers[name]=fn;}
 setAttribute(name,value){this.attributes[name]=value;}
 get text(){return this.textContent+this.children.map(x=>x.text).join(' ');}
}
function setup(){
 const nodes=new Map();const document={createElement:()=>new Element(),createElementNS:()=>new Element(),createTextNode:text=>Object.assign(new Element(),{textContent:text}),querySelectorAll:()=>[],getElementById:id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);}};
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
 assert.match(nodes.get('per-daily-heading').text,/미국 반도체/);
 assert.match(rows[0].text,/2026-11-25/);assert.equal(rows[0].children[5].textContent,'0.0000');
 assert.equal(rows[1].children[5].textContent,'—');assert.match(rows[1].text,/15거래일 전 관측값 없음/);
 assert.match(nodes.get('per-only-status').text,/3개 ETF 중 1개/);
});
test('ETF selection and market filters expose distinct missing and non-applicable states',()=>{
 const {nodes,run}=setup();run('perData='+JSON.stringify(fixture)+';renderPER()');
 nodes.get('per-etf-select').handlers.change({target:{value:'USO'}});
 assert.match(nodes.get('per-daily-rows').text,/PER 적용 대상/);
 nodes.get('per-only-kr').handlers.click();
 assert.match(nodes.get('per-daily-heading').text,/반도체/);
 assert.match(nodes.get('per-daily-rows').text,/PER 자료가 없습니다/);
 assert.equal(nodes.get('per-only-rows').children.length,1);
});
test('PER load failures and legacy snapshots do not invent slopes',()=>{
 const {nodes,run}=setup();run('renderPER()');assert.match(nodes.get('per-only-rows').text,/자료 확인 중/);run('perLoading=false;renderPER()');assert.match(nodes.get('per-only-rows').text,/조회 실패/);
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
 assert.equal(nodes.get('per-monthly-rows').children.length,2);
 assert.match(nodes.get('per-monthly-readout').text,/-9.39%/);
 assert.match(nodes.get('per-coverage').text,/2026-10-30.*2개월 중 2개월.*전월 비교 1건/);
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
 assert.match(nodes.get('per-coverage').text,/2024-10-31.*104개월 중 7개월.*전월 비교 1건/);
 assert.match(nodes.get('per-monthly-readout').text,/2024-10.*20.61/);
 assert.match(nodes.get('per-monthly-chart').text,/1건뿐/);
 const rows=run('monthlyPERRows(monthlyPERData.observations)');
 const lit=rows.find(p=>p.ticker==='LIT'&&p.date==='2016-09-30');
 assert.equal(lit.earnings_year,2016);
 assert.ok(Math.abs(lit.change_pct-1.12068965517)<1e-9);
 assert.equal(rows.filter(p=>p.ticker==='LIT'&&p.change_pct!==null).length,1);
 nodes.get('per-monthly-select').handlers.change({target:{value:'SOXX'}});
 assert.equal(nodes.get('per-monthly-rows').children.length,4);
 assert.equal(nodes.get('per-chart-change').disabled,true);
 assert.ok(nodes.get('per-monthly-rows').children.every(p=>p.children[5].textContent==='—'));
 assert.equal(rows.find(p=>p.ticker==='SOXX'&&p.date==='2025-04-30').pe,26.5);
 assert.equal(rows.find(p=>p.ticker==='SOXX'&&p.date==='2025-06-30').pe,33.78);
 assert.equal(rows.filter(p=>p.ticker==='SOXX'&&p.date==='2026-09-30').length,0,'inconsistent 60x cap disclosure is not treated as validated data');
});

test('PER graph preserves real time gaps and only connects comparable adjacent months',()=>{
 const {run}=setup();
 const per=run('monthlyChartGeometry(monthlyPERRows('+JSON.stringify(monthlyFixture.observations)+').filter(p=>p.ticker==="LIT"),"per",320)');
 assert.equal(per.points.length,7);assert.equal(per.segments.length,1);
 assert.equal(per.segments[0].from.date,'2016-08-31');assert.equal(per.segments[0].to.date,'2016-09-30');
 const points=per.points;
 const march=points.find(p=>p.date==='2016-03-31'),august=points.find(p=>p.date==='2016-08-31'),september=points.find(p=>p.date==='2016-09-30');
 assert.ok(Math.abs((august.x-march.x)/(september.x-august.x)-5)<1e-8);
 assert.equal(per.xticks.length,2);
 const skyy=run('monthlyChartGeometry(monthlyPERRows('+JSON.stringify(monthlyFixture.observations)+').filter(p=>p.ticker==="SKYY"),"change",720)');
 assert.equal(skyy.points.length,1);assert.ok(skyy.points[0].y>skyy.zero,'negative change bar must extend below zero');
 const zero=run('monthlyChartGeometry([{date:"2026-01-30",pe:20,change_pct:0}],"change",320)');
 assert.equal(zero.points[0].y,zero.zero);assert.ok(Number.isFinite(zero.points[0].x));
});

test('graph selection updates source details and unavailable changes stay empty',()=>{
 const {nodes,run}=setup();run('monthlyPERData='+JSON.stringify(monthlyFixture)+';renderMonthlyPER()');
 assert.match(nodes.get('per-monthly-readout').text,/2026-10.*26.92.*-9.39%/);
 nodes.get('per-chart-change').handlers.click();
 assert.equal(nodes.get('per-monthly-chart').children[0].children.filter(p=>p.attributes.role==='button').length,1);
 nodes.get('per-monthly-select').handlers.change({target:{value:'LIT'}});
 const litSeries=run('monthlySeriesKey(monthlyPERData.observations.find(p=>p.ticker==="LIT"&&p.earnings_year===2016))');
 nodes.get('per-chart-series').handlers.change({target:{value:litSeries}});
 const svg=nodes.get('per-monthly-chart').children[0];
 assert.equal(svg.children.filter(p=>p.attributes.role==='button').length,3);
 const september=svg.children.find(p=>p.attributes['aria-label']?.startsWith('2016-09 PER'));
 september.handlers.click();assert.match(nodes.get('per-monthly-readout').text,/23.46.*\+1.12%/);
 assert.match(nodes.get('per-monthly-readout').children[2].children[2].href,/web.archive.org/);
 nodes.get('per-chart-change').handlers.click();
 assert.equal(nodes.get('per-monthly-chart').children[0].children.filter(p=>p.attributes.role==='button').length,1);
 nodes.get('per-monthly-select').handlers.change({target:{value:'SOXX'}});
 assert.match(nodes.get('per-monthly-chart').text,/1건뿐/);
 assert.equal(nodes.get('per-chart-change').disabled,true);
 nodes.get('per-chart-change').handlers.click();assert.equal(run('monthlyChartMode'),'per');
 const soxxSeries=run('monthlySeriesKey(monthlyPERData.observations.find(p=>p.ticker==="SOXX"&&p.date==="2025-04-30"))');
 nodes.get('per-chart-series').handlers.change({target:{value:soxxSeries}});
 assert.equal(nodes.get('per-monthly-chart').children[0].children.filter(p=>p.attributes.role==='button').length,3);
 run('monthlyPERData=null;monthlyPERError=true;renderMonthlyPER()');
 assert.match(nodes.get('per-monthly-chart').text,/불러오지 못했습니다/);
 assert.equal(nodes.get('per-monthly-readout').text,'');
});

test('theme cards preserve zero scores and use prices from the signal date',()=>{
 const {nodes,run}=setup();const frames={};for(const key of ['monthly','weekly','daily'])frames[key]={state:'up',asof:'2026-11-25',actual_close:100,actual_change_pct:0,ha_open:99,ha_close:100};
 run('renderThemeCards('+JSON.stringify([{ticker:'SOXX',market:'미국',theme:'반도체',close:999.99,etf_trend:{signal:'green',advanced_bullish_score:0,bullish_score:100,asof:'2026-11-25',timeframes:frames}},{ticker:'LIT',market:'미국',theme:'리튬',etf_trend:{signal:'gray',advanced_bullish_score:null}}])+')');
 assert.equal(nodes.get('theme-cards').children.length,2);
 const first=nodes.get('theme-cards').children[0];assert.match(first.text,/0 \/ 100/);assert.match(first.text,/100.00달러/);assert.doesNotMatch(first.text,/999.99/);
 assert.equal(first.children[0].children[0].text,'미국 반도체');
 assert.equal(nodes.get('market-summary').children[0].children[1].text,'1');assert.equal(nodes.get('market-summary').children[3].children[1].text,'1');
 assert.match(nodes.get('theme-cards').children[1].text,/산출 불가/);
});

test('short scan hides empty tables, distinguishes missing data and clears failed candidates',async()=>{
 const {nodes,run}=setup();const snapshot={generated_at_utc:new Date().toISOString(),trigger_date:'2026-11-26',threshold_pct:-9,drop_pct:0.39,status:'조건 미충족',candidates:[],errors:[]};
 run('shortData='+JSON.stringify(snapshot)+';renderShort()');assert.match(nodes.get('short-state-heading').text,/급락 조건 미충족/);assert.equal(nodes.get('short-table').hidden,true);
 snapshot.drop_pct=null;snapshot.status='N/A';run('shortData='+JSON.stringify(snapshot)+';renderShort()');assert.match(nodes.get('short-state-heading').text,/자료 확인 필요/);
 snapshot.drop_pct=-10;snapshot.status='급락 조건 충족';snapshot.candidates=[{ticker:'069500.KS',name:'KODEX 200',status:'반등 확인',bounce_pct:2,volume_multiple:2}];
 run('shortData='+JSON.stringify(snapshot)+';renderShort()');assert.match(nodes.get('short-state-heading').text,/반등 조건 확인/);assert.match(nodes.get('short-cards').text,/코덱스 200/);assert.equal(nodes.get('short-table').hidden,false);
 await run('fetch=async()=>{throw Error("offline")};loadShort()');assert.equal(nodes.get('short-cards').children.length,0);assert.match(nodes.get('short-state-heading').text,/불러오지 못했습니다/);assert.equal(nodes.get('short-table').hidden,true);
});

test('navigation updates selected states and shareable view hashes',()=>{
 const {nodes,run}=setup();run('history={pushState(a,b,h){location.hash=h}};selectView("short")');
 assert.equal(run('location.hash'),'#short');assert.equal(nodes.get('short-view').hidden,false);assert.equal(nodes.get('long-view').hidden,true);assert.equal(nodes.get('short-tab').attributes['aria-pressed'],'true');
 run('selectView("per")');assert.equal(run('location.hash'),'#per');assert.equal(nodes.get('short-view').hidden,true);assert.equal(nodes.get('per-view').hidden,false);
});

test('weekly views keep dated Korean references separate from recent US observations',()=>{
 const {nodes,run}=setup();const korea=JSON.parse(fs.readFileSync(path.join(__dirname,'../data/kr_etf_per_reference.json'),'utf8')).etfs;
 const etfs={};for(const [ticker,reference_per] of Object.entries(korea))etfs[ticker]={ticker,market:'한국',status:'unavailable',history:[],reference_per,per_weekly_history:[]};
 etfs.LIT={ticker:'LIT',market:'미국',status:'observed',per_weekly_history:[{week_start:'2026-11-09',week_end:'2026-11-15',date:'2026-11-13',pe:20,change_pct:null},{week_start:'2026-11-16',week_end:'2026-11-22',date:'2026-11-17',pe:19,change_pct:-5},{week_start:'2026-11-23',week_end:'2026-11-29',date:'2026-11-26',pe:18,change_pct:-5.263158,is_partial_week:true}]};
 run('perData='+JSON.stringify({generated_at_utc:'2026-11-26T06:00:00Z',etfs})+';renderPER()');
 assert.match(nodes.get('per-weekly-status').text,/한국 6개.*2026-10-01.*주별 이력은 아직 확보하지 못했습니다/);
 assert.match(nodes.get('per-weekly-table').text,/코덱스 반도체.*8.57배.*2026-10-01.*미확보/);
 nodes.get('per-weekly-us').handlers.click();assert.match(nodes.get('per-weekly-status').text,/1개 ETF · 3주/);assert.match(nodes.get('per-weekly-table').text,/진행 중.*리튬·배터리.*20.00.*19.00.*-5.00%.*11.17 관측.*18.00.*-5.26%/);
 assert.doesNotMatch(nodes.get('per-weekly-table').text,/\bLIT\b|2026-10-01|8.57/);
 const sparse=run('weeklyColumns([{per_weekly_history:[{week_start:"2026-11-09"},{week_start:"2026-11-23"}]}],"2026-11-26")');assert.equal(sparse.length,3);assert.equal(sparse[1].start,'2026-11-16');
 run('monthlyPERData='+JSON.stringify(monthlyFixture)+';renderMonthlyPER()');assert.doesNotMatch(nodes.get('per-monthly-select').text,/\b(SOXX|LIT|SKYY|CIBR|XBI|ITA)\b/);
});
