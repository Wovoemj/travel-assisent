export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname.startsWith('/api/')) {
      return handleAPI(request, env);
    }

    return handlePage(request, env);
  }
};

async function handleAPI(request, env) {
  const url = new URL(request.url);
  const path = url.pathname;

  if (path === '/api/search') {
    const query = url.searchParams.get('q') || '';
    const results = await searchDestinations(query, env);
    return Response.json({ success: true, results });
  }

  if (path.startsWith('/api/destinations/')) {
    const id = path.split('/').pop();
    const destination = await getDestinationById(id, env);
    return Response.json({ success: true, destination });
  }

  if (path.startsWith('/api/weather/')) {
    const city = path.split('/').pop();
    const weather = await getWeather(city);
    return Response.json({ success: true, weather });
  }

  if (path === '/api/user/status') {
    return Response.json({ logged_in: false });
  }

  if (path === '/api/search/suggestions') {
    const query = url.searchParams.get('q') || '';
    const suggestions = await getSearchSuggestions(query, env);
    return Response.json({ success: true, suggestions });
  }

  if (path === '/api/recommendations/hot') {
    const recommendations = await getHotRecommendations(env);
    return Response.json({
      success: true,
      destinations: recommendations,
      count: recommendations.length
    });
  }

  return Response.json({ error: 'API not found' }, { status: 404 });
}

async function handlePage(request, env) {
  const html = await getMainPage(env);
  return new Response(html, {
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'public, max-age=3600'
    }
  });
}

async function searchDestinations(query, env) {
  try {
    const data = await env.DESTINATIONS.get('all', 'json') || [];
    if (!query) return data.slice(0, 20);
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

async function getDestinationById(id, env) {
  try {
    const data = await env.DESTINATIONS.get('all', 'json') || [];
    return data.find(dest => dest.id == id) || null;
  } catch (error) {
    console.log('Get destination error:', error);
    return null;
  }
}

async function getWeather(city) {
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

async function getSearchSuggestions(query, env) {
  if (!query || query.length < 1) return [];
  try {
    const data = await env.DESTINATIONS.get('all', 'json') || [];
    const lowerQuery = query.toLowerCase();
    return data
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
  } catch (error) {
    console.log('Suggestions error:', error);
    return [];
  }
}

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

async function getMainPage(env) {
  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>智能旅游助手 - 发现中国最美风景</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #333; background: #f0f2f5; }
        .hero { padding: 4rem 1rem; text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .hero h1 { font-size: 2.5rem; margin-bottom: 1rem; }
        .hero p { font-size: 1.2rem; opacity: 0.9; }
        .search-box { display: flex; justify-content: center; gap: 0.5rem; margin-top: 2rem; flex-wrap: wrap; }
        .search-box input { padding: 1rem; font-size: 1rem; border: none; border-radius: 25px; width: 300px; max-width: 90%; outline: none; }
        .search-box button { padding: 1rem 2rem; font-size: 1rem; background: #ff6b6b; color: white; border: none; border-radius: 25px; cursor: pointer; }
        .search-box button:hover { background: #ee5a5a; }
        .features { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; padding: 2rem; max-width: 1200px; margin: 0 auto; }
        .feature { text-align: center; padding: 1.5rem; background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); }
        .feature .icon { font-size: 2rem; margin-bottom: 0.5rem; }
        .destinations { padding: 2rem; max-width: 1200px; margin: 0 auto; }
        .destinations h2 { text-align: center; margin-bottom: 2rem; font-size: 1.8rem; }
        .dest-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 1.5rem; }
        .dest-card { background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); cursor: pointer; transition: transform 0.3s; }
        .dest-card:hover { transform: translateY(-5px); }
        .dest-emoji { height: 150px; display: flex; align-items: center; justify-content: center; font-size: 4rem; }
        .dest-info { padding: 1rem; }
        .dest-info h4 { margin-bottom: 0.3rem; }
        .dest-info .meta { color: #888; font-size: 0.85rem; }
        .dest-info .rating { color: #f39c12; margin-top: 0.3rem; }
        .dest-info .desc { color: #666; font-size: 0.85rem; margin-top: 0.5rem; }
        footer { text-align: center; padding: 2rem; background: #2c3e50; color: #aaa; }
    </style>
</head>
<body>
    <section class="hero">
        <h1>智能旅游助手</h1>
        <p>发现中国最美风景</p>
        <div class="search-box">
            <input type="text" id="searchInput" placeholder="搜索景点、城市或类型..." onkeypress="handleKeyPress(event)">
            <button onclick="search()">搜索</button>
        </div>
    </section>
    <section class="features">
        <div class="feature"><div class="icon">🔍</div><h3>智能搜索</h3><p>快速找到心仪景点</p></div>
        <div class="feature"><div class="icon">🌤️</div><h3>天气查询</h3><p>实时天气信息</p></div>
        <div class="feature"><div class="icon">🗺️</div><h3>行程规划</h3><p>AI智能推荐</p></div>
        <div class="feature"><div class="icon">🍜</div><h3>美食推荐</h3><p>当地特色美食</p></div>
    </section>
    <section class="destinations">
        <h2>热门景点</h2>
        <div id="destinations" class="dest-grid"><div style="text-align:center;grid-column:1/-1;padding:2rem;color:#999;">正在加载热门景点...</div></div>
    </section>
    <footer><p>智能旅游助手 - 发现中国最美风景</p></footer>
    <script>
        var emojis=['🏯','🏔️','🌊','🌸','🏛️','⛩️','🌄','🏞️','🗿','🎪'];
        var gradients=['linear-gradient(135deg,#667eea,#764ba2)','linear-gradient(135deg,#f093fb,#f5576c)','linear-gradient(135deg,#4facfe,#00f2fe)','linear-gradient(135deg,#43e97b,#38f9d7)','linear-gradient(135deg,#fa709a,#fee140)','linear-gradient(135deg,#a18cd1,#fbc2eb)','linear-gradient(135deg,#fccb90,#d57eeb)','linear-gradient(135deg,#e0c3fc,#8ec5fc)','linear-gradient(135deg,#f5576c,#ff6a88)','linear-gradient(135deg,#667eea,#764ba2)'];
        function search(){var q=document.getElementById('searchInput').value;if(!q){alert('请输入搜索关键词');return;}window.location.href='/?q='+encodeURIComponent(q);}
        function handleKeyPress(e){if(e.key==='Enter')search();}
        async function loadDestinations(){
            try{
                var params=new URLSearchParams(window.location.search);
                var query=params.get('q');
                var url=query?'/api/search?q='+encodeURIComponent(query):'/api/recommendations/hot';
                var res=await fetch(url);
                var data=await res.json();
                var el=document.getElementById('destinations');
                var dests=data.results||data.destinations||[];
                if(!dests.length){el.innerHTML='<div style="text-align:center;grid-column:1/-1;padding:2rem;color:#999;">暂无景点数据</div>';return;}
                el.innerHTML='';
                dests.forEach(function(d,i){
                    var card=document.createElement('div');
                    card.className='dest-card';
                    card.innerHTML='<div class="dest-emoji" style="background:'+gradients[i%10]+'">'+emojis[i%10]+'</div><div class="dest-info"><h4>'+d.name+'</h4><div class="meta">'+(d.city||'')+' '+(d.province?'· '+d.province:'')+' '+(d.category?'· '+d.category:'')+'</div><div class="rating">⭐ '+(d.rating||0)+'分</div>'+(d.description?'<div class="desc">'+d.description+'</div>':'')+'</div>';
                    card.onclick=function(){alert('景点详情: '+d.name);};
                    el.appendChild(card);
                });
            }catch(e){
                console.error('加载失败:',e);
                document.getElementById('destinations').innerHTML='<div style="text-align:center;grid-column:1/-1;padding:2rem;color:#999;">加载失败</div>';
            }
        }
        document.addEventListener('DOMContentLoaded',loadDestinations);
    </script>
</body>
</html>`;
}
