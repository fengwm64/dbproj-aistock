import { createRouter, createWebHistory } from 'vue-router'
// 使用懒加载导入组件
const HomeView = () => import('../views/HomeView.vue')
const LoginView = () => import('../views/LoginView.vue')
const ProfileView = () => import('@/views/ProfileView.vue')
const SearchView = () => import('@/views/SearchView.vue')
const StockDetailView = () => import('@/views/StockDetailView.vue')
const FavoritesView = () => import('@/views/FavoritesView.vue')
const WechatMessageView = () => import('@/views/WechatMessageView.vue')
const UpdateLogsView = () => import('@/views/UpdateLogsView.vue')

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomeView,
    meta: {
      title: '股票资讯AI智能分析 - 首页'
    }
  },
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: {
      title: '股票资讯AI智能分析 - 用户登录'
    }
  },
  {
    path: '/profile',
    name: 'Profile',
    component: ProfileView,
    meta: {
      title: '股票资讯AI智能分析 - 个人信息',
      requiresAuth: true  // 需要登录才能访问
    }
  },
  {
    path: '/search',
    name: 'search',
    component: SearchView,
    meta: {
      title: '股票资讯AI智能分析 - 股票搜索'
    }
  },
  {
    path: '/stock/:code',
    name: 'stockDetail',
    component: StockDetailView,
    props: true,
    meta: {
      title: '股票资讯AI智能分析 - 股票详情'
    }
  },
  {
    path: '/favorites',
    name: 'favorites',
    component: FavoritesView,
    meta: {
      title: '股票资讯AI智能分析 - 自选股',
      requiresAuth: true  // 需要登录才能访问
    }
  },
  {
    path: '/wechat/:msgid',
    name: 'wechatMessage',
    component: WechatMessageView,
    props: true,
    meta: {
      title: '股票资讯AI智能分析 - 微信推送消息详情'
    }
  },
  {
    path: '/update-logs',
    name: 'updateLogs',
    component: UpdateLogsView,
    meta: {
      title: '股票资讯AI智能分析 - 更新日志'
    }
  },
  {
    path: '/tags/:tagName',
    name: 'TagView',
    component: () => import('../views/TagView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes
})

// 路由级别的标题管理
router.beforeEach((to, from, next) => {
  const isLoggedIn = localStorage.getItem('token') !== null;
  // 设置页面标题
  document.title = to.meta.title || '股票资讯AI智能分析 - 智能股票分析平台';
  
  // 权限检查 - 只对需要登录的页面进行检查
  if (to.meta.requiresAuth && !isLoggedIn) {
    // 需要登录但未登录，重定向到登录页
    next({ name: 'login', query: { redirect: to.fullPath } });
  } else if (isLoggedIn && to.name === 'login') {
    // 已登录用户访问登录页面，重定向到首页
    next({ name: 'home' });
  } else {
    next();
  }
})

export default router
