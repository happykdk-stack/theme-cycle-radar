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
 assert.match(html,/id="per-select"/);
});
test('PER chart shows real valuation and real price on separate axes',()=>{
 assert.match(html,/실제 PER 왼쪽 축/);
 assert.match(html,/peSeries/);
 assert.match(html,/priceSeries/);
 assert.match(html,/x\.source/);
 assert.doesNotMatch(html,/const normalized=prices\.map/);
});
test('PER chart does not interpolate missing observations',()=>{
 assert.match(html,/PER 미관측 구간은 채우지 않습니다/);
 assert.match(html,/peSeries\.length>=2/);
});
test('market traffic lights and refresh remain available',()=>{
 assert.match(html,/id="theme-scores"/);
 assert.match(html,/id="securities-signal"/);
 assert.match(html,/setInterval/);
 assert.match(html,/loadPER\(\)/);
});
