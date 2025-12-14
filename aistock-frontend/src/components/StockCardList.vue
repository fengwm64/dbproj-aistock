<template>
  <div class="stock-card-list">
    <h3 v-if="title" class="section-title">{{ title }}</h3>
    
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="3" animated />
    </div>
    
    <template v-else-if="stocks.length > 0">
      <div class="stock-cards">
        <div class="stock-card" v-for="stock in stocks" :key="stock.code">
          <div class="stock-info">
            <div class="stock-header">
              <h4 class="stock-name" @click.stop="onViewDetail(stock)">{{ stock.name }}</h4>
              <span v-if="stock.industry" class="stock-industry">{{ stock.industry }}</span>
            </div>
            <p class="stock-code">
              <span class="market-code" v-if="getMarketCode(stock.code)">{{ getMarketCode(stock.code) }}</span>
              {{ stock.code }}
            </p>
            <div class="stock-metrics">
              <div class="metric">
                <span class="label">最新价</span>
                <span class="value">{{ formatPrice(getPrice(stock)) }}</span>
              </div>
              <div class="metric">
                <span class="label">涨跌幅</span>
                <span class="value" :class="getChangeClass(stock)">
                  {{ getChangeValue(stock) >= 0 ? '+' : '' }}{{ formatPercent(getChangeValue(stock)) }}%
                </span>
              </div>
              <slot name="extra-info" :stock="stock"></slot>
            </div>
            
            <!-- 添加显示推荐理由的插槽 -->
            <slot name="item-content" :stock="stock"></slot>
          </div>
          <div class="stock-actions">
            <el-button size="small" type="primary" plain @click="onViewDetail(stock)">查看详情</el-button>
            <slot name="favorite-button" :stock="stock" :loading="loadingStates[stock.code]">
              <el-button 
                size="small" 
                :type="isFavorite(stock.code) ? 'danger' : 'primary'" 
                plain
                @click="onToggleFavorite(stock)"
                :loading="loadingStates[stock.code]"
              >
                {{ isFavorite(stock.code) ? '取消关注' : '添加关注' }}
              </el-button>
            </slot>
            <slot name="extra-actions" :stock="stock"></slot>
          </div>
        </div>
      </div>
      
      <div v-if="showViewMore" class="view-more">
        <slot name="view-more">
          <el-button type="primary" plain @click="$emit('view-more')">查看更多</el-button>
        </slot>
      </div>
    </template>
    
    <template v-else>
      <slot name="empty">
        <el-empty :description="emptyText" />
      </slot>
    </template>
  </div>
</template>

<script>
import { reactive } from 'vue';
import { useStore } from 'vuex';

export default {
  name: 'StockCardList',
  props: {
    title: {
      type: String,
      default: ''
    },
    stocks: {
      type: Array,
      required: true
    },
    loading: {
      type: Boolean,
      default: false
    },
    emptyText: {
      type: String,
      default: '暂无数据'
    },
    showViewMore: {
      type: Boolean,
      default: false
    }
  },
  emits: ['view-detail', 'toggle-favorite', 'view-more'],
  setup(props, { emit }) {
    const store = useStore();
    const loadingStates = reactive({});
    
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
    
    // 获取股票价格（支持不同的数据结构）
    const getPrice = (stock) => {
      return stock.price !== undefined ? stock.price : 
             stock.latest_price !== undefined ? stock.latest_price : 0;
    };
    
    // 获取变化值（支持不同的数据结构）
    const getChangeValue = (stock) => {
      return stock.change !== undefined ? stock.change : 
             stock.change_percent !== undefined ? stock.change_percent : 0;
    };
    
    // 获取涨跌样式类
    const getChangeClass = (stock) => {
      const changeValue = getChangeValue(stock);
      return changeValue >= 0 ? 'stock-up' : 'stock-down';
    };
    
    // 获取交易市场代码
    const getMarketCode = (code) => {
      // 先检查对应的股票对象是否有market属性
      const stockObj = props.stocks.find(s => s.code === code);
      if (stockObj && stockObj.market) {
        return stockObj.market.toUpperCase();
      }
      return '';
    };
    
    // 检查是否已收藏
    const isFavorite = (code) => {
      const favoriteStocks = store.getters.favoriteStocks || [];
      return favoriteStocks.some(stock => stock.code === code);
    };
    
    // 查看详情
    const onViewDetail = (stock) => {
      emit('view-detail', stock);
    };
    
    // 切换收藏状态
    const onToggleFavorite = (stock) => {
      loadingStates[stock.code] = true;
      emit('toggle-favorite', stock, loadingStates);
    };
    
    return {
      loadingStates,
      formatPrice,
      formatPercent,
      getPrice,
      getChangeValue,
      getChangeClass,
      getMarketCode,
      isFavorite,
      onViewDetail,
      onToggleFavorite
    };
  }
};
</script>

<style lang="scss" scoped>
.stock-card-list {
  margin-top: 20px;
  
  .section-title {
    font-size: 1.4rem;
    margin-bottom: 15px;
    color: var(--text-primary);
    font-weight: 500;
  }
  
  .loading-container {
    margin-top: 20px;
  }
  
  .stock-cards {
    display: flex;
    flex-wrap: wrap;
    gap: 15px;
    
    .stock-card {
      background: #fff;
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 8px;
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
      cursor: pointer;
      transition: all 0.3s ease;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      flex: 1 1 calc(25% - 12px); /* 默认每行4个卡片，并允许拉伸 */
      width: 100%; /* 确保填充计算出的空间 */
      
      &:hover {
        transform: translateY(-5px);
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.15);
      }
      
      @media (max-width: 892px) {
        flex: 1 1 calc(33.333% - 10px); /* 中等屏幕每行3个 */
      }
      
      @media (max-width: 596px) {
        flex: 1 1 calc(50% - 8px); /* 小屏幕每行2个 */
      }
      
      @media (max-width: 300px) {
        flex: 1 1 100%; /* 超小屏幕每行1个 */
      }
      
      .stock-info {
        margin-bottom: 8px;
        
        .stock-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 5px;
          
          .stock-name {
            font-size: 1.2rem;
            font-weight: 600;
            color: var(--primary-color);
            margin: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            flex: 1;
            cursor: pointer;
            transition: color 0.2s;
            
            &:hover {
              color: #1890ff;
              text-decoration: underline;
            }
          }
          
          .stock-industry {
            font-size: 0.75rem;
            padding: 2px 6px;
            border-radius: 4px;
            background-color: #f9f9f9;
            color: var(--text-tertiary);
            border: 1px solid #ebeef5;
            white-space: nowrap;
            margin-left: 8px;
            flex-shrink: 0;
          }
        }
        
        .stock-code {
          color: var(--text-secondary);
          font-size: 0.9rem;
          margin-bottom: 10px;
          
          .market-code {
            font-size: 0.75rem;
            font-weight: bold;
            color: #1677ff;
            margin-right: 4px;
            padding: 1px 4px;
            border: 1px solid #d6e4ff;
            background-color: #f0f5ff;
            border-radius: 3px;
            display: inline-block;
          }
        }
        
        .stock-metrics {
          display: flex;
          justify-content: space-between;
          
          .metric {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            
            .label {
              color: var(--text-tertiary);
              font-size: 0.8rem;
              margin-bottom: 2px;
            }
            
            .value {
              font-size: 1.1rem;
              font-weight: 600;
              
              &.stock-up {
                color: var(--danger-color);
              }
              
              &.stock-down {
                color: var(--success-color);
              }
            }
          }
        }
      }
      
      .stock-actions {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        
        .el-button {
          flex: 1;
        }
      }
    }
  }
  
  .view-more {
    text-align: center;
    margin-top: 20px;
  }
}
</style>
