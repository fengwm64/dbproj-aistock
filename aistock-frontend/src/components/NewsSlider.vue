<template>
  <div class="news-slider">
    <h4 v-if="title" class="section-title">{{ title }}</h4>
    <div class="news-slideshow-container"
         @touchstart="handleTouchStart"
         @touchmove="handleTouchMove"
         @touchend="handleTouchEnd">
      <div class="news-slides" :class="{ 'headline-slides': headlineStyle }">
        <div v-for="(news, index) in newsList" :key="news.id" 
             class="news-slide" 
             :class="{ 
               'active': activeIndex === index, 
               'headline-slide': headlineStyle 
             }">
          <a @click.prevent="$emit('showDetail', news.id)" 
             class="news-title"
             :class="{ 'headline-news-title': headlineStyle }">{{ news.title }}</a>
          
          <!-- 标签显示 -->
          <div v-if="news.tag && (news.tag.positive.length > 0 || news.tag.negative.length > 0)" 
               class="news-tags">
            <span v-for="tag in news.tag.positive" :key="`pos-${tag}`" 
                  class="news-tag positive"
                  @click.stop="$emit('tagClick', tag)">{{ tag }}</span>
            <span v-for="tag in news.tag.negative" :key="`neg-${tag}`" 
                  class="news-tag negative"
                  @click.stop="$emit('tagClick', tag)">{{ tag }}</span>
          </div>
          
          <p class="news-preview" :class="{ 'headline-news-preview': headlineStyle }">
            {{ getNewsPreview(news.content) }}
          </p>
          <p class="news-time" :class="{ 'headline-news-time': headlineStyle }">
            {{ news.publish_time }}
          </p>
        </div>
      </div>
      <button class="slide-nav prev" @click="changeNews(-1)">&#10094;</button>
      <button class="slide-nav next" @click="changeNews(1)">&#10095;</button>
      <div class="news-dots" :class="{ 'headline-dots': headlineStyle }">
        <span v-for="(_, index) in newsList" :key="index" 
              :class="{ 'active': activeIndex === index }"
              @click="selectNews(index)"></span>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted, watch } from 'vue';

export default {
  name: 'NewsSlider',
  props: {
    // 新闻列表数据
    news: {
      type: Array,
      required: true,
      default: () => []
    },
    // 新闻类别标题
    title: {
      type: String,
      required: false,
      default: ''
    },
    // 是否使用头条样式
    headlineStyle: {
      type: Boolean,
      default: false
    }
  },
  emits: ['showDetail', 'tagClick'],
  setup(props) {
    const newsList = ref([]);
    const activeIndex = ref(0);
    
    // 监听输入的新闻数据变化
    watch(() => props.news, (newValue) => {
      newsList.value = newValue;
    }, { immediate: true });
    
    let slideInterval = null;
    
    // 新闻内容预览
    const getNewsPreview = (content) => {
      if (!content) return '暂无内容';
      return content;
    };
    
    // 开始自动轮播
    const startAutoplay = () => {
      clearInterval(slideInterval);
      slideInterval = setInterval(() => {
        if (newsList.value.length > 0) {
          activeIndex.value = (activeIndex.value + 1) % newsList.value.length;
        }
      }, 10000);
    };
    
    // 选择指定索引的新闻
    const selectNews = (index) => {
      activeIndex.value = index;
      clearInterval(slideInterval);
      startAutoplay();
    };
    
    // 按方向切换新闻
    const changeNews = (direction) => {
      if (newsList.value.length === 0) return;
      clearInterval(slideInterval);
      const newIndex = (activeIndex.value + direction + newsList.value.length) % newsList.value.length;
      activeIndex.value = newIndex;
      startAutoplay();
    };
    
    // --- 触摸滑动相关状态 ---
    const touchState = ref({
      startX: 0,
      startY: 0,
      currentX: 0,
      currentY: 0,
      isSwipe: false,
      threshold: 50
    });

    const handleTouchStart = (event) => {
      const touch = event.touches[0];
      touchState.value = {
        ...touchState.value,
        startX: touch.clientX,
        startY: touch.clientY,
        currentX: touch.clientX,
        currentY: touch.clientY,
        isSwipe: false
      };
    };

    const handleTouchMove = (event) => {
      const touch = event.touches[0];
      touchState.value.currentX = touch.clientX;
      touchState.value.currentY = touch.clientY;
      const deltaX = Math.abs(touchState.value.currentX - touchState.value.startX);
      const deltaY = Math.abs(touchState.value.currentY - touchState.value.startY);
      if (deltaX > deltaY && deltaX > 10) {
        touchState.value.isSwipe = true;
        event.preventDefault();
      }
    };

    const handleTouchEnd = (event) => {
      if (!touchState.value.isSwipe) {
        return;
      }
      const deltaX = touchState.value.currentX - touchState.value.startX;
      const deltaY = Math.abs(touchState.value.currentY - touchState.value.startY);
      if (Math.abs(deltaX) > touchState.value.threshold && deltaY < 100) {
        const direction = deltaX > 0 ? -1 : 1;
        changeNews(direction);
      }
      touchState.value.isSwipe = false;
    };
    
    onMounted(() => {
      // 当新闻数据加载后启动轮播
      if (newsList.value.length > 0) {
        startAutoplay();
      }
    });
    
    onUnmounted(() => {
      // 清除轮播定时器
      clearInterval(slideInterval);
    });
    
    return {
      newsList,
      activeIndex,
      getNewsPreview,
      selectNews,
      changeNews,
      handleTouchStart,
      handleTouchMove,
      handleTouchEnd
    };
  }
};
</script>

<style lang="scss" scoped>
.news-slider {
  .news-slideshow-container {
    position: relative;
    height: auto; /* 改为自适应高度，不再固定为125px */
    min-height: 150px; /* 设置最小高度 */
    touch-action: pan-y;
    user-select: none;
    
    .news-slides {
      position: relative;
      height: auto; /* 改为自适应高度 */
      min-height: 150px; /* 设置最小高度 */
      overflow: hidden;
      padding-bottom: 20px; /* 为底部导航点留出空间 */
      
      .news-slide {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: auto; /* 改为自适应高度 */
        min-height: 120px; /* 设置最小高度 */
        opacity: 0;
        visibility: hidden;
        transition: opacity 0.5s ease, visibility 0.5s ease;
        padding: 0 5px;
        padding-bottom: 25px; /* 为底部导航点留出空间 */
        
        &.active {
          opacity: 1;
          visibility: visible;
        }
        
        .news-title {
          display: block;
          font-size: 1rem;
          font-weight: 500;
          color: var(--primary-color);
          margin-bottom: 8px;
          text-decoration: none;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap; /* 确保只显示一行 */
          cursor: pointer;
          
          &:hover {
            text-decoration: underline;
          }
        }
        
        .news-preview {
          font-size: 0.85rem;
          color: var(--text-secondary);
          margin-bottom: 8px;
          overflow: hidden;
          text-overflow: ellipsis;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
        }
        
        .news-time {
          font-size: 0.75rem;
          color: var(--text-tertiary);
        }
        
        // 头条样式
        &.headline-slide {
          padding: 0 0 25px 0; /* 增加底部padding */
          box-sizing: border-box;
          display: flex;
          flex-direction: column;
          
          .headline-news-title {
            font-size: 1.1rem;
            font-weight: 500;
            color: var(--danger-color);
            margin-bottom: 8px;
            display: block;
            line-height: 1.4;
            word-wrap: break-word;
            max-height: 2.8em;
            overflow: hidden;
            text-overflow: ellipsis; /* 添加省略号 */
            display: -webkit-box;
            -webkit-line-clamp: 2; /* 限制为两行 */
            -webkit-box-orient: vertical;
            flex-shrink: 0;
          }
          
          .headline-news-preview {
            font-size: 0.9rem;
            line-height: 1.5;
            word-wrap: break-word;
            overflow-wrap: break-word;
            min-height: 1.5em;
            display: -webkit-box;
            -webkit-box-orient: vertical;
            overflow: hidden;
            margin-bottom: 8px;
            flex: unset;
          }
          
          .headline-news-time {
            font-size: 0.8rem;
            flex-shrink: 0;
          }
        }
      }
      
      // 头条幻灯片容器特有样式
      &.headline-slides {
        // 如果需要特殊样式覆盖，可在此添加
      }
    }
    
    .news-tags {
      margin: 6px 0;
      display: flex;
      flex-wrap: wrap;
      gap: 3px;
      
      .news-tag {
        display: inline-block;
        padding: 1px 4px;
        border-radius: 3px;
        font-size: 0.7rem;
        font-weight: 500;
        white-space: nowrap;
        cursor: pointer;
        transition: transform 0.2s ease;
        
        &:hover {
          transform: scale(1.05);
        }
        
        &.positive {
          background-color: #fff2f0;
          color: #d4380d;
          border: 1px solid #ffccc7;
        }
        
        &.negative {
          background-color: #f6ffed;
          color: #389e0d;
          border: 1px solid #b7eb8f;
        }
      }
    }
    
    .slide-nav {
      position: absolute;
      top: 50%;
      transform: translateY(-50%);
      background-color: rgba(255, 255, 255, 0.7);
      color: var(--primary-color);
      border: none;
      border-radius: 50%;
      width: 25px;
      height: 25px;
      font-size: 16px;
      display: flex;
      justify-content: center;
      align-items: center;
      cursor: pointer;
      opacity: 0;
      transition: opacity 0.3s, background-color 0.3s;
      z-index: 5;
      
      // 小屏幕设备隐藏导航按钮
      @media (max-width: 576px) {
        display: none;
      }
      
      &.prev {
        left: 5px;
      }
      
      &.next {
        right: 5px;
      }
    }
    
    .news-dots {
      display: flex;
      justify-content: center;
      gap: 6px;
      position: absolute;
      bottom: 5px; /* 调整点的位置 */
      left: 0;
      right: 0;
      
      span {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background-color: var(--border-color);
        cursor: pointer;
        transition: background-color 0.3s, transform 0.2s;
        
        &.active {
          background-color: var(--primary-color);
          transform: scale(1.2);
        }
      }
    }
    
    // 头条点导航特有样式
    .headline-dots {
      bottom: 5px; /* 调整头条样式下点的位置 */
    }
    
    &:hover {
      .slide-nav {
        opacity: 1;
        
        &:hover {
          background-color: rgba(255, 255, 255, 0.9);
        }
      }
    }
  }
  
  // 标题样式
  .section-title {
    font-size: 1.2rem;
    margin-bottom: 10px;
    color: var(--primary-color);
    font-weight: 500;
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 8px;
  }
}
</style>
