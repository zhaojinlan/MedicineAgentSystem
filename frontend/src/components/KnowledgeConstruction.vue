<template>
  <div class="knowledge-construction">
    <!-- 三栏布局 -->
    <div class="main-layout">
      <!-- 左侧：文件管理区 -->
      <div class="left-panel">
        <!-- 上传按钮（置于顶部） -->
        <div class="upload-button-section">
          <el-button 
            type="primary" 
            size="large"
            @click="showUploadDialog = true"
            style="width: 100%;"
          >
            <el-icon><Upload /></el-icon>
            上传新文件
          </el-button>
        </div>

        <!-- 搜索现有文件 -->
        <el-card class="search-card">
          <template #header>
            <div class="card-header">
              <el-icon><Search /></el-icon>
              <span>搜索现有文件</span>
            </div>
          </template>

          <el-input
            v-model="searchKeyword"
            placeholder="输入文件名搜索..."
            :prefix-icon="Search"
            clearable
            @input="handleSearch"
          />

          <div v-loading="loadingDocuments" class="document-list">
            <div 
              v-if="filteredDocuments.length === 0 && !loadingDocuments"
              class="empty-list"
            >
              <el-empty description="暂无已处理的文档" :image-size="60" />
            </div>
            
            <div 
              v-for="doc in filteredDocuments" 
              :key="doc.name"
              class="document-item"
              :class="{ active: doc.name === documentName, 'has-graph': doc.has_graph }"
            >
              <div class="doc-content" @click="loadDocument(doc)">
                <div class="doc-info">
                  <div class="doc-name">
                    <el-icon v-if="!doc.has_graph"><Document /></el-icon>
                    <el-icon v-else style="color: #67c23a;"><Connection /></el-icon>
                    {{ doc.name }}
                  </div>
                  <div v-if="doc.has_graph" class="doc-status">
                    <el-tag type="success" size="small" effect="dark">
                      <el-icon style="margin-right: 3px;"><CircleCheck /></el-icon>
                      已构建图谱
                    </el-tag>
                  </div>
                </div>
                <div v-if="doc.metadata.entity_count" class="doc-meta">
                  <el-icon style="font-size: 12px; margin-right: 3px;"><User /></el-icon>
                  {{ doc.metadata.entity_count }} 实体
                  <el-icon style="font-size: 12px; margin: 0 3px 0 8px;"><Connection /></el-icon>
                  {{ doc.metadata.relationship_count }} 关系
                </div>
                <div v-else-if="!doc.has_graph" class="doc-meta" style="color: #909399;">
                  点击编辑文档
                </div>
              </div>
              
              <!-- 删除按钮 -->
              <div class="doc-actions" @click.stop>
                <el-button
                  type="danger"
                  size="small"
                  circle
                  @click="handleDeleteDocument(doc.name)"
                  title="删除文档及所有资源"
                >
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>
          </div>
        </el-card>

        <!-- 数据管理功能区 -->
        <el-card class="management-card">
          <template #header>
            <div class="card-header">
              <el-icon><Setting /></el-icon>
              <span>数据管理</span>
            </div>
          </template>

          <div class="management-actions">
            <el-button
              type="primary"
              size="small"
              :icon="Refresh"
              @click="handleSyncMetadata"
              :loading="syncing"
              style="width: 100%; margin-bottom: 10px;"
            >
              同步元数据
            </el-button>
            
            <el-button
              type="info"
              size="small"
              :icon="DataAnalysis"
              @click="handleShowStats"
              style="width: 100%; margin-bottom: 10px;"
            >
              查看统计
            </el-button>
            
            <el-button
              type="warning"
              size="small"
              :icon="Warning"
              @click="handleCleanupOrphaned"
              style="width: 100%;"
            >
              清理孤立资源
            </el-button>
          </div>
        </el-card>
      </div>

      <!-- 中间：当前文件展示区（始终显示） -->
      <div class="middle-panel">
        <el-card class="html-card">
          <template #header>
            <div class="card-header">
              <el-icon><Document /></el-icon>
              <span>当前文件</span>
              <el-tag 
                v-if="documentName"
                type="primary" 
                size="small"
                style="margin-left: 10px;"
              >
                {{ documentName }}
              </el-tag>
              <div style="flex: 1"></div>
              <el-button-group v-if="currentHtmlBlobUrl" size="small">
                <el-button 
                  :type="htmlViewMode === 'raw' ? 'primary' : ''"
                  @click="htmlViewMode = 'raw'"
                >
                  原始HTML
                </el-button>
                <el-button 
                  :type="htmlViewMode === 'cleaned' ? 'primary' : ''"
                  @click="htmlViewMode = 'cleaned'"
                >
                  清洗后HTML
                </el-button>
              </el-button-group>
            </div>
          </template>

          <div v-loading="processing" class="html-viewer">
            <iframe 
              v-if="currentHtmlBlobUrl" 
              :src="currentHtmlBlobUrl"
              class="html-iframe"
              frameborder="0"
            ></iframe>
            <el-empty v-else description="请先上传文件或选择已有文档" />
          </div>
        </el-card>
      </div>

      <!-- 右侧：知识图谱或JSON编辑区 -->
      <div class="right-panel">
        <!-- 已构建图谱：显示知识图谱 -->
        <el-card v-if="graphBuilt" class="graph-card">
          <template #header>
            <div class="card-header">
              <el-icon><Connection /></el-icon>
              <span>知识图谱</span>
              <el-tag 
                type="success" 
                size="small" 
                effect="dark"
                style="margin-left: 10px;"
              >
                {{ entities.length }} 实体 / {{ relationships.length }} 关系
              </el-tag>
              <div style="flex: 1"></div>
              <el-button 
                type="primary"
                size="small"
                @click="openFullscreenGraph"
                style="margin-right: 5px;"
              >
                <el-icon><FullScreen /></el-icon>
                全屏
              </el-button>
              <el-button 
                size="small"
                @click="switchToEditMode"
              >
                <el-icon><Edit /></el-icon>
                编辑
              </el-button>
            </div>
          </template>

          <div v-loading="building" class="graph-viewer">
            <div 
              ref="graphContainer"
              class="graph-content"
            ></div>
          </div>

          <template #footer>
            <div class="graph-footer">
              <el-button type="success" size="small" @click="exportGraph" style="flex: 1;">
                <el-icon><Download /></el-icon>
                导出JSON
              </el-button>
              <el-button type="primary" size="small" @click="exportGraphImage" style="flex: 1;">
                <el-icon><Download /></el-icon>
                导出图片
              </el-button>
            </div>
          </template>
        </el-card>

        <!-- 未构建图谱：JSON编辑区 -->
        <!-- JSON文件展示（实体抽取完成后显示） -->
        <el-card v-if="!graphBuilt" class="json-card">
          <template #header>
            <div class="card-header">
              <el-icon><Tickets /></el-icon>
              <span>JSON文件展示</span>
              <el-tag 
                v-if="entities.length > 0" 
                type="success" 
                size="small"
                style="margin-left: auto;"
              >
                {{ entities.length }} 实体 / {{ relationships.length }} 关系
              </el-tag>
            </div>
          </template>

          <div v-if="entities.length === 0" class="empty-state">
            <el-empty description="该内容可修改，点击下面的'构建知识图谱'按钮后将处理后的JSON展示为构建后的知识图谱">
              <el-icon style="font-size: 80px; color: #909399;"><Document /></el-icon>
            </el-empty>
          </div>

          <div v-else class="json-content">
            <!-- 实体列表 -->
            <div class="json-section">
              <div class="section-header">
                <span class="section-title">
                  <el-icon><User /></el-icon>
                  实体列表 ({{ entities.length }})
                </span>
                <el-button 
                  type="primary" 
                  size="small"
                  @click="showAddEntityDialog"
                >
                  <el-icon><Plus /></el-icon>
                  添加
                </el-button>
              </div>
              
              <div class="entity-list">
                <div 
                  v-for="(entity, index) in entities.slice(0, 5)" 
                  :key="index"
                  class="entity-item"
                >
                  <div class="entity-header">
                    <el-tag :type="getEntityTypeColor(entity.entity_type)" size="small">
                      {{ entity.entity_type }}
                    </el-tag>
                    <span class="entity-name">{{ entity.name }}</span>
                  </div>
                  <div class="entity-actions">
                    <el-button 
                      type="primary" 
                      size="small"
                      link
                      @click="editEntity(index)"
                    >
                      编辑
                    </el-button>
                    <el-button 
                      type="danger" 
                      size="small"
                      link
                      @click="deleteEntity(index)"
                    >
                      删除
                    </el-button>
                  </div>
                </div>
                
                <el-button 
                  v-if="entities.length > 5"
                  text
                  type="info"
                  @click="showAllEntities"
                  style="width: 100%; margin-top: 10px;"
                >
                  查看全部 {{ entities.length }} 个实体
                </el-button>
              </div>
            </div>

            <el-divider />

            <!-- 关系列表 -->
            <div class="json-section">
              <div class="section-header">
                <span class="section-title">
                  <el-icon><Connection /></el-icon>
                  关系列表 ({{ relationships.length }})
                </span>
                <el-button 
                  type="primary" 
                  size="small"
                  @click="showAddRelationDialog"
                >
                  <el-icon><Plus /></el-icon>
                  添加
                </el-button>
              </div>

              <div class="relationship-list">
                <div 
                  v-for="(rel, index) in relationships.slice(0, 5)" 
                  :key="index"
                  class="relationship-item"
                >
                  <div class="rel-content">
                    <span class="rel-node">{{ rel.source }}</span>
                    <el-icon class="rel-arrow"><Right /></el-icon>
                    <span class="rel-type">{{ rel.relation_type }}</span>
                    <el-icon class="rel-arrow"><Right /></el-icon>
                    <span class="rel-node">{{ rel.target }}</span>
                  </div>
                  <div class="rel-actions">
                    <el-button 
                      type="primary" 
                      size="small"
                      link
                      @click="editRelationship(index)"
                    >
                      编辑
                    </el-button>
                    <el-button 
                      type="danger" 
                      size="small"
                      link
                      @click="deleteRelationship(index)"
                    >
                      删除
                    </el-button>
                  </div>
                </div>

                <el-button 
                  v-if="relationships.length > 5"
                  text
                  type="info"
                  @click="showAllRelationships"
                  style="width: 100%; margin-top: 10px;"
                >
                  查看全部 {{ relationships.length }} 个关系
                </el-button>
              </div>
            </div>
          </div>
        </el-card>

        <!-- 构建知识图谱按钮区域 -->
        <div v-if="entities.length > 0 && !graphBuilt" class="build-section">
          <el-button 
            type="success" 
            size="large"
            :loading="building"
            @click="buildKnowledgeGraph"
            class="build-button"
          >
            <el-icon><Connection /></el-icon>
            构建知识图谱
          </el-button>
        </div>
      </div>
    </div>

    <!-- 查看全部实体对话框 -->
    <el-dialog 
      v-model="showAllEntitiesDialog" 
      title="全部实体"
      width="800px"
    >
      <el-table :data="entities" height="500" style="width: 100%">
        <el-table-column prop="name" label="实体名称" width="200" />
        <el-table-column prop="entity_type" label="类型" width="150">
          <template #default="scope">
            <el-tag :type="getEntityTypeColor(scope.row.entity_type)" size="small">
              {{ scope.row.entity_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" />
        <el-table-column label="操作" width="150">
          <template #default="scope">
            <el-button size="small" @click="editEntity(scope.$index)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteEntity(scope.$index)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 查看全部关系对话框 -->
    <el-dialog 
      v-model="showAllRelationshipsDialog" 
      title="全部关系"
      width="900px"
    >
      <el-table :data="relationships" height="500" style="width: 100%">
        <el-table-column prop="source" label="源实体" width="150" />
        <el-table-column prop="relation_type" label="关系类型" width="200" />
        <el-table-column prop="target" label="目标实体" width="150" />
        <el-table-column prop="description" label="描述" />
        <el-table-column label="操作" width="150">
          <template #default="scope">
            <el-button size="small" @click="editRelationship(scope.$index)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteRelationship(scope.$index)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 编辑实体对话框 -->
    <el-dialog 
      v-model="showEntityDialog" 
      :title="editingEntityIndex === -1 ? '添加实体' : '编辑实体'"
      width="600px"
    >
      <el-form :model="editingEntity" label-width="100px">
        <el-form-item label="实体名称">
          <el-input v-model="editingEntity.name" placeholder="请输入实体名称" />
        </el-form-item>
        <el-form-item label="实体类型">
          <el-select v-model="editingEntity.entity_type" placeholder="请选择类型" style="width: 100%;">
            <el-option label="疾病 (Disease)" value="Disease" />
            <el-option label="症状 (Symptom)" value="Symptom" />
            <el-option label="检查 (Test)" value="Test" />
            <el-option label="治疗 (Treatment)" value="Treatment" />
            <el-option label="病原体 (Pathogen)" value="Pathogen" />
            <el-option label="风险因素 (RiskFactor)" value="RiskFactor" />
            <el-option label="鉴别诊断 (DifferentialDiagnosis)" value="DifferentialDiagnosis" />
            <el-option label="文献来源 (LiteratureSource)" value="LiteratureSource" />
          </el-select>
        </el-form-item>
        <el-form-item label="实体描述">
          <el-input 
            v-model="editingEntity.description" 
            type="textarea" 
            :rows="4"
            placeholder="请输入实体描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEntityDialog = false">取消</el-button>
        <el-button type="primary" @click="saveEntity">保存</el-button>
      </template>
    </el-dialog>

    <!-- 编辑关系对话框 -->
    <el-dialog 
      v-model="showRelationDialog" 
      :title="editingRelationIndex === -1 ? '添加关系' : '编辑关系'"
      width="600px"
    >
      <el-form :model="editingRelation" label-width="100px">
        <el-form-item label="源实体">
          <el-select v-model="editingRelation.source" placeholder="请选择源实体" filterable style="width: 100%;">
            <el-option 
              v-for="entity in entities" 
              :key="entity.name"
              :label="entity.name"
              :value="entity.name"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="关系类型">
          <el-select v-model="editingRelation.relation_type" placeholder="请选择关系类型" style="width: 100%;">
            <el-option label="具有症状 (HAS_SYMPTOM)" value="HAS_SYMPTOM" />
            <el-option label="通过诊断 (DIAGNOSED_BY)" value="DIAGNOSED_BY" />
            <el-option label="使用治疗 (TREATED_WITH)" value="TREATED_WITH" />
            <el-option label="由...引起 (CAUSED_BY)" value="CAUSED_BY" />
            <el-option label="具有风险因素 (HAS_RISK_FACTOR)" value="HAS_RISK_FACTOR" />
            <el-option label="鉴别诊断 (DIFFERENTIAL_DIAGNOSIS)" value="DIFFERENTIAL_DIAGNOSIS" />
            <el-option label="来源于 (SOURCE_FROM)" value="SOURCE_FROM" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标实体">
          <el-select v-model="editingRelation.target" placeholder="请选择目标实体" filterable style="width: 100%;">
            <el-option 
              v-for="entity in entities" 
              :key="entity.name"
              :label="entity.name"
              :value="entity.name"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="关系描述">
          <el-input 
            v-model="editingRelation.description" 
            type="textarea" 
            :rows="3"
            placeholder="请输入关系描述（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRelationDialog = false">取消</el-button>
        <el-button type="primary" @click="saveRelationship">保存</el-button>
      </template>
    </el-dialog>

    <!-- 上传文件对话框 -->
    <el-dialog
      v-model="showUploadDialog"
      title="上传新文件"
      width="600px"
    >
      <el-upload
        ref="uploadRef"
        class="upload-area"
        drag
        :auto-upload="false"
        :on-change="handleFileChange"
        :limit="1"
        accept=".pdf"
        :file-list="fileList"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          拖拽文件到此处<br/>或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持PDF格式
          </div>
        </template>
      </el-upload>
      
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button 
          type="primary" 
          :loading="uploading"
          @click="uploadFile"
          :disabled="!selectedFile"
        >
          <el-icon v-if="!uploading"><Upload /></el-icon>
          {{ uploading ? '处理中...' : '开始处理' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 全屏知识图谱对话框 -->
    <el-dialog
      v-model="showGraphFullscreen"
      title="知识图谱全屏展示"
      fullscreen
      :show-close="false"
      class="fullscreen-graph-dialog"
    >
      <template #header>
        <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <el-icon style="font-size: 20px;"><Connection /></el-icon>
            <span style="font-size: 18px; font-weight: bold;">{{ documentName }} - 知识图谱</span>
          </div>
          <div style="display: flex; gap: 10px;">
            <el-button type="success" size="small" @click="exportGraph">
              <el-icon><Download /></el-icon>
              导出JSON
            </el-button>
            <el-button type="primary" size="small" @click="exportGraphImage">
              <el-icon><Download /></el-icon>
              导出图片
            </el-button>
            <el-button size="small" @click="closeFullscreenGraph">
              <el-icon><Close /></el-icon>
              关闭
            </el-button>
          </div>
        </div>
      </template>
      
      <div 
        ref="graphContainerFullscreen"
        class="fullscreen-graph-container"
      ></div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, h } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Upload, UploadFilled, Document, Edit, Connection, 
  Tickets, Plus, Right, Download, RefreshLeft, Back,
  CircleCheck, CircleClose, User, Search, FullScreen, Close,
  Delete, Setting, Refresh, DataAnalysis, Warning
} from '@element-plus/icons-vue'
import { 
  uploadDocument, 
  extractEntities, 
  buildKnowledgeGraph as buildGraph,
  exportKnowledgeGraph,
  listKnowledgeDocuments,
  loadKnowledgeDocument,
  deleteKnowledgeDocument,
  syncMetadata,
  getStorageStats,
  cleanupOrphanedResources
} from '../api/knowledge'
import * as echarts from 'echarts'

// 文件相关
const uploadRef = ref(null)
const fileList = ref([])
const selectedFile = ref(null)
const uploading = ref(false)
const documentName = ref('')
const processing = ref(false)

// 搜索相关
const searchKeyword = ref('')  // 搜索关键词，初始为空
const allDocuments = ref([])   // 所有文档列表
const loadingDocuments = ref(false)  // 是否正在加载

// 数据管理相关
const syncing = ref(false)  // 是否正在同步

// HTML数据
const htmlData = ref({
  raw: '',
  cleaned: ''
})
const htmlViewMode = ref('cleaned')
// HTML的Blob URL用于iframe显示
const htmlBlobUrls = ref({
  raw: null,
  cleaned: null
})

// 实体和关系
const entities = ref([])
const relationships = ref([])
const extracting = ref(false)

// 知识图谱
const graphBuilt = ref(false)
const building = ref(false)
const graphContainer = ref(null)
const graphContainerFullscreen = ref(null) // 全屏模式下的容器
const showGraphFullscreen = ref(false) // 是否显示全屏图谱
let graphChart = null // ECharts 实例
let graphChartFullscreen = null // 全屏模式的ECharts实例

// 对话框
const showUploadDialog = ref(false)  // 上传文件对话框
const showAllEntitiesDialog = ref(false)
const showAllRelationshipsDialog = ref(false)
const showEntityDialog = ref(false)
const showRelationDialog = ref(false)
const editingEntityIndex = ref(-1)
const editingRelationIndex = ref(-1)
const editingEntity = ref({
  name: '',
  entity_type: '',
  description: ''
})
const editingRelation = ref({
  source: '',
  target: '',
  relation_type: '',
  description: ''
})

// 计算属性
const currentHtmlContent = computed(() => {
  return htmlViewMode.value === 'raw' ? htmlData.value.raw : htmlData.value.cleaned
})

// 当前HTML的Blob URL
const currentHtmlBlobUrl = computed(() => {
  return htmlViewMode.value === 'raw' ? htmlBlobUrls.value.raw : htmlBlobUrls.value.cleaned
})

// 创建HTML的Blob URL
const createHtmlBlobUrl = (htmlContent) => {
  if (!htmlContent) return null
  const blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8' })
  return URL.createObjectURL(blob)
}

// 清理旧的Blob URL
const cleanupBlobUrls = () => {
  if (htmlBlobUrls.value.raw) {
    URL.revokeObjectURL(htmlBlobUrls.value.raw)
  }
  if (htmlBlobUrls.value.cleaned) {
    URL.revokeObjectURL(htmlBlobUrls.value.cleaned)
  }
  htmlBlobUrls.value = { raw: null, cleaned: null }
}

// 过滤后的文档列表
const filteredDocuments = computed(() => {
  if (!searchKeyword.value || searchKeyword.value.trim() === '') {
    return allDocuments.value
  }
  return allDocuments.value.filter(doc => 
    doc.name.toLowerCase().includes(searchKeyword.value.toLowerCase())
  )
})

// 加载所有已处理的文档
const loadAllDocuments = async () => {
  loadingDocuments.value = true
  try {
    const response = await listKnowledgeDocuments()
    allDocuments.value = response.documents || []
  } catch (error) {
    console.error('加载文档列表失败:', error)
    ElMessage.error('加载文档列表失败: ' + (error.message || '未知错误'))
  } finally {
    loadingDocuments.value = false
  }
}

// 处理搜索
const handleSearch = () => {
  // 搜索逻辑在计算属性中处理
}

// 加载选中的文档
const loadDocument = async (doc) => {
  try {
    // 先检查是否已有知识图谱，如果有则提示正在加载图谱
    if (doc.has_graph) {
      ElMessage.info(`正在加载知识图谱: ${doc.name}`)
    } else {
      ElMessage.info(`正在加载文档: ${doc.name}`)
    }
    
    // 调用后端API加载文档详细信息
    const response = await loadKnowledgeDocument(doc.name)
    
    // 清理旧的Blob URL
    cleanupBlobUrls()
    
    // 更新文档基本信息
    documentName.value = response.document_name
    htmlData.value = {
      raw: response.html_raw || '',
      cleaned: response.html_cleaned || ''
    }
    
    // 创建新的Blob URL用于iframe显示
    htmlBlobUrls.value = {
      raw: createHtmlBlobUrl(response.html_raw),
      cleaned: createHtmlBlobUrl(response.html_cleaned)
    }
    
    entities.value = response.entities || []
    relationships.value = response.relationships || []
    
    // 兜底处理：如果has_knowledge_graph字段不存在，但有实体和关系数据，就认为有图谱
    const hasGraph = response.has_knowledge_graph !== false && 
                     entities.value.length > 0 && 
                     relationships.value.length > 0
    
    // 关键判断：如果文档已有知识图谱，直接显示图谱视图
    if (hasGraph) {
      // 立即设置为已构建状态，在右侧显示知识图谱
      graphBuilt.value = true
      
      // 等待DOM更新后渲染图谱
      await nextTick()
      renderGraph()
      
      ElMessage.success({
        message: `已加载知识图谱: ${doc.name}`,
        duration: 2000,
        showClose: true
      })
    } else {
      // 没有知识图谱，显示编辑界面
      graphBuilt.value = false
      
      // 检查HTML内容是否加载成功
      if (!response.html_raw && !response.html_cleaned) {
        ElMessage.warning('文档加载成功，但HTML内容为空')
      } else {
        ElMessage.success(`已加载文档: ${doc.name}，可以开始实体抽取`)
      }
    }
  } catch (error) {
    console.error('加载文档失败:', error)
    ElMessage.error('加载文档失败: ' + (error.response?.data?.detail || error.message))
  }
}

// 文件处理
const handleFileChange = (file) => {
  selectedFile.value = file.raw
  fileList.value = [file]
  console.log('选择文件:', file.name)
}

// 组件挂载时加载文档列表
onMounted(() => {
  loadAllDocuments()
})

// 上传文件并开始处理
const uploadFile = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }

  uploading.value = true
  processing.value = true

  try {
    ElMessage.info('正在上传文件并解析...')
    
    const response = await uploadDocument(selectedFile.value)

    console.log('上传文档响应:', {
      document_name: response.document_name,
      html_raw_length: response.html_raw?.length || 0,
      html_cleaned_length: response.html_cleaned?.length || 0
    })

    // 清理旧的Blob URL
    cleanupBlobUrls()
    
    documentName.value = response.document_name
    // 使用整体赋值确保响应式更新
    htmlData.value = {
      raw: response.html_raw || '',
      cleaned: response.html_cleaned || ''
    }
    
    // 创建新的Blob URL用于iframe显示
    htmlBlobUrls.value = {
      raw: createHtmlBlobUrl(response.html_raw),
      cleaned: createHtmlBlobUrl(response.html_cleaned)
    }

    // 检查HTML内容
    if (!response.html_raw && !response.html_cleaned) {
      ElMessage.warning('文件上传成功，但HTML内容为空')
    } else {
      ElMessage.success('文件上传成功！HTML已解析')
    }
    
    // 关闭上传对话框
    showUploadDialog.value = false
    
    // 清空文件列表
    fileList.value = []
    selectedFile.value = null
    
    // 刷新文档列表
    await loadAllDocuments()
    
    // 自动开始实体抽取
    ElMessage.info('文件上传成功，开始自动进行实体抽取...')
    await startEntityExtraction()
  } catch (error) {
    console.error('上传失败:', error)
    ElMessage.error('文件上传失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    uploading.value = false
    processing.value = false
  }
}

// 开始实体抽取
const startEntityExtraction = async () => {
  extracting.value = true

  try {
    ElMessage.info('正在进行实体抽取，这可能需要几分钟...')

    const response = await extractEntities(documentName.value)

    entities.value = response.entities || []
    relationships.value = response.relationships || []

    ElMessage.success(`实体抽取完成！共提取 ${entities.value.length} 个实体，${relationships.value.length} 个关系`)
  } catch (error) {
    console.error('实体抽取失败:', error)
    ElMessage.error('实体抽取失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    extracting.value = false
  }
}

// 实体类型颜色
const getEntityTypeColor = (type) => {
  const colorMap = {
    'Disease': 'danger',
    'Symptom': 'warning',
    'Test': 'info',
    'Treatment': 'success',
    'Pathogen': 'danger',
    'RiskFactor': 'warning',
    'DifferentialDiagnosis': 'info',
    'LiteratureSource': 'primary'
  }
  return colorMap[type] || ''
}

// 显示全部实体
const showAllEntities = () => {
  showAllEntitiesDialog.value = true
}

// 显示全部关系
const showAllRelationships = () => {
  showAllRelationshipsDialog.value = true
}

// 添加实体
const showAddEntityDialog = () => {
  editingEntityIndex.value = -1
  editingEntity.value = { name: '', entity_type: '', description: '' }
  showEntityDialog.value = true
}

// 编辑实体
const editEntity = (index) => {
  editingEntityIndex.value = index
  editingEntity.value = { ...entities.value[index] }
  showEntityDialog.value = true
  showAllEntitiesDialog.value = false
}

// 删除实体
const deleteEntity = async (index) => {
  try {
    await ElMessageBox.confirm('确定要删除这个实体吗？', '提示', {
      type: 'warning'
    })
    entities.value.splice(index, 1)
    ElMessage.success('实体已删除')
  } catch {
    // 用户取消
  }
}

// 保存实体
const saveEntity = () => {
  if (!editingEntity.value.name || !editingEntity.value.entity_type) {
    ElMessage.warning('请填写完整的实体信息')
    return
  }

  if (editingEntityIndex.value === -1) {
    entities.value.push({ ...editingEntity.value })
    ElMessage.success('实体已添加')
  } else {
    entities.value[editingEntityIndex.value] = { ...editingEntity.value }
    ElMessage.success('实体已更新')
  }

  showEntityDialog.value = false
  editingEntityIndex.value = -1
  editingEntity.value = { name: '', entity_type: '', description: '' }
}

// 添加关系
const showAddRelationDialog = () => {
  editingRelationIndex.value = -1
  editingRelation.value = { source: '', target: '', relation_type: '', description: '' }
  showRelationDialog.value = true
}

// 编辑关系
const editRelationship = (index) => {
  editingRelationIndex.value = index
  editingRelation.value = { ...relationships.value[index] }
  showRelationDialog.value = true
  showAllRelationshipsDialog.value = false
}

// 删除关系
const deleteRelationship = async (index) => {
  try {
    await ElMessageBox.confirm('确定要删除这个关系吗？', '提示', {
      type: 'warning'
    })
    relationships.value.splice(index, 1)
    ElMessage.success('关系已删除')
  } catch {
    // 用户取消
  }
}

// 保存关系
const saveRelationship = () => {
  if (!editingRelation.value.source || !editingRelation.value.target || !editingRelation.value.relation_type) {
    ElMessage.warning('请填写完整的关系信息')
    return
  }

  if (editingRelationIndex.value === -1) {
    relationships.value.push({ ...editingRelation.value })
    ElMessage.success('关系已添加')
  } else {
    relationships.value[editingRelationIndex.value] = { ...editingRelation.value }
    ElMessage.success('关系已更新')
  }

  showRelationDialog.value = false
  editingRelationIndex.value = -1
  editingRelation.value = { source: '', target: '', relation_type: '', description: '' }
}

// 构建知识图谱
const buildKnowledgeGraph = async () => {
  building.value = true

  try {
    ElMessage.info('正在构建知识图谱...')

    // 准备实体和关系数据
    const enhancedEntities = [...entities.value]
    const enhancedRelationships = [...relationships.value]

    // 添加文档来源实体（如果不存在）
    const docSourceEntity = {
      name: documentName.value,
      entity_type: 'LiteratureSource',
      description: `医学文献：${documentName.value}`
    }
    
    // 检查是否已存在文档来源实体
    const hasDocSource = enhancedEntities.some(e => 
      e.name === documentName.value && e.entity_type === 'LiteratureSource'
    )
    
    if (!hasDocSource) {
      enhancedEntities.push(docSourceEntity)
      
      // 只为疾病（Disease）实体添加与文档的关系
      const diseaseEntities = entities.value.filter(e => e.entity_type === 'Disease')
      
      diseaseEntities.forEach(entity => {
        // 跳过已有的SOURCE_FROM关系
        const hasSourceRelation = enhancedRelationships.some(r => 
          r.source === entity.name && 
          r.target === documentName.value && 
          r.relation_type === 'SOURCE_FROM'
        )
        
        if (!hasSourceRelation) {
          enhancedRelationships.push({
            source: entity.name,
            target: documentName.value,
            relation_type: 'SOURCE_FROM',
            description: `疾病知识来源于文献《${documentName.value}》`
          })
        }
      })
      
      // 已添加文档来源实体和关系
    }

    // 更新本地数据（包含文档来源）
    entities.value = enhancedEntities
    relationships.value = enhancedRelationships

    const response = await buildGraph(
      documentName.value,
      enhancedEntities,
      enhancedRelationships
    )

    // 立即设置为已构建状态
    graphBuilt.value = true
    
    // 刷新文档列表（更新has_graph标志）
    await loadAllDocuments()

    // 等待DOM更新后渲染图谱
    await nextTick()
    renderGraph()
    
    ElMessage.success({
      message: '知识图谱构建完成！',
      duration: 3000,
      showClose: true
    })
  } catch (error) {
    console.error('知识图谱构建失败:', error)
    ElMessage.error('知识图谱构建失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    building.value = false
  }
}

// 渲染知识图谱 - 使用 ECharts
const renderGraph = () => {
  const container = graphContainer.value
  if (!container) return

  // 清空容器
  container.innerHTML = ''

  // 创建统计信息区域
  const statsDiv = document.createElement('div')
  statsDiv.style.cssText = 'padding: 15px; background: #f0f9ff; border-radius: 8px; margin-bottom: 15px;'
  
  const entityTypeCounts = {}
  entities.value.forEach(entity => {
    const type = entity.entity_type
    entityTypeCounts[type] = (entityTypeCounts[type] || 0) + 1
  })

  statsDiv.innerHTML = `
    <h3 style="margin: 0 0 12px 0; color: #303133; font-size: 16px;">📊 知识图谱统计</h3>
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px;">
      <div style="background: white; padding: 12px; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <div style="font-size: 20px; font-weight: bold; color: #409eff;">${entities.value.length}</div>
        <div style="color: #909399; margin-top: 3px; font-size: 12px;">实体</div>
      </div>
      <div style="background: white; padding: 12px; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <div style="font-size: 20px; font-weight: bold; color: #67c23a;">${relationships.value.length}</div>
        <div style="color: #909399; margin-top: 3px; font-size: 12px;">关系</div>
      </div>
      <div style="background: white; padding: 12px; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <div style="font-size: 20px; font-weight: bold; color: #e6a23c;">${Object.keys(entityTypeCounts).length}</div>
        <div style="color: #909399; margin-top: 3px; font-size: 12px;">类型</div>
      </div>
    </div>
  `
  container.appendChild(statsDiv)

  // 创建 ECharts 图表容器
  const chartDiv = document.createElement('div')
  chartDiv.style.cssText = 'width: 100%; height: 500px; background: white; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.1);'
  container.appendChild(chartDiv)

  // 销毁旧的图表实例
  if (graphChart) {
    graphChart.dispose()
  }

  // 初始化 ECharts
  graphChart = echarts.init(chartDiv)

  // 定义实体类型颜色映射
  const typeColors = {
    'Disease': '#f56c6c',
    'Symptom': '#e6a23c',
    'Test': '#409eff',
    'Treatment': '#67c23a',
    'Pathogen': '#f56c6c',
    'RiskFactor': '#e6a23c',
    'DifferentialDiagnosis': '#409eff',
    'LiteratureSource': '#909399'
  }

  // 转换实体数据为 ECharts 节点格式
  // 先去重，避免重复节点导致ECharts报错
  const uniqueEntitiesMap = new Map()
  entities.value.forEach(entity => {
    const key = `${entity.name}_${entity.entity_type}` // 使用名称+类型作为唯一键
    if (!uniqueEntitiesMap.has(key)) {
      uniqueEntitiesMap.set(key, entity)
    } else {
      // 如果有重复，保留描述更长的版本
      const existing = uniqueEntitiesMap.get(key)
      if ((entity.description?.length || 0) > (existing.description?.length || 0)) {
        uniqueEntitiesMap.set(key, entity)
      }
    }
  })
  
  const uniqueEntities = Array.from(uniqueEntitiesMap.values())
  
  // 如果发现有重复实体，给出警告
  if (uniqueEntities.length < entities.value.length) {
    const duplicateCount = entities.value.length - uniqueEntities.length
    console.warn(`⚠️ 发现 ${duplicateCount} 个重复实体已自动去重`)
  }
  
  const nodes = uniqueEntities.map(entity => ({
    id: entity.name,
    name: entity.name,
    category: entity.entity_type,
    symbolSize: 50, // 统一节点大小
    itemStyle: {
      color: typeColors[entity.entity_type] || '#909399'
    },
    label: {
      show: true
    },
    tooltip: {
      formatter: () => {
        const relCount = relationships.value.filter(r => 
          r.source === entity.name || r.target === entity.name
        ).length
        return `
          <div style="padding: 8px;">
            <div style="font-weight: bold; font-size: 14px; margin-bottom: 6px;">${entity.name}</div>
            <div style="color: #666; font-size: 12px; margin-bottom: 4px;">类型: ${entity.entity_type}</div>
            <div style="color: #666; font-size: 12px; margin-bottom: 4px;">关系数: ${relCount}</div>
            ${entity.description ? `<div style="color: #999; font-size: 12px; max-width: 300px; margin-top: 6px; border-top: 1px solid #eee; padding-top: 6px;">${entity.description}</div>` : ''}
          </div>
        `
      }
    }
  }))

  // 转换关系数据为 ECharts 边格式
  // 创建节点名称集合用于验证
  const nodeNames = new Set(uniqueEntities.map(e => e.name))
  
  // 去重和验证关系
  const validLinks = []
  const seenRelations = new Set()
  let invalidRelCount = 0
  
  relationships.value.forEach(rel => {
    // 验证source和target是否存在
    if (!nodeNames.has(rel.source) || !nodeNames.has(rel.target)) {
      invalidRelCount++
      return
    }
    
    // 去重（基于 source-target-relation_type 组合）
    const relKey = `${rel.source}-${rel.target}-${rel.relation_type}`
    if (seenRelations.has(relKey)) {
      return
    }
    seenRelations.add(relKey)
    
    validLinks.push({
      source: rel.source,
      target: rel.target,
      label: {
        show: false, // 默认不显示关系标签，提升性能
        formatter: rel.relation_type,
        fontSize: 10
      },
      lineStyle: {
        curveness: 0.2,
        width: 1.5
      },
      tooltip: {
        formatter: () => {
          return `
            <div style="padding: 8px;">
              <div style="font-weight: bold; font-size: 13px; margin-bottom: 6px;">${rel.source} → ${rel.target}</div>
              <div style="color: #67c23a; font-size: 12px; margin-bottom: 4px;">关系: ${rel.relation_type}</div>
              ${rel.description ? `<div style="color: #999; font-size: 12px; max-width: 300px;">${rel.description}</div>` : ''}
            </div>
          `
        }
      }
    })
  })
  
  // 如果有无效关系，给出警告
  if (invalidRelCount > 0) {
    console.warn(`⚠️ 发现 ${invalidRelCount} 个无效关系（节点不存在）已忽略`)
  }
  if (validLinks.length < relationships.value.length - invalidRelCount) {
    const dupRelCount = relationships.value.length - invalidRelCount - validLinks.length
    console.warn(`⚠️ 发现 ${dupRelCount} 个重复关系已去重`)
  }
  
  const links = validLinks

  // 创建分类数据
  const categories = Object.keys(entityTypeCounts).map(type => ({
    name: type,
    itemStyle: {
      color: typeColors[type] || '#909399'
    }
  }))

  // 配置 ECharts 选项
  const option = {
    title: {
      text: '知识图谱可视化',
      left: 'center',
      top: 10,
      textStyle: {
        fontSize: 16,
        fontWeight: 'bold'
      }
    },
    tooltip: {
      trigger: 'item',
      confine: true, // 限制tooltip在图表区域内
      renderMode: 'richText' // 使用更高效的渲染模式
    },
    animation: true,
    animationDuration: 1000,
    animationEasing: 'cubicOut',
    legend: [{
      data: categories.map(c => c.name),
      orient: 'vertical',
      left: 10,
      top: 50,
      textStyle: {
        fontSize: 11
      }
    }],
    series: [{
      type: 'graph',
      layout: 'force',
      data: nodes,
      links: links,
      categories: categories,
      roam: true,
      draggable: true,
      focusNodeAdjacency: true, // 鼠标悬停时高亮相邻节点
      label: {
        position: 'right',
        formatter: '{b}',
        fontSize: 11,
        show: true
      },
      edgeLabel: {
        show: false, // 默认不显示边标签
        fontSize: 10
      },
      force: {
        repulsion: 500, // 增加斥力
        edgeLength: [180, 300], // 增加边长范围
        gravity: 0.06, // 降低引力
        layoutAnimation: true,
        friction: 0.6
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: {
          width: 4
        }
      },
      lineStyle: {
        color: 'source',
        curveness: 0.2
      }
    }]
  }

  // 设置图表配置
  graphChart.setOption(option)

  // 添加控制提示
  const tipDiv = document.createElement('div')
  tipDiv.style.cssText = 'margin-top: 15px; padding: 12px; background: #e6f7ff; border-radius: 8px; color: #0050b3; font-size: 12px;'
  tipDiv.innerHTML = `
    <div style="display: flex; align-items: center; gap: 8px;">
      <span style="font-size: 16px;">💡</span>
      <div>
        <strong>交互提示:</strong> 
        可以拖拽节点调整位置 · 滚轮缩放 · 鼠标悬停查看详情 · 点击节点高亮关联关系
      </div>
    </div>
  `
  container.appendChild(tipDiv)

  // 窗口大小改变时重新调整图表
  window.addEventListener('resize', () => {
    if (graphChart) {
      graphChart.resize()
    }
  })
}

// 导出图谱JSON
const exportGraph = async () => {
  try {
    const blob = await exportKnowledgeGraph(documentName.value)

    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `${documentName.value}_knowledge_graph.json`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)

    ElMessage.success('JSON文件已导出')
  } catch (error) {
    console.error('导出失败:', error)
    ElMessage.error('JSON导出失败')
  }
}

// 导出图谱图片
const exportGraphImage = () => {
  // 优先使用全屏图表，如果没有则使用预览图表
  const chart = graphChartFullscreen || graphChart
  
  if (!chart) {
    ElMessage.warning('请先构建知识图谱')
    return
  }

  try {
    // 获取图表的base64图片
    const imageUrl = chart.getDataURL({
      type: 'png',
      pixelRatio: 2, // 提高清晰度
      backgroundColor: '#fff'
    })

    // 创建下载链接
    const link = document.createElement('a')
    link.href = imageUrl
    link.download = `${documentName.value}_knowledge_graph.png`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)

    ElMessage.success('图片已导出')
  } catch (error) {
    console.error('导出图片失败:', error)
    ElMessage.error('图片导出失败')
  }
}

// 切换到编辑模式
const switchToEditMode = () => {
  graphBuilt.value = false
  ElMessage.info('已切换到编辑模式，您可以修改实体和关系')
}

// 打开全屏知识图谱
const openFullscreenGraph = async () => {
  if (entities.value.length === 0) {
    ElMessage.warning('没有可显示的知识图谱数据')
    return
  }
  
  showGraphFullscreen.value = true
  
  // 等待对话框打开和DOM更新
  await nextTick()
  
  // 延迟确保对话框完全打开和过渡动画完成
  setTimeout(() => {
    renderFullscreenGraph()
  }, 300)
}

// 关闭全屏知识图谱
const closeFullscreenGraph = () => {
  // 销毁全屏图表实例
  if (graphChartFullscreen) {
    graphChartFullscreen.dispose()
    graphChartFullscreen = null
  }
  
  showGraphFullscreen.value = false
}

// 渲染全屏知识图谱
const renderFullscreenGraph = () => {
  const container = graphContainerFullscreen.value
  if (!container) {
    console.error('全屏图表容器未找到')
    ElMessage.error('无法找到图表容器，请重试')
    return
  }

  console.log('全屏容器尺寸:', container.clientWidth, 'x', container.clientHeight)
  
  if (container.clientWidth === 0 || container.clientHeight === 0) {
    console.error('容器尺寸为0，延迟重试...')
    setTimeout(renderFullscreenGraph, 200)
    return
  }

  // 清空容器
  container.innerHTML = ''

  // 创建图表容器div
  const chartDiv = document.createElement('div')
  chartDiv.style.cssText = 'width: 100%; height: 100%; min-height: calc(100vh - 120px);'
  container.appendChild(chartDiv)

  // 销毁旧的图表实例
  if (graphChartFullscreen) {
    graphChartFullscreen.dispose()
    graphChartFullscreen = null
  }

  // 初始化 ECharts
  graphChartFullscreen = echarts.init(chartDiv)
  
  console.log('ECharts实例已创建')

  // 定义实体类型颜色映射
  const typeColors = {
    'Disease': '#f56c6c',
    'Symptom': '#e6a23c',
    'Test': '#409eff',
    'Treatment': '#67c23a',
    'Pathogen': '#f56c6c',
    'RiskFactor': '#e6a23c',
    'DifferentialDiagnosis': '#409eff',
    'LiteratureSource': '#909399'
  }

  // 统计实体类型
  const entityTypeCounts = {}
  entities.value.forEach(entity => {
    const type = entity.entity_type
    entityTypeCounts[type] = (entityTypeCounts[type] || 0) + 1
  })

  // 转换实体数据为 ECharts 节点格式
  // 先去重，避免重复节点导致ECharts报错
  const uniqueEntitiesMap = new Map()
  entities.value.forEach(entity => {
    const key = `${entity.name}_${entity.entity_type}`
    if (!uniqueEntitiesMap.has(key)) {
      uniqueEntitiesMap.set(key, entity)
    } else {
      const existing = uniqueEntitiesMap.get(key)
      if ((entity.description?.length || 0) > (existing.description?.length || 0)) {
        uniqueEntitiesMap.set(key, entity)
      }
    }
  })
  
  const uniqueEntities = Array.from(uniqueEntitiesMap.values())
  
  if (uniqueEntities.length < entities.value.length) {
    const duplicateCount = entities.value.length - uniqueEntities.length
    console.warn(`⚠️ [全屏] 发现 ${duplicateCount} 个重复实体已自动去重`)
  }
  
  const nodes = uniqueEntities.map(entity => ({
    id: entity.name,
    name: entity.name,
    category: entity.entity_type,
    symbolSize: 60, // 统一节点大小（全屏模式稍大）
    itemStyle: {
      color: typeColors[entity.entity_type] || '#909399'
    },
    label: {
      show: true,
      fontSize: 13
    },
    tooltip: {
      formatter: () => {
        const relCount = relationships.value.filter(r => 
          r.source === entity.name || r.target === entity.name
        ).length
        return `
          <div style="padding: 10px;">
            <div style="font-weight: bold; font-size: 16px; margin-bottom: 8px;">${entity.name}</div>
            <div style="color: #666; font-size: 13px; margin-bottom: 6px;">类型: ${entity.entity_type}</div>
            <div style="color: #666; font-size: 13px; margin-bottom: 6px;">关系数: ${relCount}</div>
            ${entity.description ? `<div style="color: #999; font-size: 13px; max-width: 400px; margin-top: 8px; border-top: 1px solid #eee; padding-top: 8px;">${entity.description}</div>` : ''}
          </div>
        `
      }
    }
  }))

  // 转换关系数据为 ECharts 边格式
  // 验证和去重关系
  const nodeNames = new Set(uniqueEntities.map(e => e.name))
  const validLinks = []
  const seenRelations = new Set()
  let invalidRelCount = 0
  
  relationships.value.forEach(rel => {
    if (!nodeNames.has(rel.source) || !nodeNames.has(rel.target)) {
      invalidRelCount++
      return
    }
    
    const relKey = `${rel.source}-${rel.target}-${rel.relation_type}`
    if (seenRelations.has(relKey)) {
      return
    }
    seenRelations.add(relKey)
    
    validLinks.push({
      source: rel.source,
      target: rel.target,
      label: {
        show: false, // 默认不显示，悬停时通过tooltip显示
        formatter: rel.relation_type,
        fontSize: 12
      },
      lineStyle: {
        curveness: 0.2,
        width: 2
      },
      tooltip: {
        formatter: () => {
          return `
            <div style="padding: 10px;">
              <div style="font-weight: bold; font-size: 15px; margin-bottom: 8px;">${rel.source} → ${rel.target}</div>
              <div style="color: #67c23a; font-size: 13px; margin-bottom: 6px;">关系: ${rel.relation_type}</div>
              ${rel.description ? `<div style="color: #999; font-size: 13px; max-width: 400px;">${rel.description}</div>` : ''}
            </div>
          `
        }
      }
    })
  })
  
  if (invalidRelCount > 0) {
    console.warn(`⚠️ [全屏] 发现 ${invalidRelCount} 个无效关系（节点不存在）已忽略`)
  }
  
  const links = validLinks

  // 创建分类数据
  const categories = Object.keys(entityTypeCounts).map(type => ({
    name: type,
    itemStyle: {
      color: typeColors[type] || '#909399'
    }
  }))

  // 配置 ECharts 选项（全屏版本）
  const option = {
    title: {
      text: '知识图谱可视化（全屏模式）',
      subtext: `${uniqueEntities.length} 个实体 · ${validLinks.length} 个关系 · ${Object.keys(entityTypeCounts).length} 种类型`,
      left: 'center',
      top: 20,
      textStyle: {
        fontSize: 24,
        fontWeight: 'bold'
      },
      subtextStyle: {
        fontSize: 14,
        color: '#999'
      }
    },
    tooltip: {
      trigger: 'item',
      confine: true,
      renderMode: 'richText'
    },
    animation: true,
    animationDuration: 1500,
    animationEasing: 'cubicOut',
    progressive: 200, // 渐进式渲染，每次渲染200个图形
    progressiveThreshold: 500, // 当数据量大于500时启用渐进式渲染
    legend: [{
      data: categories.map(c => c.name),
      orient: 'vertical',
      left: 20,
      top: 100,
      textStyle: {
        fontSize: 13
      },
      backgroundColor: 'rgba(255, 255, 255, 0.9)',
      borderRadius: 8,
      padding: 10
    }],
    series: [{
      type: 'graph',
      layout: 'force',
      data: nodes,
      links: links,
      categories: categories,
      roam: true,
      draggable: true,
      focusNodeAdjacency: true,
      label: {
        position: 'right',
        formatter: '{b}',
        fontSize: 14,
        show: true
      },
      edgeLabel: {
        show: false,
        fontSize: 11
      },
      force: {
        repulsion: 800, // 显著增加斥力，让节点更分散
        edgeLength: [250, 400], // 大幅增加边长范围
        gravity: 0.02, // 降低引力
        layoutAnimation: true, // 开启布局动画
        friction: 0.6 // 增加摩擦力，减少震荡
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: {
          width: 5
        }
      },
      lineStyle: {
        color: 'source',
        curveness: 0.2
      }
    }]
  }

  // 设置图表配置
  try {
    graphChartFullscreen.setOption(option)
    console.log('✓ 图表配置已设置，节点数:', nodes.length, '边数:', links.length)
  } catch (error) {
    console.error('设置图表配置失败:', error)
    ElMessage.error('渲染图表失败: ' + error.message)
    return
  }

  // 立即调整图表大小以适应容器
  setTimeout(() => {
    if (graphChartFullscreen) {
      graphChartFullscreen.resize()
      console.log('✓ 图表已resize (50ms)')
    }
  }, 50)
  
  // 再次确保大小正确
  setTimeout(() => {
    if (graphChartFullscreen) {
      graphChartFullscreen.resize()
      console.log('✓ 图表已resize (200ms)')
    }
  }, 200)
  
  console.log('✓ 全屏图谱渲染完成')
}

// 重置工作流
const resetWorkflow = () => {
  // 清理Blob URL
  cleanupBlobUrls()
  
  selectedFile.value = null
  fileList.value = []
  documentName.value = ''
  htmlData.value = { raw: '', cleaned: '' }
  entities.value = []
  relationships.value = []
  graphBuilt.value = false
  ElMessage.success('已重置，可以重新开始')
}

// 组件卸载时清理Blob URL和图表实例
onUnmounted(() => {
  cleanupBlobUrls()
  if (graphChart) {
    graphChart.dispose()
    graphChart = null
  }
})

// ============================================================================
// 数据管理功能
// ============================================================================

/**
 * 删除文档及其所有资源
 */
const handleDeleteDocument = async (docName) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除文档"${docName}"吗？`,
      '删除确认',
      {
        type: 'warning',
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        distinguishCancelAndClose: true,
        message: h('div', null, [
          h('p', { style: 'margin-bottom: 10px; font-weight: bold;' }, '⚠️ 此操作将删除以下资源：'),
          h('ul', { style: 'margin-left: 20px; color: #606266;' }, [
            h('li', '📁 文件夹及所有文件'),
            h('li', '🔍 Redis向量索引'),
            h('li', '🕸️ Neo4j知识图谱节点'),
          ]),
          h('p', { style: 'margin-top: 10px; color: #f56c6c;' }, '此操作不可恢复！')
        ])
      }
    )
    
    // 执行删除
    ElMessage.info(`正在删除文档: ${docName}...`)
    
    const result = await deleteKnowledgeDocument(docName, true, true, true)
    
    if (result.success) {
      ElMessage.success({
        message: '文档删除成功！',
        duration: 3000
      })
      
      // 如果删除的是当前文档，清空显示
      if (documentName.value === docName) {
        documentName.value = ''
        cleanupBlobUrls()
        htmlData.value = { raw: '', cleaned: '' }
        entities.value = []
        relationships.value = []
        graphBuilt.value = false
      }
      
      // 刷新文档列表
      await loadAllDocuments()
    } else {
      ElMessage.error({
        message: `删除失败: ${result.message}`,
        duration: 5000
      })
    }
    
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error('删除文档失败:', error)
      ElMessage.error(`删除失败: ${error.message || '未知错误'}`)
    }
  }
}

/**
 * 同步元数据
 */
const handleSyncMetadata = async () => {
  try {
    syncing.value = true
    ElMessage.info('正在同步元数据...')
    
    const result = await syncMetadata()
    
    if (result.success) {
      ElMessage.success({
        message: `元数据同步完成！共 ${result.stats.total_documents} 个文档`,
        duration: 3000
      })
      
      // 刷新文档列表
      await loadAllDocuments()
    } else {
      ElMessage.error('同步失败')
    }
    
  } catch (error) {
    console.error('同步元数据失败:', error)
    ElMessage.error(`同步失败: ${error.message || '未知错误'}`)
  } finally {
    syncing.value = false
  }
}

/**
 * 查看统计信息
 */
const handleShowStats = async () => {
  try {
    const stats = await getStorageStats()
    
    // 构建统计信息HTML
    const statsHtml = h('div', null, [
      h('div', { style: 'margin-bottom: 20px;' }, [
        h('div', { style: 'display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px;' }, [
          h('div', { style: 'text-align: center; padding: 15px; background: #e6f7ff; border-radius: 8px;' }, [
            h('div', { style: 'font-size: 24px; font-weight: bold; color: #1890ff;' }, stats.total_documents),
            h('div', { style: 'color: #666; margin-top: 5px; font-size: 12px;' }, '文档总数')
          ]),
          h('div', { style: 'text-align: center; padding: 15px; background: #f0f9ff; border-radius: 8px;' }, [
            h('div', { style: 'font-size: 24px; font-weight: bold; color: ' + (stats.redis_available ? '#52c41a' : '#ff4d4f') }, stats.redis_available ? '✓' : '✗'),
            h('div', { style: 'color: #666; margin-top: 5px; font-size: 12px;' }, 'Redis状态')
          ]),
          h('div', { style: 'text-align: center; padding: 15px; background: #f6ffed; border-radius: 8px;' }, [
            h('div', { style: 'font-size: 24px; font-weight: bold; color: ' + (stats.neo4j_available ? '#52c41a' : '#ff4d4f') }, stats.neo4j_available ? '✓' : '✗'),
            h('div', { style: 'color: #666; margin-top: 5px; font-size: 12px;' }, 'Neo4j状态')
          ])
        ])
      ]),
      h('div', { style: 'max-height: 300px; overflow-y: auto;' }, [
        h('h4', { style: 'margin: 0 0 10px 0; color: #303133;' }, '文档列表：'),
        h('table', { style: 'width: 100%; border-collapse: collapse;' }, [
          h('thead', null, [
            h('tr', { style: 'background: #fafafa;' }, [
              h('th', { style: 'padding: 8px; text-align: left; border-bottom: 2px solid #e8e8e8;' }, '文档名称'),
              h('th', { style: 'padding: 8px; text-align: center; border-bottom: 2px solid #e8e8e8;' }, '实体'),
              h('th', { style: 'padding: 8px; text-align: center; border-bottom: 2px solid #e8e8e8;' }, '关系'),
              h('th', { style: 'padding: 8px; text-align: center; border-bottom: 2px solid #e8e8e8;' }, 'Redis索引')
            ])
          ]),
          h('tbody', null, stats.documents.map(doc => 
            h('tr', { style: 'border-bottom: 1px solid #f0f0f0;' }, [
              h('td', { style: 'padding: 8px; font-size: 12px;' }, doc.name),
              h('td', { style: 'padding: 8px; text-align: center; color: #1890ff; font-weight: bold;' }, doc.entity_count),
              h('td', { style: 'padding: 8px; text-align: center; color: #52c41a; font-weight: bold;' }, doc.relationship_count),
              h('td', { style: 'padding: 8px; text-align: center; color: #722ed1; font-weight: bold;' }, doc.redis_indices)
            ])
          ))
        ])
      ])
    ])
    
    ElMessageBox({
      title: '📊 存储统计信息',
      message: statsHtml,
      confirmButtonText: '关闭',
      type: 'info',
      customClass: 'stats-message-box'
    })
    
  } catch (error) {
    console.error('获取统计信息失败:', error)
    ElMessage.error(`获取统计失败: ${error.message || '未知错误'}`)
  }
}

/**
 * 清理孤立资源
 */
const handleCleanupOrphaned = async () => {
  try {
    // 步骤1：先预演，查看有哪些孤立资源
    ElMessage.info('正在扫描孤立资源...')
    
    const previewResult = await cleanupOrphanedResources(true) // dry_run = true
    
    const orphanedRedis = previewResult.result.orphaned_redis_indices || []
    const orphanedNeo4j = previewResult.result.orphaned_neo4j_docs || []
    
    if (orphanedRedis.length === 0 && orphanedNeo4j.length === 0) {
      ElMessage.success({
        message: '✓ 未发现孤立资源，系统数据一致性良好！',
        duration: 3000
      })
      return
    }
    
    // 步骤2：显示发现的孤立资源，让用户确认是否删除
    const confirmMessage = h('div', null, [
      h('p', { style: 'margin-bottom: 15px; font-weight: bold; color: #f56c6c;' }, 
        `⚠️ 发现 ${orphanedRedis.length + orphanedNeo4j.length} 个孤立资源`
      ),
      
      orphanedRedis.length > 0 ? h('div', { style: 'margin-bottom: 15px;' }, [
        h('h4', { style: 'margin: 0 0 8px 0; color: #303133; font-size: 14px;' }, 
          `🔍 Redis孤立索引 (${orphanedRedis.length}个):`
        ),
        h('ul', { style: 'margin: 0; padding-left: 20px; max-height: 150px; overflow-y: auto; background: #f5f7fa; padding: 10px; border-radius: 4px;' }, 
          orphanedRedis.map(idx => 
            h('li', { style: 'color: #666; font-size: 12px; margin-bottom: 5px;' }, idx)
          )
        )
      ]) : null,
      
      orphanedNeo4j.length > 0 ? h('div', { style: 'margin-bottom: 15px;' }, [
        h('h4', { style: 'margin: 0 0 8px 0; color: #303133; font-size: 14px;' }, 
          `🕸️ Neo4j孤立文献 (${orphanedNeo4j.length}个):`
        ),
        h('ul', { style: 'margin: 0; padding-left: 20px; max-height: 150px; overflow-y: auto; background: #f5f7fa; padding: 10px; border-radius: 4px;' }, 
          orphanedNeo4j.map(doc => 
            h('li', { style: 'color: #666; font-size: 12px; margin-bottom: 5px;' }, doc)
          )
        )
      ]) : null,
      
      h('p', { style: 'margin-top: 15px; padding: 10px; background: #fff3cd; border-left: 4px solid #ffc107; color: #856404; font-size: 13px;' }, 
        '这些资源在数据库中存在，但元数据中没有记录，可能是之前删除不彻底导致的。'
      )
    ])
    
    await ElMessageBox.confirm(
      confirmMessage,
      '清理孤立资源',
      {
        type: 'warning',
        confirmButtonText: '确定清理',
        cancelButtonText: '取消',
        distinguishCancelAndClose: true
      }
    )
    
    // 步骤3：执行实际清理
    ElMessage.info('正在清理孤立资源...')
    
    const cleanupResult = await cleanupOrphanedResources(false) // dry_run = false
    
    if (cleanupResult.success) {
      ElMessage.success({
        message: `✓ 清理完成！已删除 ${orphanedRedis.length} 个Redis索引和 ${orphanedNeo4j.length} 个Neo4j文献`,
        duration: 5000
      })
      
      // 刷新文档列表
      await loadAllDocuments()
    } else {
      ElMessage.error('清理失败')
    }
    
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error('清理孤立资源失败:', error)
      ElMessage.error(`清理失败: ${error.message || '未知错误'}`)
    }
  }
}
</script>

<style scoped>
.knowledge-construction {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
  padding: 20px;
  overflow: hidden;
}

/* 三栏布局 */
.main-layout {
  flex: 1;
  display: grid;
  grid-template-columns: 300px 1fr 400px;
  gap: 0;
  overflow: hidden;
}

/* 左侧面板 */
.left-panel {
  display: flex;
  flex-direction: column;
  gap: 15px;
  overflow-y: auto;
  padding-right: 15px;
  border-right: 1px solid #e4e7ed;
}

.upload-button-section {
  flex-shrink: 0;
  padding: 15px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.upload-button-section .el-button {
  background: white;
  border: none;
  color: #667eea;
  font-weight: 600;
  height: 45px;
  font-size: 15px;
}

.upload-button-section .el-button:hover {
  background: #f0f0f0;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.search-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.search-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.upload-area {
  margin-bottom: 10px;
}

.upload-area :deep(.el-upload-dragger) {
  padding: 20px;
}

.el-icon--upload {
  font-size: 48px;
  color: #409eff;
  margin-bottom: 10px;
}

.file-info-section {
  margin-bottom: 15px;
}

.section-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
  font-weight: 500;
}

.info-input {
  margin-bottom: 10px;
}

.status-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
}

.status-item .el-icon {
  font-size: 20px;
}

.document-list {
  flex: 1;
  overflow-y: auto;
  margin-top: 15px;
}

.empty-list {
  padding: 20px 0;
}

.document-item {
  padding: 12px;
  margin-bottom: 8px;
  background: #f5f7fa;
  border-radius: 6px;
  border-left: 4px solid #409eff;
  transition: all 0.3s;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.document-item:hover {
  background: #e6f7ff;
  transform: translateX(4px);
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.15);
}

.document-item .doc-content {
  flex: 1;
  cursor: pointer;
  min-width: 0;
}

.document-item .doc-actions {
  flex-shrink: 0;
  margin-left: 10px;
  opacity: 0;
  transition: opacity 0.3s;
}

.document-item:hover .doc-actions {
  opacity: 1;
}

.document-item.active {
  background: #e6f7ff;
  border-left-color: #409eff;
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.25);
}

/* 已构建图谱的文档样式 */
.document-item.has-graph {
  border-left-color: #67c23a;
  border-left-width: 5px;
  background: linear-gradient(90deg, #f0f9ff 0%, #f5f7fa 100%);
}

.document-item.has-graph::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 5px;
  background: linear-gradient(180deg, #67c23a 0%, #85ce61 100%);
  border-radius: 6px 0 0 6px;
}

.document-item.has-graph:hover {
  background: linear-gradient(90deg, #e6f7ff 0%, #ecfdf5 100%);
  box-shadow: 0 2px 12px rgba(103, 194, 58, 0.25);
  transform: translateX(6px);
}

.document-item.has-graph.active {
  background: linear-gradient(90deg, #e6f7ff 0%, #f0f9ff 100%);
  border-left-color: #67c23a;
  box-shadow: 0 4px 16px rgba(103, 194, 58, 0.3);
}

.doc-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.doc-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
  color: #303133;
  font-size: 14px;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-status {
  flex-shrink: 0;
}

.doc-meta {
  font-size: 12px;
  color: #909399;
}

.action-section {
  flex-shrink: 0;
  padding: 15px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

/* 中间面板 */
.middle-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0 15px;
  border-right: 1px solid #e4e7ed;
}

.html-card {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.html-card :deep(.el-card__body) {
  flex: 1;
  overflow: hidden;
}

.html-viewer {
  height: 100%;
  overflow: hidden;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: white;
  position: relative;
}

.html-iframe {
  width: 100%;
  height: 100%;
  border: none;
  display: block;
}

.html-content {
  padding: 20px;
  line-height: 1.8;
  font-size: 14px;
  color: #303133;
}

.html-content :deep(h1) {
  font-size: 24px;
  font-weight: bold;
  margin-top: 20px;
  margin-bottom: 15px;
  color: #303133;
  border-bottom: 2px solid #e4e7ed;
  padding-bottom: 10px;
}

.html-content :deep(h2) {
  font-size: 20px;
  font-weight: bold;
  margin-top: 18px;
  margin-bottom: 12px;
  color: #409eff;
}

.html-content :deep(h3) {
  font-size: 16px;
  font-weight: bold;
  margin-top: 16px;
  margin-bottom: 10px;
  color: #606266;
}

.html-content :deep(h4) {
  font-size: 15px;
  font-weight: bold;
  margin-top: 14px;
  margin-bottom: 8px;
  color: #606266;
}

.html-content :deep(p) {
  margin-bottom: 12px;
  color: #606266;
  text-align: justify;
  text-indent: 2em;
}

.html-content :deep(ul),
.html-content :deep(ol) {
  margin: 15px 0;
  padding-left: 30px;
}

.html-content :deep(li) {
  margin-bottom: 8px;
  color: #606266;
}

.html-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 20px 0;
}

.html-content :deep(th),
.html-content :deep(td) {
  border: 1px solid #e4e7ed;
  padding: 10px;
  text-align: left;
}

.html-content :deep(th) {
  background: #f5f7fa;
  font-weight: bold;
  color: #303133;
}

.html-content :deep(strong),
.html-content :deep(b) {
  font-weight: bold;
  color: #303133;
}

.html-content :deep(em),
.html-content :deep(i) {
  font-style: italic;
}

.html-content :deep(a) {
  color: #409eff;
  text-decoration: none;
}

.html-content :deep(a:hover) {
  text-decoration: underline;
}

.html-content :deep(blockquote) {
  border-left: 4px solid #409eff;
  padding-left: 15px;
  margin: 15px 0;
  color: #606266;
  background: #f5f7fa;
  padding: 10px 15px;
}

.html-content :deep(code) {
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  color: #e6a23c;
}

.html-content :deep(pre) {
  background: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
  overflow-x: auto;
  margin: 15px 0;
}

.html-content :deep(img) {
  max-width: 100%;
  height: auto;
  display: block;
  margin: 15px auto;
}

/* 右侧面板 */
.right-panel {
  display: flex;
  flex-direction: column;
  gap: 15px;
  overflow: hidden;
  padding-left: 15px;
}

/* 知识图谱主面板（占据中间+右侧） */
.graph-main-panel {
  grid-column: 2 / 4;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0 15px;
}

.graph-card-large {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.graph-card-large :deep(.el-card__body) {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.graph-viewer-large {
  flex: 1;
  overflow: hidden;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  background: white;
}

.graph-content-large {
  width: 100%;
  height: 100%;
}

.graph-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 15px;
  flex-wrap: wrap;
}

.graph-stats {
  display: flex;
  gap: 10px;
  align-items: center;
}

.graph-stats .el-tag {
  padding: 8px 15px;
  font-size: 14px;
}

.graph-stats .el-icon {
  margin-right: 6px;
}

.graph-actions {
  display: flex;
  gap: 10px;
}

.json-card,
.graph-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.json-card :deep(.el-card__body),
.graph-card :deep(.el-card__body) {
  flex: 1;
  overflow-y: auto;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 600;
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  text-align: center;
  padding: 40px 20px;
}

.json-content {
  height: 100%;
  overflow-y: auto;
}

.json-section {
  margin-bottom: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  padding-bottom: 10px;
  border-bottom: 2px solid #e4e7ed;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.entity-list,
.relationship-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.entity-item {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 6px;
  border-left: 3px solid #409eff;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.entity-header {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.entity-name {
  font-weight: 500;
  color: #303133;
}

.entity-actions {
  display: flex;
  gap: 5px;
}

.relationship-item {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 6px;
  border-left: 3px solid #67c23a;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.rel-content {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  flex-wrap: wrap;
}

.rel-node {
  font-size: 13px;
  color: #409eff;
  font-weight: 500;
}

.rel-type {
  font-size: 12px;
  color: #67c23a;
  font-weight: 600;
}

.rel-arrow {
  color: #909399;
  font-size: 14px;
}

.rel-actions {
  display: flex;
  gap: 5px;
}

.build-section {
  padding: 15px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.build-button {
  width: 100%;
  height: 50px;
  font-size: 16px;
  font-weight: 600;
}

.graph-viewer {
  height: 600px;
  overflow: hidden;
}

.graph-content {
  width: 100%;
  height: 100%;
}

.graph-footer {
  display: flex;
  gap: 10px;
  justify-content: space-between;
}


/* 全屏知识图谱对话框样式 */
.fullscreen-graph-dialog :deep(.el-dialog__header) {
  padding: 20px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.fullscreen-graph-dialog :deep(.el-dialog__body) {
  padding: 0;
  height: calc(100vh - 80px);
  background: #f5f7fa;
}

.fullscreen-graph-container {
  width: 100%;
  height: 100%;
  min-height: calc(100vh - 80px);
  background: white;
  padding: 20px;
  box-sizing: border-box;
}

/* 上传对话框样式 */
.upload-area :deep(.el-upload-dragger) {
  padding: 40px;
}

.el-icon--upload {
  font-size: 60px;
  color: #409eff;
  margin-bottom: 15px;
}

.el-upload__text {
  font-size: 14px;
  color: #606266;
  line-height: 1.8;
}

.el-upload__text em {
  color: #409eff;
  font-style: normal;
  text-decoration: underline;
}

.el-upload__tip {
  margin-top: 10px;
  font-size: 12px;
  color: #909399;
}

/* 数据管理卡片样式 */
.management-card {
  margin-top: 15px;
  border: 1px solid #e4e7ed;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
}

.management-card :deep(.el-card__header) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 12px 15px;
}

.management-card .card-header {
  color: white;
}

.management-actions {
  padding: 5px 0;
}

.management-actions .el-button {
  font-size: 13px;
  font-weight: 500;
}

/* 统计信息对话框样式 */
:deep(.stats-message-box) {
  max-width: 800px;
}

:deep(.stats-message-box .el-message-box__message) {
  max-height: 500px;
  overflow-y: auto;
}
</style>

