import axios from 'axios';

// 开发模式下使用相对路径，生产模式下使用完整URL
const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? 'https://api.aistocklink.cn' 
  : 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 180000, // 增加超时时间为 180 秒
  headers: {
    'Content-Type': 'application/json'
  },
  withCredentials: true // 确保跨域请求时携带 cookie
});

// 请求拦截器 - 添加token
api.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  error => Promise.reject(error)
);

// 响应拦截器 - 处理错误
api.interceptors.response.use(
  response => response.data,
  error => {
    if (error.response && error.response.status === 401) {
      // 未授权，清除token和用户信息
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      
      // 不强制重定向，让路由守卫和组件自己处理
      // 这样可以确保未登录用户仍能访问不需要登录的页面
    }
    return Promise.reject(error);
  }
);

// 扫码登录相关API
export const authApi = {
  // 获取扫码登录URL
  getScanLoginUrl: () => api.get('/api/auth/scan-login-url'),
  
  // 检查扫码登录状态
  checkScanLoginStatus: (state) => api.get(`/api/auth/login-status?state=${state}`),
  
  // 获取用户信息
  getUserInfo: () => api.get('/api/user/info'),

  // 更新用户信息（昵称和头像）
  updateUserProfile: (nickname, avatar_url) => api.post('/api/user/profile', { 
    nickname, 
    avatar_url 
  })
};

// 股票相关API
export const stockApi = {
  // 获取当前用户的所有自选股票
  getStocks: () => api.get('/api/stocks/get'),

  // 批量添加自选股票
  addStocks: (stocks) => api.post('/api/stocks/add', { stocks }),

  // 批量删除自选股票
  removeStocks: (stockCodes) => api.post('/api/stocks/remove', { codes: stockCodes }),

  // 通过图片 OCR 批量添加自选股票
  addStocksFromImage: (imageBase64) => api.post('/api/stocks/add_from_image', { image: imageBase64 }),

  // 确认添加从图片中识别的股票
  confirmStocksFromImage: () => api.post('/api/stocks/confirm_from_image'),

  // 根据关键词搜索股票
  searchStocks: (keyword, limit = 10) => api.get(`/api/stocks/search?keyword=${keyword}&limit=${limit}`),

  // 获取最热门股票
  getHotStocks: (symbol = '最热门') => api.get(`/api/stocks/hot?symbol=${symbol}`),

  // 获取股票历史价格数据
  getStockHistory: (code, years = 3) => api.get(`/api/stocks/history?code=${code}&years=${years}`),
  
  // 获取股票详细信息
  getStockDetail: (code) => api.get(`/api/stocks/detail?code=${code}`),

  // 获取股票业绩预测
  getForecast: (code) => api.get(`/api/stocks/forecast?code=${code}`),

  // 获取股票相关新闻列表
  getStockNews: (code, page = 1, limit = 5) => {
    return api.get(`/api/news/get?code=${encodeURIComponent(code)}&page=${page}&limit=${limit}`);
  },
  
  // 获取自选股推送新闻
  getPushNews: (page = 1, limit = 5) => {
    return api.get(`/api/news/pushnews?page=${page}&limit=${limit}`);
  },
  
  // 获取新闻详情
  getNewsDetail: (newsId) => {
    // 为新闻详情API设置更长的超时时间
    return api.get(`/api/news/detail?id=${encodeURIComponent(newsId)}`, {
      timeout: 300000 // 5分钟超时
    });
  },
  
  // 获取标签相关的龙头股票
  getTagLeaders: (tagName) => {
    return api.get(`/api/tags/leaders?tag=${encodeURIComponent(tagName)}`);
  },

  // 获取 AI 评估结果
  getStockEvaluation: (stockCode, refresh = 0) => {
    const url = `/api/eva?code=${encodeURIComponent(stockCode)}&refresh=${refresh}`;
    return api.get(url);
  },

  // 获取市场概览数据
  getMarketOverview: () => api.get('/api/market/overview'),

  // 获取用户推送设置
  getUserPushSettings: (userId) => {
    return api.get(`/api/wechat/push/settings?user_id=${userId}`);
  },
  
  // 更新用户推送设置
  updateUserPushSettings: (userId, settings) => {
    return api.post('/api/wechat/push/settings', { 
      user_id: userId, 
      settings: settings 
    });
  },
  
  // 获取微信推送消息详情
  getWechatMessage: (msgId) => {
    // 参数验证
    if (!msgId || typeof msgId !== 'string' || msgId.trim() === '') {
      return Promise.reject(new Error('无效的消息ID'));
    }
    
    console.log(`[DEBUG] 发起获取微信推送消息请求: msgId=${msgId}`);
    return api.get(`/api/wechat?msgid=${encodeURIComponent(msgId)}`)
      .then(response => {
        // 检查响应是否有效
        if (!response) {
          throw new Error('响应为空');
        }
        return response;
      })
      .catch(err => {
        console.error(`[ERROR] 获取微信推送消息失败:`, err);
        throw err;
      });
  },

  // 获取更新日志
  getUpdateLogs: (params = {}) => {
    const { page = 1, per_page = 10, update_type = '' } = params;
    let url = `/api/logs?page=${page}&per_page=${per_page}`;
    if (update_type) {
      url += `&update_type=${encodeURIComponent(update_type)}`;
    }
    return api.get(url);
  },

  // 获取更新类型列表
  getUpdateTypes: () => api.get('/api/logs/types'),
};

async function fetchMonitorData(startTime, endTime) {
  try {
    // 构建查询参数
    const params = {}
    if (startTime) params.start_time = startTime
    if (endTime) params.end_time = endTime
    
    // 调用我们自己的后端API，而不是直接调用1Panel API
    const response = await api.get('/api/monitor/server-status', { params })
    // 检查API响应
    if (response.code === 200 && response.data) {
      return response.data;
    } else {
      console.error('监控API返回错误:', response);
      return null;
    }
  } catch (err) {
    console.error('获取监控数据失败:', err);
    return null;
  }
}

// 聊天机器人 API
export const chatApi = {
  sendMessage: (message) => api.post('/api/chat/query', { query: message })
};

export { fetchMonitorData };
export default api;
