/**
 * 滚动相关工具函数
 */

/**
 * 平滑滚动到页面顶部
 * @param {boolean} smooth - 是否使用平滑滚动，默认为 false
 */
export const scrollToTop = (smooth = false) => {
  if (smooth) {
    window.scrollTo({
      top: 0,
      left: 0,
      behavior: 'smooth'
    });
  } else {
    window.scrollTo(0, 0);
  }
};

/**
 * 滚动到指定元素
 * @param {string|Element} element - 目标元素的选择器或元素对象
 * @param {boolean} smooth - 是否使用平滑滚动，默认为 true
 */
export const scrollToElement = (element, smooth = true) => {
  const targetElement = typeof element === 'string' 
    ? document.querySelector(element) 
    : element;
    
  if (targetElement) {
    targetElement.scrollIntoView({
      behavior: smooth ? 'smooth' : 'auto',
      block: 'start'
    });
  }
};

/**
 * 获取当前滚动位置
 * @returns {Object} 包含 x 和 y 坐标的对象
 */
export const getScrollPosition = () => {
  return {
    x: window.pageXOffset || document.documentElement.scrollLeft,
    y: window.pageYOffset || document.documentElement.scrollTop
  };
};

/**
 * 滚动到指定位置
 * @param {number} x - 水平位置
 * @param {number} y - 垂直位置
 * @param {boolean} smooth - 是否使用平滑滚动，默认为 false
 */
export const scrollToPosition = (x, y, smooth = false) => {
  if (smooth) {
    window.scrollTo({
      left: x,
      top: y,
      behavior: 'smooth'
    });
  } else {
    window.scrollTo(x, y);
  }
};

/**
 * 页面路由切换时重置滚动位置的 composable
 * 在 Vue 组件的 onMounted 中使用
 */
export const useScrollReset = () => {
  scrollToTop();
};
