import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import store from './store'
import './assets/styles/global.scss'
import CacheManager from './utils/cacheManager'

const app = createApp(App)

// 应用启动时检查并清理缓存
CacheManager.checkAndClearCache();

// 只有在有token的情况下才尝试获取用户信息
if (localStorage.getItem('token')) {
  store.dispatch('fetchUserInfo').catch(() => {
    console.error('无法获取用户信息，已清除登录状态');
    // 如果获取用户信息失败，清除登录状态
    store.commit('logout');
  });
}

app.use(store)
app.use(router)
// 移除全量使用
// app.use(ElementPlus)
app.mount('#app')
