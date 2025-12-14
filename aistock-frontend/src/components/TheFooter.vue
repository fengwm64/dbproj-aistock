<template>
  <footer class="site-footer">
    <div class="container">
      <p>&copy; 2025 AI StockLink. All Rights Reserved.</p>
      <div class="footer-links">
        <router-link to="/update-logs" class="footer-link">更新日志</router-link>
        <span class="divider">|</span>
        <a href="https://status.aistocklink.cn" target="_blank" rel="noopener noreferrer">网站状态监测</a>
      </div>
      <div class="beian-info">
  <img src="@/assets/jnu-logo.svg" alt="暨大Logo" style="height: 1.2rem; vertical-align: middle; margin-right: 6px;" />
  <span class="team-info">暨大团队研发</span>
        <span style="margin: 0 8px; color: var(--text-tertiary);">|</span>
        <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">冀ICP备2025113956号</a>
      </div>
    </div>
  </footer>
</template>

<script>
export default {
  name: 'TheFooter'
}
</script>

<style lang="scss" scoped>
.site-footer {
  background-color: #fff;
  padding: 20px 0;
  border-top: 1px solid var(--border-color);
  text-align: center;
  color: var(--text-tertiary);
  
  .container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 20px;
  }
  
  p {
    margin-bottom: 10px;
    font-size: 0.9rem;
  }
  
  .footer-links {
    display: flex;
    justify-content: center;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 10px;
    
    .footer-link,
    a {
      color: var(--primary-color);
      text-decoration: none;
      font-size: 0.9rem;
      
      &:hover {
        text-decoration: underline;
      }
    }
    
    .divider {
      color: var(--text-tertiary);
    }
  }

  .beian-info {
    font-size: 0.8rem;
    
    a {
      color: var(--text-tertiary);
      text-decoration: none;
      
      &:hover {
        text-decoration: underline;
      }
    }
  }
}
</style>
