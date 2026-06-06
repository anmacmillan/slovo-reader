const CACHE_NAME = "slovo-cache-v20";
const ASSETS = [
  "index.html",
  "styles.css",
  "splash.css",
  "app.js",
  "data.js",
  "dictionary_data.js",
  "icon.png",
  "manifest.json"
];

// Install Event
self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// Activate Event
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch Event
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;

  const url = new URL(e.request.url);

  // Network First for data.js and dictionary_data.js (keep database/dictionary fresh when online)
  if (url.pathname.endsWith("data.js") || url.pathname.endsWith("dictionary_data.js")) {
    e.respondWith(
      fetch(e.request)
        .then((networkResponse) => {
          return caches.open(CACHE_NAME).then((cache) => {
            cache.put(e.request, networkResponse.clone());
            return networkResponse;
          });
        })
        .catch(() => {
          return caches.match(e.request, { ignoreSearch: true });
        })
    );
    return;
  }

  // Cache First for static UI assets
  e.respondWith(
    caches.match(e.request, { ignoreSearch: true }).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }
      return fetch(e.request).then((networkResponse) => {
        // Cache newly fetched external assets like fonts
        if (
          e.request.url.includes("fonts.googleapis.com") ||
          e.request.url.includes("fonts.gstatic.com")
        ) {
          return caches.open(CACHE_NAME).then((cache) => {
            cache.put(e.request, networkResponse.clone());
            return networkResponse;
          });
        }
        return networkResponse;
      });
    })
  );
});
