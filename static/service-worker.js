// Install the service worker
self.addEventListener('install', event => {
  console.log('[Service Worker] Installed');
  self.skipWaiting(); // Activate immediately
});

// Activate and clean old caches (optional)
self.addEventListener('activate', event => {
  console.log('[Service Worker] Activated');
});

// Intercept network requests (basic)
self.addEventListener('fetch', event => {
  event.respondWith(
    fetch(event.request).catch(() => new Response("Offline"))
  );
});
