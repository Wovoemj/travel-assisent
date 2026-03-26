// 智能旅游助手 Service Worker
// 版本号
const CACHE_NAME = 'travel-assistant-v1';
const STATIC_CACHE = 'static-v1';
const DYNAMIC_CACHE = 'dynamic-v1';

// 需要缓存的静态资源
const STATIC_ASSETS = [
  '/',
  '/static/css/optimized.css',
  '/static/js/performance.js',
  '/static/images/default-bg.jpg',
  '/static/manifest.json',
  'https://cdn.bootcdn.net/ajax/libs/twitter-bootstrap/5.1.3/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.8.1/font/bootstrap-icons.css',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css',
  'https://cdn.bootcdn.net/ajax/libs/twitter-bootstrap/5.1.3/js/bootstrap.bundle.min.js'
];

// 需要网络优先的API路径
const NETWORK_FIRST_PATHS = [
  '/api/',
  '/chat',
  '/search'
];

// 安装事件 - 缓存静态资源
self.addEventListener('install', event => {
  console.log('Service Worker: 正在安装...');
  
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => {
        console.log('Service Worker: 正在缓存静态资源');
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => {
        console.log('Service Worker: 静态资源缓存完成');
        return self.skipWaiting();
      })
      .catch(error => {
        console.error('Service Worker: 缓存失败', error);
      })
  );
});

// 激活事件 - 清理旧缓存
self.addEventListener('activate', event => {
  console.log('Service Worker: 正在激活...');
  
  event.waitUntil(
    caches.keys()
      .then(cacheNames => {
        return Promise.all(
          cacheNames.map(cacheName => {
            if (cacheName !== STATIC_CACHE && cacheName !== DYNAMIC_CACHE) {
              console.log('Service Worker: 删除旧缓存', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => {
        console.log('Service Worker: 激活完成');
        return self.clients.claim();
      })
  );
});

// 拦截网络请求
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);
  
  // 跳过非GET请求
  if (request.method !== 'GET') {
    return;
  }
  
  // 跳过chrome-extension和其他协议
  if (!url.protocol.startsWith('http')) {
    return;
  }
  
  // 网络优先策略（API请求）
  if (NETWORK_FIRST_PATHS.some(path => url.pathname.startsWith(path))) {
    event.respondWith(networkFirst(request));
    return;
  }
  
  // 缓存优先策略（静态资源）
  if (isStaticAsset(url)) {
    event.respondWith(cacheFirst(request));
    return;
  }
  
  // 网络优先，回退到缓存（其他请求）
  event.respondWith(networkFirstWithFallback(request));
});

// 判断是否为静态资源
function isStaticAsset(url) {
  return url.pathname.startsWith('/static/') ||
         url.pathname.endsWith('.css') ||
         url.pathname.endsWith('.js') ||
         url.pathname.endsWith('.png') ||
         url.pathname.endsWith('.jpg') ||
         url.pathname.endsWith('.jpeg') ||
         url.pathname.endsWith('.gif') ||
         url.pathname.endsWith('.webp') ||
         url.pathname.endsWith('.svg') ||
         url.pathname.endsWith('.ico') ||
         url.pathname.endsWith('.woff') ||
         url.pathname.endsWith('.woff2') ||
         url.pathname.endsWith('.ttf');
}

// 缓存优先策略
async function cacheFirst(request) {
  try {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.error('缓存优先策略失败:', error);
    return new Response('资源加载失败', { status: 503 });
  }
}

// 网络优先策略
async function networkFirst(request) {
  try {
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.log('网络请求失败，尝试缓存:', error);
    
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // 如果是页面请求，返回离线页面
    if (request.headers.get('accept').includes('text/html')) {
      return caches.match('/');
    }
    
    return new Response('网络连接失败', { status: 503 });
  }
}

// 网络优先带回退策略
async function networkFirstWithFallback(request) {
  try {
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.log('网络请求失败，尝试缓存:', error);
    
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // 返回离线页面或错误响应
    if (request.headers.get('accept').includes('text/html')) {
      return caches.match('/');
    }
    
    return new Response('离线模式', { status: 503 });
  }
}

// 推送通知
self.addEventListener('push', event => {
  console.log('Service Worker: 收到推送消息');
  
  const options = {
    body: event.data ? event.data.text() : '您有新的消息',
    icon: '/static/images/icon-192x192.png',
    badge: '/static/images/icon-72x72.png',
    vibrate: [100, 50, 100],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1
    },
    actions: [
      {
        action: 'explore',
        title: '查看详情',
        icon: '/static/images/checkmark.png'
      },
      {
        action: 'close',
        title: '关闭',
        icon: '/static/images/xmark.png'
      }
    ]
  };
  
  event.waitUntil(
    self.registration.showNotification('智能旅游助手', options)
  );
});

// 通知点击事件
self.addEventListener('notificationclick', event => {
  console.log('Service Worker: 通知被点击');
  
  event.notification.close();
  
  if (event.action === 'explore') {
    event.waitUntil(
      clients.openWindow('/')
    );
  }
});

// 后台同步
self.addEventListener('sync', event => {
  console.log('Service Worker: 后台同步', event.tag);
  
  if (event.tag === 'background-sync') {
    event.waitUntil(doBackgroundSync());
  }
});

// 执行后台同步
async function doBackgroundSync() {
  try {
    // 这里可以实现离线时的数据同步逻辑
    console.log('Service Worker: 执行后台同步');
  } catch (error) {
    console.error('Service Worker: 后台同步失败', error);
  }
}

// 消息处理
self.addEventListener('message', event => {
  console.log('Service Worker: 收到消息', event.data);
  
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'GET_VERSION') {
    event.ports[0].postMessage({ version: CACHE_NAME });
  }
});

console.log('Service Worker: 脚本加载完成');