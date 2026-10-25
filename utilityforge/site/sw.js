/* Cache only application assets; user datasets remain in memory. */
const CACHE='utilityforge-v2-app-shell';
const ASSETS=['/','/index.html','/assets/app.js','/assets/csv-engine.js','/assets/style.css'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)).then(()=>self.skipWaiting()));});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('utilityforge-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',event=>{const request=event.request;if(request.method!=='GET'||new URL(request.url).origin!==self.location.origin)return;event.respondWith(caches.match(request).then(hit=>hit||fetch(request)));});
