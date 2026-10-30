import axios from 'axios'
import { ElMessage } from 'element-plus'

const service = axios.create({
  baseURL: '/api',
  timeout: 300000,
})

service.interceptors.response.use(
  (response) => {
    const res = response.data
    if (res.code && res.code !== 200) {
      ElMessage.error(res.message || '请求失败')
      const err = new Error(res.message || '请求失败')
      err.payload = res
      return Promise.reject(err)
    }
    return res
  },
  (error) => {
    ElMessage.error(error.message || '网络错误')
    return Promise.reject(error)
  }
)

export default service
