<template>
  <div class="patient-detail-container">
    <!-- 标题 -->
    <div class="detail-header">
      <h2>
        <el-icon><Document /></el-icon>
        患者详细信息
      </h2>
    </div>

    <!-- 内容区域 -->
    <div class="detail-content" v-loading="loading">
      <el-empty 
        v-if="!patientData" 
        description="请选择一个患者查看详情"
        :image-size="150"
      />

      <div v-else class="info-sections">
        <!-- 基本信息 -->
        <el-card class="info-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><User /></el-icon>
              <span>基本信息</span>
            </div>
          </template>
          <div class="info-grid">
            <div class="info-item">
              <span class="label">患者ID:</span>
              <span class="value">{{ patientData.patient_id }}</span>
            </div>
            <div class="info-item">
              <span class="label">姓名:</span>
              <span class="value">{{ patientData.patient_name || '未设置' }}</span>
            </div>
            <div class="info-item">
              <span class="label">年龄:</span>
              <span class="value">{{ patientData.patient_age ? patientData.patient_age + '岁' : '未设置' }}</span>
            </div>
            <div class="info-item">
              <span class="label">性别:</span>
              <span class="value">{{ patientData.patient_gender || '未设置' }}</span>
            </div>
            <div class="info-item">
              <span class="label">创建时间:</span>
              <span class="value">{{ formatDateTime(patientData.created_at) }}</span>
            </div>
            <div class="info-item">
              <span class="label">更新时间:</span>
              <span class="value">{{ formatDateTime(patientData.updated_at) }}</span>
            </div>
          </div>
        </el-card>

        <!-- 初始症状 -->
        <el-card v-if="patientData.initial_symptoms" class="info-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Warning /></el-icon>
              <span>初始症状</span>
            </div>
          </template>
          <div class="content-text">{{ patientData.initial_symptoms }}</div>
        </el-card>

        <!-- 患者病史 -->
        <el-card v-if="patientData.patient_history" class="info-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Document /></el-icon>
              <span>患者病史</span>
            </div>
          </template>
          <div class="content-text">{{ patientData.patient_history }}</div>
        </el-card>

        <!-- 分诊信息 -->
        <el-card v-if="patientData.triage_info" class="info-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Grid /></el-icon>
              <span>分诊信息</span>
            </div>
          </template>
          <div class="info-grid">
            <div class="info-item">
              <span class="label">分诊级别:</span>
              <el-tag :type="getTriageLevelType(patientData.triage_info.triage_level)">
                {{ patientData.triage_info.triage_level }}
              </el-tag>
            </div>
            <div class="info-item">
              <span class="label">建议科室:</span>
              <span class="value">{{ patientData.triage_info.recommended_department }}</span>
            </div>
            <div class="info-item">
              <span class="label">分诊时间:</span>
              <span class="value">{{ formatDateTime(patientData.triage_info.triage_time) }}</span>
            </div>
            <div class="info-item full-width" v-if="patientData.triage_info.triage_basis">
              <span class="label">分诊依据:</span>
              <div class="value">{{ patientData.triage_info.triage_basis }}</div>
            </div>
          </div>
        </el-card>

        <!-- 诊断信息 -->
        <el-card v-if="patientData.diagnosis_info" class="info-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Finished /></el-icon>
              <span>诊断信息</span>
            </div>
          </template>
          <div class="info-grid">
            <div class="info-item">
              <span class="label">最可能疾病:</span>
              <el-tag type="danger" size="large">
                {{ patientData.diagnosis_info.most_likely_disease }}
              </el-tag>
            </div>
            <div class="info-item">
              <span class="label">置信度:</span>
              <el-progress 
                :percentage="patientData.diagnosis_info.confidence" 
                :color="getConfidenceColor(patientData.diagnosis_info.confidence)"
              />
            </div>
            <div class="info-item">
              <span class="label">诊断时间:</span>
              <span class="value">{{ formatDateTime(patientData.diagnosis_info.diagnosis_time) }}</span>
            </div>
          </div>

          <!-- 推荐检查 - 未提交时显示可填写结果的表单 -->
          <div v-if="!patientData.diagnosis_info.submitted_tests && patientData.diagnosis_info.recommended_tests?.length > 0" class="recommended-tests">
            <h4>推荐检查项目:</h4>
            <div class="test-items">
              <div 
                v-for="(test, index) in patientData.diagnosis_info.recommended_tests" 
                :key="index"
                class="test-item-card"
              >
                <div class="test-item-header">
                  <el-tag type="warning" size="large">{{ test.test_name }}</el-tag>
                  <el-switch 
                    v-model="test.selected" 
                    active-text="已选择"
                    inactive-text="未选择"
                    @change="handleTestToggle(test)"
                  />
                </div>
                <div class="test-item-description">
                  <span class="label">检查说明：</span>
                  <span class="value">{{ test.test_description }}</span>
                </div>
                <div v-if="test.selected" class="test-item-result">
                  <span class="label">检查结果：</span>
                  <el-input
                    v-model="test.result"
                    type="textarea"
                    :rows="3"
                    :placeholder="`请输入 ${test.test_name} 的检查结果...`"
                  />
                </div>
              </div>
            </div>
            <div class="test-actions">
              <el-button 
                type="primary" 
                @click="submitTests" 
                :icon="Check"
                :disabled="!hasSelectedTests"
              >
                提交已选检查结果 ({{ selectedTestCount }})
              </el-button>
            </div>
          </div>

          <!-- 已提交的检查 - 显示每个检查及其结果 -->
          <div v-if="patientData.diagnosis_info.submitted_tests?.length > 0" class="submitted-tests">
            <h4>已提交的检查项目及结果:</h4>
            <div class="submitted-test-items">
              <div 
                v-for="(test, index) in patientData.diagnosis_info.submitted_tests" 
                :key="index"
                class="submitted-test-card"
              >
                <div class="test-header">
                  <el-tag type="success" size="large">{{ test.test_name }}</el-tag>
                </div>
                <div class="test-description">
                  <span class="label">检查说明：</span>
                  <span class="value">{{ test.test_description }}</span>
                </div>
                <div class="test-result">
                  <span class="label">检查结果：</span>
                  <div class="result-content">{{ test.result || '暂无结果' }}</div>
                </div>
              </div>
            </div>
          </div>
        </el-card>

        <!-- 检查结果 -->
        <el-card v-if="patientData.test_results" class="info-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><DocumentCopy /></el-icon>
              <span>检查结果</span>
            </div>
          </template>
          <div class="content-text">{{ patientData.test_results }}</div>
        </el-card>

        <!-- 专家会诊 -->
        <el-card v-if="patientData.expert_consultation" class="info-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon><Checked /></el-icon>
              <span>专家会诊</span>
            </div>
          </template>
          
          <el-collapse accordion>
            <el-collapse-item title="诊断专家意见" name="1">
              <div class="expert-opinion">
                {{ patientData.expert_consultation.diagnostic_expert_opinion }}
              </div>
            </el-collapse-item>
            <el-collapse-item title="影像专家意见" name="2">
              <div class="expert-opinion">
                {{ patientData.expert_consultation.imaging_expert_opinion }}
              </div>
            </el-collapse-item>
            <el-collapse-item title="治疗专家意见" name="3">
              <div class="expert-opinion">
                {{ patientData.expert_consultation.treatment_expert_opinion }}
              </div>
            </el-collapse-item>
          </el-collapse>

          <div class="final-conclusion">
            <div class="conclusion-item">
              <h4>最终诊断:</h4>
              <el-alert 
                :title="patientData.expert_consultation.final_diagnosis" 
                type="error" 
                :closable="false"
              />
            </div>
            <div class="conclusion-item" v-if="patientData.expert_consultation.treatment_plan">
              <h4>治疗方案:</h4>
              <div class="content-text">{{ patientData.expert_consultation.treatment_plan }}</div>
            </div>
            <div class="conclusion-item" v-if="patientData.expert_consultation.prognosis">
              <h4>预后评估:</h4>
              <div class="content-text">{{ patientData.expert_consultation.prognosis }}</div>
            </div>
          </div>
        </el-card>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, User, Warning, Grid, Finished, Checked, DocumentCopy, Check } from '@element-plus/icons-vue'

const props = defineProps({
  patientData: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['tests-submitted'])

// 计算已选择的检查数量
const selectedTestCount = computed(() => {
  if (!props.patientData?.diagnosis_info?.recommended_tests) return 0
  return props.patientData.diagnosis_info.recommended_tests.filter(t => t.selected).length
})

// 判断是否有选中的检查
const hasSelectedTests = computed(() => {
  return selectedTestCount.value > 0
})

// 处理检查项目开关切换
const handleTestToggle = (test) => {
  // 当取消选择时，清空该检查的结果
  if (!test.selected) {
    test.result = ''
  }
}

// 提交已选检查
const submitTests = () => {
  if (!props.patientData?.diagnosis_info?.recommended_tests) return
  
  const selectedTests = props.patientData.diagnosis_info.recommended_tests.filter(t => t.selected)
  
  if (selectedTests.length === 0) {
    ElMessage.warning('请至少选择一项检查')
    return
  }
  
  // 验证所有已选择的检查都填写了结果
  const incompleteTests = selectedTests.filter(t => !t.result || t.result.trim() === '')
  if (incompleteTests.length > 0) {
    const testNames = incompleteTests.map(t => t.test_name).join('、')
    ElMessage.warning(`请填写以下检查的结果：${testNames}`)
    return
  }
  
  // 构建提交的数据
  const testsToSubmit = selectedTests.map(test => ({
    test_name: test.test_name,
    test_description: test.test_description,
    result: test.result
  }))
  
  // 构建发送给AI的消息
  let message = '我已完成以下检查项目：\n\n'
  testsToSubmit.forEach((test, index) => {
    message += `${index + 1}. **${test.test_name}**\n`
    message += `   检查结果：${test.result}\n\n`
  })
  
  // 确认提交
  ElMessageBox.confirm(
    `确定要提交 ${selectedTests.length} 项检查结果吗？提交后将发送给AI助手进行分析。`,
    '确认提交',
    {
      confirmButtonText: '确认提交',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => {
    // 通知父组件（发送到AI助手）
    emit('tests-submitted', {
      tests: testsToSubmit,
      message: message
    })
    
    ElMessage.success(`已提交 ${selectedTests.length} 项检查结果`)
  }).catch(() => {
    // 用户取消
  })
}

// 格式化日期时间
const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 获取分诊级别的标签类型
const getTriageLevelType = (level) => {
  if (!level) return 'info'
  if (level.includes('I级') || level.includes('危重')) return 'danger'
  if (level.includes('II级') || level.includes('紧急')) return 'warning'
  if (level.includes('III级')) return 'warning'
  return 'info'
}

// 获取置信度颜色
const getConfidenceColor = (confidence) => {
  if (confidence >= 80) return '#67c23a'
  if (confidence >= 60) return '#e6a23c'
  return '#f56c6c'
}
</script>

<style scoped>
.patient-detail-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.detail-header {
  padding: 20px;
  border-bottom: 1px solid #ebeef5;
}

.detail-header h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  margin: 0;
  color: #303133;
}

.detail-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.info-sections {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.info-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #303133;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 15px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.info-item.full-width {
  grid-column: 1 / -1;
}

.label {
  font-size: 13px;
  color: #909399;
  font-weight: 500;
}

.value {
  font-size: 14px;
  color: #303133;
  word-break: break-all;
}

.content-text {
  line-height: 1.8;
  color: #606266;
  white-space: pre-wrap;
}

.pre-wrap {
  white-space: pre-wrap;
  font-family: inherit;
  margin: 0;
}

.recommended-tests {
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #ebeef5;
}

.recommended-tests h4 {
  margin: 0 0 15px 0;
  color: #606266;
  font-size: 14px;
  font-weight: 600;
}

.test-items {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.test-item-card {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 15px;
  background: #fafafa;
  transition: all 0.3s;
}

.test-item-card:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.15);
}

.test-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.test-item-description {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 13px;
}

.test-item-description .label {
  color: #909399;
  flex-shrink: 0;
}

.test-item-description .value {
  color: #606266;
  flex: 1;
}

.test-item-result {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #e4e7ed;
}

.test-item-result .label {
  display: block;
  margin-bottom: 8px;
  color: #909399;
  font-size: 13px;
  font-weight: 500;
}

.test-actions {
  margin-top: 15px;
  text-align: right;
}

.submitted-tests {
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid #ebeef5;
}

.submitted-tests h4 {
  margin: 0 0 15px 0;
  color: #67c23a;
  font-size: 14px;
  font-weight: 600;
}

.submitted-test-items {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.submitted-test-card {
  border: 1px solid #d1e9ff;
  border-radius: 8px;
  padding: 15px;
  background: #f0f9ff;
}

.submitted-test-card .test-header {
  margin-bottom: 10px;
}

.submitted-test-card .test-description {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 13px;
}

.submitted-test-card .test-description .label {
  color: #909399;
  flex-shrink: 0;
}

.submitted-test-card .test-description .value {
  color: #606266;
  flex: 1;
}

.submitted-test-card .test-result {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #d1e9ff;
}

.submitted-test-card .test-result .label {
  display: block;
  margin-bottom: 8px;
  color: #67c23a;
  font-size: 13px;
  font-weight: 600;
}

.submitted-test-card .test-result .result-content {
  background: white;
  padding: 10px;
  border-radius: 6px;
  color: #303133;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.expert-opinion {
  line-height: 1.8;
  color: #606266;
  padding: 10px 0;
}

.final-conclusion {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #ebeef5;
}

.conclusion-item {
  margin-bottom: 15px;
}

.conclusion-item h4 {
  margin: 0 0 10px 0;
  color: #606266;
  font-size: 14px;
}

.json-viewer {
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.json-viewer :deep(.el-textarea__inner) {
  font-family: 'Courier New', monospace;
  background: #f5f7fa;
}
</style>

