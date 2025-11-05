/**
 * 知识图谱构建相关的API接口
 */

import axios from 'axios'

// 在Docker环境中，通过nginx代理访问后端
// 开发环境使用localhost，生产环境使用相对路径（nginx代理）
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 
                     (import.meta.env.DEV ? 'http://localhost:8012' : '')

/**
 * 上传医学文献
 * @param {File} file - PDF文件
 * @returns {Promise}
 */
export const uploadDocument = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await axios.post(
    `${API_BASE_URL}/api/knowledge/upload`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    }
  )
  
  return response.data
}

/**
 * 实体抽取（耗时操作，设置较长超时时间）
 * @param {string} documentName - 文档名称
 * @returns {Promise}
 */
export const extractEntities = async (documentName) => {
  const response = await axios.post(
    `${API_BASE_URL}/api/knowledge/extract`,
    { document_name: documentName },
    {
      timeout: 300000 // 5分钟超时，实体抽取可能需要较长时间
    }
  )
  
  return response.data
}

/**
 * 构建知识图谱
 * @param {string} documentName - 文档名称
 * @param {Array} entities - 实体列表
 * @param {Array} relationships - 关系列表
 * @returns {Promise}
 */
export const buildKnowledgeGraph = async (documentName, entities, relationships) => {
  const response = await axios.post(
    `${API_BASE_URL}/api/knowledge/build`,
    {
      document_name: documentName,
      entities,
      relationships
    }
  )
  
  return response.data
}

/**
 * 导出知识图谱
 * @param {string} documentName - 文档名称
 * @returns {Promise}
 */
export const exportKnowledgeGraph = async (documentName) => {
  const response = await axios.get(
    `${API_BASE_URL}/api/knowledge/export/${encodeURIComponent(documentName)}`,
    { responseType: 'blob' }
  )
  
  return response.data
}

/**
 * 列出所有已处理的文档
 * @returns {Promise}
 */
export const listKnowledgeDocuments = async () => {
  const response = await axios.get(
    `${API_BASE_URL}/api/knowledge/list`
  )
  
  return response.data
}

/**
 * 加载已存在文档的详细信息
 * @param {string} documentName - 文档名称
 * @returns {Promise}
 */
export const loadKnowledgeDocument = async (documentName) => {
  const response = await axios.get(
    `${API_BASE_URL}/api/knowledge/load/${encodeURIComponent(documentName)}`
  )
  
  return response.data
}

/**
 * 删除知识文档及其所有相关资源
 * @param {string} documentName - 文档名称
 * @param {boolean} deleteFiles - 是否删除文件夹
 * @param {boolean} deleteRedis - 是否删除Redis索引
 * @param {boolean} deleteNeo4j - 是否删除Neo4j节点
 * @returns {Promise}
 */
export const deleteKnowledgeDocument = async (
  documentName,
  deleteFiles = true,
  deleteRedis = true,
  deleteNeo4j = true
) => {
  const response = await axios.delete(
    `${API_BASE_URL}/api/knowledge/delete/${encodeURIComponent(documentName)}`,
    {
      params: {
        delete_files: deleteFiles,
        delete_redis: deleteRedis,
        delete_neo4j: deleteNeo4j
      }
    }
  )
  
  return response.data
}

/**
 * 同步元数据
 * @returns {Promise}
 */
export const syncMetadata = async () => {
  const response = await axios.post(
    `${API_BASE_URL}/api/knowledge/sync-metadata`
  )
  
  return response.data
}

/**
 * 获取存储统计信息
 * @returns {Promise}
 */
export const getStorageStats = async () => {
  const response = await axios.get(
    `${API_BASE_URL}/api/knowledge/stats`
  )
  
  return response.data
}

/**
 * 清理孤立资源
 * @param {boolean} dryRun - 是否为预演模式（默认true）
 * @returns {Promise}
 */
export const cleanupOrphanedResources = async (dryRun = true) => {
  const response = await axios.post(
    `${API_BASE_URL}/api/knowledge/cleanup-orphaned`,
    null,
    {
      params: {
        dry_run: dryRun
      }
    }
  )
  
  return response.data
}

