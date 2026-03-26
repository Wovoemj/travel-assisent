// 分享管理器
class ShareManager {
    constructor() {
        this.shareEndpoint = '/api/share';
        this.posterEndpoint = '/api/share/poster';
        this.currentShareData = null;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadShareSDKs();
        console.log('✅ 分享管理器已初始化');
    }

    setupEventListeners() {
        // 点击分享按钮
        document.addEventListener('click', (e) => {
            if (e.target.closest('.share-btn')) {
                const shareData = e.target.closest('.share-btn').dataset;
                this.showShareModal(shareData);
            }
            
            if (e.target.closest('.share-wechat')) {
                this.shareToWeChat();
            }
            
            if (e.target.closest('.share-weibo')) {
                this.shareToWeibo();
            }
            
            if (e.target.closest('.share-qq')) {
                this.shareToQQ();
            }
            
            if (e.target.closest('.share-link')) {
                this.copyShareLink();
            }
            
            if (e.target.closest('.share-poster')) {
                this.generatePoster();
            }
        });
    }

    // 加载分享SDK
    loadShareSDKs() {
        // 微信分享SDK
        if (typeof wx !== 'undefined') {
            this.initWeChatSDK();
        }
        
        // 微博分享SDK
        this.loadScript('https://tjs.sjs.sinajs.com/open/api/js/wb.js', () => {
            if (typeof WB2 !== 'undefined') {
                console.log('✅ 微博SDK加载成功');
            }
        });
    }

    // 初始化微信SDK
    initWeChatSDK() {
        // 这里需要从后端获取配置
        fetch('/api/wechat/config')
            .then(res => res.json())
            .then(config => {
                if (config.success) {
                    wx.config({
                        debug: false,
                        appId: config.appId,
                        timestamp: config.timestamp,
                        nonceStr: config.nonceStr,
                        signature: config.signature,
                        jsApiList: ['updateAppMessageShareData', 'updateTimelineShareData']
                    });
                    console.log('✅ 微信SDK初始化成功');
                }
            })
            .catch(error => {
                console.log('微信SDK初始化失败:', error);
            });
    }

    // 动态加载脚本
    loadScript(src, callback) {
        const script = document.createElement('script');
        script.src = src;
        script.onload = callback;
        document.head.appendChild(script);
    }

    // 显示分享模态框
    showShareModal(shareData) {
        this.currentShareData = {
            title: shareData.title || document.title,
            desc: shareData.desc || '发现一个很棒的景点，快来看看吧！',
            link: shareData.link || window.location.href,
            image: shareData.image || document.querySelector('meta[property="og:image"]')?.content || '',
            destination: shareData.destination || ''
        };

        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = 'shareModal';
        modal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">分享到</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="share-platforms">
                            <div class="row">
                                <div class="col-4 text-center mb-3">
                                    <button class="btn share-wechat" style="background: #07c160; color: white; border-radius: 50%; width: 60px; height: 60px;">
                                        <i class="fab fa-weixin fa-2x"></i>
                                    </button>
                                    <p class="small mt-1">微信</p>
                                </div>
                                <div class="col-4 text-center mb-3">
                                    <button class="btn share-weibo" style="background: #e6162d; color: white; border-radius: 50%; width: 60px; height: 60px;">
                                        <i class="fab fa-weibo fa-2x"></i>
                                    </button>
                                    <p class="small mt-1">微博</p>
                                </div>
                                <div class="col-4 text-center mb-3">
                                    <button class="btn share-qq" style="background: #12b7f5; color: white; border-radius: 50%; width: 60px; height: 60px;">
                                        <i class="fab fa-qq fa-2x"></i>
                                    </button>
                                    <p class="small mt-1">QQ</p>
                                </div>
                                <div class="col-4 text-center mb-3">
                                    <button class="btn share-link" style="background: #6c757d; color: white; border-radius: 50%; width: 60px; height: 60px;">
                                        <i class="fas fa-link fa-2x"></i>
                                    </button>
                                    <p class="small mt-1">复制链接</p>
                                </div>
                                <div class="col-4 text-center mb-3">
                                    <button class="btn share-poster" style="background: #667eea; color: white; border-radius: 50%; width: 60px; height: 60px;">
                                        <i class="fas fa-image fa-2x"></i>
                                    </button>
                                    <p class="small mt-1">生成海报</p>
                                </div>
                                <div class="col-4 text-center mb-3">
                                    <button class="btn share-more" style="background: #6c757d; color: white; border-radius: 50%; width: 60px; height: 60px;">
                                        <i class="fas fa-ellipsis-h fa-2x"></i>
                                    </button>
                                    <p class="small mt-1">更多</p>
                                </div>
                            </div>
                        </div>
                        
                        <!-- 分享预览 -->
                        <div class="share-preview mt-3 p-3 bg-light rounded">
                            <div class="d-flex">
                                ${this.currentShareData.image ? 
                                    `<img src="${this.currentShareData.image}" style="width: 60px; height: 60px; object-fit: cover; border-radius: 8px;" class="me-3">` : 
                                    '<div style="width: 60px; height: 60px; background: #ddd; border-radius: 8px;" class="me-3"></div>'
                                }
                                <div>
                                    <h6 class="mb-1">${this.currentShareData.title}</h6>
                                    <p class="small text-muted mb-0">${this.currentShareData.desc}</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();

        modal.addEventListener('hidden.bs.modal', () => {
            document.body.removeChild(modal);
        });
    }

    // 分享到微信
    shareToWeChat() {
        if (typeof wx !== 'undefined' && wx.ready) {
            wx.ready(() => {
                // 分享给朋友
                wx.updateAppMessageShareData({
                    title: this.currentShareData.title,
                    desc: this.currentShareData.desc,
                    link: this.currentShareData.link,
                    imgUrl: this.currentShareData.image,
                    success: () => {
                        this.showToast('分享设置成功', 'success');
                    }
                });

                // 分享到朋友圈
                wx.updateTimelineShareData({
                    title: this.currentShareData.title,
                    link: this.currentShareData.link,
                    imgUrl: this.currentShareData.image,
                    success: () => {
                        this.showToast('分享设置成功', 'success');
                    }
                });
            });
        } else {
            // 降级方案：显示二维码
            this.showWeChatQRCode();
        }
        
        this.closeShareModal();
    }

    // 显示微信二维码
    showWeChatQRCode() {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">分享到微信</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body text-center">
                        <p>请使用微信扫描二维码分享</p>
                        <div id="wechatQRCode" class="my-3"></div>
                        <p class="text-muted small">或复制链接发送给朋友</p>
                        <button class="btn btn-outline-primary btn-sm" onclick="shareManager.copyShareLink()">
                            <i class="fas fa-copy me-1"></i>复制链接
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();

        // 生成二维码
        this.generateQRCode('wechatQRCode', this.currentShareData.link);

        modal.addEventListener('hidden.bs.modal', () => {
            document.body.removeChild(modal);
        });
    }

    // 分享到微博
    shareToWeibo() {
        const shareUrl = `https://service.weibo.com/share/share.php?url=${encodeURIComponent(this.currentShareData.link)}&title=${encodeURIComponent(this.currentShareData.title)}&pic=${encodeURIComponent(this.currentShareData.image)}`;
        
        window.open(shareUrl, '_blank', 'width=600,height=400');
        
        this.recordShare('weibo');
        this.closeShareModal();
        this.showToast('正在跳转到微博分享页面...', 'info');
    }

    // 分享到QQ
    shareToQQ() {
        const shareUrl = `https://connect.qq.com/widget/shareqq/index.html?url=${encodeURIComponent(this.currentShareData.link)}&title=${encodeURIComponent(this.currentShareData.title)}&desc=${encodeURIComponent(this.currentShareData.desc)}&pics=${encodeURIComponent(this.currentShareData.image)}`;
        
        window.open(shareUrl, '_blank', 'width=600,height=400');
        
        this.recordShare('qq');
        this.closeShareModal();
        this.showToast('正在跳转到QQ分享页面...', 'info');
    }

    // 复制分享链接
    copyShareLink() {
        navigator.clipboard.writeText(this.currentShareData.link).then(() => {
            this.showToast('链接已复制到剪贴板', 'success');
            this.recordShare('link');
        }).catch(() => {
            // 降级方案
            const input = document.createElement('input');
            input.value = this.currentShareData.link;
            document.body.appendChild(input);
            input.select();
            document.execCommand('copy');
            document.body.removeChild(input);
            this.showToast('链接已复制到剪贴板', 'success');
            this.recordShare('link');
        });
        
        this.closeShareModal();
    }

    // 生成分享海报
    async generatePoster() {
        this.closeShareModal();
        
        // 显示加载提示
        const loadingModal = document.createElement('div');
        loadingModal.className = 'modal fade';
        loadingModal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-body text-center py-5">
                        <div class="spinner-border text-primary mb-3"></div>
                        <h5>正在生成分享海报...</h5>
                        <p class="text-muted mb-0">请稍候</p>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(loadingModal);
        const bsLoadingModal = new bootstrap.Modal(loadingModal);
        bsLoadingModal.show();

        try {
            // 调用后端生成海报
            const response = await fetch(this.posterEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(this.currentShareData)
            });

            const result = await response.json();
            
            bsLoadingModal.hide();
            document.body.removeChild(loadingModal);

            if (result.success) {
                this.showPosterModal(result.poster_url);
                this.recordShare('poster');
            } else {
                this.showToast('海报生成失败: ' + result.error, 'error');
            }
        } catch (error) {
            bsLoadingModal.hide();
            document.body.removeChild(loadingModal);
            this.showToast('海报生成失败: ' + error.message, 'error');
        }
    }

    // 显示海报模态框
    showPosterModal(posterUrl) {
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog modal-lg modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">分享海报</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body text-center">
                        <img src="${posterUrl}" class="img-fluid rounded" style="max-height: 70vh;">
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-outline-primary" onclick="shareManager.downloadPoster('${posterUrl}')">
                            <i class="fas fa-download me-1"></i>下载海报
                        </button>
                        <button class="btn btn-primary" onclick="shareManager.sharePosterToWeChat('${posterUrl}')">
                            <i class="fab fa-weixin me-1"></i>分享到微信
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();

        modal.addEventListener('hidden.bs.modal', () => {
            document.body.removeChild(modal);
        });
    }

    // 下载海报
    downloadPoster(posterUrl) {
        const link = document.createElement('a');
        link.href = posterUrl;
        link.download = `分享海报_${Date.now()}.png`;
        link.click();
        this.showToast('海报下载已开始', 'success');
    }

    // 分享海报到微信
    sharePosterToWeChat(posterUrl) {
        // 先下载图片，然后提示用户手动分享
        this.downloadPoster(posterUrl);
        this.showToast('海报已下载，请在微信中选择图片分享', 'info');
    }

    // 生成二维码
    generateQRCode(containerId, url) {
        // 这里可以使用qrcode.js库
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = `
                <div style="width: 200px; height: 200px; background: #f0f0f0; display: flex; align-items: center; justify-content: center; margin: 0 auto; border-radius: 8px;">
                    <div class="text-center">
                        <i class="fas fa-qrcode fa-3x text-muted"></i>
                        <p class="small mt-2">二维码示例</p>
                    </div>
                </div>
            `;
        }
    }

    // 记录分享
    async recordShare(platform) {
        try {
            await fetch('/api/share/record', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    platform: platform,
                    destination: this.currentShareData.destination,
                    url: this.currentShareData.link,
                    timestamp: new Date().toISOString()
                })
            });
        } catch (error) {
            console.error('分享记录失败:', error);
        }
    }

    // 关闭分享模态框
    closeShareModal() {
        const modal = document.getElementById('shareModal');
        if (modal) {
            const bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) {
                bsModal.hide();
            }
        }
    }

    // 显示提示消息
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        const bgClass = type === 'success' ? 'bg-success' : 
                       type === 'error' ? 'bg-danger' : 
                       type === 'warning' ? 'bg-warning' : 'bg-info';
        
        toast.className = `position-fixed top-0 start-50 translate-middle-x mt-4 ${bgClass} text-white px-4 py-2 rounded-pill shadow-lg`;
        toast.style.zIndex = '9999';
        toast.innerHTML = `<i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-info-circle'} me-2"></i>${message}`;
        
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }

    // 获取分享统计
    async getShareStats(destinationId = null) {
        try {
            const url = destinationId ? 
                `/api/share/stats?destination_id=${destinationId}` : 
                '/api/share/stats';
            
            const response = await fetch(url);
            return await response.json();
        } catch (error) {
            console.error('获取分享统计失败:', error);
            return { success: false, error: error.message };
        }
    }

    // 生成分享链接
    generateShareLink(destinationId, type = 'destination') {
        const baseUrl = window.location.origin;
        let shareUrl;
        
        switch (type) {
            case 'destination':
                shareUrl = `${baseUrl}/dest/${destinationId}`;
                break;
            case 'trip':
                shareUrl = `${baseUrl}/trip/${destinationId}`;
                break;
            default:
                shareUrl = window.location.href;
        }
        
        // 添加分享追踪参数
        const separator = shareUrl.includes('?') ? '&' : '?';
        return `${shareUrl}${separator}share_source=${type}&share_time=${Date.now()}`;
    }

    // 检测分享环境
    detectEnvironment() {
        const ua = navigator.userAgent.toLowerCase();
        
        return {
            isWeChat: ua.includes('micromessenger'),
            isWeibo: ua.includes('weibo'),
            isQQ: ua.includes('qq/'),
            isMobile: /android|iphone|ipad|ipod|blackberry|iemobile|opera mini/i.test(ua),
            isIOS: /iPad|iPhone|iPod/.test(navigator.platform),
            isAndroid: ua.includes('android')
        };
    }

    // 智能分享推荐
    getRecommendedPlatforms() {
        const env = this.detectEnvironment();
        const platforms = [];
        
        if (env.isWeChat) {
            platforms.push('wechat', 'wechat_timeline');
        } else if (env.isWeibo) {
            platforms.push('weibo');
        } else if (env.isQQ) {
            platforms.push('qq', 'qzone');
        }
        
        // 通用平台
        platforms.push('link', 'poster');
        
        if (!env.isMobile) {
            platforms.push('email', 'qrcode');
        }
        
        return platforms;
    }
}

// 创建全局实例
const shareManager = new ShareManager();

// 导出模块
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ShareManager;
}

// 暴露到全局
window.ShareManager = ShareManager;
window.shareManager = shareManager;