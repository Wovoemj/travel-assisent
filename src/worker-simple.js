// Cloudflare Worker 简化版 - 无需KV存储
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    // 处理API请求
    if (url.pathname.startsWith('/api/')) {
      return handleAPI(request, env);
    }
    
    // 处理页面请求
    return handlePage(request, env);
  }
};

// 处理API请求
async function handleAPI(request, env) {
  const url = new URL(request.url);
  const path = url.pathname;
  
  // 设置CORS头
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
  
  // 处理OPTIONS请求
  if (request.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }
  
  // 景点搜索API
  if (path === '/api/search') {
    const query = url.searchParams.get('q') || '';
    const results = searchDestinations(query);
    return Response.json({ success: true, results }, { headers: corsHeaders });
  }
  
  // 景点详情API
  if (path.startsWith('/api/destinations/')) {
    const id = path.split('/').pop();
    const destination = getDestinationById(id);
    return Response.json({ success: true, destination }, { headers: corsHeaders });
  }
  
  // 天气API
  if (path.startsWith('/api/weather/')) {
    const city = path.split('/').pop();
    const weather = getWeather(city);
    return Response.json({ success: true, weather }, { headers: corsHeaders });
  }
  
  // 用户状态API
  if (path === '/api/user/status') {
    return Response.json({ logged_in: false }, { headers: corsHeaders });
  }
  
  // 随机背景图片API
  if (path === '/api/random-background') {
    const backgrounds = getBackgroundImages();
    const randomBg = backgrounds[Math.floor(Math.random() * backgrounds.length)];
    return Response.json({ 
      success: true, 
      image: randomBg.url,
      name: randomBg.name,
      location: randomBg.location
    }, { headers: corsHeaders });
  }
  
  // 热门推荐API
  if (path === '/api/recommendations/hot') {
    const recommendations = getHotRecommendations();
    return Response.json({ 
      success: true, 
      destinations: recommendations,
      count: recommendations.length
    }, { headers: corsHeaders });
  }
  
  return Response.json({ error: 'API not found' }, { status: 404, headers: corsHeaders });
}

// 处理页面请求
async function handlePage(request, env) {
  const html = getMainPage();
  return new Response(html, {
    headers: { 
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'public, max-age=3600'
    }
  });
}

// 内置景点数据
function getBuiltInDestinations() {
  return [
    {
      id: 1,
      name: "故宫博物院",
      city: "北京",
      province: "北京",
      category: "历史古迹",
      description: "故宫博物院是中国最大的古代文化艺术博物馆，位于北京故宫紫禁城内",
      price_range: "60元",
      rating: 4.9,
      address: "北京市东城区景山前街4号",
      opening_hours: "08:30-17:00",
      popularity_score: 99,
      cover_image: "/static/images/故宫博物院.jpg"
    },
    {
      id: 2,
      name: "八达岭长城",
      city: "北京",
      province: "北京",
      category: "历史古迹",
      description: "八达岭长城是明长城中保存最好的一段，也是最具代表性的一段",
      price_range: "40元",
      rating: 4.8,
      address: "北京市延庆区八达岭镇",
      opening_hours: "06:30-19:00",
      popularity_score: 98,
      cover_image: "/static/images/八达岭长城.jpg"
    },
    {
      id: 3,
      name: "西湖",
      city: "杭州",
      province: "浙江",
      category: "自然风光",
      description: "西湖是中国著名的风景名胜区，以湖光山色和众多的名胜古迹闻名",
      price_range: "免费",
      rating: 4.9,
      address: "浙江省杭州市西湖区",
      opening_hours: "全天开放",
      popularity_score: 97,
      cover_image: "/static/images/西湖.jpg"
    },
    {
      id: 4,
      name: "黄山",
      city: "黄山市",
      province: "安徽",
      category: "自然风光",
      description: "黄山以奇松、怪石、云海、温泉、冬雪五绝著称于世",
      price_range: "190元",
      rating: 4.8,
      address: "安徽省黄山市黄山区",
      opening_hours: "06:00-17:00",
      popularity_score: 96,
      cover_image: "/static/images/黄山.jpg"
    },
    {
      id: 5,
      name: "张家界",
      city: "张家界市",
      province: "湖南",
      category: "自然风光",
      description: "张家界国家森林公园是中国第一个国家森林公园，以奇特的砂岩峰林地貌著称",
      price_range: "245元",
      rating: 4.7,
      address: "湖南省张家界市武陵源区",
      opening_hours: "07:00-18:00",
      popularity_score: 95,
      cover_image: "/static/images/张家界.jpg"
    }
  ];
}

// 搜索景点
function searchDestinations(query) {
  const destinations = getBuiltInDestinations();
  
  if (!query) {
    return destinations.slice(0, 20);
  }
  
  const lowerQuery = query.toLowerCase();
  return destinations.filter(dest => 
    dest.name.toLowerCase().includes(lowerQuery) || 
    dest.city.toLowerCase().includes(lowerQuery) ||
    dest.description.toLowerCase().includes(lowerQuery) ||
    dest.province.toLowerCase().includes(lowerQuery)
  ).slice(0, 20);
}

// 根据ID获取景点
function getDestinationById(id) {
  const destinations = getBuiltInDestinations();
  return destinations.find(dest => dest.id == parseInt(id)) || null;
}

// 获取天气
function getWeather(city) {
  const conditions = ['晴', '多云', '阴', '小雨', '阵雨'];
  return {
    city: city,
    temperature: `${Math.floor(Math.random() * 15 + 15)}°C`,
    condition: conditions[Math.floor(Math.random() * conditions.length)],
    humidity: `${Math.floor(Math.random() * 40 + 40)}%`,
    wind_speed: `${Math.floor(Math.random() * 10 + 5)} km/h`,
    source: '本地数据'
  };
}

// 获取背景图片
function getBackgroundImages() {
  return [
    { url: '/static/images/bg1.jpg', name: '风景', location: '未知' },
    { url: '/static/images/bg2.jpg', name: '山水', location: '未知' },
    { url: '/static/images/bg3.jpg', name: '古镇', location: '未知' }
  ];
}

// 获取热门推荐
function getHotRecommendations() {
  const destinations = getBuiltInDestinations();
  return destinations
    .sort((a, b) => (b.popularity_score || 0) - (a.popularity_score || 0))
    .slice(0, 10);
}

// 获取主页面
function getMainPage() {
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>智能旅游助手 - 发现中国最美风景</title>
    <meta name="description" content="您的智能旅行伙伴，帮助您发现中国最美的风景">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
            line-height: 1.6; 
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 0 20px; }
        
        /* 头部 */
        header {
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(10px);
            box-shadow: 0 2px 20px rgba(0,0,0,0.1);
            position: fixed;
            width: 100%;
            top: 0;
            z-index: 1000;
        }
        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 0;
        }
        .logo { 
            font-size: 1.5rem; 
            font-weight: bold; 
            color: #667eea;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        /* 主内容 */
        main { padding-top: 100px; }
        
        /* 英雄区域 */
        .hero {
            text-align: center;
            padding: 4rem 1rem;
            color: white;
        }
        .hero h1 {
            font-size: 3rem;
            margin-bottom: 1rem;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .hero p {
            font-size: 1.2rem;
            margin-bottom: 2rem;
            opacity: 0.9;
        }
        
        /* 搜索框 */
        .search-box {
            background: white;
            border-radius: 50px;
            padding: 1rem;
            display: flex;
            gap: 1rem;
            max-width: 600px;
            margin: 0 auto;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .search-box input {
            flex: 1;
            border: none;
            outline: none;
            font-size: 1rem;
            padding: 0.5rem;
        }
        .search-box button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 0.8rem 1.5rem;
            border-radius: 25px;
            cursor: pointer;
            font-weight: bold;
            transition: transform 0.3s;
        }
        .search-box button:hover {
            transform: scale(1.05);
        }
        
        /* 功能区域 */
        .features {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            padding: 3rem 0;
        }
        .feature {
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 2rem;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: transform 0.3s;
        }
        .feature:hover {
            transform: translateY(-5px);
        }
        .feature-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
        }
        .feature h3 {
            margin-bottom: 0.5rem;
            color: #333;
        }
        .feature p {
            color: #666;
            font-size: 0.9rem;
        }
        
        /* 景点区域 */
        .destinations {
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 2rem;
            margin: 2rem 0;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        .destinations h2 {
            text-align: center;
            margin-bottom: 2rem;
            color: #333;
        }
        .dest-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 1.5rem;
        }
        .dest-card {
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            cursor: pointer;
            transition: transform 0.3s;
        }
        .dest-card:hover {
            transform: translateY(-5px);
        }
        .dest-card img {
            width: 100%;
            height: 200px;
            object-fit: cover;
        }
        .dest-info {
            padding: 1.5rem;
        }
        .dest-info h4 {
            margin-bottom: 0.5rem;
            color: #333;
        }
        .dest-info p {
            color: #666;
            font-size: 0.9rem;
            margin-bottom: 0.3rem;
        }
        
        /* 底部 */
        footer {
            text-align: center;
            padding: 2rem;
            color: white;
            opacity: 0.8;
        }
        
        /* 响应式 */
        @media (max-width: 768px) {
            .hero h1 { font-size: 2rem; }
            .search-box { flex-direction: column; }
            .features { grid-template-columns: 1fr; }
            .dest-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <div class="header-content">
                <div class="logo">🎯 智能旅游助手</div>
            </div>
        </div>
    </header>
    
    <main>
        <div class="container">
            <section class="hero">
                <h1>发现中国最美风景</h1>
                <p>让AI为您规划完美旅程</p>
                <div class="search-box">
                    <input type="text" id="searchInput" placeholder="搜索景点、城市或类型..." onkeypress="handleKeyPress(event)">
                    <button onclick="performSearch()">🔍 搜索</button>
                </div>
            </section>
            
            <section class="features">
                <div class="feature">
                    <div class="feature-icon">🔍</div>
                    <h3>智能搜索</h3>
                    <p>快速找到心仪景点</p>
                </div>
                <div class="feature">
                    <div class="feature-icon">🌤️</div>
                    <h3>天气查询</h3>
                    <p>实时天气信息</p>
                </div>
                <div class="feature">
                    <div class="feature-icon">🗺️</div>
                    <h3>行程规划</h3>
                    <p>AI智能推荐</p>
                </div>
                <div class="feature">
                    <div class="feature-icon">🍜</div>
                    <h3>美食推荐</h3>
                    <p>当地特色美食</p>
                </div>
            </section>
            
            <section class="destinations">
                <h2>🔥 热门景点</h2>
                <div id="destinations" class="dest-grid">
                    <div style="text-align: center; grid-column: 1/-1; padding: 2rem;">
                        <p>正在加载热门景点...</p>
                    </div>
                </div>
            </section>
        </div>
    </main>
    
    <footer>
        <div class="container">
            <p>© 2024 智能旅游助手 - 发现中国最美风景</p>
            <p>Powered by Cloudflare Workers</p>
        </div>
    </footer>
    
    <script>
        // 搜索功能
        function performSearch() {
            const query = document.getElementById('searchInput').value;
            if (!query) {
                alert('请输入搜索关键词');
                return;
            }
            window.location.href = '/?q=' + encodeURIComponent(query);
        }
        
        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                performSearch();
            }
        }
        
        // 加载景点
        async function loadDestinations() {
            try {
                const urlParams = new URLSearchParams(window.location.search);
                const query = urlParams.get('q');
                
                const apiUrl = query ? '/api/search?q=' + encodeURIComponent(query) : '/api/recommendations/hot';
                const response = await fetch(apiUrl);
                const data = await response.json();
                
                const container = document.getElementById('destinations');
                if (!container) return;
                
                const destinations = data.results || data.destinations || [];
                
                if (destinations.length === 0) {
                    container.innerHTML = '<div style="text-align: center; grid-column: 1/-1; padding: 2rem;"><p>暂无景点数据</p></div>';
                    return;
                }
                
                container.innerHTML = '';
                destinations.forEach(dest => {
                    const card = document.createElement('div');
                    card.className = 'dest-card';
                    card.innerHTML = \`
                        <img src="\${dest.cover_image || '/static/images/placeholder.jpg'}" 
                             alt="\${dest.name}" 
                             onerror="this.src='/static/images/placeholder.jpg'">
                        <div class="dest-info">
                            <h4>\${dest.name}</h4>
                            <p>📍 \${dest.city || ''} · \${dest.category || ''}</p>
                            <p>⭐ \${dest.rating || 0}分</p>
                        </div>
                    \`;
                    card.onclick = () => alert('景点详情: ' + dest.name);
                    container.appendChild(card);
                });
            } catch (error) {
                console.error('加载失败:', error);
                const container = document.getElementById('destinations');
                if (container) {
                    container.innerHTML = '<div style="text-align: center; grid-column: 1/-1; padding: 2rem;"><p>加载失败，请稍后重试</p></div>';
                }
            }
        }
        
        // 页面加载时执行
        document.addEventListener('DOMContentLoaded', loadDestinations);
    </script>
</body>
</html>`;
}