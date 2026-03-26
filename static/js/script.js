// ==================== 全局变量 ====================
let socket = null;
let isConnected = false;
let searchTimeout = null;

// ==================== 页面初始化 ====================
$(document).ready(function() {
    console.log("页面加载完成，开始初始化...");

    // 1. 检查jQuery和Bootstrap是否加载
    if (typeof $ === 'undefined') {
        console.error("jQuery未加载！");
        showResourceError();
        return;
    }

    if (typeof bootstrap === 'undefined') {
        console.error("Bootstrap未加载！");
        showResourceError();
        return;
    }

    // 2. 检查Socket.IO是否加载
    if (typeof io === 'undefined') {
        console.warn("Socket.IO未加载，智能助手将使用HTTP模式");
    }

    // 3. 初始化所有功能
    initSocketIO();
    bindChatEvents();
    initOtherFeatures();
    initPage();

    // 4. 加载城市数据（如果存在城市下拉菜单）
    if (document.getElementById('cityMenu')) {
        loadAllCities();
    }
});

// ==================== 资源错误处理 ====================
function showResourceError() {
    const errorHTML = `
        <div style="text-align:center; padding:50px; color:red;">
            <h2>资源加载失败</h2>
            <p>无法加载必要的JavaScript库</p>
            <p>请检查网络连接并刷新页面</p>
            <p>确保按正确顺序加载：jQuery → Bootstrap JS → 自定义JS</p>
        </div>
    `;
    document.body.innerHTML = errorHTML;
}

// ==================== SocketIO 连接 ====================
function initSocketIO() {
    try {
        // 检查Socket.IO是否加载
        if (typeof io === 'undefined') {
            console.error("Socket.IO未加载！");
            // 降级到HTTP API
            useHTTPAPI();
            return;
        }

        // 连接服务器
        socket = io();

        // 连接成功
        socket.on('connect', function() {
            console.log("SocketIO连接成功");
            isConnected = true;
            showNotification('智能助手已连接', 'success');
        });

        // 连接失败
        socket.on('connect_error', function(error) {
            console.error("SocketIO连接失败:", error);
            isConnected = false;
            showNotification('无法连接智能助手，使用备用方案', 'warning');
            useHTTPAPI();
        });

        // 接收服务器消息
        socket.on('server_message', function(data) {
            console.log("服务器消息:", data);
            if (data.type === 'welcome') {
                addAssistantMessage(data.content, data.timestamp);
            }
        });

        // 接收AI回复
        socket.on('assistant_response', function(data) {
            console.log("AI回复:", data);
            hideTypingIndicator();

            if (data.type === 'text') {
                addAssistantMessage(data.content, data.timestamp);

                // 显示建议
                if (data.suggestions) {
                    updateSuggestions(data.suggestions);
                }
            }
        });

        // 显示输入状态
        socket.on('assistant_typing', function(data) {
            showTypingIndicator();
        });

        // 断开连接
        socket.on('disconnect', function() {
            console.log("SocketIO连接断开");
            isConnected = false;
            showNotification('与智能助手的连接已断开', 'warning');
        });

    } catch (error) {
        console.error("SocketIO初始化错误:", error);
        useHTTPAPI();
    }
}

// ==================== HTTP API 降级方案 ====================
function useHTTPAPI() {
    console.log("使用HTTP API作为备用方案");

    // 修改sendMessage函数，使用HTTP请求
    window.sendMessage = function() {
        const input = document.getElementById('chatInput');
        const message = input.value.trim();

        if (!message) {
            return;
        }

        // 添加用户消息
        addUserMessage(message);
        input.value = '';

        // 显示输入状态
        showTypingIndicator();

        // 发送HTTP请求
        fetch('/api/assistant', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message })
        })
        .then(response => response.json())
        .then(data => {
            hideTypingIndicator();

            if (data.error) {
                addAssistantMessage("抱歉，无法处理您的请求。", getCurrentTime());
            } else {
                addAssistantMessage(data.content, data.timestamp);

                if (data.suggestions) {
                    updateSuggestions(data.suggestions);
                }
            }
        })
        .catch(error => {
            hideTypingIndicator();
            addAssistantMessage("网络错误，请稍后再试。", getCurrentTime());
            console.error("API请求失败:", error);
        });
    };
}

// ==================== 聊天相关函数 ====================
function bindChatEvents() {
    // 发送按钮点击
    $('#sendButton').on('click', function() {
        sendMessage();
    });

    // 回车发送
    $('#chatInput').on('keypress', function(e) {
        if (e.which === 13) {
            sendMessage();
        }
    });

    // 建议按钮点击
    $(document).on('click', '.suggestion-btn', function() {
        const suggestion = $(this).data('suggestion');
        $('#chatInput').val(suggestion);
        sendMessage();
    });

    // 模态框完全显示时聚焦输入框
    $('#chatModal').on('shown.bs.modal', function() {
        $('#chatInput').focus();
    });
}

// 发送消息（SocketIO版本）
function sendMessage() {
    // 检查是否使用HTTP API模式
    if (typeof window.sendMessage === 'function' && !isConnected) {
        window.sendMessage();
        return;
    }

    if (!isConnected || !socket) {
        showNotification('智能助手未连接', 'warning');
        return;
    }

    const input = document.getElementById('chatInput');
    const message = input.value.trim();

    if (!message) {
        return;
    }

    // 添加用户消息
    addUserMessage(message);
    input.value = '';

    // 发送消息到服务器
    socket.emit('user_message', {
        message: message,
        user_id: 'user_' + Date.now()
    });
}

// 添加用户消息
function addUserMessage(message) {
    const messagesDiv = document.getElementById('chatMessages');
    const time = getCurrentTime();

    const messageHTML = `
        <div class="message user-message">
            <div>${escapeHtml(message)}</div>
            <div class="message-time">${time}</div>
        </div>
    `;

    messagesDiv.innerHTML += messageHTML;
    scrollToBottom();
}

// 添加AI助手消息
function addAssistantMessage(message, time) {
    const messagesDiv = document.getElementById('chatMessages');

    // 处理换行和格式
    const formattedMessage = message.replace(/\n/g, '<br>');

    const messageHTML = `
        <div class="message assistant-message">
            <div>${formattedMessage}</div>
            <div class="message-time">${time || getCurrentTime()}</div>
        </div>
    `;

    messagesDiv.innerHTML += messageHTML;
    scrollToBottom();
}

// 显示输入状态
function showTypingIndicator() {
    const messagesDiv = document.getElementById('chatMessages');

    // 移除现有的输入指示器
    const existingIndicator = document.getElementById('typingIndicator');
    if (existingIndicator) {
        existingIndicator.remove();
    }

    const indicatorHTML = `
        <div class="message assistant-message" id="typingIndicator">
            <div class="typing-indicator">
                <span>●</span><span>●</span><span>●</span>
            </div>
        </div>
    `;

    messagesDiv.innerHTML += indicatorHTML;
    scrollToBottom();
}

// 隐藏输入状态
function hideTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) {
        indicator.remove();
    }
}

// 更新建议按钮
function updateSuggestions(suggestions) {
    const container = document.getElementById('suggestionButtons');

    if (!container || !suggestions || suggestions.length === 0) {
        return;
    }

    let html = '<small class="text-muted">建议：</small><div class="d-flex flex-wrap gap-1 mt-1">';

    suggestions.forEach(suggestion => {
        html += `<button class="btn btn-sm btn-outline-primary suggestion-btn" data-suggestion="${escapeHtml(suggestion)}">${escapeHtml(suggestion)}</button>`;
    });

    html += '</div>';
    container.innerHTML = html;
}

// 打开聊天模态框
function openChatModal() {
    const modal = new bootstrap.Modal(document.getElementById('chatModal'));
    modal.show();
}

// 滚动到底部
function scrollToBottom() {
    const container = document.getElementById('chatContainer');
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

// 获取当前时间
function getCurrentTime() {
    const now = new Date();
    return now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

// HTML转义
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, function(m) { return map[m]; });
}

// ==================== 页面初始化和功能 ====================
function initPage() {
    // 添加页面淡入效果
    $('main').addClass('fade-in');

    // 检查浏览器支持
    checkBrowserSupport();

    // 设置当前年份
    const currentYear = new Date().getFullYear();
    $('#current-year').text(currentYear);

    // 搜索表单自动提交（AJAX方式）
    $('#search-form').on('submit', function(e) {
        e.preventDefault();
        performSearch();
    });

    // 搜索输入框实时搜索（防抖）
    $('#search-input').on('input', function() {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            if ($(this).val().length >= 2) {
                performSearch($(this).val());
            }
        }, 300);
    });

    // 分类筛选变化
    $('#category-filter').on('change', function() {
        filterDestinations();
    });

    // 省份筛选变化
    $('#province-filter').on('change', function() {
        filterDestinations();
    });

    // 排序变化
    $('#sort-by').on('change', function() {
        sortDestinations();
    });

    // 回到顶部功能
    $(window).scroll(function() {
        if ($(this).scrollTop() > 300) {
            $('#backToTop').removeClass('d-none');
        } else {
            $('#backToTop').addClass('d-none');
        }
    });

    $('#backToTop').click(function() {
        $('html, body').animate({scrollTop: 0}, 500);
        return false;
    });

    // 暗黑模式切换检查
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        document.documentElement.setAttribute('data-bs-theme', 'dark');
    }

    // 添加主题切换按钮
    const themeToggle = $('<button/>', {
        class: 'btn btn-sm btn-outline-secondary',
        html: '<i class="bi bi-moon-stars"></i>',
        click: toggleDarkMode
    });

    $('.navbar .container').append(
        $('<div/>', { class: 'ms-2' }).append(themeToggle)
    );
}

// 检查浏览器支持
function checkBrowserSupport() {
    if (!window.fetch) {
        console.warn('您的浏览器不支持Fetch API，部分功能可能无法使用');
    }

    if (!window.navigator.geolocation) {
        console.warn('您的浏览器不支持地理位置功能');
    }
}

// 执行搜索
function performSearch(query) {
    if (!query) {
        query = $('#search-input').val().trim();
    }

    if (!query) {
        showToast('请输入搜索关键词', 'warning');
        return;
    }

    // 显示加载状态
    showLoading();

    // 执行搜索
    fetch('/api/search?q=' + encodeURIComponent(query))
        .then(response => response.json())
        .then(data => {
            hideLoading();
            if (data.success) {
                displaySearchResults(data.results, data.count);
            } else {
                showToast('搜索失败: ' + data.error, 'error');
            }
        })
        .catch(() => {
            hideLoading();
            showToast('网络错误，请稍后重试', 'error');
        });
}

// 显示搜索结果
function displaySearchResults(results, count) {
    const container = $('#search-results');
    container.empty();

    if (results.length === 0) {
        container.html(`
            <div class="alert alert-info text-center">
                <h5><i class="bi bi-search"></i> 未找到结果</h5>
                <p>请尝试其他关键词</p>
            </div>
        `);
        return;
    }

    let html = `<div class="alert alert-success">
        <strong>找到 ${count} 个结果</strong>
    </div>`;

    html += '<div class="row">';

    results.forEach(dest => {
        html += `
            <div class="col-md-6 mb-3">
                <div class="card h-100">
                    <div class="card-body">
                        <h6 class="card-title">
                            <a href="/dest/${dest.id}" class="text-decoration-none">
                                ${dest.name}
                            </a>
                        </h6>
                        <p class="card-text small text-muted mb-1">
                            <i class="bi bi-geo-alt"></i> ${dest.city} | ${dest.province}
                        </p>
                        <p class="card-text small mb-1">
                            <span class="badge bg-primary">${dest.category}</span>
                            <span class="badge bg-warning text-dark">
                                <i class="bi bi-star-fill"></i> ${dest.rating}
                            </span>
                        </p>
                        <p class="card-text small text-muted">
                            ${dest.description.substring(0, 80)}...
                        </p>
                    </div>
                </div>
            </div>
        `;
    });

    html += '</div>';
    container.html(html);
}

// 筛选景点
function filterDestinations() {
    const category = $('#category-filter').val();
    const province = $('#province-filter').val();

    // 重新加载页面并传递参数
    const url = new URL(window.location.href);
    if (category) {
        url.searchParams.set('category', category);
    } else {
        url.searchParams.delete('category');
    }

    if (province) {
        url.searchParams.set('province', province);
    } else {
        url.searchParams.delete('province');
    }

    window.location.href = url.toString();
}

// 排序景点
function sortDestinations() {
    const sortBy = $('#sort-by').val();

    const url = new URL(window.location.href);
    url.searchParams.set('sort_by', sortBy);

    window.location.href = url.toString();
}

// 显示加载状态
function showLoading() {
    $('#loading').removeClass('d-none');
}

// 隐藏加载状态
function hideLoading() {
    $('#loading').addClass('d-none');
}

// ==================== 城市相关功能 ====================
// 动态加载所有城市
function loadAllCities() {
    console.log("开始加载所有城市...");

    fetch('/api/cities')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.cities.length > 0) {
                const cityMenu = document.getElementById('cityMenu');
                if (cityMenu) {
                    // 清除现有内容（保留"全部城市"选项）
                    const currentUrl = window.location.href;
                    const urlParams = new URLSearchParams(window.location.search);
                    const currentCategory = urlParams.get('category');
                    const currentSort = urlParams.get('sort_by') || 'popularity';

                    // 重建菜单
                    let html = '<li><a class="dropdown-item" href="' +
                        buildUrl(currentCategory, null, currentSort) +
                        '">全部城市</a></li>';

                    // 添加所有城市
                    data.cities.forEach(city => {
                        html += '<li><a class="dropdown-item" href="' +
                            buildUrl(currentCategory, city, currentSort) +
                            '">' + city + '</a></li>';
                    });

                    cityMenu.innerHTML = html;
                    console.log(`成功加载 ${data.count} 个城市`);
                }
            } else {
                console.warn("未能获取城市数据:", data.error);
                showNotification('城市数据加载失败', 'warning');
            }
        })
        .catch(error => {
            console.error("加载城市数据失败:", error);
            showNotification('网络错误，无法加载城市数据', 'error');
        });
}

// 构建URL
function buildUrl(category, province, sort) {
    const params = [];
    if (category) params.push(`category=${encodeURIComponent(category)}`);
    if (province) params.push(`province=${encodeURIComponent(province)}`);
    if (sort) params.push(`sort_by=${sort}`);

    return window.location.pathname + (params.length ? '?' + params.join('&') : '');
}

// ==================== 其他功能 ====================
// 显示通知（统一使用showNotification）
function showNotification(message, type = 'info') {
    const toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        return;
    }

    const toastHTML = `
        <div class="toast align-items-center text-white bg-${type === 'success' ? 'success' : type === 'warning' ? 'warning' : 'primary'} border-0" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="关闭"></button>
            </div>
        </div>
    `;

    toastContainer.insertAdjacentHTML('beforeend', toastHTML);

    // 显示并自动隐藏
    const toastElement = toastContainer.lastElementChild;
    const toast = new bootstrap.Toast(toastElement, { delay: 3000 });
    toast.show();

    // 移除后清理
    toastElement.addEventListener('hidden.bs.toast', function() {
        toastElement.remove();
    });
}

// 显示Toast通知（兼容旧代码）
function showToast(message, type = 'info') {
    showNotification(message, type);
}

// ==================== 其他辅助功能 ====================
// 初始化其他功能（下拉菜单、统计板块等）
function initOtherFeatures() {
    console.log("初始化其他功能...");

    // 方案A：让Bootstrap管理下拉菜单（推荐）
    // 删除自定义的下拉菜单事件绑定，让Bootstrap的原生功能正常工作
    // 如果下拉菜单需要动态加载数据，请在HTML模板中直接渲染，而不是在JS中动态加载

    // 方案B：如果确实需要动态加载下拉菜单数据，使用以下修复后的代码：
    // 注意：这需要您的后端API返回数据，且前端模板需要调整

    // 仅对需要动态加载的下拉菜单绑定事件（例如“全部城市”下拉菜单）
    // 假设您有一个ID为'cityMenu'的下拉菜单需要动态加载
    const cityDropdown = document.getElementById('cityMenu');
    if (cityDropdown) {
        const dropdownToggle = cityDropdown.parentElement.querySelector('.dropdown-toggle');
        if (dropdownToggle) {
            dropdownToggle.addEventListener('click', function(e) {
                // 检查菜单是否为空
                const menu = cityDropdown;
                if (menu.querySelectorAll('.dropdown-item').length <= 1) { // 只有“全部城市”选项
                    const type = this.textContent.trim();
                    loadDropdownData(type, menu);
                }
                // 不阻止事件，让Bootstrap处理下拉菜单的显示/隐藏
            });
        }
    }

    // 统计板块点击事件（保持不变）
    const statCards = document.querySelectorAll('.stat-card, .card');
    statCards.forEach(card => {
        card.style.cursor = 'pointer';
        card.addEventListener('click', function() {
            const title = this.querySelector('.card-title')?.textContent || '未知板块';
            console.log(`点击了统计板块: ${title}`);

            if (title.includes('景点总数')) {
                window.location.href = '/';
            } else if (title.includes('覆盖省份')) {
                window.location.href = '/?expand=provinces';
            } else if (title.includes('景点分类')) {
                window.location.href = '/?expand=categories';
            } else if (title.includes('平均评分')) {
                window.location.href = '/?sort_by=rating';
            }
        });
    });
}


// 加载下拉菜单数据
// 加载下拉菜单数据（修改后）
function loadDropdownData(type, menuElement) {
    console.log(`加载数据: ${type}`);

    // 根据类型选择API端点
    const endpoint = type.includes('分类') ? '/api/categories' : '/api/provinces';

    fetch(endpoint)
        .then(response => response.json())
        .then(data => {
            console.log(`数据加载成功:`, data);

            if (data.success && data.items.length > 0) {
                menuElement.innerHTML = '';

                // 添加“全部省份”选项
                const allItem = document.createElement('li');
                const allLink = document.createElement('a');
                allLink.className = 'dropdown-item';
                allLink.href = `?${type.includes('分类') ? 'category' : 'province'}=`;
                allLink.textContent = `全部${type.includes('分类') ? '分类' : '省份'}`;
                allItem.appendChild(allLink);
                menuElement.appendChild(allItem);

                // 添加所有省份
                data.items.forEach(item => {
                    const li = document.createElement('li');
                    const a = document.createElement('a');
                    a.className = 'dropdown-item';
                    a.href = `?${type.includes('分类') ? 'category' : 'province'}=${encodeURIComponent(item.name)}`;
                    a.textContent = `${item.name} (${item.count})`;
                    li.appendChild(a);
                    menuElement.appendChild(li);
                });

                console.log(`下拉菜单已更新，${data.items.length} 个选项`);
            } else {
                menuElement.innerHTML = '<li><a class="dropdown-item text-muted">暂无数据</a></li>';
            }
        })
        .catch(error => {
            console.error(`数据加载失败: ${error}`);
            menuElement.innerHTML = '<li><a class="dropdown-item text-danger">加载失败</a></li>';
        });
}


// 暗黑模式切换
function toggleDarkMode() {
    const html = document.documentElement;
    const isDark = html.getAttribute('data-bs-theme') === 'dark';

    if (isDark) {
        html.removeAttribute('data-bs-theme');
        localStorage.setItem('theme', 'light');
        showToast('已切换到浅色模式', 'info');
    } else {
        html.setAttribute('data-bs-theme', 'dark');
        localStorage.setItem('theme', 'dark');
        showToast('已切换到深色模式', 'info');
    }
}
