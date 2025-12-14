// 版本管理和缓存清理工具
class CacheManager {
  constructor() {
    this.VERSION_KEY = 'app_version';
    this.CURRENT_VERSION = process.env.VUE_APP_VERSION || Date.now().toString();
  }

  // 检查是否需要清理缓存
  checkAndClearCache() {
    const storedVersion = localStorage.getItem(this.VERSION_KEY);
    
    if (storedVersion !== this.CURRENT_VERSION) {
      this.clearCache();
      localStorage.setItem(this.VERSION_KEY, this.CURRENT_VERSION);
      console.log(`应用版本已更新: ${storedVersion} -> ${this.CURRENT_VERSION}`);
      return true;
    }
    return false;
  }

  // 清理各种缓存
  async clearCache() {
    try {
      // 清理 localStorage 中的旧数据（保留用户登录信息）
      const preserveKeys = ['token', 'user', 'favoriteStocks'];
      const allKeys = Object.keys(localStorage);
      allKeys.forEach(key => {
        if (!preserveKeys.includes(key)) {
          localStorage.removeItem(key);
        }
      });

      // 清理 sessionStorage
      sessionStorage.clear();

      // 清理浏览器缓存 (需要用户交互)
      if ('caches' in window) {
        const cacheNames = await caches.keys();
        await Promise.all(
          cacheNames.map(cacheName => caches.delete(cacheName))
        );
      }

      console.log('缓存清理完成');
    } catch (error) {
      console.error('缓存清理失败:', error);
    }
  }

  // 完全清理缓存（退出登录时使用）
  async clearAllCache() {
    try {
      // 清理所有 localStorage
      localStorage.clear();

      // 清理 sessionStorage
      sessionStorage.clear();

      // 清理浏览器缓存
      if ('caches' in window) {
        const cacheNames = await caches.keys();
        await Promise.all(
          cacheNames.map(cacheName => caches.delete(cacheName))
        );
      }

      console.log('所有缓存已清理');
    } catch (error) {
      console.error('缓存清理失败:', error);
    }
  }

  // 强制重新加载页面（如果需要）
  forceReload() {
    if (this.checkAndClearCache()) {
      setTimeout(() => {
        window.location.reload(true);
      }, 1000);
    }
  }
}

export default new CacheManager();
