// AI助手管理器
class AIAssistantManager {
    constructor() {
        this.currentProvider = 'openai';
        this.conversationHistory = [];
        this.isTyping = false;
        this.providers = {
            'openai': { name: 'OpenAI GPT', model: 'gpt-3.5-turbo', endpoint: '/api/ai/openai/chat' },
            'claude': { name: 'Anthropic Claude', model: 'claude-3-sonnet', endpoint: '/api/ai/claude/chat' },
            'wenxin': { name: '百度文心一言', model: 'ERNIE-Bot', endpoint: '/api/ai/wenxin/chat' },
            'tongyi': { name: '阿里通义千问', model: 'qwen-turbo', endpoint: '/api/ai/tongyi/chat' },
            'zhipu': { name: '智谱ChatGLM', model: 'glm-4', endpoint: '/api/ai/zhipu/chat' }
        };
        this.init();
    }

    init() {
        this.loadConversationHistory();
        this.setupEventListeners();
        this.initVoiceInput();
        console.log('✅ AI助手管理器已初始化');
    }

    setupEventListeners() {
        document.addEventListener('click', (e) => {
            if (e.target.closest('.ai-send-btn')) this.sendMessage();
            if (e.target.closest('.ai-voice-btn')) this.startVoiceInput();
            if (e.target.closest('.ai-clear-btn')) this.clearConversation();
            if (e.target.closest('.ai-provider-option')) {
                const provider = e.target.closest('.ai-provider-option').dataset.provider;
                this.switchProvider(provider);
            }
            if (e.target.closest('.ai-export-btn')) this.exportConversation();
        });

        document.addEventListener('keydown', (e) => {
            if (e.target.classList.contains('ai-input') && e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        document.addEventListener('input', (e) => {
            if (e.target.classList.contains('ai-input')) {
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
            }
        });
    }

    initVoiceInput() {
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = false;
            this.recognition.interimResults = false;
            this.recognition.lang = 'zh-CN';

            this.recognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                document.querySelector('.ai-input').value = transcript;
                this.showToast('语音输入完成', 'success');
            };

            this.recognition.onerror = (event) => {
                console.error('语音识别错误:', event.error);
                this.showToast('语音输入失败', 'error');
            };

            this.recognition.onend = () => {
                document.querySelector('.ai-voice-btn').classList.remove('recording');
            };

            console.log('✅ 语音输入已初始化');
        }
    }

    startVoiceInput() {
        if (this.recognition) {
            document.querySelector('.ai-voice-btn').classList.add('recording');
            this.recognition.start();
            this.showToast('正在听取语音...', 'info');
        } else {
            this.showToast('您的浏览器不支持语音输入', 'warning');
        }
    }

    async sendMessage() {
        const input = document.querySelector('.ai-input');
        const message = input.value.trim();
        
        if (!message || this.isTyping) return;

        input.value = '';
        input.style.height = 'auto';

        this.addMessageToUI('user', message);
        
        this.conversationHistory.push({
            role: 'user',
            content: message,
            timestamp: new Date().toISOString()
        });

        this.isTyping = true;
        this.showTypingIndicator();

        try {
            const response = await this.callAIAPI(message);
            this.hideTypingIndicator();
            this.addMessageToUI('assistant', response);
            
            this.conversationHistory.push({
                role: 'assistant',
                content: response,
                timestamp: new Date().toISOString(),
                provider: this.currentProvider
            });

            this.saveConversationHistory();

        } catch (error) {
            this.hideTypingIndicator();
            this.addMessageToUI('error', `抱歉，发生了错误: ${error.message}`);
            console.error('AI API调用失败:', error);
        }

        this.isTyping = false;
    }

    async callAIAPI(message) {
        const provider = this.providers[this.currentProvider];
        
        const requestData = {
            message: message,
            history: this.conversationHistory.slice(-10),
            provider: this.currentProvider,
            model: provider.model
        };

        const response = await fetch(provider.endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) throw new Error(`API请求失败: ${response.status}`);

        const result = await response.json();
        if (!result.success) throw new Error(result.error || '未知错误');

        return result.response;
    }

    addMessageToUI(role, content) {
        const messagesContainer = document.querySelector('.ai-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `ai-message ai-message-${role}`;
        
        const timestamp = new Date().toLocaleTimeString();
        let avatar, bubbleClass;
        
        switch (role) {
            case 'user':
                avatar = '<div class="ai-avatar ai-avatar-user"><i class="fas fa-user"></i></div>';
                bubbleClass = 'ai-bubble-user';
                break;
            case 'assistant':
                avatar = '<div class="ai-avatar ai-avatar-assistant"><i class="fas fa-robot"></i></div>';
                bubbleClass = 'ai-bubble-assistant';
                break;
            case 'error':
                avatar = '<div class="ai-avatar ai-avatar-error"><i class="fas fa-exclamation-triangle"></i></div>';
                bubbleClass = 'ai-bubble-error';
                break;
        }

        messageDiv.innerHTML = `
            ${avatar}
            <div class="ai-bubble ${bubbleClass}">
                <div class="ai-message-content">${this.formatMessage(content)}</div>
                <div class="ai-message-time">${timestamp}</div>
                ${role === 'assistant' ? `
                    <div class="ai-message-actions">
                        <button class="btn btn-sm btn-outline-secondary ai-copy-btn" onclick="aiAssistant.copyMessage(this)">
                            <i class="fas fa-copy"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-secondary ai-like-btn" onclick="aiAssistant.likeMessage(this)">
                            <i class="fas fa-thumbs-up"></i>
                        </button>
                    </div>
                ` : ''}
            </div>
        `;

        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    showTypingIndicator() {
        const messagesContainer = document.querySelector('.ai-messages');
        const typingDiv = document.createElement('div');
        typingDiv.className = 'ai-message ai-message-assistant ai-typing-indicator';
        typingDiv.innerHTML = `
            <div class="ai-avatar ai-avatar-assistant"><i class="fas fa-robot"></i></div>
            <div class="ai-bubble ai-bubble-assistant">
                <div class="ai-typing">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;
        
        messagesContainer.appendChild(typingDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    hideTypingIndicator() {
        const typingIndicator = document.querySelector('.ai-typing-indicator');
        if (typingIndicator) typingIndicator.remove();
    }

    formatMessage(content) {
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>')
            .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
    }

    switchProvider(providerName) {
        if (this.providers[providerName]) {
            this.currentProvider = providerName;
            
            document.querySelectorAll('.ai-provider-option').forEach(option => {
                option.classList.remove('active');
                if (option.dataset.provider === providerName) option.classList.add('active');
            });
            
            const providerNameElement = document.querySelector('.ai-current-provider');
            if (providerNameElement) providerNameElement.textContent = this.providers[providerName].name;
            
            this.showToast(`已切换到 ${this.providers[providerName].name}`, 'success');
            localStorage.setItem('ai_provider', providerName);
        }
    }

    clearConversation() {
        if (confirm('确定要清空所有对话记录吗？')) {
            this.conversationHistory = [];
            document.querySelector('.ai-messages').innerHTML = '';
            this.saveConversationHistory();
            this.showToast('对话已清空', 'success');
        }
    }

    exportConversation() {
        const exportData = {
            provider: this.currentProvider,
            export_time: new Date().toISOString(),
            messages: this.conversationHistory.map(msg => ({
                role: msg.role,
                content: msg.content,
                timestamp: msg.timestamp
            }))
        };
        
        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `ai_conversation_${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
        
        this.showToast('对话已导出', 'success');
    }

    copyMessage(button) {
        const messageContent = button.closest('.ai-bubble').querySelector('.ai-message-content').textContent;
        navigator.clipboard.writeText(messageContent).then(() => {
            this.showToast('已复制到剪贴板', 'success');
        });
    }

    likeMessage(button) {
        const icon = button.querySelector('i');
        if (icon.classList.contains('liked')) {
            icon.classList.remove('liked', 'fas');
            icon.classList.add('far');
        } else {
            icon.classList.add('liked', 'fas');
            icon.classList.remove('far');
        }
    }

    saveConversationHistory() {
        const historyToSave = this.conversationHistory.slice(-100);
        localStorage.setItem('ai_conversation_history', JSON.stringify(historyToSave));
    }

    loadConversationHistory() {
        const savedHistory = localStorage.getItem('ai_conversation_history');
        if (savedHistory) {
            try {
                this.conversationHistory = JSON.parse(savedHistory);
                this.conversationHistory.forEach(msg => {
                    if (msg.role !== 'system') this.addMessageToUI(msg.role, msg.content);
                });
            } catch (e) {
                console.error('加载对话历史失败:', e);
                this.conversationHistory = [];
            }
        }
        
        const savedProvider = localStorage.getItem('ai_provider');
        if (savedProvider && this.providers[savedProvider]) this.switchProvider(savedProvider);
    }

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
}

// 创建全局实例
const aiAssistant = new AIAssistantManager();

// 暴露到全局
window.AIAssistantManager = AIAssistantManager;
window.aiAssistant = aiAssistant;