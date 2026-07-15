import axios from 'axios'
import { ElMessage } from 'element-plus'

const client = axios.create({ baseURL: '/api/v1' })

// Request: attach token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Response: unwrap envelope, refresh on 401
let isRefreshing = false
let failedQueue: Array<{ resolve: Function; reject: Function }> = []

function processQueue(error: any, token: string | null) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error)
    else resolve(token)
  })
  failedQueue = []
}

client.interceptors.response.use(
  (res) => {
    const body = res.data
    if (body.code === 0) return body.data
    if (body.code === 1001) {
      // Will be handled in error interceptor logic below — actually this path
      // is when the server returns 200 with code=1001, which our backend doesn't do
      // (it returns 401 HTTP status). Fall through.
    }
    return Promise.reject(new Error(body.message || 'Request failed'))
  },
  async (error) => {
    const originalRequest = error.config
    const status = error.response?.status
    const body = error.response?.data

    // Handle 401: try refresh
    if (status === 401 && body?.code === 1001 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return client(originalRequest)
        })
      }
      originalRequest._retry = true
      isRefreshing = true
      const refreshToken = localStorage.getItem('refresh_token')
      if (!refreshToken) {
        isRefreshing = false
        localStorage.clear()
        window.location.href = '/login'
        return Promise.reject(error)
      }
      try {
        const { data } = await axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken })
        const newToken = data.data.access_token
        const newRefresh = data.data.refresh_token
        localStorage.setItem('access_token', newToken)
        localStorage.setItem('refresh_token', newRefresh)
        processQueue(null, newToken)
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return client(originalRequest)
      } catch (e) {
        processQueue(e, null)
        localStorage.clear()
        window.location.href = '/login'
        return Promise.reject(e)
      } finally {
        isRefreshing = false
      }
    }

    // Show error message for non-401 errors
    if (status !== 401) {
      ElMessage.error(body?.message || error.message || 'Network error')
    }
    return Promise.reject(error)
  },
)

export default client
