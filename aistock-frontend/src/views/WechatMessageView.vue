<template>
  <div class="wechat-message-page">
    <div class="page-container">
      <div class="message-container">
        <div v-if="loading" class="loading-container">
          <el-skeleton :rows="10" animated />
        </div>
        <div v-else-if="error" class="error-container">
          <i class="el-icon-warning-outline"></i>
            <h3>加载失败</h3>
            <p>{{ error }}</p>
            <el-button type="primary" @click="fetchMessageData">重试</el-button>
            <el-button @click="goToHome">返回首页</el-button>
        </div>
        <template v-if="messageData">
          <div class="message-content">
            <div class="message-header">
              <h2>{{ isSingleStock ? '个股推送' : '行情速览' }}</h2>
              <div class="message-time">{{ messageData.date }}</div>
            </div>
            <!-- 统一使用行情速览样式：个股推送被归一为 top_news 的单条记录 -->
            <div v-if="messageData.top_news && messageData.top_news.length > 0" class="news-section">
              <h3 class="section-title" v-if="!isSingleStock">头条新闻</h3>
              <div class="news-list">
                <div v-for="news in messageData.top_news" :key="news.id" class="news-card">
                  <h4 class="news-title">{{ news.title }}</h4>
                  <div class="news-meta">
                    <span class="news-time">{{ formatDate(news.published_at) }}</span>
                    <span :class="['news-evaluation', getEvaluationClass(news.evaluation)]">{{ news.evaluation }}</span>
                    <span v-for="sector in getSectorList(news.sector)" :key="sector" class="news-sector clickable-sector" @click="isSingleStock ? goToStock(news.stock_id) : goToTag(sector)">{{ sector }}</span>
                  </div>
                  <div class="news-content" v-html="formatContent(news.content)"></div>
                  <div v-if="news.reason && news.reason.trim()" :class="['news-reason', getReasonClass(news.evaluation)]">
                    <strong>AI分析：</strong>{{ news.reason }}
                  </div>
                  <div class="news-link" v-if="news.link">
                    <a :href="news.link" target="_blank" rel="noopener noreferrer">阅读原文</a>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="!isSingleStock && messageData.hk_us_news && messageData.hk_us_news.length > 0" class="news-section">
              <h3 class="section-title">港美股资讯</h3>
              <div class="news-list">
                <div v-for="news in messageData.hk_us_news" :key="news.id" class="news-card">
                  <h4 class="news-title">{{ news.title }}</h4>
                  <div class="news-meta">
                    <span class="news-time">{{ formatDate(news.published_at) }}</span>
                    <span :class="['news-evaluation', getEvaluationClass(news.evaluation)]">{{ news.evaluation }}</span>
                    <span v-for="sector in getSectorList(news.sector)" :key="sector" class="news-sector clickable-sector" @click="goToTag(sector)">{{ sector }}</span>
                  </div>
                  <div class="news-content" v-html="formatContent(news.content)"></div>
                  <div v-if="news.reason && news.reason.trim()" :class="['news-reason', getReasonClass(news.evaluation)]">
                    <strong>AI分析：</strong>{{ news.reason }}
                  </div>
                  <div class="news-link" v-if="news.link">
                    <a :href="news.link" target="_blank" rel="noopener noreferrer">阅读原文</a>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="!isSingleStock && (!messageData.top_news || messageData.top_news.length === 0) && (!messageData.hk_us_news || messageData.hk_us_news.length === 0)" class="empty-state">
              <p>暂无数据</p>
            </div>
            <div class="footer-actions">
              <el-button type="primary" @click="goToHome">返回首页</el-button>
              <el-button @click="copyShareLink">复制分享链接</el-button>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useStore } from 'vuex';
import { ElMessage } from 'element-plus';
import 'element-plus/es/components/message/style/css';

export default {
  name: 'WechatMessageView',
  setup() {
    const route = useRoute();
    const router = useRouter();
    const store = useStore();
    const msgId = ref(route.params.msgid);
    const messageData = ref(null);
    const loading = ref(true);
    const error = ref(null);
    const isSingleStock = computed(() => {
      return messageData.value && messageData.value.top_news && messageData.value.top_news.length === 1 && messageData.value.top_news[0].stock_id;
    });

    const isValidMsgId = computed(() => msgId.value && typeof msgId.value === 'string' && msgId.value.trim() !== '');

    const fetchMessageData = async () => {
      if (!isValidMsgId.value) {
        error.value = '无效的消息ID';
        loading.value = false;
        return;
      }
      loading.value = true;
      error.value = null;
      try {
        console.log(`[DEBUG] 开始获取微信消息数据, msgId: ${msgId.value}`);
        const data = await store.dispatch('fetchWechatMessage', msgId.value);
        console.log(`[DEBUG] 微信消息数据响应:`, data);
        if (data) {
          if (typeof data === 'object' && data.stock_id && data.stock_name) {
            // 个股推送 -> 归一为 top_news 单条
            messageData.value = {
              date: data.date || data.published_at || '',
              top_news: [{
                id: data.id || data.stock_id || Date.now(),
                title: data.title || data.stock_name,
                published_at: data.published_at || data.date,
                evaluation: data.evaluation || '',
                sector: data.stock_name, // 用股票名称显示标签样式
                stock_id: data.stock_id,
                content: data.content || '',
                reason: data.reason || '',
                link: data.link || ''
              }],
              hk_us_news: []
            };
          } else if (typeof data === 'object' && (data.top_news || data.hk_us_news || data.date)) {
            messageData.value = {
              date: data.date || '',
              top_news: data.top_news || [],
              hk_us_news: data.hk_us_news || []
            };
          } else {
            console.warn('[WARN] 未知的微信消息格式，使用空结构');
            messageData.value = { date: '', top_news: [], hk_us_news: [] };
          }
        } else {
          error.value = '获取数据失败：服务器返回空数据';
        }
      } catch (err) {
        console.error('获取微信消息数据失败:', err);
        if (err.response) {
          const status = err.response.status;
            const message = err.response.data?.message || '未知错误';
            error.value = `获取数据失败 (${status}): ${message}`;
        } else if (err.request) {
          error.value = '网络请求失败，请检查您的网络连接';
        } else {
          error.value = `请求出错: ${err.message || '未知错误'}`;
        }
      } finally {
        loading.value = false;
      }
    };

    const formatDate = (dateStr) => {
      if (!dateStr) return '';
      const date = new Date(dateStr);
      if (isNaN(date)) return dateStr; // 如果不是标准日期格式，直接返回原字符串
      return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
    };

    const formatContent = (content) => content ? content.replace(/\n/g, '<br>') : '';

    const getEvaluationClass = (evaluation) => {
      if (!evaluation) return '';
      if (evaluation.includes('利好')) return 'positive';
      if (evaluation.includes('利空')) return 'negative';
      return 'neutral';
    };

    const getReasonClass = (evaluation) => {
      if (!evaluation) return '';
      if (evaluation.includes('利好')) return 'reason-positive';
      if (evaluation.includes('利空')) return 'reason-negative';
      return 'reason-neutral';
    };

    const getSectorList = (sector) => {
      if (!sector || typeof sector !== 'string') return [];
      return sector.split(/[、，,;]/).filter(s => s.trim() !== '').map(s => s.trim());
    };

    const goToTag = (tagName) => { if (tagName && tagName.trim()) router.push(`/tags/${encodeURIComponent(tagName.trim())}`); };
    const goToStock = (stockId) => { if (stockId) window.open(`https://aistocklink.cn/stock/${stockId}`, '_blank'); };
    const goToHome = () => router.push('/');
    const copyShareLink = () => {
      const url = window.location.href;
      navigator.clipboard.writeText(url).then(() => ElMessage.success('链接已复制到剪贴板'), () => ElMessage.error('复制失败，请手动复制'));
    };

    onMounted(() => {
      // 重置滚动位置到顶部
      window.scrollTo(0, 0);
      
      document.title = '微信推送消息详情 - AI StockLink';
      if (isValidMsgId.value) fetchMessageData(); else { error.value = '消息ID不存在或无效'; loading.value = false; }
    });

    return {
      msgId,
      messageData,
      loading,
      error,
      isSingleStock,
      fetchMessageData,
      formatDate,
      formatContent,
      getEvaluationClass,
      getReasonClass,
      getSectorList,
      goToTag,
      goToStock,
      goToHome,
      copyShareLink
    };
  }
};
</script>

<style lang="scss" scoped>
.wechat-message-page {
  background-color: var(--background-color);
  min-height: 100vh;

  .message-container {
    background-color: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
    padding: 20px;
    margin-bottom: 20px;
  }

  .loading-container {
    padding: 20px 0;
  }

  .error-container {
    text-align: center;
    padding: 40px 0;
    color: var(--text-tertiary);

    i {
      font-size: 40px;
      color: #f56c6c;
      margin-bottom: 15px;
    }

    h3 {
      margin-bottom: 15px;
      font-size: 20px;
      color: var(--text-primary);
    }

    p {
      margin-bottom: 25px;
      word-break: break-word;
      max-width: 80%;
      margin-left: auto;
      margin-right: auto;
    }

    .el-button {
      margin: 0 10px;
    }
  }

  .message-header {
    text-align: center;
    margin-bottom: 20px;
    padding-bottom: 15px;
    border-bottom: 1px solid var(--border-color);

    h2 {
      font-size: 24px;
      color: var(--primary-color);
      margin-bottom: 10px;
    }

    .message-time {
      color: var(--text-tertiary);
      font-size: 14px;
    }
  }

  .news-section {
    margin-bottom: 30px;

    .section-title {
      font-size: 18px;
      font-weight: 500;
      color: var(--text-primary);
      margin-bottom: 15px;
      padding-left: 10px;
      border-left: 3px solid var(--primary-color);
    }

    .news-list {
      .news-card {
        background: #f9f9f9;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 15px;

        .news-title {
          font-size: 16px;
          font-weight: 500;
          color: var(--text-primary);
          margin-bottom: 10px;
        }

        .news-meta {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
          margin-bottom: 10px;
          font-size: 12px;

          .news-time {
            color: var(--text-tertiary);
          }

          .news-evaluation {
            padding: 2px 6px;
            border-radius: 3px;
            font-weight: 500;

            &.positive {
              background-color: #ffecec;
              color: #f56c6c;
            }

            &.negative {
              background-color: #f0f9eb;
              color: #67c23a;
            }

            &.neutral {
              background-color: #f4f4f5;
              color: #909399;
            }
          }

          .news-sector {
            background-color: #ecf5ff;
            color: #409eff;
            padding: 2px 6px;
            border-radius: 3px;
            
            &.clickable-sector {
              cursor: pointer;
              transition: all 0.2s ease;
              
              &:hover {
                background-color: #409eff;
                color: white;
                transform: translateY(-1px);
              }
            }
          }

          .news-stocks {
            background-color: #ecf5ff;
            color: #409eff;
            padding: 2px 6px;
            border-radius: 3px;
          }
        }

        .news-content {
          font-size: 14px;
          line-height: 1.6;
          color: var(--text-secondary);
          margin-bottom: 10px;
          white-space: pre-line;
        }

        .news-reason {
          padding: 10px;
          border-radius: 5px;
          font-size: 14px;
          color: var(--text-secondary);
          margin-bottom: 10px;
          background-color: #f5f7fa;
          
          strong {
            font-weight: 600;
            color: #909399;
          }
          
          &.reason-positive {
            background-color: #ffecec;
            
            strong {
              color: #f56c6c;
            }
          }
          
          &.reason-negative {
            background-color: #f0f9eb;
            
            strong {
              color: #67c23a;
            }
          }
          
          &.reason-neutral {
            background-color: #f5f7fa;
            
            strong {
              color: #909399;
            }
          }
        }

        .news-link {
          text-align: right;

          a {
            color: var(--primary-color);
            text-decoration: none;
            font-size: 14px;

            &:hover {
              text-decoration: underline;
            }
          }
        }
      }
    }
  }

  .empty-state {
    text-align: center;
    padding: 40px 0;
    color: var(--text-tertiary);
  }

  .footer-actions {
    display: flex;
    justify-content: center;
    gap: 15px;
    margin-top: 30px;
  }
}
</style>
