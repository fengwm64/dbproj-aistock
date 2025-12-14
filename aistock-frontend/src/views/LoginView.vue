<template>
  <div class="login-page">
    <div class="login-card">
      <div class="card-header">
        <div class="logo">
          <img src="@/assets/logo.png" alt="股票资讯AI智能分析" />
          <h1>股票资讯AI智能分析</h1>
        </div>
        <div class="welcome-text">
          <p>
            <img src="@/assets/wechat.svg" alt="微信" class="wechat-inline-logo" />
            欢迎使用，请扫码登录
          </p>
        </div>
      </div>
      
      <div class="card-body">
        <LoginQrCode @login-success="handleLoginSuccess" />
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useStore } from 'vuex'
import { useRouter } from 'vue-router'
import LoginQrCode from '@/components/LoginQrCode.vue'
import 'element-plus/es/components/message/style/css';

export default {
  name: 'LoginView',
  components: {
    LoginQrCode
  },
  setup() {
    const store = useStore()
    const router = useRouter()
    const isProcessingLogin = ref(false)
    
    // 检查是否已登录，如果已登录则重定向到首页
    onMounted(() => {
      // 重置滚动位置到顶部
      window.scrollTo(0, 0);
      
      if (localStorage.getItem('token')) {
        router.push('/');
      }
    });
    
    const handleLoginSuccess = async (user) => {
      if (isProcessingLogin.value) return;
      try {
        isProcessingLogin.value = true;
        console.log('[LoginView] 处理登录成功事件，用户信息:', user);

        // 登录并存储用户信息
        await store.dispatch('login', user);
        // 登录后立即从后端拉取最新用户信息，确保昵称/avatar等是最新的
        await store.dispatch('fetchUserInfo');

        setTimeout(async () => {
          console.log('[LoginView] 登录完成，即将跳转');
          const redirect = router.currentRoute.value.query.redirect;
          const targetPath = redirect || '/';
          router.push(targetPath);
        }, 500);
      } catch (error) {
        console.error('[LoginView] 处理登录失败:', error);
      } finally {
        isProcessingLogin.value = false;
      }
    };
    
    return {
      handleLoginSuccess,
      isProcessingLogin
    }
  }
}
</script>

<style lang="scss" scoped>
.login-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: var(--background-color);
  
  .login-card {
    width: 400px;
    background-color: #fff;
    border-radius: 8px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
    overflow: hidden;
    
    .card-header {
      padding: 20px;
      
      .logo {
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 20px;
        
        img {
          height: 40px;
          margin-right: 10px;
        }
        
        h1 {
          font-size: 1.5rem;
          color: var(--primary-color);
        }
      }
      
      .welcome-text {
        text-align: center;
        margin: 10px 0;
        
        p {
          font-size: 16px;
          color: var(--text-secondary);
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
        }
        .wechat-inline-logo {
          width: 22px;
          height: 22px;
          vertical-align: middle;
        }
      }
    }
    
    .card-body {
      padding: 20px;
    }
  }
}
</style>
