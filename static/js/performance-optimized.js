/**
 * 性能优化JavaScript - 轻量级版本
 * 包含关键功能：懒加载、资源预加载、缓存管理
 */

// 性能监控
const perf = {
  start: Date.now(),
  metrics: {},
  
  mark(name) {
    this.metrics[name] = Date.now() - this.start;
  },
  
  getMetrics() {
    return { ...this.metrics };
  }
};

// 资源预加载
const preload = {
  image(src) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = src;
    });
  },
  
  css(href) {
    return new Promise((resolve) => {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = href;
      link.onload = resolve;
      document.head.appendChild(link);
    });
  },
  
  js(src) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = src;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }
};

// 懒加载实现
const lazyLoad = {
  observer: null,
  
  init() {
    if ('IntersectionObserver' in window) {
      this.observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            this.loadElement(entry.target);
            this.observer.unobserve(entry.target);
          }
        });
      }, { rootMargin: '200px' });
    }
  },
  
  loadElement(el) {
    const src = el.dataset.src;
    if (!src) return;
    
    if (el.tagName === 'IMG') {
      el.src = src;
      el.classList.add('loaded');
    } else if (el.tagName === 'DIV' || el.tagName === 'SECTION') {
      el.style.backgroundImage = `url(${src})`;
    }
  },
  
  observe(selector) {
    const elements = document.querySelectorAll(selector);
    elements.forEach(el => {
      if (this.observer) {
        this.observer.observe(el);
      } else {
        // 回退方案
        this.loadElement(el);
      }
    });
  }
};

// 缓存管理
const cache = {
  set(key, value, ttl = 300000) { // 默认5分钟
    const item = {
      value,
      expiry: Date.now() + ttl
    };
    try {
      localStorage.setItem(`cache_${key}`, JSON.stringify(item));
    } catch (e) {
      console.warn('缓存写入失败:', e);
    }
  },
  
  get(key) {
    try {
      const itemStr = localStorage.getItem(`cache_${key}`);
      if (!itemStr) return null;
      
      const item = JSON.parse(itemStr);
      if (Date.now() > item.expiry) {
        localStorage.removeItem(`cache_${key}`);
        return null;
      }
      return item.value;
    } catch (e) {
      return null;
    }
  },
  
  clear(prefix = '') {
    Object.keys(localStorage)
      .filter(key => key.startsWith(`cache_${prefix}`))
      .forEach(key => localStorage.removeItem(key));
  }
};

// 防抖函数
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// 节流函数
function throttle(func, limit) {
  let inThrottle;
  return function(...args) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

// 图片优化
const imageOptimizer = {
  // 响应式图片
  getResponsiveUrl(baseUrl, width) {
    // 如果支持WebP，使用WebP格式
    if (this.supportsWebP()) {
      return `${baseUrl}?format=webp&width=${width}`;
    }
    return `${baseUrl}?width=${width}`;
  },
  
  // 检测WebP支持
  supportsWebP() {
    const canvas = document.createElement('canvas');
    canvas.width = 1;
    canvas.height = 1;
    return canvas.toDataURL('image/webp').indexOf('data:image/webp') === 0;
  },
  
  // 懒加载图片
  lazyLoadImages() {
    lazyLoad.observe('img[data-src], [data-background]');
  }
};

// 资源加载优化
const resourceLoader = {
  // 延迟加载非关键资源
  loadNonCritical() {
    // 延迟加载字体
    setTimeout(() => {
      preload.css('/static/css/beautify.css');
    }, 100);
    
    // 延迟加载动画库
    setTimeout(() => {
      preload.js('/static/js/lazy-loading.js');
    }, 200);
  },
  
  // 预加载关键资源
  preloadCritical() {
    // 预加载下一页可能需要的图片
    const nextPageImages = document.querySelectorAll('[data-next-page-image]');
    nextPageImages.forEach(img => {
      preload.image(img.dataset.nextPageImage);
    });
  }
};

// 性能优化初始化
function initPerformance() {
  perf.mark('initStart');
  
  // 初始化懒加载
  lazyLoad.init();
  lazyLoad.observe('.lazy-image, .lazy-bg');
  
  // 延迟加载非关键资源
  resourceLoader.loadNonCritical();
  
  // 预加载关键资源
  resourceLoader.preloadCritical();
  
  // 优化图片加载
  imageOptimizer.lazyLoadImages();
  
  perf.mark('initEnd');
  
  // 报告性能指标
  if (window.performance && window.performance.timing) {
    window.addEventListener('load', () => {
      const timing = window.performance.timing;
      const loadTime = timing.loadEventEnd - timing.navigationStart;
      console.log(`页面加载时间: ${loadTime}ms`);
      console.log('性能指标:', perf.getMetrics());
    });
  }
}

// 页面可见性优化
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    // 页面不可见时暂停动画
    document.body.classList.add('paused');
  } else {
    // 页面可见时恢复动画
    document.body.classList.remove('paused');
  }
});

// 滚动优化
let ticking = false;
window.addEventListener('scroll', () => {
  if (!ticking) {
    window.requestAnimationFrame(() => {
      // 滚动相关的优化操作
      lazyLoad.observe('.lazy-image, .lazy-bg');
      ticking = false;
    });
    ticking = true;
  }
});

// 初始化
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initPerformance);
} else {
  initPerformance();
}

// 导出模块
window.PerformanceOptimizer = {
  preload,
  lazyLoad,
  cache,
  debounce,
  throttle,
  imageOptimizer,
  perf
};