<template>
  <div class="chat-bot-container">
    <!-- Floating Button -->
    <div class="chat-fab" @click="toggleChat" v-show="!isOpen">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
      <span style="margin-top: 2px;">AI助手</span>
    </div>

    <!-- Chat Window -->
    <div class="chat-window" v-show="isOpen">
      <div class="chat-header">
        <span>智能数据助手</span>
        <span class="close-btn" @click="toggleChat">×</span>
      </div>
      
      <div class="chat-messages" ref="messagesContainer">
        <div v-for="(msg, index) in messages" :key="index" :class="['message', msg.role === 'assistant' ? 'bot' : 'user']">
          <div class="message-content" v-html="renderMarkdown(msg.content)"></div>
        </div>
      </div>

      <div class="chat-input">
        <input 
          v-model="input" 
          @keyup.enter="handleSend" 
          placeholder="输入您的问题..."
          :disabled="isLoading"
        />
        <button @click="handleSend" :disabled="isLoading || !input.trim()">发送</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt()
const isOpen = ref(false)
const messagesContainer = ref(null)
const input = ref('')
const isLoading = ref(false)
const messages = ref([
  { id: 'welcome', role: 'assistant', content: '你好！我是您的智能数据助手，有什么可以帮您？' }
])

// Determine API URL based on environment
const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? 'https://api.aistocklink.cn' 
  : 'http://localhost:8000';

const toggleChat = () => {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    scrollToBottom()
  }
}

const renderMarkdown = (text) => {
  return md.render(text)
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// Auto-scroll when messages change
watch(messages, () => {
  scrollToBottom()
}, { deep: true })

const handleSend = async () => {
  if (!input.value.trim() || isLoading.value) return
  
  const userMessage = { role: 'user', content: input.value }
  messages.value.push(userMessage)
  input.value = ''
  isLoading.value = true

  try {
    const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        messages: messages.value
      }),
    })

    if (!response.ok) {
      throw new Error(response.statusText)
    }

    // Create a placeholder for the assistant's response
    const assistantMessage = { role: 'assistant', content: '' }
    messages.value.push(assistantMessage)

    const reader = response.body.getReader()
    const decoder = new TextDecoder()

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      const chunk = decoder.decode(value, { stream: true })
      // Append chunk to the last message
      messages.value[messages.value.length - 1].content += chunk
    }

  } catch (error) {
    console.error('Chat error:', error)
    messages.value.push({ role: 'assistant', content: '抱歉，服务暂时不可用，请稍后再试。' })
  } finally {
    isLoading.value = false
  }
}
</script>

<style lang="scss" scoped>
.chat-bot-container {
  position: fixed;
  bottom: 30px;
  right: 30px;
  z-index: 9999;
  font-family: 'PingFang SC', sans-serif;
}

.chat-fab {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background-color: #409EFF;
  color: white;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.4);
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
  font-size: 12px;
  user-select: none;

  &:hover {
    transform: translateY(-2px) scale(1.05);
    box-shadow: 0 6px 20px rgba(64, 158, 255, 0.5);
  }
  
  &:active {
    transform: translateY(0) scale(0.95);
  }
}

.chat-window {
  width: 380px;
  height: 550px;
  background-color: white;
  border-radius: 16px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(0,0,0,0.05);
  animation: slideIn 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}

@keyframes slideIn {
  from { opacity: 0; transform: translateY(20px) scale(0.95); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.chat-header {
  padding: 16px 20px;
  background: linear-gradient(135deg, #409EFF, #3a8ee6);
  color: white;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  font-size: 16px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.05);

  .close-btn {
    cursor: pointer;
    font-size: 24px;
    line-height: 1;
    opacity: 0.8;
    transition: opacity 0.2s;
    
    &:hover {
      opacity: 1;
    }
  }
}

.chat-messages {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  background-color: #f5f7fa;
  display: flex;
  flex-direction: column;
  gap: 16px;
  scroll-behavior: smooth;
}

.message {
  max-width: 85%;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-wrap: break-word;
  position: relative;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);

  &.user {
    align-self: flex-end;
    background-color: #409EFF;
    color: white;
    border-bottom-right-radius: 2px;
    
    :deep(a) {
      color: white;
      text-decoration: underline;
    }
  }

  &.bot {
    align-self: flex-start;
    background-color: white;
    color: #2c3e50;
    border-bottom-left-radius: 2px;
    
    :deep(p) {
      margin-bottom: 8px;
      &:last-child { margin-bottom: 0; }
    }
    
    :deep(ul), :deep(ol) {
      padding-left: 20px;
      margin: 8px 0;
    }
    
    :deep(code) {
      background-color: #f0f2f5;
      padding: 2px 4px;
      border-radius: 4px;
      font-family: monospace;
      color: #e65100;
    }
    
    :deep(pre) {
      background-color: #282c34;
      color: #abb2bf;
      padding: 10px;
      border-radius: 8px;
      overflow-x: auto;
      margin: 8px 0;
      
      code {
        background-color: transparent;
        color: inherit;
        padding: 0;
      }
    }
  }
}

.chat-input {
  padding: 16px;
  border-top: 1px solid #eee;
  display: flex;
  gap: 12px;
  background-color: white;

  input {
    flex: 1;
    padding: 10px 14px;
    border: 1px solid #dcdfe6;
    border-radius: 20px;
    outline: none;
    transition: border-color 0.2s;
    font-size: 14px;
    
    &:focus {
      border-color: #409EFF;
    }
    
    &:disabled {
      background-color: #f5f7fa;
    }
  }

  button {
    padding: 8px 20px;
    background-color: #409EFF;
    color: white;
    border: none;
    border-radius: 20px;
    cursor: pointer;
    font-weight: 500;
    transition: background-color 0.2s;
    
    &:hover:not(:disabled) {
      background-color: #66b1ff;
    }
    
    &:disabled {
      background-color: #a0cfff;
      cursor: not-allowed;
    }
  }
}

.loading span {
  display: inline-block;
  width: 6px;
  height: 6px;
  background-color: #909399;
  border-radius: 50%;
  margin: 0 2px;
  animation: bounce 1.4s infinite both;
}

.loading span:nth-child(1) { animation-delay: -0.32s; }
.loading span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}
</style>
