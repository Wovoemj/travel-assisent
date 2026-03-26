// 智能旅游助手 - Cloudflare Workers JavaScript

document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

// 初始化应用
function initializeApp() {
    setupSearchFunctionality();
    loadHotDestinations();
    setupBackgroundSwitch();
}

// 设置搜索功能
function setupSearchFunctionality() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        // 支持回车搜索
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                performSearch();
            }
        });
        
        // 实时搜索建议
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                showSearchSuggestions(this.value);
            }, 300);
        });
    }
}

// 执行搜索
function performSearch() {
    const query = document.getElementById('searchInput')?.value;
    if (!query || query.trim().length === 0) {
        showToast('请输入搜索关键词', 'warning');
        return;
    }
    
    showLoading();
    window.location.href = `/?q=${encodeURIComponent(query.trim())}`;
}

// 显示搜索建议
async function showSearchSuggestions(query) {
    if (!query || query.length < 1) {
        hideSuggestions();
        return;
    }
    
    try {
        const response = await fetch(`/api/search/suggestions?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        
        if (data.success && data.suggestions && data.suggestions.length > 0) {
            displaySuggestions(data.suggestions);
        } else {
            hideSuggestions();
        }
    } catch (error) {
        console.log('搜索建议加载失败:', error);
        hideSuggestions();
    }
}

// 显示搜索建议下拉框
function displaySuggestions(suggestions) {
    let suggestionsContainer = document.getElementById('searchSuggestions');
    if (!suggestionsContainer) {
        suggestionsContainer = document.createElement('div');
        suggestionsContainer.id = 'searchSuggestions';
        suggestionsContainer.style.cssText = `
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: white;
            border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            z-index: 1000;
            max-height: 300px;
            overflow-y: auto;
        `;
        
        const searchBox = document.querySelector('.search-box');
        if (searchBox) {
            searchBox.style.position = 'relative';
            searchBox.appendChild(suggestionsContainer);
        }
    }
    
    suggestionsContainer.innerHTML = '';
    suggestions.forEach(suggestion => {
        const item = document.createElement('div');
        item.className = 'suggestion-item';
        item.style.cssText = `
            padding: 1rem;
            cursor: pointer;
            border-bottom: 1px solid #eee;
            display: flex;
            align-items: center;
            gap: 1rem;
        `;
        item.innerHTML = `
            <img src="${suggestion.cover_image || '/static/images/placeholder.jpg'}" 
                 style="width: 40px; height: 40px; border-radius: 8px; object-fit: cover;"
                 onerror="this.src='/static/images/placeholder.jpg'">
            <div>
                <div style="font-weight: bold;">${suggestion.name}</div>
                <div style="color: #666; font-size: 0.9rem;">${suggestion.city || ''} · ${suggestion.category || ''}</div>
            </div>
        `;
        
        item.addEventListener('click', () => {
            document.getElementById('searchInput').value = suggestion.name;
            hideSuggestions();
            performSearch();
        });
        
        item.addEventListener('mouseenter', () => {
            item.style.background = '#f5f5f5';
        });
        
        item.addEventListener('mouseleave', () => {
            item.style.background = 'white';
        });
        
        suggestionsContainer.appendChild(item);
    });
    
    suggestionsContainer.style.display = 'block';
}

// 隐藏搜索建议
function hideSuggestions() {
    const suggestionsContainer = document.getElementById('searchSuggestions');
    if (suggestionsContainer) {
        suggestionsContainer.style.display = 'none';
    }
}

// 加载热门景点
async function loadHotDestinations() {
    const container = document.getElementById('destinations');
    if (!container) return;
    
    try {
        // 检查是否有搜索查询
        const urlParams = new URLSearchParams(window.location.search);
        const query = urlParams.get('q');
        
        const apiUrl = query ? 
            `/api/search?q=${encodeURIComponent(query)}` : 
            '/api/recommendations/hot';
        
        const response = await fetch(apiUrl);
        const data = await response.json();
        
        const destinations = data.results || data.destinations || [];
        
        if (destinations.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i>🔍</i>
                    <h3>暂无景点数据</h3>
                    <p>请尝试其他搜索关键词</p>
                </div>
            `;
            return;
        }
        
        displayDestinations(destinations);
        
    } catch (error) {
        console.error('加载景点失败:', error);
        container.innerHTML = `
            <div class="empty-state">
                <i>⚠️</i>
                <h3>加载失败</h3>
                <p>请检查网络连接后重试</p>
                <button onclick="loadHotDestinations()" class="btn btn-primary" style="margin-top: 1rem;">
                    重新加载
                </button>
            </div>
        `;
    }
}

// 显示景点卡片
function displayDestinations(destinations) {
    const container = document.getElementById('destinations');
    if (!container) return;
    
    container.innerHTML = '';
    
    destinations.forEach((dest, index) => {
        const card = document.createElement('div');
        card.className = 'dest-card';
        card.style.animationDelay = `${index * 0.1}s`;
        
        card.innerHTML = `
            <img src="${dest.cover_image || '/static/images/placeholder.jpg'}" 
                 alt="${dest.name}"
                 onerror="this.src='/static/images/placeholder.jpg'"
                 loading="lazy">
            <div class="dest-info">
                <h4>${dest.name}</h4>
                <p>📍 ${dest.city || ''} · ${dest.category || ''}</p>
                <p>⭐ ${dest.rating || 0}分 ${dest.price_range ? '· 💰' + dest.price_range : ''}</p>
            </div>
        `;
        
        card.addEventListener('click', () => {
            showDestinationDetail(dest);
        });
        
        container.appendChild(card);
    });
}

// 显示景点详情
function showDestinationDetail(dest) {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.8);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 2000;
        padding: 1rem;
    `;
    
    modal.innerHTML = `
        <div style="
            background: white;
            border-radius: 15px;
            max-width: 500px;
            width: 100%;
            max-height: 80vh;
            overflow-y: auto;
        ">
            <img src="${dest.cover_image || '/static/images/placeholder.jpg'}" 
                 style="width: 100%; height: 200px; object-fit: cover; border-radius: 15px 15px 0 0;"
                 onerror="this.src='/static/images/placeholder.jpg'">
            <div style="padding: 1.5rem;">
                <h2 style="margin-bottom: 1rem;">${dest.name}</h2>
                <p style="color: #666; margin-bottom: 0.5rem;">📍 ${dest.address || dest.city}</p>
                <p style="color: #666; margin-bottom: 0.5rem;">💰 ${dest.price_range || '价格未知'}</p>
                <p style="color: #666; margin-bottom: 0.5rem;">⏰ ${dest.opening_hours || '营业时间未知'}</p>
                <p style="color: #666; margin-bottom: 1rem;">⭐ ${dest.rating || 0}分</p>
                <p style="margin-bottom: 1.5rem; line-height: 1.6;">${dest.description || '暂无描述'}</p>
                <button onclick="this.closest('.modal').remove()" 
                        style="
                            width: 100%;
                            padding: 1rem;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                            border: none;
                            border-radius: 10px;
                            font-size: 1rem;
                            cursor: pointer;
                        ">
                    关闭
                </button>
            </div>
        </div>
    `;
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
    
    document.body.appendChild(modal);
}

// 设置背景切换功能
function setupBackgroundSwitch() {
    const bgSwitchBtn = document.querySelector('.bg-switch-btn');
    if (bgSwitchBtn) {
        bgSwitchBtn.addEventListener('click', changeBackground);
    }
}

// 切换背景图片
async function changeBackground() {
    try {
        const response = await fetch('/api/random-background');
        const data = await response.json();
        
        if (data.success && data.image) {
            document.body.style.backgroundImage = `url(${data.image})`;
            document.body.style.backgroundSize = 'cover';
            document.body.style.backgroundPosition = 'center';
            document.body.style.backgroundAttachment = 'fixed';
            
            showToast(`✨ 背景已更换：${data.name || '随机背景'}`, 'success');
        }
    } catch (error) {
        console.error('切换背景失败:', error);
        showToast('切换背景失败', 'error');
    }
}

// 显示提示框
function showToast(message, type = 'info') {
    // 移除现有的toast
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }
    
    const toast = document.createElement('div');
    toast.className = 'toast';
    
    // 根据类型设置样式
    let backgroundColor;
    switch (type) {
        case 'success':
            backgroundColor = '#4CAF50';
            break;
        case 'error':
            backgroundColor = '#f44336';
            break;
        case 'warning':
            backgroundColor = '#ff9800';
            break;
        default:
            backgroundColor = '#333';
    }
    
    toast.style.background = backgroundColor;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    // 3秒后自动消失
    setTimeout(() => {
        if (toast.parentNode) {
            toast.remove();
        }
    }, 3000);
}

// 显示加载状态
function showLoading() {
    const loading = document.createElement('div');
    loading.id = 'globalLoading';
    loading.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(255,255,255,0.9);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 9999;
    `;
    loading.innerHTML = `
        <div style="text-align: center;">
            <div class="loading" style="margin: 0 auto 1rem;"></div>
            <p>正在加载...</p>
        </div>
    `;
    
    document.body.appendChild(loading);
}

// 隐藏加载状态
function hideLoading() {
    const loading = document.getElementById('globalLoading');
    if (loading) {
        loading.remove();
    }
}

// 工具函数：防抖
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

// 工具函数：节流
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
    }
}

// 错误处理
window.addEventListener('error', function(e) {
    console.error('全局错误:', e.error);
    hideLoading();
});

// 网络状态检测
window.addEventListener('online', function() {
    showToast('网络已连接', 'success');
});

window.addEventListener('offline', function() {
    showToast('网络已断开', 'warning');
});

// 键盘快捷键
document.addEventListener('keydown', function(e) {
    // Ctrl+K 聚焦搜索框
    if (e.ctrlKey && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.focus();
            searchInput.select();
        }
    }
    
    // Escape 关闭模态框
    if (e.key === 'Escape') {
        const modals = document.querySelectorAll('.modal');
        modals.forEach(modal => modal.remove());
        
        hideSuggestions();
    }
});

// 点击页面其他地方隐藏搜索建议
document.addEventListener('click', function(e) {
    if (!e.target.closest('.search-box')) {
        hideSuggestions();
    }
});

// 性能监控
if ('performance' in window) {
    window.addEventListener('load', function() {
        setTimeout(function() {
            const perfData = performance.timing;
            const loadTime = perfData.loadEventEnd - perfData.navigationStart;
            console.log(`页面加载时间: ${loadTime}ms`);
        }, 0);
    });
}

// Service Worker 注册（PWA支持）
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker.register('/static/sw.js')
            .then(function(registration) {
                console.log('ServiceWorker 注册成功:', registration.scope);
            })
            .catch(function(error) {
                console.log('ServiceWorker 注册失败:', error);
            });
    });
}

console.log('智能旅游助手已加载完成！');
