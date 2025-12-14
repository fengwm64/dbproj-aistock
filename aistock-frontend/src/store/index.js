import { createStore } from 'vuex'
import { authApi, stockApi } from '@/services/api'

export default createStore({
  state: {
    user: JSON.parse(localStorage.getItem('user')) || null, // 从 localStorage 恢复用户信息
    isAuthenticated: !!localStorage.getItem('token'), // 从 localStorage 恢复登录状态
    stockList: [],
    marketOverview: {},
    favoriteStocks: JSON.parse(localStorage.getItem('favoriteStocks')) || [] // 自选股列表
  },
  getters: {
    isLoggedIn: state => state.isAuthenticated,
    currentUser: state => state.user,
    stockList: state => state.stockList,
    marketOverview: state => state.marketOverview,
    favoriteStocks: state => state.favoriteStocks
  },
  mutations: {
    setUser(state, user) {
      state.user = user
      state.isAuthenticated = !!user
      // 将用户信息存储到 localStorage
      if (user) {
        localStorage.setItem('user', JSON.stringify(user));
      } else {
        localStorage.removeItem('user');
      }
    },
    setStockList(state, stocks) {
      state.stockList = stocks
    },
    setMarketOverview(state, overview) {
      state.marketOverview = overview
    },
    setFavoriteStocks(state, stocks) {
      state.favoriteStocks = stocks;
      localStorage.setItem('favoriteStocks', JSON.stringify(stocks)); // 更新缓存
    },
    logout(state) {
      state.user = null
      state.isAuthenticated = false
      state.favoriteStocks = []
      // 清除所有localStorage数据
      localStorage.removeItem('user'); // 清除用户信息
      localStorage.removeItem('token'); // 清除 token
      localStorage.removeItem('favoriteStocks'); // 清除自选股
      // 清除所有sessionStorage
      sessionStorage.clear();
      // 清除版本缓存，强制下次重新检查
      localStorage.removeItem('app_version');
    }
  },
  actions: {
    async login({ commit }, userData) {
      try {
        commit('setUser', userData);

        // 从 localStorage 中读取 token 并设置
        const token = localStorage.getItem('token');
        if (token) {
          console.log('Token 已成功存储:', token);
        }

        return true;
      } catch (error) {
        console.error('登录失败:', error);
        return false;
      }
    },
    async fetchUserInfo({ commit }) {
      try {
        const response = await authApi.getUserInfo();
        if (response.code === 0) {
          const user = {
            id: response.data.user_id,
            name: response.data.nickname,
            avatar: response.data.avatar_url,
            role: response.data.role,
            createdAt: response.data.created_at,
            stocksCount: response.data.stocks_count
          };
          commit('setUser', user);
          return true;
        }
        return false;
      } catch (error) {
        console.error('获取用户信息失败:', error);
        commit('logout'); // 如果获取失败，清除登录状态
        return false;
      }
    },

    async updateUserProfile({ commit, state }, { nickname, avatar_url }) {
      try {
        const response = await authApi.updateUserProfile(nickname, avatar_url);
        if (response.code === 0) {
          const updatedUser = { ...state.user, name: nickname, avatar: avatar_url };
          commit('setUser', updatedUser); // 更新 Vuex 和缓存
          return true;
        }
        return false;
      } catch (error) {
        console.error('更新用户信息失败:', error);
        return false;
      }
    },
    async fetchFavoriteStocks({ commit }) {
      try {
        const response = await stockApi.getStocks();
        if (response.code === 0) {
          commit('setFavoriteStocks', response.data);
          return true;
        }
        return false;
      } catch (error) {
        console.error('获取自选股失败:', error);
        return false;
      }
    },
    async addFavoriteStocks({ dispatch, commit, state }, stocks) {
      try {
        console.log('[DEBUG] 发起添加自选股请求:', stocks);
        const response = await stockApi.addStocks(stocks);
        console.log('[DEBUG] 添加自选股响应:', response);
        
        if (response.code === 0) {
          // 直接调用 fetchFavoriteStocks 来获取最新的自选股列表
          await dispatch('fetchFavoriteStocks');
          return response.data;
        } else {
          console.error('添加自选股失败，服务器返回错误:', response);
          return null;
        }
      } catch (error) {
        console.error('添加自选股失败:', error);
        return null;
      }
    },
    async removeFavoriteStocks({ dispatch, commit, state }, stockCodes) {
      try {
        console.log('[DEBUG] 发起删除自选股请求:', stockCodes);
        const response = await stockApi.removeStocks(stockCodes);
        console.log('[DEBUG] 删除自选股响应:', response);
        
        if (response.code === 0) {
          // 直接调用 fetchFavoriteStocks 来获取最新的自选股列表
          await dispatch('fetchFavoriteStocks');
          return response.data;
        } else {
          console.error('删除自选股失败，服务器返回错误:', response);
          return null;
        }
      } catch (error) {
        console.error('删除自选股失败:', error);
        return null;
      }
    },
    async searchStocks(_, { keyword, limit }) {
      try {
        const response = await stockApi.searchStocks(keyword, limit);
        if (response.code === 0) {
          return response.data.stocks;
        }
        return [];
      } catch (error) {
        console.error('搜索股票失败:', error);
        return [];
      }
    },
    async fetchHotStocks(_, symbol = '国内人气榜') {
      try {
        // 热门股票API已经包含market、industry、latest_price和change_percent字段
        const response = await stockApi.getHotStocks(symbol);
        if (response.code === 0) {
          return response.data.map(stock => ({
            code: stock.code,
            name: stock.name,
            change_percent: stock.change_percent,
            latest_price: stock.latest_price,
            market: stock.market,
            industry: stock.industry,
            rank: stock.rank
          }));
        }
        return [];
      } catch (error) {
        console.error('获取热门股票失败:', error);
        return [];
      }
    },
    async addStocksFromImage({ dispatch }, imageBase64) {
      try {
        const response = await stockApi.addStocksFromImage(imageBase64);
        if (response.code === 0) {
          await dispatch('fetchFavoriteStocks'); // 更新自选股列表
          return response.data;
        }
        return null;
      } catch (error) {
        console.error('通过图片添加自选股失败:', error);
        return null;
      }
    },
    async fetchStockHistory(_, { code, years = 3 }) {
      try {
        const response = await stockApi.getStockHistory(code, years);
        if (response.code === 0) {
          return response.data;
        }
        return null;
      } catch (error) {
        console.error('获取股票历史价格数据失败:', error);
        return null;
      }
    },
    async fetchStockDetail(_, code) {
      try {
        const response = await stockApi.getStockDetail(code);
        if (response.code === 0) {
          return response.data;
        }
        return null;
      } catch (error) {
        console.error('获取股票详细信息失败:', error);
        return null;
      }
    },
    async fetchStockNews(_, { stockCode, page = 1, limit = 5 }) {
      try {
        console.log('[DEBUG] 发起获取股票新闻请求:', { stockCode, page, limit });
        const response = await stockApi.getStockNews(stockCode, page, limit);
        console.log('[DEBUG] 获取股票新闻响应:', response);

        if (response.code === 0 && response.data) {
          const newsList = response.data.news || [];
          const pagination = response.data.pagination || {};
          return {
            list: newsList,
            total: pagination.total || 0,
            currentPage: pagination.page || 1,
            totalPages: pagination.total_pages || 1,
            hasMore: pagination.has_more || false
          };
        }
        return { list: [], total: 0, currentPage: 1, totalPages: 1, hasMore: false };
      } catch (error) {
        console.error('获取股票新闻失败:', error);
        return { list: [], total: 0, currentPage: 1, totalPages: 1, hasMore: false };
      }
    },
    async fetchNewsDetail(_, newsId) {
      try {
        console.log(`[DEBUG] Store action - 获取新闻详情: ${newsId}`);
        
        // 添加超时提示
        const timeoutPromise = new Promise((_, reject) => {
          setTimeout(() => reject(new Error('请求超时，可能是网络较慢或服务器繁忙')), 280000);
        });
        
        const response = await Promise.race([
          stockApi.getNewsDetail(newsId),
          timeoutPromise
        ]);
        
        console.log(`[DEBUG] 新闻详情响应:`, response);
        
        if (response.code === 0) {
          return response.data;
        } else {
          console.error('获取新闻详情失败，服务器返回错误:', response);
          return null;
        }
      } catch (error) {
        console.error('获取新闻详情失败:', error);
        
        // 重新抛出错误以便组件可以捕获并显示适当的错误信息
        throw error;
      }
    },
    async fetchNews(_, { code, page = 1, limit = 10 }) {
      try {
        const response = await stockApi.getStockNews(code, page, limit);
        if (response.code === 0) {
          return response.data;
        }
        return null;
      } catch (error) {
        console.error('获取新闻失败:', error);
        return null;
      }
    },
    
    // 添加获取推送新闻的 action
    async fetchPushNews(_, { page = 1, limit = 5 } = {}) {
      try {
        console.log('[DEBUG] 发起获取自选股推送新闻请求:', { page, limit });
        const response = await stockApi.getPushNews(page, limit);
        console.log('[DEBUG] 获取自选股推送新闻响应:', response);
        
        if (response.code === 0) {
          return response.data;
        }
        return null;
      } catch (error) {
        console.error('获取自选股推送新闻失败:', error);
        return null;
      }
    },
    
    // 添加新的 action 获取标签相关的股票
    async fetchTagStocks(_, tagName) {
      try {
        console.log('[DEBUG] 发起获取标签龙头股票请求:', tagName);
        const response = await stockApi.getTagLeaders(tagName);
        console.log('[DEBUG] 获取标签龙头股票响应:', response);
        
        if (response.code === 0 && response.data) {
          // 获取股票列表并按照change_percent从大到小排序
          const leaders = response.data.leaders || [];
          const sortedLeaders = leaders.sort((a, b) => {
            const changeA = parseFloat(a.change_percent) || 0;
            const changeB = parseFloat(b.change_percent) || 0;
            return changeB - changeA; // 从大到小排序
          });
          
          // 返回标签描述和排序后的股票列表
          return {
            description: response.data.description || '',
            stocks: sortedLeaders
          };
        }
        return { description: '', stocks: [] };
      } catch (error) {
        console.error('获取标签股票失败:', error);
        throw error; // 抛出错误，让组件可以捕获并处理
      }
    },
    
    async fetchStockForecast(_, stockCode) {
      try {
        const response = await stockApi.getForecast(stockCode);
        if (response.code === 200) {
          return response.data;
        }
        return [];
      } catch (error) {
        console.error('获取股票业绩预测失败:', error);
        return [];
      }
    },

    async fetchStockEvaluation(_, { stockCode, refresh = false }) {
      try {
        // 检查用户是否登录
        if (!localStorage.getItem('token')) {
          console.error('[DEBUG] 获取股票AI评估失败: 用户未登录');
          return null;
        }
        
        console.log('[DEBUG] 发起获取股票AI评估请求:', stockCode, '刷新:', refresh);
        const response = await stockApi.getStockEvaluation(stockCode, refresh);
        console.log('[DEBUG] 获取股票AI评估响应:', response);
        
        if (response.code === 0 && response.data) {
          return {
            conclusion: response.data.conclusion || '未知',
            evaluation_time: response.data.evaluation_time || '',
            news_list: response.data.news_list || [],
            reason: response.data.reason || '暂无评估理由'
          };
        }
        return null;
      } catch (error) {
        console.error('获取股票AI评估失败:', error);
        return null;
      }
    },
    async fetchMarketOverview({ commit }) {
      try {
        const response = await stockApi.getMarketOverview();
        if (response.code === 0) {
          // 处理API返回的数据格式，将其转换为组件期望的格式
          const marketData = {};
          response.data.forEach(item => {
            // 根据索引名称映射到相应的键
            let key;
            switch(item.index) {
              case '上证指数':
                key = 'shangzheng';
                break;
              case '深证成指':
                key = 'shenzheng';
                break;
              case '创业板指':
                key = 'chuangye';
                break;
              case '纳斯达克中国金龙指数':
                key = 'nasdaqChina';
                break;
              case '富时中国A50':
                key = 'ftseChina';
                break;
              case '恒生科技指数':
                key = 'hktech';
                break;
              default:
                // 如有其他指数可在此添加
                key = item.index.replace(/\s+/g, '').toLowerCase();
            }
            marketData[key] = {
              value: item.value,
              change: item.change_pct
            };
          });
          
          commit('setMarketOverview', marketData);
          return marketData;
        }
        
        // 如果API请求失败，使用备用数据
        const fallbackData = {
          shangzheng: { value: 3341.99, change: -0.30 },
          shenzheng: { value: 10126.83, change: -0.70 },
          chuangye: { value: 2011.77, change: -0.87 }
        };
        commit('setMarketOverview', fallbackData);
        return fallbackData;
      } catch (error) {
        console.error('获取市场概览数据失败:', error);
        
        // 使用备用数据
        const fallbackData = {
          shangzheng: { value: 3341.99, change: -0.30 },
          shenzheng: { value: 10126.83, change: -0.70 },
          chuangye: { value: 2011.77, change: -0.87 }
        };
        commit('setMarketOverview', fallbackData);
        return fallbackData;
      }
    },
    async fetchWechatMessage(_, msgId) {
      if (!msgId || typeof msgId !== 'string' || msgId.trim() === '') {
        console.error('[ERROR] fetchWechatMessage: 无效的消息ID');
        return {};
      }
      
      try {
        console.log(`[DEBUG] Store action - 获取微信推送消息: msgId=${msgId}`);
        const response = await stockApi.getWechatMessage(msgId);
        console.log('[DEBUG] 微信推送消息响应:', response);
        
        if (response) {
          if (response.stock_id && response.stock_name) {
            return response;
          }
          if (response.code === 0 && response.data) {
            return response.data;
          }
          if (response.top_news || response.hk_us_news || response.good_news || response.bad_news) {
            return response;
          }
          console.warn('[WARN] 未知的微信推送消息格式，返回空数据:', response);
          return { date: '', top_news: [], hk_us_news: [] };
        } else {
          return { date: '', top_news: [], hk_us_news: [] };
        }
      } catch (error) {
        console.error('[ERROR] 获取微信推送消息异常:', error);
        return { date: '', top_news: [], hk_us_news: [] };
      }
    },
    async fetchUpdateLogs(_, params = {}) {
      try {
        console.log('[DEBUG] 发起获取更新日志请求:', params);
        const response = await stockApi.getUpdateLogs(params);
        console.log('[DEBUG] 获取更新日志响应:', response);
        
        if (response.code === 0 && response.data) {
          return {
            logs: response.data.logs || [],
            pagination: response.data.pagination || {}
          };
        }
        return null;
      } catch (error) {
        console.error('获取更新日志失败:', error);
        throw error;
      }
    },
    async fetchUpdateTypes(_) {
      try {
        console.log('[DEBUG] 发起获取更新类型请求');
        const response = await stockApi.getUpdateTypes();
        console.log('[DEBUG] 获取更新类型响应:', response);
        
        if (response.code === 0 && response.data) {
          return response.data.types || [];
        }
        return [];
      } catch (error) {
        console.error('获取更新类型失败:', error);
        return [];
      }
    },
    // 添加获取推送设置的action
    async fetchPushSettings(_, userId) {
      try {
        console.log('[DEBUG] 发起获取推送设置请求:', userId);
        const response = await stockApi.getUserPushSettings(userId);
        console.log('[DEBUG] 获取推送设置响应:', response);
        
        if (response.code === 0 && response.data) {
          return response.data;
        }
        return { settings: {} };
      } catch (error) {
        console.error('获取推送设置失败:', error);
        return { settings: {} };
      }
    },
    
    // 添加更新推送设置的action
    async updatePushSettings(_, { userId, settings }) {
      try {
        console.log('[DEBUG] 发起更新推送设置请求:', userId, settings);
        const response = await stockApi.updateUserPushSettings(userId, settings);
        console.log('[DEBUG] 更新推送设置响应:', response);
        
        return response.code === 0;
      } catch (error) {
        console.error('更新推送设置失败:', error);
        return false;
      }
    },
    logout({ commit }) {
      commit('logout');
    }
  }
})
