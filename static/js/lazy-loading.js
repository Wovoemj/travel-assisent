// 图片懒加载实现
class LazyImageLoader {
    constructor() {
        this.imageObserver = null;
        this.images = [];
        this.loadedImages = new Set();
        this.init();
    }

    init() {
        // 检查浏览器是否支持IntersectionObserver
        if ('IntersectionObserver' in window) {
            this.imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        this.loadImage(img);
                        observer.unobserve(img);
                    }
                });
            }, {
                root: null,
                rootMargin: '50px',
                threshold: 0.1
            });
        } else {
            // 降级处理：直接加载所有图片
            this.loadAllImages();
        }
    }

    loadImage(img) {
        const src = img.dataset.src;
        if (!src || this.loadedImages.has(src)) return;

        // 显示加载状态
        img.classList.add('loading');
        
        // 创建新的图片对象预加载
        const tempImg = new Image();
        
        tempImg.onload = () => {
            img.src = src;
            img.classList.remove('loading');
            img.classList.add('loaded');
            this.loadedImages.add(src);
            
            // 触发自定义事件
            img.dispatchEvent(new CustomEvent('imageLoaded', {
                detail: { src: src }
            }));
        };

        tempImg.onerror = () => {
            img.classList.remove('loading');
            img.classList.add('error');
            
            // 设置默认图片
            if (img.dataset.fallback) {
                img.src = img.dataset.fallback;
            }
            
            // 触发错误事件
            img.dispatchEvent(new CustomEvent('imageError', {
                detail: { src: src }
            }));
        };

        tempImg.src = src;
    }

    loadAllImages() {
        const lazyImages = document.querySelectorAll('img[data-src]');
        lazyImages.forEach(img => {
            this.loadImage(img);
        });
    }

    observe(img) {
        if (this.imageObserver) {
            this.imageObserver.observe(img);
        } else {
            this.loadImage(img);
        }
    }

    // 添加新的图片到观察列表
    addImage(img) {
        if (img.dataset.src && !this.loadedImages.has(img.dataset.src)) {
            this.images.push(img);
            this.observe(img);
        }
    }

    // 批量添加图片
    addImages(images) {
        images.forEach(img => this.addImage(img));
    }

    // 预加载图片
    preload(src) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => resolve(img);
            img.onerror = reject;
            img.src = src;
        });
    }

    // 批量预加载
    preloadAll(srcArray) {
        return Promise.all(srcArray.map(src => this.preload(src)));
    }

    // 清理已加载的图片缓存
    clearCache() {
        this.loadedImages.clear();
    }

    // 获取加载统计
    getStats() {
        return {
            total: this.images.length,
            loaded: this.loadedImages.size,
            pending: this.images.length - this.loadedImages.size
        };
    }
}

// 创建全局实例
const lazyLoader = new LazyImageLoader();

// 自动初始化函数
function initLazyLoading() {
    const lazyImages = document.querySelectorAll('img[data-src]:not(.loaded):not(.loading)');
    lazyLoader.addImages(Array.from(lazyImages));
}

// DOM加载完成后自动初始化
document.addEventListener('DOMContentLoaded', initLazyLoading);

// 动态内容加载后重新初始化
const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        if (mutation.type === 'childList') {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === 1) { // Element node
                    if (node.tagName === 'IMG' && node.dataset.src) {
                        lazyLoader.addImage(node);
                    }
                    // 检查子元素
                    const childImages = node.querySelectorAll ? 
                        node.querySelectorAll('img[data-src]') : [];
                    lazyLoader.addImages(Array.from(childImages));
                }
            });
        }
    });
});

// 观察DOM变化
observer.observe(document.body, {
    childList: true,
    subtree: true
});

// 暴露到全局
window.LazyImageLoader = LazyImageLoader;
window.lazyLoader = lazyLoader;
window.initLazyLoading = initLazyLoading;

// jQuery插件支持（如果存在）
if (typeof jQuery !== 'undefined') {
    jQuery.fn.lazyLoad = function() {
        return this.each(function() {
            if (this.tagName === 'IMG' && this.dataset.src) {
                lazyLoader.addImage(this);
            }
        });
    };
}

// Vue.js指令支持
if (typeof Vue !== 'undefined') {
    Vue.directive('lazy', {
        inserted: function(el) {
            if (el.tagName === 'IMG' && el.dataset.src) {
                lazyLoader.addImage(el);
            }
        },
        componentUpdated: function(el) {
            if (el.tagName === 'IMG' && el.dataset.src && !el.classList.contains('loaded')) {
                lazyLoader.addImage(el);
            }
        }
    });
}

console.log('✅ 图片懒加载系统已初始化');