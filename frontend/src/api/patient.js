import axios from 'axios'

// 创建axios实例
const request = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 请求拦截器
request.interceptors.request.use(
  config => {
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    console.error('API错误:', error)
    return Promise.reject(error)
  }
)

// 获取所有患者列表
export const getPatientList = () => {
  return request.get('/patients')
}

// 获取单个患者详情
export const getPatientDetail = (patientId) => {
  return request.get(`/patients/${patientId}`)
}

// 创建新患者
export const createPatient = (data) => {
  return request.post('/patients', data)
}

// 更新患者信息
export const updatePatient = (patientId, data) => {
  return request.put(`/patients/${patientId}`, data)
}

// 删除患者
export const deletePatient = (patientId) => {
  return request.delete(`/patients/${patientId}`)
}

// 发送聊天消息
export const sendChatMessage = (data) => {
  return request.post('/chat', data)
}

// 提交检查结果
export const submitTestResults = (patientId, data) => {
  return request.post(`/patients/${patientId}/submit-tests`, data)
}

export default request

