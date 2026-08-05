// Service Worker for 期货盯盘系统
var CACHE_NAME = 'futures-monitor-v8';
var urlsToCache = [
  './index.html',
  './manifest.json',
  './icon.svg',
  './spot_data.json',
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
  var url = new URL(event.request.url);
  var isDynamicApi = url.hostname.includes('eastmoney.com') || url.hostname.includes('sina.com.cn');
  if (isDynamicApi) {
    event.respondWith(fetch(event.request, { cache: 'no-store' }));
    return;
  }
  if (event.request.mode === 'navigate' || url.pathname.endsWith('/index.html')) {
    event.respondWith(
      fetch(event.request, { cache: 'no-store' }).then(function(resp) {
        var copy = resp.clone();
        caches.open(CACHE_NAME).then(function(cache) { cache.put('./index.html', copy); });
        return resp;
      }).catch(function() { return caches.match('./index.html'); })
    );
    return;
  }
  if (url.pathname.endsWith('/spot_data.json')) {
    event.respondWith(
      fetch(event.request, { cache: 'no-store' }).then(function(resp) {
        var copy = resp.clone();
        caches.open(CACHE_NAME).then(function(cache) { cache.put(event.request, copy); });
        return resp;
      }).catch(function() { return caches.match(event.request); })
    );
    return;
  }
  event.respondWith(caches.match(event.request).then(function(resp) { return resp || fetch(event.request); }));
});