// Permite instalar como app. Lista de posts sempre da rede; o resto do cache se cair a internet.
const CACHE = "achadinhos-v1";
const BASE = ["./", "index.html", "style.css", "app.js", "icons/icon-192.png", "icons/icon-512.png", "manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(BASE)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  // rede primeiro (posts novos aparecem na hora); cache so sem internet
  e.respondWith(
    fetch(e.request).then((r) => {
      if (r.ok && !url.pathname.endsWith(".mp4")) {
        const copia = r.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copia));
      }
      return r;
    }).catch(() => caches.match(e.request, { ignoreSearch: true }))
  );
});
