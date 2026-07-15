<template>
  <div class="login-page">
    <el-card class="login-card">
      <h2>企业内部管理系统</h2>
      <el-form @submit.prevent="handleLogin">
        <el-form-item>
          <el-input v-model="username" placeholder="用户名" prefix-icon="User" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="password" type="password" placeholder="密码" prefix-icon="Lock" show-password @keyup.enter="handleLogin" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handleLogin" style="width: 100%">登录</el-button>
        </el-form-item>
        <p v-if="error" class="error">{{ error }}</p>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const router = useRouter()
const auth = useAuthStore()

async function handleLogin() {
  if (!username.value || !password.value) return
  loading.value = true
  error.value = ''
  try {
    await auth.login(username.value, password.value)
    router.push('/')
  } catch (e: any) {
    error.value = e.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page { display: flex; align-items: center; justify-content: center; height: 100vh; background: #f0f2f5; }
.login-card { width: 400px; }
.login-card h2 { text-align: center; margin-bottom: 24px; }
.error { color: var(--el-color-danger); text-align: center; }
</style>
