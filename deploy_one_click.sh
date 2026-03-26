#!/bin/bash

# 智能旅游助手 - 一键部署到Cloudflare Workers
# 使用方法: chmod +x deploy_one_click.sh && ./deploy_one_click.sh

set -e  # 遇到错误立即停止

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查依赖
check_dependencies() {
    log_info "检查依赖环境..."
    
    # 检查Node.js
    if ! command -v node &> /dev/null; then
        log_error "Node.js未安装，请先安装Node.js"
        log_info "访问 https://nodejs.org/ 下载安装"
        exit 1
    fi
    
    # 检查npm
    if ! command -v npm &> /dev/null; then
        log_error "npm未安装"
        exit 1
    fi
    
    log_success "依赖检查完成"
}

# 安装Wrangler CLI
install_wrangler() {
    log_info "检查Wrangler CLI..."
    
    if ! command -v wrangler &> /dev/null; then
        log_info "正在安装Wrangler CLI..."
        npm install -g wrangler
        
        if [ $? -eq 0 ]; then
            log_success "Wrangler CLI安装成功"
        else
            log_error "Wrangler CLI安装失败"
            exit 1
        fi
    else
        log_success "Wrangler CLI已安装"
    fi
}

# 登录Cloudflare
login_cloudflare() {
    log_info "检查Cloudflare登录状态..."
    
    # 检查是否已登录
    if wrangler whoami &> /dev/null; then
        log_success "已登录Cloudflare账号"
        wrangler whoami
    else
        log_info "正在登录Cloudflare..."
        log_warning "请在浏览器中完成授权"
        wrangler login
        
        if [ $? -eq 0 ]; then
            log_success "Cloudflare登录成功"
        else
            log_error "Cloudflare登录失败"
            exit 1
        fi
    fi
}

# 创建项目结构
create_project_structure() {
    log_info "创建项目结构..."
    
    # 创建目录
    mkdir -p src
    mkdir -p static/css
    mkdir -p static/js
    mkdir -p static/images
    
    # 检查必要文件
    if [ ! -f "src/worker.js" ]; then
        log_error "Worker文件不存在: src/worker.js"
        exit 1
    fi
    
    if [ ! -f "wrangler.toml" ]; then
        log_error "配置文件不存在: wrangler.toml"
        exit 1
    fi
    
    log_success "项目结构检查完成"
}

# 创建KV存储
create_kv_namespaces() {
    log_info "创建KV存储命名空间..."
    
    # 创建景点数据存储
    log_info "创建景点数据存储..."
    DESTINATIONS_KV=$(wrangler kv namespace create DESTINATIONS 2>&1 | grep -oP 'id = "\K[^"]+' || echo "")
    
    if [ -z "$DESTINATIONS_KV" ]; then
        log_warning "景点数据存储创建失败，尝试获取现有命名空间..."
        DESTINATIONS_KV=$(wrangler kv namespace list 2>&1 | grep "DESTINATIONS" | awk '{print $1}' || echo "")
    fi
    
    # 创建资源存储
    log_info "创建资源存储..."
    ASSETS_KV=$(wrangler kv namespace create ASSETS 2>&1 | grep -oP 'id = "\K[^"]+' || echo "")
    
    if [ -z "$ASSETS_KV" ]; then
        log_warning "资源存储创建失败，尝试获取现有命名空间..."
        ASSETS_KV=$(wrangler kv namespace list 2>&1 | grep "ASSETS" | awk '{print $1}' || echo "")
    fi
    
    # 更新配置文件
    if [ ! -z "$DESTINATIONS_KV" ]; then
        log_success "景点数据存储ID: $DESTINATIONS_KV"
        # 更新wrangler.toml中的ID
        sed -i "s/travel-destinations-kv/$DESTINATIONS_KV/g" wrangler.toml
    fi
    
    if [ ! -z "$ASSETS_KV" ]; then
        log_success "资源存储ID: $ASSETS_KV"
        # 更新wrangler.toml中的ID
        sed -i "s/travel-assets-kv/$ASSETS_KV/g" wrangler.toml
    fi
    
    log_success "KV存储创建完成"
}

# 上传数据到KV存储
upload_data() {
    log_info "上传景点数据到KV存储..."
    
    if [ -f "destinations.json" ]; then
        wrangler kv key put --binding DESTINATIONS "all" --path destinations.json
        if [ $? -eq 0 ]; then
            log_success "景点数据上传成功"
        else
            log_error "景点数据上传失败"
            exit 1
        fi
    else
        log_error "景点数据文件不存在: destinations.json"
        exit 1
    fi
    
    log_info "上传静态资源到KV存储..."
    
    # 上传CSS文件
    if [ -f "static/css/style.css" ]; then
        wrangler kv key put --binding ASSETS "static/css/style.css" --path static/css/style.css
        log_success "CSS文件上传成功"
    fi
    
    # 上传JavaScript文件
    if [ -f "static/js/app.js" ]; then
        wrangler kv key put --binding ASSETS "static/js/app.js" --path static/js/app.js
        log_success "JavaScript文件上传成功"
    fi
    
    log_success "数据上传完成"
}

# 部署到Cloudflare Workers
deploy_worker() {
    log_info "部署到Cloudflare Workers..."
    
    wrangler deploy
    
    if [ $? -eq 0 ]; then
        log_success "部署成功！"
        
        # 获取访问地址
        log_info "获取访问地址..."
        WORKER_URL=$(wrangler deployments list 2>&1 | grep -oP 'https://[^\s]+' | head -1 || echo "")
        
        if [ ! -z "$WORKER_URL" ]; then
            log_success "访问地址: $WORKER_URL"
        else
            log_warning "请在Cloudflare Dashboard中查看访问地址"
        fi
    else
        log_error "部署失败"
        exit 1
    fi
}

# 测试部署
test_deployment() {
    log_info "测试部署..."
    
    # 获取Worker URL
    WORKER_URL=$(wrangler deployments list 2>&1 | grep -oP 'https://[^\s]+' | head -1 || echo "")
    
    if [ ! -z "$WORKER_URL" ]; then
        log_info "测试访问: $WORKER_URL"
        
        # 测试主页
        if curl -s "$WORKER_URL" &> /dev/null; then
            log_success "主页访问正常"
        else
            log_warning "主页访问异常，请检查部署"
        fi
        
        # 测试API
        if curl -s "$WORKER_URL/api/search" &> /dev/null; then
            log_success "API接口正常"
        else
            log_warning "API接口异常，请检查配置"
        fi
    else
        log_warning "无法获取访问地址，请手动检查"
    fi
}

# 显示部署结果
show_results() {
    echo ""
    echo "=========================================="
    echo "🎉 部署完成！"
    echo "=========================================="
    echo ""
    
    # 获取访问地址
    WORKER_URL=$(wrangler deployments list 2>&1 | grep -oP 'https://[^\s]+' | head -1 || echo "")
    
    if [ ! -z "$WORKER_URL" ]; then
        echo "📱 访问地址: $WORKER_URL"
        echo ""
        echo "🌐 功能测试:"
        echo "   主页: $WORKER_URL"
        echo "   搜索: $WORKER_URL/?q=故宫"
        echo "   API: $WORKER_URL/api/search"
        echo ""
    fi
    
    echo "✅ 主要功能:"
    echo "   • 景点搜索和详情"
    echo "   • 天气查询"
    echo "   • 行程规划"
    echo "   • 美食推荐"
    echo "   • 全球CDN加速"
    echo ""
    echo "💰 费用: 完全免费"
    echo "🌍 访问: 全球任何网络"
    echo "⏰ 可用性: 24/7"
    echo ""
    echo "=========================================="
}

# 主函数
main() {
    echo "🚀 智能旅游助手 - 一键部署到Cloudflare Workers"
    echo "=================================================="
    echo ""
    
    # 执行部署步骤
    check_dependencies
    install_wrangler
    login_cloudflare
    create_project_structure
    create_kv_namespaces
    upload_data
    deploy_worker
    test_deployment
    show_results
    
    log_success "部署完成！"
}

# 执行主函数
main "$@"