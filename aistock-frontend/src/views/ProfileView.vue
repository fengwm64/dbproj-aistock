<template>
  <div class="profile-page">
    <div class="page-container">
      <div class="profile-card">
        <div class="card-header">
          <h2>个人信息</h2>
        </div>
        <div class="card-body">
          <div class="avatar-section">
            <img :src="user?.avatar || defaultAvatar" alt="头像" class="avatar" />
            <el-upload
              class="avatar-uploader"
              action="/api/user/upload-avatar"
              :show-file-list="false"
              :on-success="handleAvatarUploadSuccess"
              :headers="uploadHeaders"
            >
              <el-button size="small" type="primary">上传头像</el-button>
            </el-upload>
          </div>
          <div class="nickname-section">
            <el-input v-model="nickname" placeholder="请输入昵称" />
            <el-button type="primary" @click="updateUserProfile">保存信息</el-button>
          </div>

          <!-- 添加推送设置区域 -->
          <div class="push-settings-section">
            <h3>推送设置</h3>
            <div class="settings-container">
              <el-switch
                v-model="pushSettings.stock_push"
                active-text="自选股推送"
                :loading="settingsLoading"
                @change="updatePushSettings('stock_push')"
              />
              <el-switch
                v-model="pushSettings.morning_report"
                active-text="早报推送"
                :loading="settingsLoading"
                @change="updatePushSettings('morning_report')"
              />
            </div>
          </div>
        </div>
        <div class="card-footer">
          <h3>我的自选股</h3>
          <el-table :data="favoriteStocks" border>
            <el-table-column prop="code" label="股票代码" />
            <el-table-column prop="name" label="股票名称" />
            <el-table-column prop="added_at" label="添加时间" />
          </el-table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useStore } from 'vuex'
import { ElMessage } from 'element-plus'
import 'element-plus/es/components/message/style/css';

export default {
  name: 'ProfileView',
  setup() {
    const store = useStore()
    const user = store.state.user
    const favoriteStocks = ref([]) // 自选股列表
    const nickname = ref(user?.name || '')
    const defaultAvatar = require('@/assets/default-avatar.svg')
    const settingsLoading = ref(false)
    const pushSettings = ref({
      stock_push: false,
      morning_report: false
    })

    const uploadHeaders = {
      Authorization: `Bearer ${document.cookie.replace(/(?:(?:^|.*;\s*)token\s*=\s*([^;]*).*$)|^.*$/, '$1')}`
    }

    const handleAvatarUploadSuccess = (response) => {
      if (response.code === 0) {
        ElMessage.success('头像上传成功')
        store.commit('setUser', { ...user, avatar: response.data.avatar_url })
      } else {
        ElMessage.error('头像上传失败')
      }
    }

    const updateUserProfile = async () => {
      try {
        const response = await store.dispatch('updateUserProfile', {
          nickname: nickname.value,
          avatar_url: user.avatar
        })
        if (response) {
          ElMessage.success('用户信息更新成功')
          store.commit('setUser', { ...user, name: nickname.value }) // 更新缓存
        } else {
          ElMessage.error('用户信息更新失败')
        }
      } catch (error) {
        console.error('更新用户信息失败:', error)
        ElMessage.error('用户信息更新失败')
      }
    }

    const fetchFavoriteStocks = async () => {
      try {
        const success = await store.dispatch('fetchFavoriteStocks')
        if (success) {
          favoriteStocks.value = store.getters.favoriteStocks
        } else {
          ElMessage.error('获取自选股失败')
        }
      } catch (error) {
        console.error('获取自选股失败:', error)
      }
    }

    const fetchPushSettings = async () => {
      if (!user?.id) return;
      
      settingsLoading.value = true;
      try {
        const response = await store.dispatch('fetchPushSettings', user.id);
        if (response && response.settings) {
          pushSettings.value.stock_push = response.settings.stock_push || false;
          pushSettings.value.morning_report = response.settings.morning_report || false;
        }
      } catch (error) {
        console.error('获取推送设置失败:', error);
        ElMessage.error('获取推送设置失败');
      } finally {
        settingsLoading.value = false;
      }
    };

    const updatePushSettings = async (type) => {
      if (!user?.id) return;
      
      settingsLoading.value = true;
      try {
        const settings = {
          stock_push: pushSettings.value.stock_push,
          morning_report: pushSettings.value.morning_report
        };
        
        const success = await store.dispatch('updatePushSettings', {
          userId: user.id,
          settings: settings
        });
        
        if (success) {
          ElMessage.success('推送设置已更新');
        } else {
          ElMessage.error('更新推送设置失败');
          // 回滚UI状态
          await fetchPushSettings();
        }
      } catch (error) {
        console.error('更新推送设置失败:', error);
        ElMessage.error('更新推送设置失败');
        // 回滚UI状态
        await fetchPushSettings();
      } finally {
        settingsLoading.value = false;
      }
    };

    onMounted(() => {
      // 重置滚动位置到顶部
      window.scrollTo(0, 0);
      
      if (!user) {
        ElMessage.error('请先登录')
      } else {
        fetchFavoriteStocks()
        fetchPushSettings()
      }
    })

    return {
      user,
      favoriteStocks,
      nickname,
      defaultAvatar,
      uploadHeaders,
      handleAvatarUploadSuccess,
      updateUserProfile,
      pushSettings,
      settingsLoading,
      updatePushSettings
    }
  }
}
</script>

<style lang="scss" scoped>
.profile-page {
  padding-top: 80px; /* 增加顶部内边距，避免被导航栏遮挡 */
  min-height: 100vh;
  background-color: var(--background-color);

  .page-container {
    max-width: 800px;
    margin: 0 auto;
    padding: 0 20px;
  }

  .profile-card {
    width: 100%;
    background-color: #fff;
    border-radius: 8px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
    padding: 20px;

    .card-header {
      text-align: center;
      margin-bottom: 20px;

      h2 {
        font-size: 1.5rem;
        color: var(--primary-color);
      }
    }

    .card-body {
      .avatar-section {
        display: flex;
        align-items: center;
        margin-bottom: 20px;

        .avatar {
          width: 80px;
          height: 80px;
          border-radius: 50%;
          margin-right: 20px;
        }
      }

      .nickname-section {
        display: flex;
        align-items: center;

        .el-input {
          margin-right: 10px;
        }
      }

      .push-settings-section {
        margin-top: 20px;
        padding-top: 15px;
        border-top: 1px solid #eee;

        h3 {
          font-size: 1.1rem;
          color: var(--text-secondary);
          margin-bottom: 15px;
        }

        .settings-container {
          display: flex;
          flex-wrap: wrap;
          gap: 20px;
        }
      }
    }

    .card-footer {
      margin-top: 20px;

      h3 {
        margin-bottom: 10px;
        color: var(--text-secondary);
      }
    }
  }
}
</style>
