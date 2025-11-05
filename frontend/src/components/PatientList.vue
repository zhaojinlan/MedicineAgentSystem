<template>
  <div class="patient-list-container">
    <!-- 标题和新建按钮 -->
    <div class="list-header">
      <h2>
        <el-icon><User /></el-icon>
        患者列表
      </h2>
      <el-button 
        type="primary" 
        @click="showCreateDialog = true"
        :icon="Plus"
        round
      >
        新建患者
      </el-button>
    </div>

    <!-- 搜索框 -->
    <div class="search-box">
      <el-input
        v-model="searchKeyword"
        placeholder="搜索患者姓名或症状..."
        :prefix-icon="Search"
        clearable
      />
    </div>

    <!-- 患者列表 -->
    <div class="patient-list" v-loading="loading">
      <div 
        v-for="patient in filteredPatients" 
        :key="patient.patient_id"
        class="patient-item"
        :class="{ active: patient.patient_id === selectedPatientId }"
        @click="selectPatient(patient.patient_id)"
      >
        <div class="patient-info">
          <div class="patient-name">
            {{ patient.patient_name || '未命名患者' }}
            <el-tag v-if="patient.patient_age" size="small" type="info">
              {{ patient.patient_age }}岁
            </el-tag>
          </div>
          <div class="patient-symptoms">
            {{ patient.initial_symptoms || '暂无症状描述' }}
          </div>
          <div class="patient-time">
            <el-icon><Clock /></el-icon>
            {{ formatTime(patient.updated_at) }}
          </div>
        </div>
        <div class="patient-actions">
          <el-button 
            type="danger" 
            size="small" 
            :icon="Delete"
            circle
            @click.stop="handleDelete(patient)"
          />
        </div>
      </div>

      <el-empty 
        v-if="!loading && filteredPatients.length === 0" 
        description="暂无患者记录"
      />
    </div>

    <!-- 新建患者对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      title="新建患者档案"
      width="520px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      draggable
      align-center
    >
      <el-form 
        :model="newPatient" 
        label-width="90px"
        :rules="formRules"
        ref="formRef"
        label-position="left"
        class="create-form"
      >
        <el-form-item label="患者姓名" prop="patient_name">
          <el-input 
            v-model="newPatient.patient_name" 
            placeholder="请输入患者姓名"
            :prefix-icon="User"
            clearable
            @keyup.enter="handleCreate"
            autofocus
          />
        </el-form-item>
        
        <el-form-item label="患者年龄" prop="patient_age">
          <el-input-number 
            v-model="newPatient.patient_age" 
            :min="0" 
            :max="150"
            controls-position="right"
            placeholder="年龄"
            style="width: 100%"
          />
        </el-form-item>
        
        <el-form-item label="性别">
          <el-radio-group v-model="newPatient.patient_gender">
            <el-radio label="男">男</el-radio>
            <el-radio label="女">女</el-radio>
          </el-radio-group>
        </el-form-item>
        
        <el-form-item label="初始症状">
          <el-input
            v-model="newPatient.initial_symptoms"
            type="textarea"
            :rows="5"
            placeholder="请详细描述患者的主要症状、发病时间等信息..."
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
        
        <el-alert
          title="提示"
          type="info"
          :closable="false"
          show-icon
        >
          创建后可立即开始AI智能分诊
        </el-alert>
      </el-form>
      
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="handleCancel" size="large">
            取消
          </el-button>
          <el-button 
            type="primary" 
            @click="handleCreate" 
            :loading="creating"
            size="large"
            :icon="Plus"
          >
            {{ creating ? '创建中...' : '立即创建' }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, User, Clock, Delete } from '@element-plus/icons-vue'
import { getPatientList, createPatient, deletePatient } from '../api/patient'

const props = defineProps({
  selectedPatientId: String
})

const emit = defineEmits(['patient-selected', 'patient-created'])

const loading = ref(false)
const creating = ref(false)
const patients = ref([])
const searchKeyword = ref('')
const showCreateDialog = ref(false)
const formRef = ref(null)

const newPatient = ref({
  patient_name: '',
  patient_age: null,
  patient_gender: '男',
  initial_symptoms: ''
})

const formRules = {
  patient_name: [
    { required: true, message: '请输入患者姓名', trigger: 'blur' }
  ],
  patient_age: [
    { required: true, message: '请输入患者年龄', trigger: 'blur' }
  ]
}

// 过滤患者列表
const filteredPatients = computed(() => {
  if (!searchKeyword.value) return patients.value
  
  const keyword = searchKeyword.value.toLowerCase()
  return patients.value.filter(patient => {
    return (
      patient.patient_name?.toLowerCase().includes(keyword) ||
      patient.initial_symptoms?.toLowerCase().includes(keyword)
    )
  })
})

// 加载患者列表
const loadPatients = async () => {
  loading.value = true
  try {
    patients.value = await getPatientList()
  } catch (error) {
    ElMessage.error('加载患者列表失败')
  } finally {
    loading.value = false
  }
}

// 选择患者
const selectPatient = (patientId) => {
  emit('patient-selected', patientId)
}

// 创建患者
const handleCreate = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (!valid) {
      ElMessage.warning('请填写必填项')
      return
    }
    
    creating.value = true
    try {
      const data = await createPatient(newPatient.value)
      
      ElMessage.success({
        message: '患者档案创建成功！',
        type: 'success',
        duration: 2000
      })
      showCreateDialog.value = false
      
      // 重置表单
      resetForm()
      
      // 刷新列表
      await loadPatients()
      
      // 选中新创建的患者
      emit('patient-created', data.patient_id)
    } catch (error) {
      ElMessage.error('创建患者失败，请重试')
      console.error('创建患者错误:', error)
    } finally {
      creating.value = false
    }
  })
}

// 取消创建
const handleCancel = () => {
  showCreateDialog.value = false
  resetForm()
}

// 重置表单
const resetForm = () => {
  newPatient.value = {
    patient_name: '',
    patient_age: null,
    patient_gender: '男',
    initial_symptoms: ''
  }
  if (formRef.value) {
    formRef.value.clearValidate()
  }
}

// 删除患者
const handleDelete = async (patient) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除患者 "${patient.patient_name}" 吗？此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    await deletePatient(patient.patient_id)
    ElMessage.success('患者已删除')
    
    // 刷新列表
    await loadPatients()
    
    // 如果删除的是当前选中的患者，清空选择
    if (patient.patient_id === props.selectedPatientId) {
      emit('patient-selected', null)
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除患者失败')
    }
  }
}

// 格式化时间
const formatTime = (timeStr) => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now - date
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  
  return date.toLocaleDateString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

onMounted(() => {
  loadPatients()
})
</script>

<style scoped>
.patient-list-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.list-header {
  padding: 20px;
  border-bottom: 1px solid #ebeef5;
}

.list-header h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  margin-bottom: 15px;
  color: #303133;
}

.search-box {
  padding: 15px 20px;
  border-bottom: 1px solid #ebeef5;
}

.patient-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.patient-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 15px;
  margin-bottom: 10px;
  border-radius: 8px;
  border: 2px solid transparent;
  background: #f5f7fa;
  cursor: pointer;
  transition: all 0.3s;
}

.patient-item:hover {
  background: #e8f4ff;
  border-color: #409eff;
  transform: translateX(5px);
}

.patient-item.active {
  background: #409eff;
  color: white;
  border-color: #409eff;
}

.patient-info {
  flex: 1;
}

.patient-name {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.patient-item.active .patient-name {
  color: white;
}

.patient-symptoms {
  font-size: 13px;
  color: #909399;
  margin-bottom: 5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.patient-item.active .patient-symptoms {
  color: rgba(255, 255, 255, 0.9);
}

.patient-time {
  font-size: 12px;
  color: #c0c4cc;
  display: flex;
  align-items: center;
  gap: 4px;
}

.patient-item.active .patient-time {
  color: rgba(255, 255, 255, 0.8);
}

.patient-actions {
  margin-left: 10px;
}

/* 新建患者对话框样式 */
.create-form {
  padding: 10px 0;
}

.create-form .el-form-item {
  margin-bottom: 22px;
}

.create-form .el-alert {
  margin-top: 10px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

:deep(.el-dialog__header) {
  padding: 20px 20px 10px;
  font-weight: 600;
  font-size: 18px;
}

:deep(.el-dialog__body) {
  padding: 20px 30px;
}

:deep(.el-dialog__footer) {
  padding: 15px 30px 20px;
}
</style>

