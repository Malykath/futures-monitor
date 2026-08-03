// Service Worker for 期货盯盘系统
var CACHE_NAME = 'futures-monitor-v2';
var urlsToCache = [
  './index.html',
  './manifest.json',
  './icon.svg',
  'https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js'
];

self.addEventListener('install', function(event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache) {
      return cache.addAll(urlsToCache).catch(function() {});
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', function(event) {
  event.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) { return k !== CACHE_NAME; })
          .map(function(k) { return caches.delete(k); })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', function(event) {
  // 行情API和搜索API走网络优先（实时数据）
  if (event.request.url.includes('push2.eastmoney.com') ||
      event.request.url.includes('searchapi.eastmoney.com')) {
    event.respondWith(
      fetch(event.request, { cache: 'no-store' }).catch(function() {
        return new Response(JSON.stringify({ error: 'offline' }), {
          headers: { 'Content-Type': 'application/json' }
        });
      })
    );
    return;
  }
  // 其他资源走缓存优先
  event.respondWith(
    caches.match(event.request).then(function(resp) {
      return resp || fetch(event.request);
    })
  );
});