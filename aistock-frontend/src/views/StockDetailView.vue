<template>
  <div class="stock-detail-page">
    <div class="page-container">
      <div class="stock-header">
        <div class="stock-title">
          <h1>{{ stockInfo?.name || '加载中...' }} 
            <span class="stock-code-container">
              <span class="market-code">{{ stockInfo?.market || '未知' }}</span><span class="code-separator">.</span>{{ stockInfo?.code }}
            </span>
          </h1>
          <div class="stock-price-info">
            <span class="current-price">{{ stockInfo.price }}</span>
            <span :class="stockInfo.change >= 0 ? 'stock-up' : 'stock-down'">
              {{ stockInfo.change >= 0 ? '+' : '' }}{{ stockInfo.change.toFixed(2) }}
              ({{ stockInfo.changePercent }}%)
            </span>
          </div>
          <el-button 
            :type="isFavorite ? 'danger' : 'primary'" 
            size="small" 
            @click="toggleFavorite" 
            :loading="addingToFavorites">
            <img 
              :src="isFavorite ? require('@/assets/unfollow.svg') : require('@/assets/follow.svg')" 
              alt="关注" 
              class="button-icon" 
            />
            {{ isLoggedIn ? (isFavorite ? '已关注' : '关注') : '登录后关注' }}
          </el-button>
        </div>
        <div class="stock-tags">
          <el-tag size="small" type="info">行业：{{ stockInfo.industry }}</el-tag>
          <el-tag size="small" type="info">上市日期：{{ stockInfo.listingDate }}</el-tag>
        </div>
      </div>

      <div class="stock-tabs-section">
        <h3 class="section-title">资讯汇聚</h3>
        <el-tabs v-model="activeTab">
          <el-tab-pane label="股票资讯" name="news">
            <div class="stock-news-list">
              <div v-for="(news, index) in stockNews" :key="index" class="news-item">
                <h4 @click="viewNewsDetail(news.id)" class="news-title">{{ news.title }}</h4>
                <p v-if="news.summary" class="news-summary">{{ news.summary }}</p>
                <div class="news-footer">
                  <a v-if="news.url" :href="news.url" target="_blank" rel="noopener noreferrer" class="news-link">
                    查看原文
                  </a>
                  <span class="news-time">{{ news.time }}</span>
                </div>
              </div>
              <el-empty v-if="stockNews.length === 0" description="暂无相关资讯">
                <template #description>
                  <p>暂无相关资讯</p>
                  <p v-if="isRetryingNews" class="retry-info">
                    <span class="loading-icon"></span> 正在重试 ({{ newsRetryCount }}/8)...
                  </p>
                </template>
              </el-empty>
            </div>
            <el-pagination
              v-if="totalNews > pageSize"
              @current-change="handlePageChange"
              :current-page="currentPage"
              :page-size="pageSize"
              :total="totalNews"
              layout="prev, pager, next">
            </el-pagination>
          </el-tab-pane>
          <el-tab-pane label="AI投资建议" name="analysis">
            <!-- 已登录用户显示AI投资建议 -->
            <div v-if="isLoggedIn" class="analysis-content">
              <div class="analysis-header">
                <div class="analysis-title">
                  <div class="rating-display">
                    <span :class="getEvaluationClass(analysisResult.conclusion)">
                      {{ analysisResult.conclusion || '加载中...' }}
                    </span>
                  </div>
                </div>
                <div class="analysis-meta">
                  <span class="analysis-date">分析日期：{{ analysisResult.date }}</span>
                  <el-button 
                    size="small" 
                    type="primary" 
                    @click="refreshAIEvaluation" 
                    :loading="loadingEvaluation"
                    class="refresh-btn">
                    <img v-if="!loadingEvaluation" src="@/assets/refresh.svg" alt="刷新" class="button-icon" />
                    刷新评测
                  </el-button>
                </div>
              </div>
              
              <div class="analysis-detail">
                <h4>分析依据</h4>
                <div class="markdown-content" v-html="analysisResult.detail"></div>
              </div>
              
              <div class="reference-news" v-if="analysisResult.newsList && analysisResult.newsList.length > 0">
                <h4>参考新闻</h4>
                <ul class="news-reference-list">
                  <li v-for="(news, index) in analysisResult.newsList" :key="index" class="news-reference-item">
                    <div class="news-number">{{ index + 1 }}.</div>
                    <a 
                      :href="news.link || '#'" 
                      target="_blank" 
                      rel="noopener noreferrer"
                      class="news-reference-title"
                    >
                      {{ news.title }}
                    </a>
                    <div class="news-reference-time">{{ formatDate(news.publish_time) }}</div>
                  </li>
                </ul>
              </div>
            </div>
            
            <!-- 未登录用户显示登录提示 -->
            <div v-else class="login-required-content">
              <div class="login-prompt">
                <div class="prompt-icon">
                  🔒
                </div>
                <h3>需要登录才能查看AI投资建议</h3>
                <p>登录后可获得：</p>
                <ul class="feature-list">
                  <li>🤖 AI智能投资建议分析</li>
                  <li>📊 专业股票评级</li>
                  <li>📈 详细分析依据</li>
                  <li>📰 相关新闻参考</li>
                </ul>
                <el-button 
                  type="primary" 
                  size="large" 
                  @click="goToLogin"
                  class="login-button">
                  立即登录
                </el-button>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane label="业绩预测" name="forecast">
            <div class="forecast-content" v-loading="loadingForecast">
              <div v-if="forecastList.length > 0" class="forecast-list">
                <div v-for="item in forecastList" :key="item.id" class="forecast-item">
                  <div class="forecast-header">
                    <span class="report-period">{{ item.report_period }}</span>
                    <span class="forecast-type" :class="getForecastColor(item.forecast_type)">{{ item.forecast_type }}</span>
                  </div>
                  <div class="forecast-summary">{{ item.forecast_summary }}</div>
                  <div class="forecast-details">
                    <div class="detail-item">
                      <span class="label">上年同期净利润:</span>
                      <span class="value">{{ (item.last_year_profit / 10000).toFixed(2) }}万元</span>
                    </div>
                    <div class="detail-item" v-if="item.profit_forecast_median">
                      <span class="label">预计净利润(中值):</span>
                      <span class="value">{{ (item.profit_forecast_median / 10000).toFixed(2) }}万元</span>
                    </div>
                    <div class="detail-item" v-if="item.profit_growth_median">
                      <span class="label">预计增长(中值):</span>
                      <span class="value" :class="item.profit_growth_median > 0 ? 'stock-up' : 'stock-down'">
                        {{ item.profit_growth_median }}%
                      </span>
                    </div>
                  </div>
                  <div class="announcement-date">公告日期: {{ item.announcement_date }}</div>
                </div>
              </div>
              <el-empty v-else description="暂无业绩预测数据"></el-empty>
              
              <div class="forecast-footer">
                <a href="https://stcn.com/dc/sdcb.html?type=yjyg" target="_blank" class="source-link">
                  <img src="https://static-web.stcn.com/static/images/zqsb.png" alt="STCN Logo" class="source-logo">
                  <span>STCN证券时报网</span>
                </a>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
      
      <!-- 使用新的StockChart组件替代原来的股票图表部分 -->
      <StockChart :stockCode="stockInfo.code" />
      
      <div class="stock-data-section">
        <h3 class="section-title">交易数据</h3>
        <div class="data-grid">
          <div class="data-item">
            <span class="label">开盘价</span>
            <span class="value">{{ stockInfo.open }}</span>
          </div>
          <div class="data-item">
            <span class="label">最高价</span>
            <span class="value">{{ stockInfo.high }}</span>
          </div>
          <div class="data-item">
            <span class="label">最低价</span>
            <span class="value">{{ stockInfo.low }}</span>
          </div>
          <div class="data-item">
            <span class="label">5分钟变化</span>
            <span class="value">{{ stockInfo.change5min }}</span>
          </div>
          <div class="data-item">
            <span class="label">成交量</span>
            <span class="value">{{ stockInfo.volume }}</span>
          </div>
          <div class="data-item">
            <span class="label">成交额</span>
            <span class="value">{{ stockInfo.turnover }}</span>
          </div>
          <div class="data-item">
            <span class="label">市值</span>
            <span class="value">{{ stockInfo.marketCap }}</span>
          </div>
          <div class="data-item">
            <span class="label">最后更新</span>
            <span class="value">{{ stockInfo.lastUpdated }}</span>
          </div>
        </div>
      </div>
    </div>
    <el-dialog
      v-model="newsDetailDialogVisible"
      title="新闻详情"
      width="50%">
      <div v-if="currentNewsDetail">
        <h3>{{ currentNewsDetail.title }}</h3>
        <p>{{ currentNewsDetail.content }}</p>
        <div class="news-footer">
          <span class="news-source">{{ currentNewsDetail.source }}</span>
          <span class="news-time">{{ currentNewsDetail.publish_time }}</span>
        </div>
      </div>
      <div v-else>
        <el-empty description="暂无新闻详情"></el-empty>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { ref, onMounted, watch, onBeforeUnmount, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useStore } from 'vuex';
import { ElMessage } from 'element-plus';
import MarkdownIt from 'markdown-it';
import StockChart from '@/components/StockChart.vue';
import 'element-plus/es/components/message/style/css';

export default {
  name: 'StockDetailView',
  components: {
    StockChart // 注册组件
  },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const store = useStore();

    // 确保stockInfo总是存在，即使默认值
    const stockInfo = ref({
      name: '加载中...',
      code: route.params.code || '',
      market: '', // 添加市场代码字段
      price: '--',
      change: 0,
      changePercent: '--',
      industry: '--',
      region: '--',
      listingDate: '--',
      open: '--',
      high: '--',
      low: '--',
      change5min: '--',
      volume: '--',
      turnover: '--',
      marketCap: '--',
      lastUpdated: '--'
    });

    const activeTab = ref('news');
    const isLoggedIn = computed(() => store.getters.isLoggedIn);
    const isFavorite = ref(false);
    const addingToFavorites = ref(false);
    const stockNews = ref([]);
    const analysisResult = ref({
      conclusion: '',
      rating: '',
      date: '',
      summary: '',
      detail: '',
      factors: [],
      newsList: []
    });

    const currentNewsDetail = ref(null);
    const newsDetailDialogVisible = ref(false);
    const forecastList = ref([]);
    const loadingForecast = ref(false);
    const currentPage = ref(1);
    const pageSize = ref(5);
    const totalNews = ref(0);

    const md = new MarkdownIt({
      breaks: true,
      linkify: true,
      typographer: true
    });

    const loadingEvaluation = ref(false);

    const refreshAIEvaluation = async () => {
      if (!isLoggedIn.value) {
        ElMessage.warning('请先登录后查看AI投资建议');
        return;
      }
      loadingEvaluation.value = true;
      await loadAIEvaluation(true); // 强制刷新时设置 refresh 为 true
      loadingEvaluation.value = false;
    };

    const formatDate = (date) => {
      if (!date) return '';
      try {
        const parsedDate = new Date(date);
        return parsedDate.toLocaleDateString('zh-CN', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
        });
      } catch (error) {
        console.error('日期格式化失败:', error);
        return date;
      }
    };

    // 新闻自动重试相关变量
    const newsRetryCount = ref(0);
    const newsRetryTimer = ref(null);
    const isRetryingNews = ref(false);
    
    const loadForecast = async () => {
      loadingForecast.value = true;
      try {
        const data = await store.dispatch('fetchStockForecast', stockInfo.value.code);
        forecastList.value = data || [];
      } catch (error) {
        console.error('获取业绩预测失败:', error);
      } finally {
        loadingForecast.value = false;
      }
    };

    const getForecastColor = (type) => {
      if (!type) return '';
      if (type.includes('增')) return 'rating-strong-buy'; // 重大利好
      if (type.includes('减')) return 'rating-strong-sell'; // 重大利空
      if (type.includes('平')) return 'rating-hold'; // 中性
      return '';
    };

    const loadNewsAndAnalysis = async () => {
      try {
        const newsData = await store.dispatch('fetchStockNews', {
          stockCode: stockInfo.value.code,
          page: currentPage.value,
          limit: pageSize.value
        });

        if (newsData && newsData.list && newsData.list.length > 0) {
          stockNews.value = newsData.list.map(item => ({
            id: item.id,
            title: item.title,
            summary: item.summary || item.content?.substring(0, 100) || item.description || '',
            url: item.url || '#', // 使用新闻的 URL
            time: item.time || item.publish_time || new Date().toLocaleString()
          }));
          totalNews.value = newsData.total || stockNews.value.length;
          currentPage.value = newsData.currentPage || 1;
          
          // 重置重试计数
          newsRetryCount.value = 0;
          isRetryingNews.value = false;
          
          // 清除可能存在的重试定时器
          if (newsRetryTimer.value) {
            clearTimeout(newsRetryTimer.value);
            newsRetryTimer.value = null;
          }
        } else {
          stockNews.value = [];
          totalNews.value = 0;
          
          // 如果没有新闻，开始自动重试机制
          startNewsRetry();
        }
      } catch (error) {
        console.error('获取股票新闻失败:', error);
        stockNews.value = [];
        totalNews.value = 0;
        
        // 错误情况也启动重试
        startNewsRetry();
      }
    };
    
    // 新闻自动重试机制
    const startNewsRetry = () => {
      // 如果已经在重试中或已达到最大重试次数，则不再重试
      if (isRetryingNews.value || newsRetryCount.value >= 8) {
        if (newsRetryCount.value >= 8) {
          console.log('[NEWS] 已达到最大重试次数(8次)，停止重试');
          isRetryingNews.value = false;
        }
        return;
      }
      
      isRetryingNews.value = true;
      newsRetryCount.value++;
      
      console.log(`[NEWS] 暂无资讯，30秒后将进行第 ${newsRetryCount.value}/8 次重试`);
      
      // 清除之前的定时器（如果有）
      if (newsRetryTimer.value) {
        clearTimeout(newsRetryTimer.value);
      }
      
      // 设置3秒后重试
      newsRetryTimer.value = setTimeout(async () => {
        console.log(`[NEWS] 执行第 ${newsRetryCount.value} 次资讯重试`);
        await loadNewsAndAnalysis();
      }, 3000); // 3秒
    };
    
    const mapConclusionToRating = (conclusion) => {
      if (!conclusion) return '';
      
      if (['看多', '强烈看多', '买入', '利好'].includes(conclusion)) {
        return 'rating-buy';
      } else if (['重大利好'].includes(conclusion)) {
        return 'rating-strong-buy';
      } else if (['看空', '强烈看空', '卖出', '利空'].includes(conclusion)) {
        return 'rating-sell';
      } else if (['重大利空'].includes(conclusion)) {
        return 'rating-strong-sell';
      } else if (['中性', '观望', '持有'].includes(conclusion)) {
        return 'rating-hold';
      }
      return '';
    };

    const loadAIEvaluation = async (refresh = false) => {
      if (!isLoggedIn.value) {
        console.log('[DEBUG] 用户未登录，跳过AI评估加载');
        return;
      }
      
      try {
        console.log('[DEBUG] 发起获取股票AI评估请求:', stockInfo.value.code, '刷新:', refresh);
        const evaluation = await store.dispatch('fetchStockEvaluation', {
          stockCode: stockInfo.value.code,
          refresh: refresh
        });

        console.log('[DEBUG] 接收到评估结果:', evaluation);

        if (evaluation) {
          analysisResult.value = {
            conclusion: evaluation.conclusion || '未知',
            rating: mapConclusionToRating(evaluation.conclusion),
            date: evaluation.evaluation_time || formatDate(new Date()),
            summary: md.render(evaluation.reason || '暂无分析内容'), 
            detail: md.render(evaluation.reason || '暂无分析内容'),
            newsList: evaluation.news_list || []
          };
          
          console.log('[DEBUG] 解析后的新闻列表:', analysisResult.value.newsList);
        } else {
          analysisResult.value = {
            conclusion: '未知',
            rating: '未知',
            date: formatDate(new Date()),
            summary: '暂无AI评估数据',
            detail: '无法获取AI评估结果，请稍后再试。',
            newsList: []
          };
        }
      } catch (error) {
        console.error('获取股票AI评估失败:', error);
        analysisResult.value = {
          conclusion: '获取失败',
          rating: '未知',
          date: formatDate(new Date()),
          summary: 'AI评估数据获取失败',
          detail: '获取AI评估结果时发生错误，请稍后再试。',
          newsList: []
        };
      } finally {
        loadingEvaluation.value = false;
      }
    };

    const loadStockData = async () => {
      try {
        const stockDetail = await store.dispatch('fetchStockDetail', stockInfo.value.code);

        if (stockDetail) {
          const tradingData = stockDetail.trading || {};
          stockInfo.value = {
            name: stockDetail.name || '未知',
            code: stockDetail.code || stockInfo.value.code,
            market: stockDetail.market || '', // 从API响应获取市场代码
            price: tradingData.current_price || '--',
            change: tradingData.current_price * tradingData.change_percent / 100 || 0,
            changePercent: tradingData.change_percent || '--',
            industry: stockDetail.industry || '未知行业',
            region: '未知',
            listingDate: stockDetail.listing_date || '--',
            open: tradingData.open || '--',
            high: tradingData.high || '--',
            low: tradingData.low || '--',
            change5min: tradingData.change_5min || '--',
            volume: tradingData.volume || '--',
            turnover: tradingData.turnover || '--',
            marketCap: tradingData.market_cap || '--',
            lastUpdated: tradingData.last_updated || '--'
          };

          document.title = `${stockInfo.value.name}(${stockInfo.value.market || '未知'}${stockInfo.value.code}) - AI StockLink`;

          // 更新最后价格更新时间
          lastPriceUpdate.value = new Date();
        } else {
          ElMessage.error('获取股票数据失败');
        }
      } catch (error) {
        console.error('加载股票数据异常:', error);
        ElMessage.error('获取股票数据失败');
      }
    };
    
    const checkIfFavorite = () => {
      const favoriteStocks = store.getters.favoriteStocks || [];
      isFavorite.value = favoriteStocks.some(stock => stock.code === stockInfo.value.code);
    };

    const toggleFavorite = async () => {
      if (!isLoggedIn.value) {
        ElMessage.warning('请先登录');
        router.push('/login');
        return;
      }

      addingToFavorites.value = true;
      
      try {
        if (isFavorite.value) {
          // 取消关注
          const result = await store.dispatch('removeFavoriteStocks', [stockInfo.value.code]);
          if (result) {
            ElMessage.success(`已将 ${stockInfo.value.name} 从自选股中移除`);
            isFavorite.value = false;
          } else {
            ElMessage.error(`移除 ${stockInfo.value.name} 失败`);
          }
        } else {
          // 添加关注
          const result = await store.dispatch('addFavoriteStocks', [
            { code: stockInfo.value.code, name: stockInfo.value.name }
          ]);
          
          if (result) {
            ElMessage.success(`成功添加 ${stockInfo.value.name} 到自选股`);
            isFavorite.value = true;
          } else {
            ElMessage.error(`添加 ${stockInfo.value.name} 到自选股失败`);
          }
        }
        // 刷新自选股列表
        await store.dispatch('fetchFavoriteStocks');
      } catch (error) {
        console.error('操作自选股失败:', error);
        ElMessage.error('操作失败，请稍后再试');
      } finally {
        addingToFavorites.value = false;
      }
    };

    const getEvaluationClass = (conclusion) => {
      if (!conclusion) return '';
      
      if (['看多', '强烈看多', '买入', '利好'].includes(conclusion)) {
        return 'rating-buy';
      } else if (['重大利好'].includes(conclusion)) {
        return 'rating-strong-buy';
      } else if (['看空', '强烈看空', '卖出', '利空'].includes(conclusion)) {
        return 'rating-sell';
      } else if (['重大利空'].includes(conclusion)) {
        return 'rating-strong-sell';
      } else if (['中性', '观望', '持有'].includes(conclusion)) {
        return 'rating-hold';
      }
      return '';
    };

    const handlePageChange = async (page) => {
      currentPage.value = page;
      await loadNewsAndAnalysis(); // 重新加载新闻数据
    };

    const viewNewsDetail = async (newsId) => {
      try {
        console.log(`查看新闻详情，新闻ID: ${newsId}`);
        newsDetailDialogVisible.value = true;
        currentNewsDetail.value = null; // 清空当前新闻详情，显示加载状态

        const response = await store.dispatch('fetchNewsDetail', newsId);
        if (response) {
          currentNewsDetail.value = response;
        } else {
          ElMessage.error('获取新闻详情失败');
          newsDetailDialogVisible.value = false;
        }
      } catch (error) {
        console.error('获取新闻详情失败:', error);
        ElMessage.error('获取新闻详情失败');
        newsDetailDialogVisible.value = false;
      }
    };

    // 定时器相关
    const priceUpdateTimer = ref(null); // 价格更新定时器
    const newsUpdateTimer = ref(null);  // 新闻更新定时器
    const lastPriceUpdate = ref(new Date()); // 最后价格更新时间
    const lastNewsUpdate = ref(new Date()); // 最后新闻更新时间

    // 设置自动刷新定时器
    const setupAutoRefresh = () => {
      // 清除现有的定时器（如果有）
      clearAutoRefreshTimers();
      
      // 价格数据每5分钟更新一次（300000毫秒）
      priceUpdateTimer.value = setInterval(() => {
        console.log('[AUTO] 5分钟定时更新价格数据');
        loadStockData();
      }, 5 * 60 * 1000); // 5分钟
      
      // 新闻每10分钟更新一次（600000毫秒）
      newsUpdateTimer.value = setInterval(() => {
        console.log('[AUTO] 10分钟定时更新新闻数据');
        loadNewsAndAnalysis();
      }, 10 * 60 * 1000); // 10分钟
    };
    
    // 清除所有定时器
    const clearAllTimers = () => {
      clearAutoRefreshTimers();
      
      // 清除新闻重试定时器
      if (newsRetryTimer.value) {
        clearTimeout(newsRetryTimer.value);
        newsRetryTimer.value = null;
      }
    };
    
    // 清除自动刷新定时器
    const clearAutoRefreshTimers = () => {
      if (priceUpdateTimer.value) {
        clearInterval(priceUpdateTimer.value);
        priceUpdateTimer.value = null;
      }
      
      if (newsUpdateTimer.value) {
        clearInterval(newsUpdateTimer.value);
        newsUpdateTimer.value = null;
      }
    };

    // 当路由中的股票代码改变时触发重新加载
    watch(() => route.params.code, (newCode) => {
      if (newCode && newCode !== stockInfo.value.code) {
        stockInfo.value.code = newCode;
        
        // 切换股票时重置新闻重试状态
        newsRetryCount.value = 0;
        isRetryingNews.value = false;
        if (newsRetryTimer.value) {
          clearTimeout(newsRetryTimer.value);
          newsRetryTimer.value = null;
        }
        
        loadStockData();
        loadNewsAndAnalysis();
        
        // 重新设置自动刷新定时器
        setupAutoRefresh();
        
        // 重置滚动位置到顶部
        window.scrollTo(0, 0);
      }
    });

    watch(activeTab, async (newTab) => {
      if (newTab === 'analysis' && isLoggedIn.value) {
        loadingEvaluation.value = true;
        await loadAIEvaluation(false); // 切换到 "AI投资建议" Tab 时自动加载数据
        loadingEvaluation.value = false;
      } else if (newTab === 'forecast') {
        loadForecast();
      }
    });

    onMounted(() => {
      // 重置滚动位置到顶部
      window.scrollTo(0, 0);
      
      // 确保在挂载时stockInfo已经初始化
      if (!stockInfo.value || !stockInfo.value.code) {
        stockInfo.value = {
          name: '加载中...',
          code: route.params.code || '',
          market: '',
          price: '--',
          change: 0,
          changePercent: '--',
          industry: '--',
          region: '--',
          listingDate: '--',
          open: '--',
          high: '--',
          low: '--',
          change5min: '--',
          volume: '--',
          turnover: '--',
          marketCap: '--',
          lastUpdated: '--'
        };
      }

      loadStockData();
      loadNewsAndAnalysis();
      // 加载时检查是否已在自选列表中
      if (isLoggedIn.value) {
        store.dispatch('fetchFavoriteStocks').then(() => {
          checkIfFavorite();
        });
      }
      
      // 设置自动刷新定时器
      setupAutoRefresh();
      
      // 确保页面加载时滚动到顶部
      window.scrollTo(0, 0);
    });

    onBeforeUnmount(() => {
      // 使用新的清除所有定时器函数
      clearAllTimers();
    });

    // 跳转到登录页面
    const goToLogin = () => {
      router.push('/login');
    };

    return {
      stockInfo,
      activeTab,
      isFavorite,
      addingToFavorites,
      stockNews,
      analysisResult,
      currentNewsDetail,
      newsDetailDialogVisible,
      currentPage,
      pageSize,
      totalNews,
      loadNewsAndAnalysis,
      loadAIEvaluation,
      loadStockData,
      toggleFavorite,
      getEvaluationClass,
      formatDate,
      refreshAIEvaluation,
      loadingEvaluation,
      handlePageChange,
      viewNewsDetail,
      mapConclusionToRating,  // 确保函数被返回
      lastPriceUpdate,
      lastNewsUpdate,
      isRetryingNews,
      newsRetryCount,
      isLoggedIn,
      goToLogin,
      forecastList,
      loadingForecast,
      loadForecast,
      getForecastColor
    };
  },
};
</script>

<style lang="scss" scoped>
.stock-detail-page {
  padding-top: 80px;

  .page-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 20px;
  }

  .stock-header {
    margin-bottom: 20px;

    .stock-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 10px;

      h1 {
        font-size: 2rem;
        margin: 0;

        .stock-code-container {
          display: inline-block;
          font-size: 1.2rem;
          color: var(--text-secondary);
          margin-left: 10px;
          border: 1px solid #ddd;
          padding: 2px 8px;
          border-radius: 4px;
          background-color: #f8f8f8;
        }

        .market-code {
          font-weight: bold;
          color: #409EFF;
          margin-right: 2px;
        }
        
        .code-separator {
          color: #999;
          margin: 0 2px;
        }
      }

      .stock-price-info {
        margin-left: auto;
        margin-right: 20px;

        .current-price {
          font-size: 1.5rem;
          font-weight: bold;
          margin-right: 10px;
        }

        .stock-up {
          color: var(--danger-color);
        }

        .stock-down {
          color: var(--success-color);
        }
      }
    }

    .stock-tags {
      display: flex;
      gap: 10px;
    }
  }

  .section-title {
    margin-top: 0;
    margin-bottom: 20px;
    font-size: 1.5rem;
    font-weight: 600;
  }

  .stock-data-section,
  .stock-tabs-section {
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
    padding: 20px;
    margin-bottom: 20px;
  }

  .stock-data-section {
    .data-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 20px;

      @media (max-width: 992px) {
        grid-template-columns: repeat(2, 1fr);
      }

      @media (max-width: 576px) {
        grid-template-columns: 1fr;
      }

      .data-item {
        display: flex;
        flex-direction: column;

        .label {
          font-size: 0.9rem;
          color: var(--text-secondary);
        }

        .value {
          font-size: 1.1rem;
          font-weight: 500;
        }
      }
    }
  }

  .stock-tabs-section {
    .stock-news-list {
      margin-top: 0;
      margin-bottom: 10px;

      .news-item {
        padding: 15px 0;
        border-bottom: 1px solid var(--border-color);

        &:last-child {
          border-bottom: none;
        }

        h4.news-title {
          margin-top: 0;
          margin-bottom: 10px;
          font-size: 1.1rem;
          cursor: pointer;
          color: var(--primary-color);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          width: 100%;
          display: block;
        }

        .news-summary {
          color: var(--text-secondary);
          margin-bottom: 10px;
          line-height: 1.5;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          width: 100%;
          display: block;
        }

        .news-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 0.9rem;
          color: var(--text-tertiary);

          .news-link {
            color: var(--primary-color);
            text-decoration: none;

            &:hover {
              text-decoration: underline;
            }
          }
        }
      }
    }

    .analysis-content {
      .analysis-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 20px;

        .analysis-title {
          display: flex;
          align-items: center;
          gap: 15px;

          .rating-display {
            > span {
              font-weight: bold;
              font-size: 2.0rem;

              &.rating-buy {
                color: #f56c6c !important; // 明确的红色
              }

              &.rating-strong-buy {
                color: #ff0000 !important; // 更鲜艳的红色
                font-weight: 800;
              }

              &.rating-sell {
                color: #67c23a !important; // 明确的绿色
              }

              &.rating-strong-sell {
                color: #00cc00 !important; // 更鲜艳的绿色
                font-weight: 800;
              }

              &.rating-hold {
                color: #0066cc !important; // 明确的深蓝色
              }
            }
          }
        }

        .analysis-meta {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 8px;
        }

        .analysis-date {
          color: var(--text-tertiary);
        }
      }

      .analysis-detail {
        margin-bottom: 20px;

        h4 {
          margin-top: 0;
          margin-bottom: 10px;
          font-size: 1.1rem;
        }

        .markdown-content {
          line-height: 1.6;
          color: var(--text-secondary);

          :deep(p) {
            margin-bottom: 10px;
          }

          :deep(ul),
          :deep(ol) {
            padding-left: 20px;
            margin-bottom: 10px;
          }

          :deep(h1),
          :deep(h2),
          :deep(h3),
          :deep(h4),
          :deep(h5),
          :deep(h6) {
            margin-top: 16px;
            margin-bottom: 10px;
          }

          :deep(code) {
            background-color: #f5f5f5;
            padding: 2px 4px;
            border-radius: 3px;
          }

          :deep(blockquote) {
            border-left: 4px solid #ddd;
            padding-left: 10px;
            color: #777;
            margin: 10px 0;
          }
        }
      }

      .reference-news {
        margin-top: 20px;
        margin-bottom: 20px;

        h4 {
          margin-top: 0;
          margin-bottom: 15px;
          font-size: 1.1rem;
        }

        .news-reference-list {
          list-style: none;
          padding: 0;
          margin: 0;

          .news-reference-item {
            padding: 6px 0;  // 降低行高
            border-bottom: 1px dashed #eee;
            display: flex;
            justify-content: flex-start;
            align-items: center;
            
            &:last-child {
              border-bottom: none;
            }

            .news-number {
              width: 24px;
              color: #999;
              font-size: 0.85rem;
            }

            .news-reference-title {
              flex: 1;
              font-size: 0.95rem;
              color: #999;  // 浅灰色
              white-space: nowrap;
              overflow: hidden;
              text-overflow: ellipsis;
              text-decoration: none;
              
              &:hover {
                text-decoration: underline;  // 鼠标悬停时显示下划线
                color: var(--primary-color);
              }
            }

            .news-reference-time {
              margin-left: 15px;
              font-size: 0.85rem;
              color: var(--text-tertiary);
              white-space: nowrap;
            }
          }
        }
      }
    }
  }

  .button-icon {
    width: 14px;
    height: 14px;
    margin-right: 4px;
    vertical-align: middle;
  }

  .refresh-btn {
    .button-icon {
      width: 16px;
      height: 16px;
    }
  }
  
  .retry-info {
    font-size: 0.9rem;
    color: var(--text-tertiary);
    margin-top: 5px;
    
    .loading-icon {
      display: inline-block;
      width: 14px;
      height: 14px;
      margin-right: 5px;
      border: 2px solid #e6e6e6;
      border-radius: 50%;
      border-top: 2px solid #409EFF;
      vertical-align: middle;
      animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
  }
}

// 登录提示框样式
.login-required-content {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
  
  .login-prompt {
    text-align: center;
    padding: 40px;
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    border-radius: 12px;
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
    max-width: 400px;
    
    .prompt-icon {
      font-size: 48px;
      color: #409EFF;
      margin-bottom: 20px;
      
      i {
        font-size: 48px;
      }
    }
    
    h3 {
      color: #303133;
      margin-bottom: 16px;
      font-weight: 600;
    }
    
    p {
      color: #606266;
      margin-bottom: 16px;
      font-size: 14px;
    }
    
    .feature-list {
      text-align: left;
      margin: 20px 0;
      padding: 0;
      list-style: none;
      
      li {
        padding: 8px 0;
        color: #606266;
        font-size: 14px;
        display: flex;
        align-items: center;
        
        &:before {
          content: '';
          width: 6px;
          height: 6px;
          background-color: #409EFF;
          border-radius: 50%;
          margin-right: 12px;
        }
      }
    }
    
    .login-button {
      margin-top: 24px;
      padding: 12px 32px;
      font-size: 16px;
      border-radius: 6px;
      box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
      
      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(64, 158, 255, 0.4);
      }
    }
  }
}

.forecast-content {
  .forecast-list {
    display: flex;
    flex-direction: column;
    gap: 15px;
  }

  .forecast-item {
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 15px;
    background-color: #fff;
    transition: all 0.3s;

    &:hover {
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
    }

    .forecast-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;

      .report-period {
        font-weight: 600;
        font-size: 16px;
        color: var(--text-primary);
      }

      .forecast-type {
        font-size: 14px;
        padding: 2px 8px;
        border-radius: 4px;
        background-color: #f0f2f5;
        color: var(--text-secondary);

        &.rating-strong-buy {
          background-color: rgba(245, 108, 108, 0.1);
          color: #f56c6c;
        }

        &.rating-strong-sell {
          background-color: rgba(103, 194, 58, 0.1);
          color: #67c23a;
        }

        &.rating-hold {
          background-color: rgba(230, 162, 60, 0.1);
          color: #e6a23c;
        }
      }
    }

    .forecast-summary {
      font-size: 15px;
      color: var(--text-regular);
      margin-bottom: 12px;
      line-height: 1.5;
    }

    .forecast-details {
      display: flex;
      flex-wrap: wrap;
      gap: 20px;
      margin-bottom: 10px;
      padding: 10px;
      background-color: #f9fafc;
      border-radius: 4px;

      .detail-item {
        display: flex;
        align-items: center;
        font-size: 13px;

        .label {
          color: var(--text-secondary);
          margin-right: 8px;
        }

        .value {
          font-weight: 500;
          color: var(--text-primary);
        }
      }
    }

    .announcement-date {
      font-size: 12px;
      color: var(--text-tertiary);
      text-align: right;
    }
  }

  .forecast-footer {
    margin-top: 20px;
    display: flex;
    justify-content: flex-end;
    
    .source-link {
      display: flex;
      align-items: center;
      text-decoration: none;
      color: #909399;
      font-size: 12px;
      transition: opacity 0.2s;
      
      &:hover {
        opacity: 0.8;
      }
      
      .source-logo {
        height: 16px;
        margin-right: 6px;
      }
    }
  }
}
</style>