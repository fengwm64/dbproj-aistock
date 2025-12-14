<template>
  <div class="tag-page">
    <TheNavbar />
    
    <div class="page-container">
      <div class="main-content">
        <div class="container">
          <div class="tag-header">
            <h1 class="tag-title">
            <span class="tag-name">#{{ tagName }}</span> 
            </h1>
            <p class="tag-description" style="display: flex; align-items: center; gap: 8px;">
              <img src="@/assets/deepseek-color.svg" alt="DeepSeek Logo" style="height: 1.6rem; vertical-align: middle;" />
              <span>{{ `DeepSeek AI 推荐的 ${tagName} 相关板块龙头个股` }}</span>
            </p>
            <div class="powered-by">
              <img src="@/assets/siliconflow-logo.svg" alt="SiliconFlow Logo" class="powered-by-logo" />
              <span class="powered-by-text">Powered by SiliconFlow</span>
            </div>
          </div>

          <!-- 使用StockCardList组件显示股票 -->
          <StockCardList
            :stocks="stocks"
            :loading="loading"
            :emptyText="`暂无${tagName}相关个股推荐`"
            @view-detail="viewStockDetail"
            @toggle-favorite="toggleFavorite"
          >
            <!-- 空状态自定义 -->
            <template #empty>
              <el-empty :description="`暂无${tagName}相关个股推荐`">
                <router-link to="/">
                  <el-button type="primary">返回首页</el-button>
                </router-link>
              </el-empty>
            </template>
            
            <template #item-content="{ stock }">
              <div class="stock-reason">
                <span>{{ stock.reason || '推荐理由' }}</span>
              </div>
            </template>
          </StockCardList>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive, computed, onMounted, watch } from 'vue';
import { useStore } from 'vuex';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import TheNavbar from '@/components/TheNavbar.vue';
import StockCardList from '@/components/StockCardList.vue';
import 'element-plus/es/components/message/style/css'

export default {
  name: 'TagView',
  components: {
    TheNavbar,
    StockCardList
  },
  setup() {
    const store = useStore();
    const route = useRoute();
    const router = useRouter();

    const stocks = ref([]);
    const loading = ref(true);
    const error = ref(false);
    const loadingStates = reactive({});
    const tagDescription = ref('');
    
    // 从路由参数获取标签名，并进行URL解码
    const tagName = computed(() => decodeURIComponent(route.params.tagName || ''));
    
    // 监听标签名变化，重新获取数据
    watch(() => route.params.tagName, (newTagName) => {
      if (newTagName) {
        fetchTagStocks();
      }
    });
    
    // 获取标签相关股票
    const fetchTagStocks = async () => {
      if (!tagName.value) return;
      
      loading.value = true;
      error.value = false;
      
      try {
        const result = await store.dispatch('fetchTagStocks', tagName.value);
        if (result) {
          stocks.value = result.stocks || [];
          tagDescription.value = result.description || '';
        } else {
          stocks.value = [];
          console.error('获取标签股票返回格式不正确', result);
        }
      } catch (err) {
        console.error('获取标签股票失败:', err);
        error.value = true;
        stocks.value = [];
        ElMessage.error('获取标签股票失败，请稍后再试');
      } finally {
        loading.value = false;
      }
    };
    
    // 格式化价格
    const formatPrice = (price) => {
      if (price === undefined || price === null) return '--';
      return Number(price).toFixed(2);
    };
    
    // 格式化百分比
    const formatPercent = (percent) => {
      if (percent === undefined || percent === null) return '--';
      return Number(percent).toFixed(2);
    };
    
    // 检查股票是否已收藏
    const isFavorite = (code) => {
      const favoriteStocks = store.getters.favoriteStocks || [];
      return favoriteStocks.some(stock => stock.code === code);
    };
    
    // 添加/删除收藏
    const toggleFavorite = async (stock, loadingState) => {
      if (!store.getters.isLoggedIn) {
        ElMessage.warning('请先登录后才能添加自选股');
        router.push('/login');
        return;
      }
      
      try {
        if (isFavorite(stock.code)) {
          // 取消关注
          const result = await store.dispatch('removeFavoriteStocks', [stock.code]);
          if (result) {
            ElMessage.success(`已将 ${stock.name} 从自选股中移除`);
          } else {
            ElMessage.error(`移除 ${stock.name} 失败`);
          }
        } else {
          // 添加关注
          const result = await store.dispatch('addFavoriteStocks', [
            { code: stock.code, name: stock.name }
          ]);
          
          if (result) {
            ElMessage.success(`成功添加 ${stock.name} 到自选股`);
          } else {
            ElMessage.error(`添加 ${stock.name} 到自选股失败`);
          }
        }
        // 刷新自选股列表
        await store.dispatch('fetchFavoriteStocks');
      } catch (error) {
        console.error('操作自选股失败:', error);
        ElMessage.error('操作失败，请稍后再试');
      } finally {
        if (loadingState) {
          loadingState[stock.code] = false;
        }
      }
    };
    
    // 查看股票详情
    const viewStockDetail = (stock) => {
      router.push(`/stock/${stock.code}`);
    };
    
    // 组件挂载时获取数据
    onMounted(() => {
      // 重置滚动位置到顶部
      window.scrollTo(0, 0);
      
      fetchTagStocks();
      
      // 如果用户已登录，预先加载自选股列表
      if (store.getters.isLoggedIn) {
        store.dispatch('fetchFavoriteStocks');
      }
    });
    
    return {
      tagName,
      tagDescription,
      stocks,
      loading,
      error,
      loadingStates,
      formatPrice,
      formatPercent,
      isFavorite,
      toggleFavorite,
      viewStockDetail,
      fetchTagStocks
    };
  }
};
</script>

<style lang="scss" scoped>
.tag-page {
  .tag-header {
    position: relative;
    margin-bottom: 30px;
    padding: 20px;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
    
    .tag-title {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 10px;
      
      .tag-name {
        color: var(--primary-color);
        font-size: 2rem;
        font-weight: 700;
      }
    }
    
    .tag-description {
      color: var(--text-tertiary);
      font-size: 1rem;
    }
    
    .powered-by {
      position: absolute;
      bottom: 8px;
      right: 20px;
      display: flex;
      align-items: center;
      gap: 4px;
      opacity: 0.4;
      
      .powered-by-logo {
        height: 12px;
        width: auto;
      }
      
      .powered-by-text {
        font-size: 0.8rem;
        color: #999;
        font-weight: 500;
      }
    }
  }
  
  .loading-container,
  .error-container,
  .empty-container {
    padding: 40px;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
    text-align: center;
  }
  
  // 移除之前的reason-metric样式，添加新的stock-reason样式
  .stock-reason {
    padding: 6px 0;
    margin: 10px 0;
    border-top: 1px dashed #ebeef5;
    border-bottom: 1px dashed #ebeef5;
    background-color: rgba(245, 247, 250, 0.5);
    
    span {
      font-size: 0.80rem;
      color: #a7a7a7;
      line-height: 1.4;
      display: block;
      text-align: left;
      padding: 0 2px;
      font-weight: bold;
    }
  }
}
</style>
