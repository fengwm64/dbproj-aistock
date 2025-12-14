# Flask 股票自选API文档

## 1. 获取当前用户的所有自选股票

### 基本信息
- **URL**：`/api/stocks/get`
- **请求方法**：`GET`
- **认证**：需要JWT认证

### 请求参数
无

### 响应结果
- **成功响应**：
```json
{
    "code": 0,
    "data": [
        {
            "id": 1,
            "user_id": "user123",
            "code": "600000",
            "name": "浦发银行",
            "added_at": "2025-05-09 10:30:00"
        },
        {
            "id": 2,
            "user_id": "user123",
            "code": "000001",
            "name": "平安银行",
            "added_at": "2025-05-09 11:45:00"
        }
    ]
}
```
- **失败响应**：
```json
{
    "code": 500,
    "msg": "服务器内部错误: 数据库连接失败"
}
```

## 2. 批量添加自选股票

### 基本信息
- **URL**：`/api/stocks/add`
- **请求方法**：`POST`
- **认证**：需要JWT认证
- **请求体类型**：`application/json`

### 请求参数
```json
{
    "stocks": [
        {
            "code": "SH600000",
            "name": "浦发银行"
        },
        {
            "code": "SZ000001"
        }
    ]
}
```

### 响应结果
- **成功响应**：
```json
{
    "code": 0,
    "data": {
        "added": [
            {
                "code": "600000",
                "name": "浦发银行"
            },
            {
                "code": "000001",
                "name": "平安银行"
            }
        ],
        "errors": [
            {
                "code": "SH600001",
                "reason": "股票代码不存在"
            }
        ],
        "total_added": 2
    }
}
```
- **失败响应**：
```json
{
    "code": 500,
    "msg": "服务器内部错误: 数据库操作失败"
}
```

## 3. 批量删除自选股票

### 基本信息
- **URL**：`/api/stocks/remove`
- **请求方法**：`POST`
- **认证**：需要JWT认证
- **请求体类型**：`application/json`

### 请求参数
```json
{
    "codes": ["600000", "000001", "600036"]
}
```

### 响应结果
- **成功响应**：
```json
{
    "code": 0,
    "data": {
        "deleted_codes": ["600000", "000001"],
        "total_deleted": 2
    }
}
```
- **失败响应**：
```json
{
    "code": 500,
    "msg": "服务器内部错误: 数据库连接失败"
}
```

## 4. 从图片中添加自选股票

### 基本信息
- **URL**：`/api/stocks/add_from_image`
- **请求方法**：`POST`
- **认证**：需要JWT认证
- **请求体类型**：`application/json`

### 请求参数
```json
{
    "image": "base64编码的图片数据"
}
```

### 响应结果
- **成功响应**：
```json
{
    "code": 0,
    "msg": "成功识别出3只股票",
    "data": {
        "stocks": [
            {
                "code": "600000",
                "name": "浦发银行"
            },
            {
                "code": "000001",
                "name": "平安银行"
            },
            {
                "code": "600036",
                "name": "招商银行"
            }
        ],
        "total": 3,
        "rejected": null
    }
}
```
- **失败响应**：
```json
{
    "code": 400,
    "msg": "未能正确解析出股票信息，请确保图片清晰",
    "detail": [
        {
            "item": "某股票信息",
            "reason": "无效股票代码格式"
        }
    ]
}
```

## 5. 确认从图片中添加自选股票

### 基本信息
- **URL**：`/api/stocks/confirm_from_image`
- **请求方法**：`POST`
- **认证**：需要JWT认证

### 请求参数
无（使用之前`add_from_image`接口存储的临时数据）

### 响应结果
- **成功响应**：与`/api/stocks/add`接口相同
- **失败响应**：
```json
{
    "code": 400,
    "msg": "没有待确认的股票数据，请重新上传图片"
}
```

## 6. 搜索股票

### 基本信息
- **URL**：`/api/stocks/search`
- **请求方法**：`GET`

### 请求参数
- **keyword**：搜索关键词，至少2个字符
- **limit**：返回结果数量限制，默认10，最大30

### 响应结果
- **成功响应**：
```json
{
    "code": 0,
    "data": {
        "stocks": [
            {
                "code": "600519",
                "name": "贵州茅台"
            },
            {
                "code": "600000",
                "name": "浦发银行"
            }
        ],
        "total": 2,
        "keyword": "贵州"
    }
}
```
- **失败响应**：
```json
{
    "code": 400,
    "msg": "搜索关键词不能少于2个字符"
}
```

## 7. 获取热门股票

### 基本信息
- **URL**：`/api/stocks/hot`
- **请求方法**：`GET`

### 请求参数
- **symbol**：榜单类型，可选值为"国内人气榜"或"港股人气榜"，默认"国内人气榜"

### 响应结果
- **成功响应**：
```json
{
    "code": 0,
    "msg": "获取热门股票成功",
    "data": [
        {
            "code": "600519",
            "name": "贵州茅台",
            "rank": 1,
            "latest_price": 1819.00,
            "change_percent": 2.13
        },
        {
            "code": "000858",
            "name": "五粮液",
            "rank": 2,
            "latest_price": 168.75,
            "change_percent": 1.56
        }
    ]
}
```
- **失败响应**：
```json
{
    "code": 400,
    "msg": "参数错误，symbol必须为\"国内人气榜\"或\"港股人气榜\""
}
```

## 8. 获取股票历史数据

### 基本信息
- **URL**：`/api/stocks/history`
- **请求方法**：`GET`

### 请求参数
- **code**：股票代码

### 响应结果
- **成功响应**：
```json
{
    "code": 0,
    "msg": "获取历史价格数据成功",
    "data": {
        "code": "600519",
        "history": [
            {
                "date": "2022-01-01",
                "open_price": 1800.00,
                "close_price": 1820.50,
                "high": 1830.00,
                "low": 1795.00,
                "volume": 1234567,
                "turnover": 2234567890.00,
                "amplitude": 1.94,
                "change_percent": 1.14,
                "change_amount": 20.50,
                "turnover_rate": 0.98
            }
        ]
    }
}
```
- **失败响应**：
```json
{
    "code": 404,
    "msg": "未找到股票 600519 的历史价格数据"
}
```

## 9. 获取股票详情

### 基本信息
- **URL**：`/api/stocks/detail`
- **请求方法**：`GET`

### 请求参数
- **code**：股票代码

### 响应结果
- **成功响应**：
```json
{
    "code": 0,
    "msg": "获取股票详细信息成功",
    "data": {
        "code": "600519",
        "name": "贵州茅台",
        "industry": "白酒",
        "listing_date": "2001-08-27",
        "total_shares": 12.56,
        "circulating_shares": 10.89,
        "trading": {
            "current_price": 1819.00,
            "change_percent": 2.13,
            "open": 1780.00,
            "high": 1825.00,
            "low": 1775.00,
            "volume": 1234567,
            "turnover": 2234567890.00,
            "market_cap": 2285.00,
            "change_5min": 0.75
        }
    }
}
```
- **失败响应**：
```json
{
    "code": 404,
    "msg": "未找到股票 600519 的基本信息"
}
```

## 10. 获取市场概览

### 基本信息
- **URL**：`/api/market/overview`
- **请求方法**：`GET`

### 请求参数
无

### 响应结果
- **成功响应**：
```json
{
    "code": 0,
    "msg": "success",
    "data": [
        {
            "index": "上证指数",
            "value": 3352.00,
            "change": 9.33,
            "change_pct": 0.279
        },
        {
            "index": "深证成指",
            "value": 10126.83,
            "change": -70.83,
            "change_pct": -0.69
        },
        {
            "index": "创业板指",
            "value": 2008.56,
            "change": -15.22,
            "change_pct": -0.755
        }
    ]
}
```
- **失败响应**：
```json
{
    "code": 500,
    "msg": "服务端错误",
    "error": "无法获取实时指数数据"
}
```

## 11. 获取股票新闻

### 基本信息
- **URL**：`/api/news/get`
- **请求方法**：`GET`

### 请求参数
- **code**：股票代码
- **page**：页码，默认1
- **limit**：每页条数，默认20，最大100

### 响应结果
- **成功响应**：
```json
{
    "code": 0,
    "msg": "success",
    "data": {
        "news": [
            {
                "id": "123",
                "title": "浦发银行发布2023年报",
                "content": "浦发银行今日发布2023年报，净利润同比增长...",
                "publish_time": "2023-03-30 10:15:20",
                "source": "http://news.example.com/123.html",
                "url": "http://news.example.com/123.html"
            }
        ],
        "pagination": {
            "page": 1,
            "limit": 20,
            "total": 35,
            "total_pages": 2,
            "has_more": true
        }
    }
}
```
- **失败响应**：
```json
{
    "code": 400,
    "error": "缺少 code 参数"
}
```

## 12. 获取新闻详情

### 基本信息
- **URL**：`/api/news/detail`
- **请求方法**：`GET`

### 请求参数
- **id**：新闻ID

### 响应结果
- **成功响应**：
```json
{
    "code": 0,
    "msg": "success",
    "data": {
        "id": "123",
        "title": "浦发银行发布2023年报",
        "content": "浦发银行今日发布2023年报，净利润同比增长10.5%，营业收入达到1345亿元...",
        "publish_time": "2023-03-30 10:15:20",
        "url": "http://news.example.com/123.html"
    }
}
```
- **失败响应**：
```json
{
    "code": 404,
    "msg": "新闻不存在"
}
```

## 13. AI评估股票新闻

### 基本信息
- **URL**：`/api/eva`
- **请求方法**：`GET`

### 请求参数
- **code**：股票代码
- **refresh**：是否强制刷新评估结果，默认false

### 响应结果
- **成功响应**：
```json
{
    "code": 0,
    "msg": "success",
    "data": {
        "conclusion": "利好",
        "reason": "根据近期新闻分析，该股票有多项积极因素：1. 公司发布新产品获得市场积极反馈；2. 季度财报超出市场预期；3. 行业政策支持力度加大。",
        "news_list": [
            {
                "title": "浦发银行推出新型金融产品",
                "content": "浦发银行今日宣布推出新型金融产品，获得市场积极反馈...",
                "link": "http://news.example.com/123.html",
                "publish_time": "2023-03-30 10:15:20"
            }
        ],
        "evaluation_time": "2023-03-31 09:25:30"
    }
}
```
- **失败响应**：
```json
{
    "code": 400,
    "msg": "缺少 code 参数"
}
```

## 14. 用户信息接口

### 基本信息
- **URL**：`/api/user/info`
- **请求方法**：`GET`
- **认证**：需要JWT认证

### 请求参数
无

### 响应结果
- **成功响应**：
```json
{
    "code": 0,
    "data": {
        "user_id": 123,
        "nickname": "股市高手",
        "avatar_url": "https://example.com/avatar.jpg",
        "role": "user",
        "created_at": "2023-01-15 13:45:30",
        "stocks_count": 15
    }
}
```
- **失败响应**：
```json
{
    "code": 404,
    "msg": "用户不存在"
}
```

## 15. 修改用户个人信息

### 基本信息
- **URL**：`/api/user/profile`
- **请求方法**：`POST`
- **认证**：需要JWT认证
- **请求体类型**：`application/json`

### 请求参数
```json
{
    "nickname": "新昵称",
    "avatar_url": "https://example.com/new_avatar.jpg"
}
```

### 响应结果
- **成功响应**：
```json
{
    "code": 0,
    "msg": "个人信息更新成功",
    "data": {
        "user_id": 123,
        "nickname": "新昵称",
        "avatar_url": "https://example.com/new_avatar.jpg",
        "updated_at": "2023-05-10 14:20:30"
    }
}
```
- **失败响应**：
```json
{
    "code": 400,
    "msg": "昵称不能超过30个字符"
}
```

## 16. 微信登录接口

### 基本信息
- **URL**：`/api/auth/login`
- **请求方法**：`POST`
- **请求体类型**：`application/json`

### 请求参数
```json
{
    "code": "微信授权登录的临时code"
}
```

### 响应结果
- **成功响应**：
```json
{
    "code": 0,
    "token": "eyJhbGc...",
    "user_id": 123,
    "expires_in": 2592000
}
```
- **失败响应**：
```json
{
    "code": 401,
    "msg": "登录失败: 微信授权码无效，请重新进入小程序获取",
    "detail": "微信code已过期或已被使用，需要重新获取",
    "action": "relogin",
    "wx_error": {}
}
```

## 17. 获取扫码登录URL

### 基本信息
- **URL**：`/api/auth/scan-login-url`
- **请求方法**：`GET`

### 请求参数
无

### 响应结果
- **成功响应**：
```json
{
    "code": 0,
    "qrcode_url": "https://mp.weixin.qq.com/cgi-bin/showqrcode?ticket=123",
    "state": "c8e5f-1d2a3b-4c5d6e",
    "expires_in": 300
}
```
- **失败响应**：
```json
{
    "code": 500,
    "msg": "微信登录配置错误: 缺少AppID",
    "error_type": "config_missing"
}
```

## 18. 检查扫码登录状态

### 基本信息
- **URL**：`/api/auth/login-status`
- **请求方法**：`GET`

### 请求参数
- **state**：从`/api/auth/scan-login-url`获取的状态码

### 响应结果
- **待扫码状态**：
```json
{
    "code": 0,
    "status": "pending",
    "msg": "等待扫码登录",
    "remaining": 285
}
```
- **扫码成功状态**：
```json
{
    "code": 0,
    "status": "confirmed",
    "msg": "扫码登录成功",
    "token": "eyJhbGc...",
    "user_id": 123,
    "expires_in": 2592000,
    "user_info": {
        "nickname": "股市高手",
        "avatar_url": "https://example.com/avatar.jpg",
        "role": "user"
    }
}
```
- **失败响应**：
```json
{
    "code": 401,
    "msg": "扫码状态已过期，请重新获取二维码",
    "status": "expired"
}
```

