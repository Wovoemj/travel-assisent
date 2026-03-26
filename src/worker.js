// Cloudflare Worker 入口文件 - 智能旅游助手
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    // 处理静态文件
    if (url.pathname.startsWith('/static/')) {
      return handleStaticFile(request, env);
    }
    
    // 处理API请求
    if (url.pathname.startsWith('/api/')) {
      return handleAPI(request, env);
    }
    
    // 处理页面请求
    return handlePage(request, env);
  }
};

// 处理静态文件
async function handleStaticFile(request, env) {
  const url = new URL(request.url);
  const path = url.pathname;
  
  // 从KV存储获取文件
  try {
    const asset = await env.ASSETS.get(path);
    if (asset) {
      const contentType = getContentType(path);
      return new Response(asset, {
        headers: { 
          'Content-Type': contentType,
          'Cache-Control': 'public, max-age=31536000'
        }
      });
    }
  } catch (error) {
    console.log('Static file error:', error);
  }
  
  return new Response('Not Found', { status: 404 });
}

// 处理API请求
async function handleAPI(request, env) {
  const url = new URL(request.url);
  const path = url.pathname;
  
  // 景点搜索API
  if (path === '/api/search') {
    const query = url.searchParams.get('q') || '';
    const results = await searchDestinations(query, env);
    return Response.json({ success: true, results });
  }
  
  // 景点详情API
  if (path.startsWith('/api/destinations/')) {
    const id = path.split('/').pop();
    const destination = await getDestinationById(id, env);
    return Response.json({ success: true, destination });
  }
  
  // 天气API
  if (path.startsWith('/api/weather/')) {
    const city = path.split('/').pop();
    const weather = await getWeather(city);
    return Response.json({ success: true, weather });
  }
  
  // 用户状态API
  if (path === '/api/user/status') {
    return Response.json({ logged_in: false });
  }
  
  // 随机背景图片API
  if (path === '/api/random-background') {
    const backgrounds = await getBackgroundImages(env);
    const randomBg = backgrounds[Math.floor(Math.random() * backgrounds.length)];
    return Response.json({ 
      success: true, 
      image: randomBg.url,
      name: randomBg.name,
      location: randomBg.location
    });
  }
  
  // 搜索建议API
  if (path === '/api/search/suggestions') {
    const query = url.searchParams.get('q') || '';
    const suggestions = await getSearchSuggestions(query, env);
    return Response.json({ success: true, suggestions });
  }
  
  // 热门推荐API
  if (path === '/api/recommendations/hot') {
    const recommendations = await getHotRecommendations(env);
    return Response.json({ 
      success: true, 
      destinations: recommendations,
      count: recommendations.length
    });
  }
  
  // 其他API...
  return Response.json({ error: 'API not found' }, { status: 404 });
}

// 处理页面请求
async function handlePage(request, env) {
  const html = await getMainPage(env);
  return new Response(html, {
    headers: { 
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'public, max-age=3600'
    }
  });
}

// 搜索景点
async function searchDestinations(query, env) {
  try {
    const data = await env.DESTINATIONS.get('all', 'json') || [];
    
    if (!query) {
      return data.slice(0, 20);
    }
    
    const lowerQuery = query.toLowerCase();
    return data.filter(dest => 
      (dest.name && dest.name.toLowerCase().includes(lowerQuery)) || 
      (dest.city && dest.city.toLowerCase().includes(lowerQuery)) ||
      (dest.description && dest.description.toLowerCase().includes(lowerQuery)) ||
      (dest.province && dest.province.toLowerCase().includes(lowerQuery))
    ).slice(0, 20);
  } catch (error) {
    console.log('Search error:', error);
    return [];
  }
}

// 根据ID获取景点
async function getDestinationById(id, env) {
  try {
    const data = await env.DESTINATIONS.get('all', 'json') || [];
    return data.find(dest => dest.id == id) || null;
  } catch (error) {
    console.log('Get destination error:', error);
    return null;
  }
}

// 获取天气
async function getWeather(city) {
  // 模拟天气数据
  const conditions = ['晴', '多云', '阴', '小雨'];
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
async function getBackgroundImages(env) {
  return [
    { url: '/static/images/bg1.jpg', name: '风景', location: '未知' },
    { url: '/static/images/bg2.jpg', name: '山水', location: '未知' },
    { url: '/static/images/bg3.jpg', name: '古镇', location: '未知' }
  ];
}

// 获取搜索建议
async function getSearchSuggestions(query, env) {
  if (!query || query.length < 1) {
    return [];
  }
  
  try {
    const data = await env.DESTINATIONS.get('all', 'json') || [];
    const lowerQuery = query.toLowerCase();
    
    // 获取匹配的景点名称
    const suggestions = data
      .filter(dest => dest.name && dest.name.toLowerCase().includes(lowerQuery))
      .slice(0, 10)
      .map(dest => ({
        type: 'destination',
        id: dest.id,
        name: dest.name,
        city: dest.city,
        province: dest.province,
        category: dest.category,
        rating: dest.rating,
        cover_image: dest.cover_image
      }));
    
    return suggestions;
  } catch (error) {
    console.log('Suggestions error:', error);
    return [];
  }
}

// 获取热门推荐
async function getHotRecommendations(env) {
  try {
    const data = await env.DESTINATIONS.get('all', 'json') || [];
    return data
      .sort((a, b) => (b.popularity_score || 0) - (a.popularity_score || 0))
      .slice(0, 10);
  } catch (error) {
    console.log('Hot recommendations error:', error);
    return [];
  }
}

// 获取主页面
async function getMainPage(env) {
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>智能旅游助手 - 发现中国最美风景</title>
    <meta name="description" content="您的智能旅行伙伴，帮助您发现中国最美的风景">
    <link rel="stylesheet" href="/static/css/style.css">
    <style>
        /* 内联关键CSS */
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #333; }
        header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1rem; text-align: center; }
        .hero { padding: 4rem 1rem; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .hero h1 { font-size: 2.5rem; margin-bottom: 1rem; }
        .search-box { display: flex; justify-content: center; gap: 0.5rem; margin-top: 2rem; flex-wrap: wrap; }
        .search-box input { padding: 1rem; font-size: 1rem; border: none; border-radius: 25px; width: 300px; max-width: 90%; }
        .search-box button { padding: 1rem 2rem; font-size: 1rem; background: #ff6b6b; color: white; border: none; border-radius: 25px; cursor: pointer; }
        .features { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; padding: 2rem; }
        .feature { text-align: center; padding: 1.5rem; border: 1px solid #eee; border-radius: 10px; }
        .feature i { font-size: 2rem; margin-bottom: 0.5rem; display: block; }
        .destinations { padding: 2rem; }
        .dest-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 1rem; }
        .dest-card { background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); cursor: pointer; transition: transform 0.3s; }
        .dest-card:hover { transform: translateY(-5px); }
        .dest-card img { width: 100%; height: 150px; object-fit: cover; }
        .dest-info { padding: 1rem; }
        footer { text-align: center; padding: 2rem; background: #f5f5f5; }
    </style>
</head>
<body>
    <header>
        <h1>🎯 智能旅游助手</h1>
        <p>您的智能旅行伙伴</p>
    </header>
    
    <section class="hero">
        <h1>发现中国最美风景</h1>
        <p>让AI为您规划完美旅程</p>
        <div class="search-box">
            <input type="text" id="searchInput" placeholder="搜索景点、城市或类型..." onkeypress="handleKeyPress(event)">
            <button onclick="search()">🔍 搜索</button>
        </div>
    </section>
    
    <section class="features">
        <div class="feature">
            <i>🔍</i>
            <h3>智能搜索</h3>
            <p>快速找到心仪景点</p>
        </div>
        <div class="feature">
            <i>🌤️</i>
            <h3>天气查询</h3>
            <p>实时天气信息</p>
        </div>
        <div class="feature">
            <i>🗺️</i>
            <h3>行程规划</h3>
            <p>AI智能推荐</p>
        </div>
        <div class="feature">
            <i>🍜</i>
            <h3>美食推荐</h3>
            <p>当地特色美食</p>
        </div>
    </section>
    
    <section class="destinations">
        <h2 style="text-align: center; margin-bottom: 2rem;">🔥 热门景点</h2>
        <div id="destinations" class="dest-grid">
            <div style="text-align: center; grid-column: 1/-1; padding: 2rem;">
                <p>正在加载热门景点...</p>
            </div>
        </div>
    </section>
    
    <footer>
        <p>© 2024 智能旅游助手 - 发现中国最美风景</p>
        <p>Powered by Cloudflare Workers</p>
    </footer>
    
    <script>
        // 搜索功能
        function search() {
            const query = document.getElementById('searchInput').value;
            if (!query) {
                alert('请输入搜索关键词');
                return;
            }
            window.location.href = '/?q=' + encodeURIComponent(query);
        }
        
        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                search();
            }
        }
        
        // 加载热门景点
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
                            <p>\${dest.city || ''} · \${dest.category || ''}</p>
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

// 获取内容类型
function getContentType(path) {
  const ext = path.split('.').pop().toLowerCase();
  const types = {
    'html': 'text/html',
    'css': 'text/css',
    'js': 'application/javascript',
    'json': 'application/json',
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'gif': 'image/gif',
    'svg': 'image/svg+xml',
    'webp': 'image/webp',
    'ico': 'image/x-icon'
  };
  return types[ext] || 'application/octet-stream';
}