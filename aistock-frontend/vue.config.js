const AutoImport = require('unplugin-auto-import/webpack')
const Components = require('unplugin-vue-components/webpack')
const { ElementPlusResolver } = require('unplugin-vue-components/resolvers')
const CompressionPlugin = require('compression-webpack-plugin')

module.exports = {
  lintOnSave: false,
  // 添加publicPath确保资源正确加载
  publicPath: '/',
  // 添加 transpileDependencies 以转译潜在的问题依赖
  transpileDependencies: true,
  // 启用文件名哈希以防止缓存问题
  filenameHashing: true,
  // 禁用HMR/热重载
  chainWebpack: config => {
    config.plugins.delete('hmr');
    
    // 为所有资源添加版本控制
    config.output.filename('[name].[contenthash:8].js')
    config.output.chunkFilename('[name].[contenthash:8].js')
    
    // CSS文件名也添加hash（仅在生产环境）
    if (process.env.NODE_ENV === 'production') {
      config.plugin('extract-css').tap(args => {
        args[0].filename = 'css/[name].[contenthash:8].css'
        args[0].chunkFilename = 'css/[name].[contenthash:8].css'
        return args
      })
    }
    
    // 生产环境优化
    if (process.env.NODE_ENV === 'production') {
      // 代码分割优化
      config.optimization.splitChunks({
        chunks: 'all',
        cacheGroups: {
          vendor: {
            test: /[\\/]node_modules[\\/]/,
            name: 'vendors',
            priority: 10,
            chunks: 'initial'
          },
          elementUI: {
            name: 'chunk-elementPlus',
            priority: 20,
            test: /[\\/]node_modules[\\/]_?element-plus(.*)/
          },
          echarts: {
            name: 'chunk-echarts',
            priority: 20,
            test: /[\\/]node_modules[\\/]_?echarts(.*)/
          }
        }
      })
      
      // 添加Gzip压缩
      config.plugin('CompressionPlugin').use(CompressionPlugin, [
        {
          test: /\.(js|css|html|svg)$/,
          threshold: 10240,
          minRatio: 0.8
        }
      ])
    }
  },
  configureWebpack: {
    resolve: {
      alias: {
        '@': require('path').resolve(__dirname, 'src')
      }
    },
    plugins: [
      AutoImport({
        resolvers: [ElementPlusResolver()],
      }),
      Components({
        resolvers: [ElementPlusResolver()],
      }),
    ],
    // 生产环境性能优化
    ...(process.env.NODE_ENV === 'production' && {
      performance: {
        hints: 'warning',
        maxAssetSize: 512000,
        maxEntrypointSize: 512000,
      },
      optimization: {
        usedExports: true,
        sideEffects: false,
      }
    })
  },
  devServer: {
    allowedHosts: 'all',
    // 完全禁用WebSocket服务器
    webSocketServer: false,
    // 关闭热重载和实时刷新
    hot: false,
    liveReload: false,
    // 正确配置client选项
    client: {
      // 使用有效的WebSocketURL配置
      webSocketURL: {
        protocol: 'wss',  // 使用安全WebSocket协议
        hostname: 'localhost',
        port: '0'  // 使用无效端口，确保不会连接
      },
      overlay: {
        warnings: false,
        errors: true
      },
      progress: false,
    },
    proxy: {
      '/api': {
        target: 'https://api.aistocklink.cn',
        changeOrigin: true,
        secure: false,
        headers: {
          Referer: 'https://api.aistocklink.cn'
        },
        onProxyReq(proxyReq, req, res) {
          console.log('代理请求:', req.method, req.url);
        },
        onProxyRes(proxyRes, req, res) {
          console.log('代理响应:', proxyRes.statusCode, req.url);
          const contentType = proxyRes.headers['content-type'] || '';
          console.log('响应内容类型:', contentType);
        }
      }
    },
    setupMiddlewares: (middlewares, devServer) => {
      if (!devServer) {
        throw new Error('webpack-dev-server is not defined');
      }

      devServer.app.use((req, res, next) => {
        console.log('请求:', req.method, req.url);
        next();
      });

      return middlewares;
    }
  }
}
