/**
 * common.js - 公共 JavaScript 模块
 * 包含背景管理、通知提示、退出登录等共享功能
 */

// ==================== Toast 通知 ====================
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `position-fixed top-0 start-50 translate-middle-x mt-4 ${type === 'error' ? 'bg-danger' : 'bg-success'} text-white px-4 py-2 rounded-pill shadow-lg animate-fade-in-out`;
    toast.style.zIndex = '9999';
    toast.innerHTML = `<i class="fas ${type === 'error' ? 'fa-exclamation-circle' : 'fa-check-circle'} me-2"></i>${message}`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// ==================== 退出登录 ====================
async function logout() {
    try {
        const response = await fetch('/api/logout', { method: 'POST' });
        const data = await response.json();
        if (data.success) {
            window.location.href = '/';
        }
    } catch (error) {
        console.error('退出失败:', error);
        window.location.href = '/';
    }
}

// ==================== 背景图片管理 ====================
const BackgroundManager = {
    styleElement: null,

    init() {
        if (!this.styleElement) {
            this.styleElement = document.getElementById('bg-style');
            if (!this.styleElement) {
                this.styleElement = document.createElement('style');
                this.styleElement.id = 'bg-style';
                document.head.appendChild(this.styleElement);
            }
        }
    },

    update(imageUrl, name, location) {
        this.init();
        this.styleElement.textContent = `body::before { background-image: url('${imageUrl}') !important; }`;
        document.body.style.backgroundImage = `url('${imageUrl}')`;

        const badge = document.getElementById('locationBadge');
        if (badge) {
            badge.innerHTML = `<i class="fas fa-map-marker-alt me-2"></i>${name} · ${location}`;
        }

        localStorage.setItem('lastBackground', JSON.stringify({
            image: imageUrl, name, location, timestamp: Date.now()
        }));
    },

    change() {
        const btn = document.querySelector('.bg-switch-btn');
        if (btn) {
            btn.disabled = true;
            const icon = btn.querySelector('i');
            if (icon) icon.classList.add('fa-spin');
        }

        fetch('/api/random-background?t=' + Date.now())
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    const img = new Image();
                    img.onload = () => {
                        this.update(data.image, data.name, data.location);
                        showToast(`✨ 当前背景：${data.name} · ${data.location}`);
                    };
                    img.src = data.image;
                }
            })
            .catch(error => {
                console.error('切换背景失败:', error);
                showToast('❌ 切换背景失败', 'error');
            })
            .finally(() => {
                if (btn) {
                    btn.disabled = false;
                    const icon = btn.querySelector('i');
                    if (icon) setTimeout(() => icon.classList.remove('fa-spin'), 500);
                }
            });
    },

    loadSaved() {
        this.init();
        const saved = localStorage.getItem('lastBackground');
        if (saved) {
            try {
                const bgData = JSON.parse(saved);
                if (bgData.timestamp && (Date.now() - bgData.timestamp < 24 * 60 * 60 * 1000)) {
                    this.update(bgData.image, bgData.name, bgData.location);
                    return;
                }
            } catch (e) {
                console.log('解析保存的背景失败');
            }
        }
        setTimeout(() => this.change(), 100);
    }
};

// 全局便捷方法
function changeBackground() {
    BackgroundManager.change();
}

// ==================== 图片错误处理 ====================
function handleImageError(img, name, city) {
    img.onerror = null;
    img.src = '/static/images/placeholder.jpg';
}

// ==================== 动画样式 ====================
const animationStyle = document.createElement('style');
animationStyle.textContent = `
@keyframes fadeInOut {
    0% { opacity: 0; transform: translate(-50%, -20px); }
    10% { opacity: 1; transform: translate(-50%, 0); }
    90% { opacity: 1; transform: translate(-50%, 0); }
    100% { opacity: 0; transform: translate(-50%, -20px); }
}
.animate-fade-in-out { animation: fadeInOut 3s ease forwards; }
`;
document.head.appendChild(animationStyle);
