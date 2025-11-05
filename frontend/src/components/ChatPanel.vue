<template>
  <div class="chat-panel-container">
    <!-- 标题 -->
    <div class="chat-header">
      <h2>
        <el-icon><ChatDotRound /></el-icon>
        AI智能诊断助手
      </h2>
      <el-tag v-if="patientId" type="success" size="small">
        连接中
      </el-tag>
      <el-tag v-else type="info" size="small">
        未选择患者
      </el-tag>
    </div>

    <!-- 消息列表 -->
    <div class="message-list" ref="messageListRef">
      <el-empty 
        v-if="!patientId" 
        description="请先选择或创建一个患者"
        :image-size="120"
      />

      <div v-else-if="messages.length === 0" class="welcome-message">
        <el-alert
          title="欢迎使用AI诊断助手"
          type="info"
          :closable="false"
        >
          <template #default>
            <p>您可以：</p>
            <ul>
              <li>输入患者症状进行分诊</li>
              <li>回答系统问题完善病史</li>
              <li>提供检查结果获取专家意见</li>
              <li>咨询医学知识</li>
            </ul>
          </template>
        </el-alert>
      </div>

      <div v-else class="messages">
        <div
          v-for="(msg, index) in messages"
          :key="index"
          class="message-item"
          :class="msg.role"
        >
          <div class="message-avatar">
            <el-avatar 
              :icon="msg.role === 'user' ? User : Headset" 
              :style="{ background: msg.role === 'user' ? '#409eff' : '#67c23a' }"
            />
          </div>
          <div class="message-content">
            <div class="message-header">
              <span class="message-role">
                {{ msg.role === 'user' ? '您' : 'AI助手' }}
              </span>
              <span class="message-time">
                {{ formatTime(msg.timestamp) }}
              </span>
            </div>
            
            <!-- 思考过程（可折叠） -->
            <div v-if="msg.role === 'assistant' && msg.thinking_steps && msg.thinking_steps.length > 0" class="thinking-section">
              <el-collapse v-model="msg.thinkingExpanded" accordion>
                <el-collapse-item name="thinking">
                  <template #title>
                    <div class="thinking-title">
                      <el-icon :class="{'thinking-icon': msg.streaming}"><Loading /></el-icon>
                      <span>🧠 AI推理过程（{{ msg.thinking_steps.length }} 个节点）</span>
                      <el-tag size="small" type="success" style="margin-left: 8px">点击查看详情</el-tag>
                    </div>
                  </template>
                  <div class="thinking-steps">
                    <div class="thinking-flow">
                      <div
                        v-for="(step, idx) in msg.thinking_steps"
                        :key="idx"
                        class="thinking-step-item"
                      >
                        <div class="step-indicator">
                          <div class="step-number">{{ idx + 1 }}</div>
                          <div v-if="idx < msg.thinking_steps.length - 1" class="step-line"></div>
                        </div>
                        <div class="step-content">
                          <div class="step-name">{{ step.display_name }}</div>
                          <div v-if="step.content" class="step-detail">
                            {{ step.content }}
                            <span v-if="msg.streaming && idx === msg.thinking_steps.length - 1" class="typing-cursor">▋</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>
            
            <!-- AI回复内容 -->
            <div class="message-text" v-html="formatMessage(msg.content)"></div>
            
            <!-- 流式输出指示器 -->
            <div v-if="msg.streaming" class="streaming-indicator">
              <span class="cursor-blink">▋</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入框 -->
    <div class="chat-input">
      <el-input
        v-model="inputMessage"
        type="textarea"
        :rows="3"
        placeholder="请输入消息..."
        :disabled="!patientId || sending"
        @keydown.enter.ctrl="sendMessage"
      />
      <div class="input-footer">
        <span class="input-tip">
          <el-icon><Warning /></el-icon>
          Ctrl + Enter 发送
        </span>
        <el-button
          type="primary"
          :icon="Promotion"
          :loading="sending"
          :disabled="!patientId || !inputMessage.trim()"
          @click="sendMessage"
        >
          发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatDotRound, User, Headset, Promotion, Warning, Loading, Operation } from '@element-plus/icons-vue'
import { getPatientDetail } from '../api/patient'

const props = defineProps({
  patientId: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['conversation-updated'])

const messages = ref([])
const inputMessage = ref('')
const sending = ref(false)
const messageListRef = ref(null)

// 监听患者切换，加载历史消息
watch(() => props.patientId, async (newId) => {
  if (newId) {
    await loadConversationHistory()
  } else {
    messages.value = []
  }
}, { immediate: true })

// 加载对话历史
const loadConversationHistory = async () => {
  try {
    const data = await getPatientDetail(props.patientId)
    messages.value = (data.conversation_history || []).map(msg => ({
      ...msg,
      thinkingExpanded: []  // 初始化折叠状态
    }))
    await nextTick()
    scrollToBottom()
  } catch (error) {
    console.error('加载对话历史失败:', error)
  }
}

// 发送消息（使用流式API）
const sendMessage = async () => {
  if (!inputMessage.value.trim() || !props.patientId) return

  const userMessage = inputMessage.value.trim()
  inputMessage.value = ''

  // 添加用户消息到界面
  messages.value.push({
    role: 'user',
    content: userMessage,
    timestamp: new Date().toISOString()
  })

  await nextTick()
  scrollToBottom()

  sending.value = true

  // 创建一个AI消息占位符
  const aiMessageIndex = messages.value.length
  messages.value.push({
    role: 'assistant',
    content: '',
    timestamp: new Date().toISOString(),
    streaming: true,
    thinking_steps: [],
    thinkingExpanded: []
  })

  try {
    // 使用 EventSource 接收流式数据
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        patient_id: props.patientId,
        message: userMessage
      })
    })

    if (!response.ok) {
      throw new Error('请求失败')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      
      if (done) break
      
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || '' // 保留不完整的行
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const jsonStr = line.slice(6)
          try {
            const data = JSON.parse(jsonStr)
            
            if (data.type === 'thinking_step_start') {
              // 开始一个新的思考步骤
              messages.value[aiMessageIndex].thinking_steps.push({
                node: data.node,
                display_name: data.display_name,
                content: ''
              })
            } else if (data.type === 'thinking_chunk') {
              // 追加思考内容到最后一个步骤
              const steps = messages.value[aiMessageIndex].thinking_steps
              if (steps.length > 0) {
                const lastStep = steps[steps.length - 1]
                if (lastStep.node === data.node) {
                  lastStep.content += data.content
                }
              }
              await nextTick()
              scrollToBottom()
            } else if (data.type === 'thinking_step_end') {
              // 思考步骤完成（可以添加动画效果）
              await nextTick()
              scrollToBottom()
            } else if (data.type === 'thinking_step') {
              // 兼容旧格式：一次性发送完整步骤
              messages.value[aiMessageIndex].thinking_steps.push({
                node: data.node,
                display_name: data.display_name,
                content: data.content || ''
              })
            } else if (data.type === 'response_chunk') {
              // 逐步添加响应内容
              messages.value[aiMessageIndex].content += data.content
              await nextTick()
              scrollToBottom()
            } else if (data.type === 'done') {
              // 完成
              messages.value[aiMessageIndex].streaming = false
            } else if (data.type === 'error') {
              throw new Error(data.message)
            }
          } catch (e) {
            console.error('解析SSE数据失败:', e, jsonStr)
          }
        }
      }
    }

    // 通知父组件刷新患者详情
    emit('conversation-updated')

  } catch (error) {
    ElMessage.error('发送消息失败，请重试')
    console.error('发送消息失败:', error)
    
    // 移除AI消息占位符和用户消息
    messages.value.splice(aiMessageIndex, 1)
    messages.value.pop()
  } finally {
    sending.value = false
  }
}

// 滚动到底部
const scrollToBottom = () => {
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}

// 格式化消息内容（支持换行和markdown）
const formatMessage = (content) => {
  return content
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
}

// 格式化时间
const formatTime = (timeStr) => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 暴露给父组件调用的方法
const sendMessageFromParent = (message) => {
  if (!message || !props.patientId) return
  
  // 设置输入框内容并发送
  inputMessage.value = message
  sendMessage()
}

// 使用defineExpose暴露方法
defineExpose({
  sendMessageFromParent
})
</script>

<style scoped>
.chat-panel-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.chat-header {
  padding: 20px;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chat-header h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  margin: 0;
  color: #303133;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #f5f7fa;
}

.welcome-message {
  max-width: 400px;
  margin: 50px auto;
}

.welcome-message ul {
  margin: 10px 0 0 20px;
}

.welcome-message li {
  margin: 5px 0;
  color: #606266;
}

.messages {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.message-item {
  display: flex;
  gap: 12px;
  animation: fadeIn 0.3s;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-item.user {
  flex-direction: row-reverse;
}

.message-content {
  max-width: 70%;
  background: white;
  border-radius: 12px;
  padding: 12px 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.message-item.user .message-content {
  background: #409eff;
  color: white;
}

.message-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12px;
}

.message-role {
  font-weight: 600;
}

.message-item.user .message-role {
  color: rgba(255, 255, 255, 0.9);
}

.message-time {
  color: #c0c4cc;
}

.message-item.user .message-time {
  color: rgba(255, 255, 255, 0.7);
}

/* 思考过程样式 */
.thinking-section {
  margin: 8px 0 12px 0;
  background: linear-gradient(135deg, #e8f4fd 0%, #f0f9ff 100%);
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #d1e9ff;
}

.thinking-section :deep(.el-collapse) {
  border: none;
  background: transparent;
}

.thinking-section :deep(.el-collapse-item__header) {
  background: transparent;
  border: none;
  padding: 10px 14px;
  font-size: 13px;
  color: #409eff;
  font-weight: 500;
}

.thinking-section :deep(.el-collapse-item__content) {
  padding: 0 14px 14px 14px;
  background: transparent;
}

.thinking-title {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.thinking-icon {
  animation: rotate 2s linear infinite;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.thinking-steps {
  font-size: 13px;
}

.thinking-flow {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.thinking-step-item {
  display: flex;
  gap: 12px;
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.step-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}

.step-number {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #409eff;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
  box-shadow: 0 2px 4px rgba(64, 158, 255, 0.3);
}

.step-line {
  width: 2px;
  flex: 1;
  min-height: 20px;
  background: linear-gradient(to bottom, #409eff, #a0cfff);
  margin: 4px 0;
}

.step-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 4px 0 16px 0;
  flex: 1;
}

.step-name {
  color: #303133;
  font-weight: 600;
  font-size: 14px;
}

.step-detail {
  color: #606266;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  background: rgba(255, 255, 255, 0.6);
  padding: 8px 12px;
  border-radius: 6px;
  border-left: 3px solid #409eff;
}

.typing-cursor {
  animation: blink 1s step-end infinite;
  color: #409eff;
  font-weight: bold;
  margin-left: 2px;
}

.message-text {
  line-height: 1.6;
  word-break: break-word;
}

.message-text :deep(br) {
  display: block;
  margin: 5px 0;
}

.message-text :deep(strong) {
  font-weight: 600;
  color: #303133;
}

.message-item.user .message-text :deep(strong) {
  color: rgba(255, 255, 255, 0.95);
}

/* 流式输出指示器 */
.streaming-indicator {
  margin-top: 4px;
  display: inline-block;
}

.cursor-blink {
  animation: blink 1s step-end infinite;
  color: #67c23a;
  font-weight: bold;
}

@keyframes blink {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}

.chat-input {
  padding: 20px;
  border-top: 1px solid #ebeef5;
  background: white;
}

.input-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}

.input-tip {
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
