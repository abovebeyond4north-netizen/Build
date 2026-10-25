/* UtilityForge CSV engine. Standard-library-only, no network calls, no dependencies. */
export class CsvError extends Error {}

export function detectDelimiter(text) {
  const candidates = [',', '\t', ';', '|'];
  const lines = [];
  let buf = '', quoted = false;
  for (let i = 0; i < Math.min(text.length, 12000) && lines.length < 12; i++) {
    const c = text[i];
    if (c === '"') {
      if (quoted && text[i+1] === '"') { buf += '""'; i++; continue; }
      quoted = !quoted;
    }
    if (!quoted && (c === '\n' || c === '\r')) {
      if (buf.trim()) lines.push(buf);
      buf = '';
      if (c === '\r' && text[i+1] === '\n') i++;
    } else buf += c;
  }
  if (lines.length < 12 && buf.trim()) lines.push(buf);
  if (!lines.length) return ',';
  const quality = (delimiter) => {
    const counts = lines.map(line => countOutsideQuotes(line, delimiter));
    const positive = counts.filter(n => n > 0).length;
    const frequency = new Map();
    for (const count of counts) if (count > 0) frequency.set(count, (frequency.get(count) || 0) + 1);
    const dominant = Math.max(0, ...frequency.values());
    return positive * 2 + dominant * 3 - (Math.max(...counts)-Math.min(...counts));
  };
  return candidates.map(c => [c, quality(c)]).sort((a,b)=>b[1]-a[1])[0][1] > 0
    ? candidates.map(c => [c, quality(c)]).sort((a,b)=>b[1]-a[1])[0][0] : ',';
}
function countOutsideQuotes(line, delimiter) {
  let n=0, quoted=false;
  for (let i=0;i<line.length;i++) {
    if (line[i] === '"') {
      if (quoted && line[i+1] === '"') { i++; continue; }
      quoted = !quoted;
    } else if (!quoted && line[i] === delimiter) n++;
  }
  return n;
}

export function parseCSV(input, {delimiter='auto', maxRows=100000, maxColumns=250}={}) {
  if (typeof input !== 'string') throw new CsvError('Input must be text.');
  const text = input.replace(/^\uFEFF/, '');
  if (!text.trim()) throw new CsvError('CSV is empty.');
  const sep = delimiter === 'auto' ? detectDelimiter(text) : delimiter;
  if (![',',';','|','\t'].includes(sep)) throw new CsvError('Unsupported delimiter.');
  const rows=[]; let row=[], field='', state='start';
  const pushField=()=>{row.push(field);field='';if(row.length>maxColumns)throw new CsvError(`Too many columns (maximum ${maxColumns}).`);};
  const pushRow=()=>{pushField();rows.push(row);row=[];if(rows.length>maxRows+1)throw new CsvError(`Too many data rows (maximum ${maxRows}).`);};
  for (let i=0;i<text.length;i++) {
    const c=text[i];
    if (state==='quoted') {
      if (c==='"') {
        if (text[i+1]==='"'){field+='"';i++;}
        else state='afterquote';
      } else field+=c;
    } else if (state==='afterquote') {
      if (c===sep) { pushField();state='start'; }
      else if (c==='\r'||c==='\n'){pushRow();state='start';if(c==='\r'&&text[i+1]==='\n')i++;}
      else if (c===' '||c==='\t') { /* RFC4180 permissive post-quote space */ }
      else throw new CsvError(`Unexpected character after a closing quote at offset ${i}.`);
    } else if (c===sep) {pushField();state='start';}
    else if (c==='\r'||c==='\n') {pushRow();state='start';if(c==='\r'&&text[i+1]==='\n')i++;}
    else if (c==='"' && state==='start' && field==='') state='quoted';
    else if (c==='"') throw new CsvError(`Unexpected quote inside unquoted field at offset ${i}.`);
    else { field+=c;state='unquoted'; }
  }
  if (state==='quoted') throw new CsvError('Unterminated quoted field.');
  if (row.length || field !== '' || (text[text.length-1]!== '\n' && text[text.length-1] !== '\r')) pushRow();
  if (!rows.length) throw new CsvError('No CSV records found.');
  const rawHeaders=rows.shift();
  if (!rawHeaders.length || rawHeaders.every(h=>h.trim()==='')) throw new CsvError('A nonempty header row is required.');
  const expected=rawHeaders.length;
  rows.forEach((r,i)=>{if(r.length!==expected)throw new CsvError(`Data row ${i+2} has ${r.length} columns, expected ${expected}.`);});
  return {headers:rawHeaders,rows,delimiter:sep};
}

export function normalizedHeaders(headers) {
  const used=new Set();
  return headers.map((header,index)=>{
    const base=(header.normalize('NFKC').trim().toLowerCase().replace(/[^\p{L}\p{N}]+/gu,'_').replace(/^_+|_+$/g,'') || `column_${index+1}`).slice(0,72);
    let name=base, suffix=2;
    while(used.has(name)) name=`${base}_${suffix++}`;
    used.add(name);
    return name;
  });
}

export function transform(table, options={}) {
  const {trimCells=true,normalizeHeaders=false,dropEmptyRows=true,removeDuplicates=false,fillBlank=''}=options;
  let headers=normalizeHeaders?normalizedHeaders(table.headers):[...table.headers];
  let rows=table.rows.map(r=>r.map(v=>trimCells?v.trim():v));
  if (dropEmptyRows) rows=rows.filter(r=>r.some(c=>c!==''));
  if (fillBlank!=='' && typeof fillBlank==='string') rows=rows.map(r=>r.map(v=>v===''?fillBlank:v));
  if (removeDuplicates){const seen=new Set();rows=rows.filter(r=>{const key=JSON.stringify(r);if(seen.has(key))return false;seen.add(key);return true;});}
  return {headers,rows,delimiter:table.delimiter};
}

export function profile(table) {
  const total=table.rows.length;
  return table.headers.map((name,index)=>{
    const values=table.rows.map(row=>row[index]);
    const nonempty=values.filter(v=>v!=='');
    const numeric=nonempty.filter(v=>/^[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?$/.test(v)&&Number.isFinite(Number(v)));
    const unique=new Set(nonempty).size;
    let min=null,max=null;
    for (const value of numeric) {const number=Number(value);min=min===null?number:Math.min(min,number);max=max===null?number:Math.max(max,number);}
    return {name,index,rows:total,filled:nonempty.length,empty:total-nonempty.length,unique,
      type:nonempty.length && numeric.length===nonempty.length?'numeric':'text',min,max};
  });
}

function escapeSpreadsheetFormula(value){
  // Quoting a CSV cell does NOT neutralize spreadsheet formula execution.
  if (/^[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?$/.test(value.trim())) return value;
  return /^[\s\u0000-\u001f]*[=+@\-]/.test(value) ? "'" + value : value;
}
export function serializeCSV(table,{delimiter=',',protectSpreadsheet=true}={}){
  if (![',',';','|','\t'].includes(delimiter)) throw new CsvError('Unsupported export delimiter.');
  const quote=v=>{
    let s=String(v??'');
    if(protectSpreadsheet) s=escapeSpreadsheetFormula(s);
    return /["\r\n]/.test(s)||s.includes(delimiter)?`"${s.replaceAll('"','""')}"`:s;
  };
  return [table.headers,...table.rows].map(row=>row.map(quote).join(delimiter)).join('\r\n')+'\r\n';
}
export function serializeJSON(table){
  // Objects lose data when headers repeat; map duplicate headers to distinct names.
  const keys=uniqueDisplayHeaders(table.headers);
  return JSON.stringify(table.rows.map(row=>Object.fromEntries(keys.map((k,i)=>[k,row[i]]))),null,2);
}
export function uniqueDisplayHeaders(headers){
  const seen=new Set();
  return headers.map((name,index)=>{
    const base=name.trim()||`column_${index+1}`;
    let key=base,n=2;
    while(seen.has(key)) key=`${base}_${n++}`;
    seen.add(key);return key;
  });
}
export function reportData(source,output){
  return {generatedAt:new Date().toISOString(),input:{rows:source.rows.length,columns:source.headers.length},
    output:{rows:output.rows.length,columns:output.headers.length},
    rowsRemoved:source.rows.length-output.rows.length,columns:profile(output)};
}