<template>
  <div class="market-overview">
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="1" animated />
    </div>
    <div v-else class="market-cards">
      <div class="market-card" v-for="(data, index) in marketData" :key="index">
        <div class="index-name">
          <a :href="getIndexUrl(index)" target="_blank" class="index-link">
            {{ getIndexDisplayName(index) }}
          </a>
        </div>
        <div class="index-value">{{ formatValue(data.value) }}</div>
        <div :class="data.change >= 0 ? 'change-up' : 'change-down'">
          {{ formatChange(data.change) }}
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onBeforeUnmount } from 'vue'; // ✅ 加入 onBeforeUnmount
import { useStore } from 'vuex';

export default {
  name: 'MarketOverview',
  setup() {
    const store = useStore();
    const marketData = ref({});
    const loading = ref(true);
    let timer = null; // ✅ 声明定时器变量

    const fetchMarketData = async () => {
      try {
        loading.value = true;
        const data = await store.dispatch('fetchMarketOverview');
        if (data) {
          marketData.value = data;
        }
      } catch (error) {
        console.error('获取市场概览失败:', error);
      } finally {
        loading.value = false;
      }
    };

    const getIndexDisplayName = (code) => {
      const nameMap = {
        'shangzheng': '上证指数',
        'shenzheng': '深证成指',
        'chuangye': '创业板指',
        'shangzheng50': '上证50',
        'nasdaqChina': '纳斯达克中国金龙指数',
        'ftseChina': '富时中国A50指数',
        'hktech': '恒生科技指数'
      };
      return nameMap[code] || code;
    };

    const getIndexUrl = (code) => {
      const urlMap = {
        'shangzheng': 'https://quote.eastmoney.com/zs000001.html',
        'shenzheng': 'https://quote.eastmoney.com/zs399001.html',
        'chuangye': 'https://quote.eastmoney.com/zs399006.html',
        'shangzheng50': '#',
        'nasdaqChina': 'https://quote.eastmoney.com/gb/zsHXC.html',
        'ftseChina': 'https://quote.eastmoney.com/gb/zsXIN9.html',
        'hktech': 'https://quote.eastmoney.com/gb/zsHSTECH.html'
      };
      return urlMap[code] || '#';
    };

    const formatValue = (value) => {
      return Number(value).toFixed(2);
    };

    const formatChange = (change) => {
      const sign = change >= 0 ? '+' : '';
      return `${sign}${Number(change).toFixed(2)}%`;
    };

    onMounted(() => {
      fetchMarketData();

      // ✅ 每 60 秒刷新一次
      timer = setInterval(() => {
        console.log('刷新市场数据...');
        fetchMarketData();
      }, 60000);
    });

    onBeforeUnmount(() => {
      if (timer) {
        clearInterval(timer);
      }
    });

    return {
      marketData,
      loading,
      getIndexDisplayName,
      getIndexUrl,
      formatValue,
      formatChange
    };
  }
};
</script>


<style lang="scss" scoped>
.market-overview {
  .loading-container {
    margin: 10px 0;
  }
  
  .market-cards {
    display: flex;
    flex-wrap: wrap;
    gap: 15px;
    
    .market-card {
      background: #fff;
      border-radius: 8px;
      box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
      padding: 10px; // 减少卡片内边距
      flex: 0 0 calc(33.333% - 10px); // 改为每行3个
      min-width: 60px; // 调整最小宽度
      text-align: center;
      
      .index-name {
        font-size: 0.9rem; // 缩小字体
        color: var(--text-secondary);
        margin-bottom: 5px; // 减少间距
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        
        .index-link {
          color: inherit;
          text-decoration: none;
          
          &:hover {
            text-decoration: underline;
            color: var(--primary-color);
          }
        }
      }
      
      .index-value {
        font-size: 1rem; // 缩小字体
        font-weight: bold;
        margin-bottom: 5px; // 减少间距
      }
      
      .change-up {
        color: var(--danger-color);
        font-weight: 500;
        font-size: 0.9rem; // 缩小字体
      }
      
      .change-down {
        color: var(--success-color);
        font-weight: 500;
        font-size: 0.9rem; // 缩小字体
      }
    }
  }
}

/* 响应式处理 */
@media (max-width: 768px) {
  .market-overview .market-cards .market-card {
    flex: 0 0 calc(50% - 7.5px); /* 中等屏幕显示2个 */
  }
}

@media (max-width: 256px) {
  .market-overview .market-cards .market-card {
    flex: 0 0 100%; /* 小屏幕显示1个，占用所有列宽 */
  }
}
</style>
