# 数据源 API 参考

> 记录各数据源的请求地址、参数、响应格式。✅=已验证可用 ❌=已废弃/不可用。

---

## 雪球 (Xueqiu)

**Base URL:** `https://xueqiu.com`
**行情 Base URL:** `https://stock.xueqiu.com`

### 认证方式

从浏览器手动获取 Cookie，在管理后台填入。核心字段：`xq_a_token`、`xq_r_token`、`xq_id_token`、`u`

### 通用请求头

```
Cookie: <完整 Cookie>
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36
Accept: application/json
Referer: https://xueqiu.com/
X-Requested-With: XMLHttpRequest
```

### 注意事项

- 请求间隔建议 >2s，高频会触发 302 重定向
- 时间戳均为**毫秒**，需 `/1000`
- `target` 为相对路径，拼接 `https://xueqiu.com` 得到完整 URL

---

### 端点 1：推荐时间线 ✅

```
GET /v4/statuses/public_timeline_by_category.json
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `category` | int | `0`=推荐 |

**特点：** `list[].data` 是 **JSON 字符串**，需 `json.loads()` 二次解析。
**翻页：** `next_max_id` 游标

**内层 `data` 字段（解析后）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 帖子 ID |
| `title` | str | 标题 |
| `description` | str | 正文（含 `<br/>`） |
| `target` | str | 相对路径 |
| `user.screen_name` | str | 作者 |
| `user.followers_count` | int | 粉丝数 |
| `created_at` | int | 毫秒时间戳 |
| `reply_count` / `retweet_count` / `like_count` / `view_count` | int | 互动数据 |

---

### 端点 2：关键词搜索 ✅

```
GET /statuses/search.json
```

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `q` | str | 关键词或股票代码 | `芯片`、`SH600519` |
| `count` | int | 每页条数 | `20` |
| `page` | int | 页码 | `1` |

**特点：扁平结构**，`list[].title` / `list[].description` 直接可用，无需二次解析。字段同端点 1（内层）。
**翻页：** `maxPage` 总页数

---

### 端点 3：热门话题 ✅

```
GET /hot_event/list.json
```

无需参数，返回当日 10 个热门话题。

**响应：**

```json
{
  "count": 10,
  "page": 1,
  "list": [
    {
      "id": 482998,
      "tag": "#PCB概念大涨，鹏鼎控股创新高#",
      "content": "PCB概念再度走强，鹏鼎控股涨停...",
      "hot": 1,
      "status_count": 46,
      "pic": "https://xqimg.imedao.com/..."
    }
  ]
}
```

| 字段 | 说明 |
|------|------|
| `tag` | 话题标签（含 `#` 号） |
| `content` | 话题摘要 |
| `hot` | 是否热门 |
| `status_count` | 相关帖子数 |

**适用场景：** 发现当日热点主题，作为搜索关键词喂给端点 2

---

### 端点 4：热股榜 ✅

```
GET https://stock.xueqiu.com/v5/stock/hot_stock/list.json
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `type` | int | **必填**。`10`=A股热度榜，`11`=美股，`12`=A股，`20`/`30`=另类排行 |
| `size` | int | 返回条数 |

**响应 `data.items[]`：**

| 字段 | 说明 |
|------|------|
| `code` | 股票代码 `SZ000725` |
| `name` | 股票名称 |
| `symbol` | 股票代码 |
| `value` | 热度值 |
| `increment` | 热度变化（正=升温） |
| `rank_change` | 排名变化 |
| `current` | 当前价 |
| `percent` | 涨跌幅 % |
| `chg` | 涨跌额 |
| `exchange` | 交易所 |

---

### 端点 5：活跃股票筛选 ✅

```
GET /service/screener/quote/list
```

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `page` | int | 页码 | `1` |
| `size` | int | 每页条数 | `20` |
| `order` | str | `asc` / `desc` | `desc` |
| `order_by` | str | 排序字段 | `percent`、`turnover_rate`、`volume`、`amount` |
| `type` | str | `stock` | `stock` |
| `exchange` | str | 交易所 | `CN` |
| `market` | str | 市场 | `CN` |

**响应 `data.list[]`：** 40 个字段，核心：

| 字段 | 说明 |
|------|------|
| `symbol` | 股票代码 |
| `name` | 股票名称 |
| `current` | 当前价 |
| `percent` | 涨跌幅 % |
| `chg` | 涨跌额 |
| `amount` | 成交额 |
| `volume` | 成交量 |
| `turnover_rate` | 换手率 % |
| `market_capital` | 总市值 |
| `pe_ttm` | 市盈率 TTM |
| `pb` | 市净率 |
| `amplitude` | 振幅 % |
| `followers` | 关注人数 |

**适用场景：** 发现异动股（涨幅/换手率排序），作为搜索关键词喂给端点 2

---

### 端点 6：个股行情快照 ✅

```
GET https://stock.xueqiu.com/v5/stock/quote.json
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `symbol` | str | 股票代码 `SH600519` |
| `extend` | str | `detail` |

**响应字段：** `quote.name`、`quote.current`、`quote.percent`、`quote.amount`、`quote.high/low/open/last_close`、`market.status`

---

### 端点总览

| # | 端点 | 用途 | 格式 | 需Cookie | 已适配 |
|---|------|------|------|----------|--------|
| 1 | `v4/statuses/public_timeline_by_category.json` | 推荐 Feed | 嵌套JSON | 是 | ✅ |
| 2 | `statuses/search.json` | 关键词搜索 | 扁平JSON | 是 | ❌ |
| 3 | `hot_event/list.json` | 热门话题 | 扁平JSON | 是 | ❌ |
| 4 | `stock.xueqiu.com/v5/stock/hot_stock/list.json` | 热股榜 | 扁平JSON | 是 | ❌ |
| 5 | `service/screener/quote/list` | 活跃股票 | 扁平JSON | 是 | ❌ |
| 6 | `stock.xueqiu.com/v5/stock/quote.json` | 个股行情 | 扁平JSON | 是 | ❌ |

### 已废弃端点

| 端点 | 状态 |
|------|------|
| 热帖 `hot.json` / `hot/list/v2-v3.json` / `hot/page/1.json` | 404 |
| `friends_timeline.json` | 404 |
| `topic/list.json` / `search/topic.json` / `topic/hot/list.json` | 404 |
| `stock/hot_stock.json`（无 type 参数） | Tomcat 报错 |
| `stock/portfolio/stocks.json` | 400（需额外认证） |
| `v4/statuses/recommend.json` | 未测试 |
| `industry/list` | 404 |

---

## 同花顺 (Tonghuashun / 10jqka)

> TODO: 待调研

**可能入口：** `https://t.10jqka.com.cn/circle/index/` — 社区板块

### 认证方式

> TODO: 推测需要手机号登录 + Cookie

### 端点

> TODO

---

## 东方财富 (Eastmoney)

> TODO: 待调研

**可能入口：**
- `https://np-anotice-stock.eastmoney.com/` — 公告 API（公开）
- `https://push2.eastmoney.com/` — 行情推送（公开）
- 股吧社区 API

### 认证方式

> TODO: 行情和公告 API 可能是公开的，社区需要登录

### 端点

> TODO

---

## 足球 (Football)

> TODO: 待调研

**可能数据源：**

| 来源 | 说明 |
|------|------|
| 懂球帝 (dongqiudi.com) | 新闻、赛程、社区 |
| 直播吧 (zhibo8.cc) | 新闻聚合 |
| ESPN API | 英文，需 API Key |
| openligadb | 开源足球数据 API |

### 认证方式

> TODO

---

## 模板：新增数据源

```markdown
## 数据源名称

**Base URL:** `https://...`

### 认证方式

> Cookie / API Key / OAuth / 无需认证

### 端点

#### 1. 端点名称

METHOD /path

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|

响应格式、字段映射、注意事项...
```
