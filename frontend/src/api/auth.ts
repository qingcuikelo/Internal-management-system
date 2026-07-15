import client from './client'

export function login(username: string, password: string) {
  return client.post('/auth/login', { username, password })
}
export function refresh(refreshToken: string) {
  return client.post('/auth/refresh', { refresh_token: refreshToken })
}
export function logout() {
  return client.post('/auth/logout')
}
export function me() {
  return client.get('/auth/me')
}
