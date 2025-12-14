<template>
  <div class="favorites-page">
    <div class="page-container">
      <div class="favorites-header">
        <h1>自选股</h1>
        <div class="favorites-actions">
          <el-button 
            type="primary" 
            @click="refreshStockData" 
            :loading="refreshing"
            class="refresh-button">
            <img v-if="!refreshing" src="@/assets/refresh.svg" alt="刷新" class="button-icon" />
            刷新数据
          </el-button>
          <el-button 
            type="success" 
            @click="goToSearch" 
            class="add-button">
            <img src="@/assets/add.svg" alt="添加" class="button-icon" />
            添加股票
          </el-button>
        </div>
      </div>
      
      <div v-loading="loading" class="favorites-content">
        <!-- 表格显示模式 -->
        <el-table 
          v-if="favoriteStocks.length > 0" 
          :data="favoriteStocks" 
          border 
          stripe 
          class="stock-table">
          <el-table-column prop="code" label="代码" width="100" />
          <el-table-column prop="name" label="名称" width="160" />
          <el-table-column label="最新价" width="100" align="right">
            <template #default="scope">
              <span>{{ formatPrice(scope.row.price) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="涨跌幅" width="100" align="right">
            <template #default="scope">
              <span :class="scope.row.change >= 0 ? 'stock-up' : 'stock-down'">
                {{ scope.row.change >= 0 ? '+' : '' }}{{ formatPercent(scope.row.change) }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="市值" width="120" align="right">
            <template #default="scope">
              <span>{{ formatMarketCap(scope.row.marketCap) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="industry" label="所属行业" width="140" />
          <el-table-column label="操作" fixed="right" width="180">
            <template #default="scope">
              <div class="action-buttons">
                <el-button 
                  type="primary" 
                  size="small" 
                  @click="viewStockDetail(scope.row)">
                  <img src="@/assets/search.svg" alt="详情" class="button-icon" />
                  详情
                </el-button>
                <el-popconfirm
                  title="确定取消关注该股票吗？"
                  @confirm="removeFromFavorite(scope.row)"
                >
                  <template #reference>
                    <el-button 
                      type="danger" 
                      size="small">
                      <img src="@/assets/unfollow.svg" alt="取消关注" class="button-icon" />
                      取消关注
                    </el-button>
                  </template>
                </el-popconfirm>
              </div>
            </template>
          </el-table-column>
        </el-table>
        
        <!-- 卡片显示模式 (适用于移动设备) -->
        <div v-if="favoriteStocks.length > 0" class="stock-cards">
          <div 
            v-for="stock in favoriteStocks" 
            :key="stock.code" 
            class="stock-card">
            <div class="card-header">
              <div class="stock-name-code">
                <h3>{{ stock.name }}</h3>
                <span class="stock-code">{{ stock.code }}</span>
              </div>
              <div class="stock-price-change">
                <div class="price">{{ formatPrice(stock.price) }}</div>
                <div :class="stock.change >= 0 ? 'change-up' : 'change-down'">
                  {{ stock.change >= 0 ? '+' : '' }}{{ formatPercent(stock.change) }}%
                </div>
              </div>
            </div>
            <div class="card-body">
              <div class="info-row">
                <span class="label">行业</span>
                <span class="value">{{ stock.industry || '未知' }}</span>
              </div>
              <div class="info-row">
                <span class="label">市值</span>
                <span class="value">{{ formatMarketCap(stock.marketCap) }}</span>
              </div>
            </div>
            <div class="card-footer">
              <el-button 
                type="primary" 
                size="small" 
                @click="viewStockDetail(stock)">
                <img src="@/assets/view.svg" alt="详情" class="button-icon" />
                详情
              </el-button>
              <el-popconfirm
                title="确定取消关注该股票吗？"
                @confirm="removeFromFavorite(stock)"
              >
                <template #reference>
                  <el-button 
                    type="danger" 
                    size="small">
                    <img src="@/assets/unfollow.svg" alt="取消关注" class="button-icon" />
                    取消关注
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
        </div>
        
        <!-- 空状态 -->
        <el-empty 
          v-if="favoriteStocks.length === 0 && !loading" 
          description="您还没有添加自选股" 
          class="empty-state">
          <el-button type="primary" @click="goToSearch">去添加</el-button>
        </el-empty>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import { useStore } from 'vuex';
import { ElMessage } from 'element-plus';
import { useScrollReset } from '@/utils/scrollUtils';

export default {
  name: 'FavoritesView',
  setup() {
    const store = useStore();
    const router = useRouter();
    
    const loading = ref(true);
    const refreshing = ref(false);
    const favoriteStocks = ref([]);
    const refreshTimer = ref(null);

    // 获取自选股数据
    const fetchFavoriteStocks = async () => {
      try {
        loading.value = true;
        await store.dispatch('fetchFavoriteStocks');
        
        // 获取自选股列表
        const stocks = store.getters.favoriteStocks || [];
        
        // 为每支股票获取实时价格数据
        const enrichedStocks = await Promise.all(stocks.map(async (stock) => {
          try {
            const stockDetail = await store.dispatch('fetchStockDetail', stock.code);
            if (stockDetail) {
              return {
                ...stock,
                price: stockDetail.trading?.current_price || 0,
                change: stockDetail.trading?.change_percent || 0,
                marketCap: stockDetail.trading?.market_cap || 0,
                industry: stockDetail.industry || '未知行业'
              };
            }
            return stock;
          } catch (err) {
            console.error(`获取股票${stock.code}价格失败:`, err);
            return stock;
          }
        }));
        
        favoriteStocks.value = enrichedStocks;
      } catch (error) {
        console.error('获取自选股失败:', error);
        ElMessage.error('获取自选股数据失败');
      } finally {
        loading.value = false;
      }
    };
    
    // 手动刷新股票数据
    const refreshStockData = async () => {
      if (refreshing.value) return;
      
      try {
        refreshing.value = true;
        await fetchFavoriteStocks();
        ElMessage.success('数据刷新成功');
      } catch (error) {
        console.error('刷新数据失败:', error);
        ElMessage.error('刷新数据失败');
      } finally {
        refreshing.value = false;
      }
    };
    
    // 移除自选股
    const removeFromFavorite = async (stock) => {
      try {
        loading.value = true;
        const result = await store.dispatch('removeFavoriteStocks', [stock.code]);
        if (result) {
          ElMessage.success(`已将 ${stock.name} 从自选股中移除`);
          await store.dispatch('fetchFavoriteStocks');
          store.commit('setFavoriteStocks', store.getters.favoriteStocks); // 更新缓存
        } else {
          ElMessage.error('移除自选股失败');
        }
      } catch (error) {
        console.error('移除自选股失败:', error);
        ElMessage.error('移除自选股失败');
      } finally {
        loading.value = false;
      }
    };
    
    // 查看股票详情
    const viewStockDetail = (stock) => {
      router.push(`/stock/${stock.code}`);
    };
    
    // 跳转到搜索页
    const goToSearch = () => {
      router.push('/search');
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
    
    // 格式化市值
    const formatMarketCap = (marketCap) => {
      if (!marketCap) return '--';
      if (marketCap >= 100000000000) {
        return (marketCap / 100000000000).toFixed(2) + '千亿';
      } else if (marketCap >= 100000000) {
        return (marketCap / 100000000).toFixed(2) + '亿';
      } else if (marketCap >= 10000) {
        return (marketCap / 10000).toFixed(2) + '万';
      }
      return marketCap.toLocaleString();
    };
    
    onMounted(async () => {
      // 重置滚动位置到顶部
      useScrollReset();
      
      if (!store.getters.isLoggedIn) {
        ElMessage.warning('请先登录');
        router.push('/login');
        return;
      }
      
      await fetchFavoriteStocks();
      
      // 设置自动刷新定时器 (每60秒刷新一次)
      refreshTimer.value = setInterval(() => {
        fetchFavoriteStocks();
      }, 60000);
    });
    
    onBeforeUnmount(() => {
      // 清除定时器
      if (refreshTimer.value) {
        clearInterval(refreshTimer.value);
      }
    });
    
    return {
      loading,
      refreshing,
      favoriteStocks,
      refreshStockData,
      removeFromFavorite,
      viewStockDetail,
      goToSearch,
      formatPrice,
      formatPercent,
      formatMarketCap
    };
  }
};
</script>

<style lang="scss" scoped>
.favorites-page {
  padding-top: 80px; /* 为顶部导航条预留空间 */
  
  .favorites-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    
    h1 {
      font-size: 1.75rem;
      color: var(--text-primary);
    }
    
    .favorites-actions {
      display: flex;
      gap: 10px;
      
      .button-icon {
        width: 16px;
        height: 16px;
        margin-right: 5px;
        vertical-align: middle;
      }
    }
  }
  
  .favorites-content {
    margin-bottom: 20px;
    min-height: 200px;
    
    .stock-table {
      width: 100%; /* 确保表格占满全部宽度 */
      margin-bottom: 20px;
      display: block;
      
      @media (max-width: 992px) {
        display: none;
      }
    }
    
    .stock-cards {
      display: none;
      
      @media (max-width: 992px) {
        display: grid;
        grid-template-columns: repeat(1, 1fr);
        gap: 15px;
      }
      
      .stock-card {
        background: #fff;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
        
        .card-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 15px;
          
          .stock-name-code {
            h3 {
              margin: 0;
              font-size: 1.1rem;
            }
            
            .stock-code {
              font-size: 0.9rem;
              color: var(--text-secondary);
            }
          }
          
          .stock-price-change {
            text-align: right;
            
            .price {
              font-size: 1.1rem;
              font-weight: bold;
            }
            
            .change-up {
              color: var(--danger-color);
            }
            
            .change-down {
              color: var(--success-color);
            }
          }
        }
        
        .card-body {
          margin-bottom: 15px;
          
          .info-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
            
            .label {
              color: var(--text-secondary);
            }
            
            .value {
              font-weight: 500;
            }
          }
        }
        
        .card-footer {
          display: flex;
          justify-content: space-between;
        }
      }
    }
    
    .empty-state {
      padding: 40px 0;
    }
  }
}

.el-table {
  width: 100%; /* 确保表格占满全部宽度 */
}

.stock-up {
  color: var(--danger-color);
}

.stock-down {
  color: var(--success-color);
}

.button-icon {
  width: 14px;
  height: 14px;
  margin-right: 4px;
  vertical-align: middle;
}

.action-buttons {
  display: flex;
  gap: 10px;
}
</style>
