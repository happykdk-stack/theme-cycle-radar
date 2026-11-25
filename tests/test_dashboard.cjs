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
test('country PER table and independent index chart are present',()=>{
 assert.match(html,/id="per-only-rows"/);
 assert.match(html,/국가별 주가지수 · PER/);
 assert.doesNotMatch(html,/id="per-plot"/);
 assert.doesNotMatch(html,/id="price-plot"/);
 assert.match(html,/id="index-price-chart"/);
 assert.match(html,/id="index-chart-select"/);
 assert.match(html,/renderIndexChart/);
});
test('missing PER values are explicit',()=>{
 assert.match(html,/검증된 PER 데이터 미연결/);
 assert.match(html,/N\/A/);
});
test('market traffic lights and refresh remain available',()=>{
 assert.match(html,/id="theme-scores"/);
 assert.match(html,/id="securities-signal"/);
 assert.match(html,/setInterval/);
 assert.match(html,/loadPER\(\)/);
});
