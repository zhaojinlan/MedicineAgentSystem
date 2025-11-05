<template>
  <div class="medical-system">
    <!-- 顶部导航栏 -->
    <div class="top-nav">
      <div class="nav-title">医疗智能体系统</div>
      <el-menu
        :default-active="activeView"
        mode="horizontal"
        @select="handleViewChange"
        class="nav-menu"
      >
        <el-menu-item index="patient">
          <el-icon><User /></el-icon>
          <span>患者管理</span>
        </el-menu-item>
        <el-menu-item index="knowledge">
          <el-icon><Connection /></el-icon>
          <span>知识图谱构建</span>
        </el-menu-item>
      </el-menu>
    </div>

    <!-- 患者管理视图 -->
    <div v-show="activeView === 'patient'" class="main-container">
      <!-- 左侧：患者列表 -->
      <div class="left-panel">
        <PatientList 
          @patient-selected="handlePatientSelected"
          @patient-created="handlePatientCreated"
          :selected-patient-id="selectedPatientId"
        />
      </div>

      <!-- 中间：患者详情 -->
      <div class="middle-panel">
        <PatientDetail 
          :patient-data="currentPatientData"
          :loading="detailLoading"
          @tests-submitted="handleTestsSubmitted"
        />
      </div>

      <!-- AI助手切换按钮 -->
      <div class="toggle-chat-btn" @click="toggleChat">
        <el-icon :class="{ rotate: showChat }">
          <DArrowLeft v-if="showChat" />
          <DArrowRight v-else />
        </el-icon>
      </div>

      <!-- 右侧：AI对话（可滑动显示/隐藏，可调整大小） -->
      <transition name="slide">
        <div v-show="showChat" class="right-panel" :style="{ width: chatWidth + 'px' }">
          <!-- 可拖动的分隔条 -->
          <div 
            class="resize-handle"
            @mousedown="startResize"
          >
            <div class="resize-indicator"></div>
          </div>
          
          <ChatPanel 
            ref="chatPanelRef"
            :patient-id="selectedPatientId"
            @conversation-updated="refreshPatientDetail"
          />
        </div>
      </transition>
    </div>

    <!-- 知识图谱构建视图 -->
    <div v-show="activeView === 'knowledge'" class="knowledge-view">
      <KnowledgeConstruction />
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { DArrowLeft, DArrowRight, User, Connection } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import PatientList from './components/PatientList.vue'
import PatientDetail from './components/PatientDetail.vue'
import ChatPanel from './components/ChatPanel.vue'
import KnowledgeConstruction from './components/KnowledgeConstruction.vue'
import { getPatientDetail, submitTestResults } from './api/patient'

// 视图切换
const activeView = ref('patient')

// 处理视图切换
const handleViewChange = (index) => {
  activeView.value = index
}

const selectedPatientId = ref(null)
const currentPatientData = ref(null)
const detailLoading = ref(false)
const showChat = ref(true)
const chatWidth = ref(420) // AI助手面板宽度，默认420px
const isResizing = ref(false)
const chatPanelRef = ref(null) // ChatPanel组件引用

// 处理患者选中
const handlePatientSelected = (patientId) => {
  selectedPatientId.value = patientId
  loadPatientDetail(patientId)
}

// 处理新建患者
const handlePatientCreated = (patientId) => {
  selectedPatientId.value = patientId
  loadPatientDetail(patientId)
}

// 加载患者详情
const loadPatientDetail = async (patientId) => {
  if (!patientId) {
    currentPatientData.value = null
    return
  }

  detailLoading.value = true
  try {
    const data = await getPatientDetail(patientId)
    currentPatientData.value = data
  } catch (error) {
    console.error('加载患者详情失败:', error)
  } finally {
    detailLoading.value = false
  }
}

// 刷新患者详情（对话后更新）
const refreshPatientDetail = () => {
  if (selectedPatientId.value) {
    loadPatientDetail(selectedPatientId.value)
  }
}

// 切换AI助手显示
const toggleChat = () => {
  showChat.value = !showChat.value
}

// 处理检查项目提交
const handleTestsSubmitted = async (data) => {
  try {
    console.log('提交的检查结果:', data)
    
    // 先调用后端API保存检查结果
    await submitTestResults(selectedPatientId.value, {
      submitted_tests: data.tests  // tests现在包含test_name、test_description、result
    })
    
    ElMessage.success('检查结果已保存')
    
    // 刷新患者详情
    await loadPatientDetail(selectedPatientId.value)
    
    // 确保AI助手显示
    if (!showChat.value) {
      showChat.value = true
    }
    
    // 使用nextTick确保ChatPanel已渲染
    nextTick(() => {
      if (chatPanelRef.value && data.message) {
        // 调用ChatPanel的发送消息方法
        chatPanelRef.value.sendMessageFromParent(data.message)
      }
    })
  } catch (error) {
    console.error('提交检查结果失败:', error)
    ElMessage.error('提交检查结果失败: ' + (error.response?.data?.detail || error.message))
  }
}

// 开始调整大小
const startResize = (e) => {
  isResizing.value = true
  const startX = e.clientX
  const startWidth = chatWidth.value
  
  const handleMouseMove = (e) => {
    if (!isResizing.value) return
    
    // 计算新宽度（从右向左拖动，所以是减法）
    const deltaX = startX - e.clientX
    const newWidth = startWidth + deltaX
    
    // 限制最小和最大宽度
    const minWidth = 320 // 最小宽度320px
    const maxWidth = window.innerWidth * 0.6 // 最大宽度为屏幕的60%
    
    chatWidth.value = Math.max(minWidth, Math.min(newWidth, maxWidth))
  }
  
  const handleMouseUp = () => {
    isResizing.value = false
    document.body.style.cursor = 'default'
    document.body.style.userSelect = 'auto'
    document.removeEventListener('mousemove', handleMouseMove)
    document.removeEventListener('mouseup', handleMouseUp)
  }
  
  document.body.style.cursor = 'ew-resize'
  document.body.style.userSelect = 'none'
  document.addEventListener('mousemove', handleMouseMove)
  document.addEventListener('mouseup', handleMouseUp)
}

// 键盘快捷键处理
const handleKeydown = (event) => {
  // Ctrl+L 切换AI助手
  if (event.ctrlKey && event.key.toLowerCase() === 'l') {
    event.preventDefault() // 阻止浏览器默认行为
    toggleChat()
    ElMessage.info({
      message: showChat.value ? 'AI助手已显示' : 'AI助手已隐藏',
      duration: 1000
    })
  }
}

// 组件挂载时添加键盘事件监听
onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
  // 从 localStorage 恢复宽度设置
  const savedWidth = localStorage.getItem('chatPanelWidth')
  if (savedWidth) {
    chatWidth.value = parseInt(savedWidth)
  }
})

// 组件卸载时移除键盘事件监听
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

// 监听宽度变化，保存到 localStorage
watch(chatWidth, (newWidth) => {
  localStorage.setItem('chatPanelWidth', newWidth.toString())
})
</script>

<style scoped>
.medical-system {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}

.top-nav {
  height: 60px;
  background: white;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  padding: 0 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.nav-title {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  margin-right: 40px;
}

.nav-menu {
  flex: 1;
  border-bottom: none;
}

.main-container {
  flex: 1;
  display: flex;
  overflow: hidden;
  position: relative;
}

.knowledge-view {
  flex: 1;
  overflow: hidden;
}

.left-panel {
  width: 320px;
  background: white;
  border-right: 1px solid #e4e7ed;
  overflow: hidden;
}

.middle-panel {
  flex: 1;
  background: white;
  overflow: hidden;
}

.toggle-chat-btn {
  width: 24px;
  background: white;
  border-left: 1px solid #e4e7ed;
  border-right: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
  z-index: 10;
}

.toggle-chat-btn:hover {
  background: #409eff;
  color: white;
}

.toggle-chat-btn .el-icon {
  font-size: 16px;
  transition: transform 0.3s ease;
}

.toggle-chat-btn .el-icon.rotate {
  transform: rotate(0deg);
}

.right-panel {
  position: relative;
  min-width: 320px;
  max-width: 60vw;
  background: white;
  border-left: 1px solid #e4e7ed;
  overflow: hidden;
}

/* 可拖动的分隔条 */
.resize-handle {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 8px;
  cursor: ew-resize;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
}

.resize-handle:hover {
  background: rgba(64, 158, 255, 0.1);
}

.resize-indicator {
  width: 2px;
  height: 40px;
  background: #d1e9ff;
  border-radius: 2px;
  transition: all 0.2s;
}

.resize-handle:hover .resize-indicator {
  background: #409eff;
  height: 60px;
}

/* 滑动动画 */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-enter-from {
  transform: translateX(100%);
  opacity: 0;
}

.slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}

.slide-enter-to,
.slide-leave-from {
  transform: translateX(0);
  opacity: 1;
}
</style>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

#app {
  height: 100vh;
}
</style>

