<template>
  <div class="stock-chart-section">
    <div class="chart-header">
      <h3 class="section-title">价格走势</h3>
      <div class="chart-timeframes">
        <el-radio-group v-model="timeframe" size="small">
          <el-radio-button label="日" value="day"></el-radio-button>
          <el-radio-button label="月" value="month"></el-radio-button>
        </el-radio-group>
      </div>
    </div>
    
    <!-- 添加自定义图例组件 -->
    <div class="custom-legend">
      <span 
        v-for="series in seriesList" 
        :key="series" 
        class="legend-item"
        :class="{ 'legend-item-inactive': !seriesVisibility[series] }"
        @click="toggleSeries(series)"
      >
        <span class="legend-icon" :class="getSeriesColorClass(series)"></span>
        <span class="legend-label">{{ series }}</span>
      </span>
    </div>
    
    <div class="stock-chart" ref="chartContainer"></div>
  </div>
</template>

<script>
import { ref, onMounted, watch, onBeforeUnmount } from 'vue';
import { useStore } from 'vuex';
// 按需引入 ECharts
import * as echarts from 'echarts/core';
import { LineChart, BarChart } from 'echarts/charts';
import { 
  TitleComponent, 
  TooltipComponent, 
  LegendComponent, 
  GridComponent,
  DataZoomComponent 
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

// 注册必需的组件
echarts.use([
  LineChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  CanvasRenderer
]);

export default {
  name: 'StockChart',
  props: {
    stockCode: {
      type: String,
      required: true
    }
  },
  setup(props) {
    const store = useStore();
    const chartContainer = ref(null);
    const chartInstance = ref(null);
    const timeframe = ref('day');
    const allHistory = ref([]);
    const seriesList = ref([]);
    const seriesVisibility = ref({
      '最高价': true,
      '最低价': true,
      '成交量': true
    });
    
    // 添加一个防抖函数
    const debounce = (fn, delay) => {
      let timer = null;
      return function(...args) {
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => {
          fn.apply(this, args);
        }, delay);
      };
    };

    // 初始化图表
    const initChart = () => {
      if (!chartContainer.value) return;

      // 确保先完全销毁旧实例
      if (chartInstance.value) {
        try {
          chartInstance.value.dispose();
        } catch (e) {
          console.warn('图表实例销毁失败:', e);
        }
        chartInstance.value = null;
      }

      // 使用 try-catch 包装以防止可能的异常
      try {
        chartInstance.value = echarts.init(chartContainer.value, null, {
          renderer: 'canvas',
          useDirtyRect: false // 关闭脏矩形渲染以提高稳定性
        });
        
        chartInstance.value.showLoading();
        updateChartData();
      } catch (error) {
        console.error('初始化图表失败:', error);
      }
    };

    // 安全地处理窗口大小调整
    const handleResize = debounce(() => {
      if (!chartContainer.value) return;
      
      try {
        if (chartInstance.value) {
          chartInstance.value.resize();
        } else {
          // 如果实例不存在，重新创建
          initChart();
        }
      } catch (error) {
        console.error('处理窗口大小变化失败:', error);
        // 如果resize失败，则尝试重新初始化图表
        initChart();
      }
    }, 200);  // 添加200ms的防抖

    // 本地筛选历史数据
    const filterHistoryByTimeframe = (history) => {
      if (timeframe.value === 'day') {
        return history.slice(-30);
      } else {
        const map = new Map();
        history.forEach(item => {
          const month = formatXAxisLabel(item.date || '').slice(0,7);
          const h = item.high || 0, l = item.low || 0;
          if (map.has(month)) {
            const m = map.get(month);
            m.high = Math.max(m.high, h);
            m.low  = Math.min(m.low, l);
          } else {
            map.set(month, { date: month, high: h, low: l, volume: item.volume || 0 });
          }
        });
        return Array.from(map.values()).slice(-48);  // 最近48个月
      }
    };

    // 更新图表数据：首次拉取（年：4年，日：1年），后续本地过滤
    const updateChartData = async () => {
      if (!chartInstance.value) return;
      try {
        if (!allHistory.value.length) {
          const years = timeframe.value === 'month' ? 4 : 1;    // 月视图4年
          const res = await store.dispatch('fetchStockHistory', {
            code: props.stockCode,
            years
          });
          allHistory.value = (res && res.history) ? res.history : [];
        }
        const items = filterHistoryByTimeframe(allHistory.value);
        
        // 增强数据处理和格式化
        const chartData = {
          dates: items.map(i => i.date || ''),
          // 确保数值类型数据不为 null/undefined
          highPrices: items.map(i => parseFloat(i.high) || 0),
          lowPrices: items.map(i => parseFloat(i.low) || 0),
          volumes: timeframe.value === 'day'
                      ? items.map(i => parseInt(i.volume, 10) || 0)
                      : []
        };
        renderChart(chartData);
      } catch (error) {
        console.error('更新图表数据失败:', error);
      }
    };

    // 渲染图表
    const renderChart = (chartData) => {
      if (!chartInstance.value) return;

      try {
        console.log('[DEBUG] 开始渲染图表, 数据点数量:', chartData.dates.length);
        
        // 计算y轴的合适范围
        let minPrice = Math.min(...chartData.lowPrices);
        let maxPrice = Math.max(...chartData.highPrices);
        const padding = (maxPrice - minPrice) * 0.1; // 增加10%的边距
        minPrice = Math.max(0, minPrice - padding); // 确保最小值不小于0
        maxPrice = maxPrice + padding;
        
        // 更新系列列表和可见性状态
        seriesList.value = timeframe.value === 'day' 
          ? ['最高价', '最低价', '成交量'] 
          : ['最高价', '最低价'];
          
        // 初始化所有系列为可见
        seriesList.value.forEach(series => {
          seriesVisibility.value[series] = true;
        });
        
        // 决定是否显示数据点，当数据点少于一定数量时显示
        const shouldShowSymbols = chartData.dates.length <= 60;
        
        const option = {
          tooltip: {                      // 新增：基础 tooltip
            trigger: 'axis'
          },
          legend: { show: false },  // 隐藏原生图例
          xAxis: {
            id: 'mainXAxis', // 添加 id
            type:'category',
            data:chartData.dates,
            boundaryGap:true,
            axisLine:{ lineStyle:{ color:'#ddd' } },
            axisLabel:{ color:'#666' }
          },
          yAxis: [
            {
              id: 'priceYAxis', // 添加 id
              type: 'value',
              min: minPrice,
              max: maxPrice,
              axisLine: { lineStyle: { color: '#ddd' } },
              axisLabel: { color: '#666', formatter: v => v.toFixed(2) },
              splitLine: { show: true, lineStyle: { color: '#f5f5f5', type: 'dashed' } },
              splitNumber: 5
            },
            ...(timeframe.value === 'day' 
              ? [{ 
                  id: 'volumeYAxis', // 添加 id
                  type: 'value', 
                  name: '成交量', 
                  position: 'right', 
                  axisLabel: { color: '#999' } 
                }] 
              : [])
           ],
          series: [
            { 
              name:'最高价', 
              type:'line', 
              data:chartData.highPrices, 
              smooth:true, 
              showSymbol: shouldShowSymbols, // 当数据点少时显示
              symbolSize: 4, // 设置合适的点大小
              itemStyle:{ color:'#f56c6c' }, 
              lineStyle:{width:2}, 
              yAxisId: 'priceYAxis'
            },
            { 
              name:'最低价', 
              type:'line', 
              data:chartData.lowPrices,  
              smooth:true, 
              showSymbol: shouldShowSymbols, // 当数据点少时显示
              symbolSize: 4, // 设置合适的点大小
              itemStyle:{ color:'#67c23a' }, 
              lineStyle:{width:2}, 
              yAxisId: 'priceYAxis'
            },
            ...(timeframe.value === 'day'
              ? [{ 
                  name: '成交量',
                  type: 'bar',
                  data: chartData.volumes,
                  yAxisId: 'volumeYAxis',
                  barMaxWidth: 10,
                  itemStyle: { color: '#409EFF33' }
                }]
              : [])
          ],
          grid: {
            left: '3%',
            right: '4%',
            bottom: '10%',            // 增大下方空白
            top: '15%',
            containLabel: true
          },
          dataZoom: [
            {
              type: 'inside',
              xAxisId: 'mainXAxis', // 使用 xAxisId 替代 xAxisIndex
              start: 0,
              end: 100,
              zoomLock: false
            }
          ]
        };

        chartInstance.value.hideLoading();
        chartInstance.value.setOption(option, true);
        console.log('[DEBUG] 图表渲染完成');
        
        chartInstance.value.off('legendselectchanged');
      } catch (error) {
        console.error('[ERROR] 渲染图表失败:', error);
        // 如果渲染失败，尝试使用最简单的配置重新渲染
        try {
          const simpleOption = {
            xAxis: {
              type: 'category',
              data: chartData.dates,
              boundaryGap: true
            },
            yAxis: { type: 'value' },
            series: [
              {
                name: '最高价',
                type: 'line',
                data: chartData.highPrices || []
              },
              {
                name: '最低价',
                type: 'line',
                data: chartData.lowPrices || []
              }
            ]
          };
          chartInstance.value.hideLoading();
          chartInstance.value.setOption(simpleOption, true);
        } catch (fallbackError) {
          console.error('[ERROR] 备用图表渲染也失败:', fallbackError);
        }
      }
    };

    // 格式化X轴标签
    const formatXAxisLabel = (dateStr) => {
      if (!dateStr) return '';
      // 支持 YYYY-MM-DD 或 YYYYMMDD
      if (/^\d{8}$/.test(dateStr)) {
        // 20240101 -> 2024-01-01
        return `${dateStr.slice(0,4)}-${dateStr.slice(4,6)}-${dateStr.slice(6,8)}`;
      }
      if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
        return dateStr;
      }
      // 其他格式直接返回
      return dateStr;
    };

    // 对外暴露刷新图表的方法
    const refreshChart = () => {
      updateChartData();
    };

    // 切换系列可见性
    const toggleSeries = (seriesName) => {
      if (!chartInstance.value) return;
      
      // 更新可见性状态
      seriesVisibility.value[seriesName] = !seriesVisibility.value[seriesName];
      
      try {
        // 获取当前图表配置
        const option = chartInstance.value.getOption();
        
        // 找到对应的系列索引
        const seriesIndex = option.series.findIndex(s => s.name === seriesName);
        if (seriesIndex === -1) return;
        
        // 克隆系列数组以避免直接修改对象
        const newSeries = [...option.series];
        const isVisible = seriesVisibility.value[seriesName];
        
        // 保持原有的 showSymbol 设置（基于数据点数量）
        const currentShowSymbol = newSeries[seriesIndex].showSymbol;
        
        // 更新系列可见性
        newSeries[seriesIndex] = {
          ...newSeries[seriesIndex],
          silent: !isVisible,  // 静默处理事件
          showSymbol: isVisible ? currentShowSymbol : true,  // 保持原有配置，若隐藏则不显示点
          lineStyle: {
            ...newSeries[seriesIndex].lineStyle,
            opacity: isVisible ? 1 : 0.1
          },
          itemStyle: {
            ...newSeries[seriesIndex].itemStyle,
            opacity: isVisible ? 1 : 0.1
          }
        };
        
        // 更新图表
        chartInstance.value.setOption({ series: newSeries });
        console.log(`[DEBUG] 切换系列 ${seriesName} 可见性: ${isVisible}`);
      } catch (error) {
        console.error('[ERROR] 切换系列可见性失败:', error);
      }
    };
    
    // 获取系列颜色类名
    const getSeriesColorClass = (series) => {
      switch (series) {
        case '最高价': return 'color-high';
        case '最低价': return 'color-low';
        case '成交量': return 'color-volume';
        default: return '';
      }
    };

    // 监听时间范围变化
    watch(timeframe, async () => {
      initChart(); // 直接调用initChart而不是手动销毁
    });

    // 监听股票代码变化
    watch(() => props.stockCode, (newCode, oldCode) => {
      if (newCode && newCode !== oldCode) {
        allHistory.value = [];
        if (chartInstance.value) {
          updateChartData();
        } else {
          initChart();
        }
      }
    });

    onMounted(() => {
      initChart();
      // 使用防抖函数处理resize事件
      window.addEventListener('resize', handleResize);
    });

    onBeforeUnmount(() => {
      window.removeEventListener('resize', handleResize);
      if (chartInstance.value) {
        try {
          chartInstance.value.dispose();
        } catch (e) {
          console.warn('卸载组件时图表实例销毁失败:', e);
        }
        chartInstance.value = null;
      }
    });

    return {
      timeframe,
      chartContainer,
      seriesList,
      seriesVisibility,
      toggleSeries,
      getSeriesColorClass,
      refreshChart: updateChartData
    };
  }
}
</script>

<style lang="scss" scoped>
.stock-chart-section {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  padding: 20px;
  margin-bottom: 20px;

  .chart-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 15px;
  }

  .section-title {
    margin-top: 0;
    margin-bottom: 0;
    font-size: 1.5rem;
    font-weight: 600;
  }

  .stock-chart {
    height: 400px;
    width: 100%;
    
    // 为 ECharts 添加自定义样式
    :deep(.tooltip-container) {
      font-size: 12px;
      line-height: 1.5;
    }

    :deep(.tooltip-title) {
      font-weight: bold;
      text-align: center;
      margin-bottom: 5px;
      font-size: 14px;
      border-bottom: 1px dotted #ddd;
      padding-bottom: 3px;
    }

    :deep(.tooltip-item) {
      display: flex;
      justify-content: space-between;
      margin: 2px 0;
    }

    :deep(.tooltip-label) {
      color: #666;
      margin-right: 12px;
    }

    :deep(.tooltip-value) {
      font-weight: 600;
      color: #333;
    }

    :deep(.tooltip-up) {
      color: #f56c6c !important;
    }

    :deep(.tooltip-down) {
      color: #67c23a !important;
    }
  }

  .custom-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 15px;
    margin-bottom: 10px;
    
    .legend-item {
      display: flex;
      align-items: center;
      cursor: pointer;
      padding: 4px 8px;
      border-radius: 4px;
      transition: all 0.2s;
      user-select: none;
      
      &:hover {
        background-color: #f5f7fa;
      }
      
      &.legend-item-inactive {
        opacity: 0.5;
      }
    }
    
    .legend-icon {
      width: 16px;
      height: 3px;
      margin-right: 6px;
      
      &.color-high {
        background-color: #f56c6c;
      }
      
      &.color-low {
        background-color: #67c23a;
      }
      
      &.color-volume {
        background-color: #409EFF;
      }
    }
    
    .legend-label {
      font-size: 12px;
    }
  }
}
</style>
