const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root=path.join(__dirname,'../site');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
test('v2 site contains a usable local-first workspace',()=>{
 for(const id of ['loadSample','runButton','downloadCsv','downloadJson','downloadReport','dropZone','preview']) assert.ok(html.includes('id="'+id+'"'),id);
 assert.match(html,/<script type="module" src="\/assets\/app.js"/);
});
test('all local assets exist',()=>{
 for(const pathName of ['assets/csv-engine.js','assets/app.js','assets/style.css'])
  assert.ok(fs.statSync(path.join(root,pathName)).size>500,pathName);
});
test('no external payment processor or tracker',()=>{
 assert.doesNotMatch(html,/<script[^>]+src="https?:\/\//);
 assert.doesNotMatch(html,/<form[^>]*>/);
});
test('core JS imports are explicit and local',()=>{
 const app=fs.readFileSync(path.join(root,'assets/app.js'),'utf8');
 assert.match(app,/from '\.\/csv-engine.js'/);
 assert.doesNotMatch(app,/\beval\s*\(/);
});
