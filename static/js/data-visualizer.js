// 数据可视化管理器
class DataVisualizer {
    constructor() {
        this.charts = {};
        this.colors = {
            primary: '#667eea',
            secondary: '#764ba2',
            success: '#28a745',
            warning: '#ffc107',
            danger: '#dc3545',
            info: '#17a2b8',
            gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
        };
        this.init();
    }

    init() {
        this.loadChartLibrary();
        console.log('✅ 数据可视化管理器已初始化');
    }

    // 加载图表库
    loadChartLibrary() {
        // 动态加载Chart.js
        if (typeof Chart === 'undefined') {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js';
            script.onload = () => {
                console.log('✅ Chart.js 加载成功');
                this.initDefaultCharts();
            };
            document.head.appendChild(script);
        } else {
            this.initDefaultCharts();
        }
    }

    // 初始化默认图表
    initDefaultCharts() {
        // 检查页面中是否有图表容器
        const chartContainers = document.querySelectorAll('[data-chart]');
        chartContainers.forEach(container => {
            const chartType = container.dataset.chart;
            const chartId = container.id;
            this.createChart(chartId, chartType);
        });
    }

    // 创建图表
    async createChart(containerId, chartType, options = {}) {
        const container = document.getElementById(containerId);
        if (!container) return null;

        try {
            // 获取数据
            const data = await this.getChartData(chartType, options);
            
            // 创建画布
            const canvas = document.createElement('canvas');
            container.innerHTML = '';
            container.appendChild(canvas);

            // 根据类型创建图表
            let chart;
            switch (chartType) {
                case 'rating-distribution':
                    chart = this.createRatingChart(canvas, data);
                    break;
                case 'user-growth':
                    chart = this.createUserGrowthChart(canvas, data);
                    break;
                case 'category-distribution':
                    chart = this.createCategoryChart(canvas, data);
                    break;
                case 'province-map':
                    chart = this.createProvinceMap(canvas, data);
                    break;
                case 'monthly-trend':
                    chart = this.createTrendChart(canvas, data);
                    break;
                case 'popular-destinations':
                    chart = this.createPopularChart(canvas, data);
                    break;
                default:
                    chart = this.createDefaultChart(canvas, data);
            }

            this.charts[containerId] = chart;
            return chart;

        } catch (error) {
            console.error('创建图表失败:', error);
            container.innerHTML = `<div class="alert alert-danger">图表加载失败: ${error.message}</div>`;
            return null;
        }
    }

    // 获取图表数据
    async getChartData(chartType, options = {}) {
        try {
            const response = await fetch(`/api/analytics/${chartType}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(options)
            });
            return await response.json();
        } catch (error) {
            console.error('获取图表数据失败:', error);
            return this.getMockData(chartType);
        }
    }

    // 评分分布图
    createRatingChart(canvas, data) {
        return new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: ['5星', '4星', '3星', '2星', '1星'],
                datasets: [{
                    data: data.distribution || [45, 30, 15, 7, 3],
                    backgroundColor: [
                        '#28a745', '#20c997', '#ffc107', '#fd7e14', '#dc3545'
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    title: {
                        display: true,
                        text: '景点评分分布'
                    }
                }
            }
        });
    }

    // 用户增长趋势图
    createUserGrowthChart(canvas, data) {
        return new Chart(canvas, {
            type: 'line',
            data: {
                labels: data.labels || this.generateDateLabels(30),
                datasets: [{
                    label: '新用户',
                    data: data.new_users || this.generateRandomData(30, 5, 50),
                    borderColor: this.colors.primary,
                    backgroundColor: this.colors.primary + '20',
                    tension: 0.4,
                    fill: true
                }, {
                    label: '活跃用户',
                    data: data.active_users || this.generateRandomData(30, 20, 100),
                    borderColor: this.colors.success,
                    backgroundColor: this.colors.success + '20',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top' },
                    title: { display: true, text: '用户增长趋势' }
                },
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });
    }

    // 分类分布图
    createCategoryChart(canvas, data) {
        return new Chart(canvas, {
            type: 'bar',
            data: {
                labels: data.categories || ['自然景观', '历史古迹', '主题公园', '博物馆', '宗教场所'],
                datasets: [{
                    label: '景点数量',
                    data: data.counts || [120, 85, 45, 38, 25],
                    backgroundColor: [
                        this.colors.primary,
                        this.colors.secondary,
                        this.colors.success,
                        this.colors.warning,
                        this.colors.info
                    ],
                    borderRadius: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    title: { display: true, text: '景点分类分布' }
                },
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });
    }

    // 省份地图（简化版热力图）
    createProvinceMap(canvas, data) {
        // 创建简单的热力图表示
        const provinces = data.provinces || [
            { name: '北京', count: 150 },
            { name: '上海', count: 120 },
            { name: '浙江', count: 95 },
            { name: '江苏', count: 88 },
            { name: '广东', count: 82 },
            { name: '四川', count: 75 },
            { name: '云南', count: 68 },
            { name: '山东', count: 62 }
        ];

        return new Chart(canvas, {
            type: 'bar',
            data: {
                labels: provinces.map(p => p.name),
                datasets: [{
                    label: '景点数量',
                    data: provinces.map(p => p.count),
                    backgroundColor: provinces.map((p, i) => 
                        `hsl(${240 - (i * 20)}, 70%, ${60 + (i * 5)}%)`
                    ),
                    borderRadius: 8
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    title: { display: true, text: '热门省份景点分布' }
                },
                scales: {
                    x: { beginAtZero: true }
                }
            }
        });
    }

    // 趋势图
    createTrendChart(canvas, data) {
        return new Chart(canvas, {
            type: 'line',
            data: {
                labels: data.months || ['1月', '2月', '3月', '4月', '5月', '6月'],
                datasets: [{
                    label: '访问量',
                    data: data.visits || [1200, 1900, 3000, 5000, 4200, 3800],
                    borderColor: this.colors.primary,
                    backgroundColor: 'transparent',
                    tension: 0.4,
                    pointRadius: 6,
                    pointBackgroundColor: this.colors.primary
                }, {
                    label: '搜索量',
                    data: data.searches || [800, 1200, 2100, 3500, 2900, 2600],
                    borderColor: this.colors.secondary,
                    backgroundColor: 'transparent',
                    tension: 0.4,
                    pointRadius: 6,
                    pointBackgroundColor: this.colors.secondary
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'top' },
                    title: { display: true, text: '月度趋势分析' }
                },
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });
    }

    // 热门景点图
    createPopularChart(canvas, data) {
        const destinations = data.destinations || [
            { name: '故宫', score: 98 },
            { name: '长城', score: 96 },
            { name: '西湖', score: 94 },
            { name: '兵马俑', score: 92 },
            { name: '黄山', score: 90 }
        ];

        return new Chart(canvas, {
            type: 'radar',
            data: {
                labels: destinations.map(d => d.name),
                datasets: [{
                    label: '热门指数',
                    data: destinations.map(d => d.score),
                    borderColor: this.colors.primary,
                    backgroundColor: this.colors.primary + '30',
                    pointBackgroundColor: this.colors.primary,
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: this.colors.primary
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    title: { display: true, text: '热门景点排行' }
                },
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 100
                    }
                }
            }
        });
    }

    // 默认图表
    createDefaultChart(canvas, data) {
        return new Chart(canvas, {
            type: 'bar',
            data: {
                labels: data.labels || ['数据1', '数据2', '数据3', '数据4', '数据5'],
                datasets: [{
                    label: '数值',
                    data: data.values || [10, 20, 30, 40, 50],
                    backgroundColor: this.colors.primary
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    }

    // 生成日期标签
    generateDateLabels(days) {
        const labels = [];
        for (let i = days - 1; i >= 0; i--) {
            const date = new Date();
            date.setDate(date.getDate() - i);
            labels.push(date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' }));
        }
        return labels;
    }

    // 生成随机数据
    generateRandomData(count, min, max) {
        return Array.from({ length: count }, () => 
            Math.floor(Math.random() * (max - min + 1)) + min
        );
    }

    // 获取模拟数据
    getMockData(chartType) {
        const mockData = {
            'rating-distribution': { distribution: [45, 30, 15, 7, 3] },
            'user-growth': {
                labels: this.generateDateLabels(30),
                new_users: this.generateRandomData(30, 5, 50),
                active_users: this.generateRandomData(30, 20, 100)
            },
            'category-distribution': {
                categories: ['自然景观', '历史古迹', '主题公园', '博物馆', '宗教场所'],
                counts: [120, 85, 45, 38, 25]
            },
            'province-map': {
                provinces: [
                    { name: '北京', count: 150 },
                    { name: '上海', count: 120 },
                    { name: '浙江', count: 95 },
                    { name: '江苏', count: 88 }
                ]
            },
            'monthly-trend': {
                months: ['1月', '2月', '3月', '4月', '5月', '6月'],
                visits: [1200, 1900, 3000, 5000, 4200, 3800],
                searches: [800, 1200, 2100, 3500, 2900, 2600]
            },
            'popular-destinations': {
                destinations: [
                    { name: '故宫', score: 98 },
                    { name: '长城', score: 96 },
                    { name: '西湖', score: 94 }
                ]
            }
        };
        return mockData[chartType] || {};
    }

    // 更新图表
    updateChart(containerId, newData) {
        const chart = this.charts[containerId];
        if (chart) {
            chart.data = newData;
            chart.update();
        }
    }

    // 销毁图表
    destroyChart(containerId) {
        const chart = this.charts[containerId];
        if (chart) {
            chart.destroy();
            delete this.charts[containerId];
        }
    }

    // 导出图表
    exportChart(containerId, format = 'png') {
        const chart = this.charts[containerId];
        if (chart) {
            const url = chart.toBase64Image();
            const a = document.createElement('a');
            a.href = url;
            a.download = `chart_${containerId}_${Date.now()}.${format}`;
            a.click();
        }
    }

    // 创建统计卡片
    createStatCard(container, data) {
        const statCard = document.createElement('div');
        statCard.className = 'stat-card';
        statCard.innerHTML = `
            <div class="stat-icon" style="background: ${data.color || this.colors.primary}">
                <i class="fas ${data.icon || 'fa-chart-line'}"></i>
            </div>
            <div class="stat-content">
                <h3 class="stat-number">${data.value || 0}</h3>
                <p class="stat-label">${data.label || '统计项'}</p>
                ${data.change ? `
                    <span class="stat-change ${data.change > 0 ? 'positive' : 'negative'}">
                        <i class="fas fa-arrow-${data.change > 0 ? 'up' : 'down'}"></i>
                        ${Math.abs(data.change)}%
                    </span>
                ` : ''}
            </div>
        `;
        container.appendChild(statCard);
    }

    // 创建进度条
    createProgressBar(container, data) {
        const progressBar = document.createElement('div');
        progressBar.className = 'progress-bar-container';
        progressBar.innerHTML = `
            <div class="progress-label">
                <span>${data.label}</span>
                <span>${data.value}%</span>
            </div>
            <div class="progress">
                <div class="progress-bar" style="width: ${data.value}%; background: ${data.color || this.colors.primary}"></div>
            </div>
        `;
        container.appendChild(progressBar);
    }
}

// 创建全局实例
const dataVisualizer = new DataVisualizer();

// 暴露到全局
window.DataVisualizer = DataVisualizer;
window.dataVisualizer = dataVisualizer;