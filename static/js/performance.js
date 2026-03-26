// ==================== 性能优化脚本 ====================

// 1. 防抖函数
function debounce(func, wait, immediate) {
    let timeout;
    return function executedFunction() {
        const context = this;
        const args = arguments;
        const later = function() {
            timeout = null;
            if (!immediate) func.apply(context, args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func.apply(context, args);
    };
}

// 2. 节流函数
function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// 3. 图片懒加载优化
const ImageLazyLoader = {
    observer: null,
    
    init() {
        if ('IntersectionObserver' in window) {
            this.observer = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        this.loadImage(img);
                        observer.unobserve(img);
                    }
                });
            }, {
                rootMargin: '50px 0px',
                threshold: 0.01
            });
        }
    },
    
    observe(images) {
        if (this.observer) {
            images.forEach(img => {
                if (img.dataset.src) {
                    this.observer.observe(img);
                }
            });
        } else {
            images.forEach(img => this.loadImage(img));
        }
    },
    
    loadImage(img) {
        if (img.dataset.src) {
            img.src = img.dataset.src;
            img.removeAttribute('data-src');
            img.classList.add('loaded');
        }
    }
};

// 4. 资源预加载器
const ResourcePreloader = {
    cache: new Map(),
    
    preload(url, type = 'fetch') {
        if (this.cache.has(url)) {
            return Promise.resolve(this.cache.get(url));
        }
        
        return new Promise((resolve, reject) => {
            if (type === 'image') {
                const img = new Image();
                img.onload = () => {
                    this.cache.set(url, img);
                    resolve(img);
                };
                img.onerror = reject;
                img.src = url;
            } else if (type === 'fetch') {
                fetch(url)
                    .then(response => response.text())
                    .then(data => {
                        this.cache.set(url, data);
                        resolve(data);
                    })
                    .catch(reject);
            }
        });
    },
    
    preloadImages(urls) {
        return Promise.all(urls.map(url => this.preload(url, 'image')));
    }
};

// 5. 滚动优化器
const ScrollOptimizer = {
    ticking: false,
    callbacks: [],
    
    addCallback(callback) {
        this.callbacks.push(callback);
    },
    
    removeCallback(callback) {
        const index = this.callbacks.indexOf(callback);
        if (index > -1) {
            this.callbacks.splice(index, 1);
        }
    },
    
    onScroll() {
        if (!this.ticking) {
            requestAnimationFrame(() => {
                this.callbacks.forEach(callback => callback());
                this.ticking = false;
            });
            this.ticking = true;
        }
    },
    
    init() {
        window.addEventListener('scroll', () => this.onScroll(), { passive: true });
    }
};

// 6. 内存管理器
const MemoryManager = {
    observers: [],
    intervals: [],
    timeouts: [],
    
    addObserver(observer) {
        this.observers.push(observer);
    },
    
    addInterval(interval) {
        this.intervals.push(interval);
    },
    
    addTimeout(timeout) {
        this.timeouts.push(timeout);
    },
    
    cleanup() {
        this.observers.forEach(observer => {
            if (observer.disconnect) {
                observer.disconnect();
            }
        });
        this.observers = [];
        
        this.intervals.forEach(interval => clearInterval(interval));
        this.intervals = [];
        
        this.timeouts.forEach(timeout => clearTimeout(timeout));
        this.timeouts = [];
    }
};

// 7. 网络状态监控
const NetworkMonitor = {
    isOnline: navigator.onLine,
    listeners: [],
    
    init() {
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.notifyListeners('online');
        });
        
        window.addEventListener('offline', () => {
            this.isOnline = false;
            this.notifyListeners('offline');
        });
    },
    
    addListener(callback) {
        this.listeners.push(callback);
    },
    
    notifyListeners(status) {
        this.listeners.forEach(callback => callback(status));
    }
};

// 8. 性能监控
const PerformanceMonitor = {
    metrics: {},
    
    startTiming(name) {
        this.metrics[name] = performance.now();
    },
    
    endTiming(name) {
        if (this.metrics[name]) {
            const duration = performance.now() - this.metrics[name];
            console.log(`[Performance] ${name}: ${duration.toFixed(2)}ms`);
            delete this.metrics[name];
            return duration;
        }
    }
};

// 9. 工具函数
const Utils = {
    safeJSONParse(str, defaultValue = null) {
        try {
            return JSON.parse(str);
        } catch (e) {
            return defaultValue;
        }
    },
    
    setLocalStorage(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
            return true;
        } catch (e) {
            console.warn('localStorage不可用:', e);
            return false;
        }
    },
    
    getLocalStorage(key, defaultValue = null) {
        try {
            const value = localStorage.getItem(key);
            return value ? JSON.parse(value) : defaultValue;
        } catch (e) {
            return defaultValue;
        }
    },
    
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    },
    
    generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }
};

// 10. 缓存管理器
const CacheManager = {
    cache: new Map(),
    maxSize: 100,
    
    set(key, value, ttl = 300000) {
        if (this.cache.size >= this.maxSize) {
            const firstKey = this.cache.keys().next().value;
            this.cache.delete(firstKey);
        }
        
        this.cache.set(key, {
            value,
            timestamp: Date.now(),
            ttl
        });
    },
    
    get(key) {
        const item = this.cache.get(key);
        if (!item) return null;
        
        if (Date.now() - item.timestamp > item.ttl) {
            this.cache.delete(key);
            return null;
        }
        
        return item.value;
    },
    
    clear() {
        this.cache.clear();
    }
};

// 11. 初始化所有优化
function initPerformanceOptimizations() {
    ImageLazyLoader.init();
    ScrollOptimizer.init();
    NetworkMonitor.init();
    
    window.addEventListener('beforeunload', () => {
        MemoryManager.cleanup();
    });
    
    console.log('[Performance] 性能优化已初始化');
}

// 导出所有模块
window.Performance = {
    debounce,
    throttle,
    ImageLazyLoader,
    ResourcePreloader,
    ScrollOptimizer,
    MemoryManager,
    NetworkMonitor,
    PerformanceMonitor,
    Utils,
    CacheManager,
    init: initPerformanceOptimizations
};

// 自动初始化
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPerformanceOptimizations);
} else {
    initPerformanceOptimizations();
}