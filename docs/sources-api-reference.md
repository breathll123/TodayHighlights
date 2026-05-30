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
| 2 | `statuses/search.json` | 关键词搜索 | 扁平JSON | 是 | ⚠️ 302 |
| 3 | `hot_event/list.json` | 热门话题 | 扁平JSON | 是 | ✅ |
| 4 | `stock.xueqiu.com/v5/stock/hot_stock/list.json` | 热股榜 | 扁平JSON | 是 | ✅ |
| 5 | `service/screener/quote/list` | 活跃股票 | 扁平JSON | 是 | ✅ |
| 6 | `stock.xueqiu.com/v5/stock/quote.json` | 个股行情 | 扁平JSON | 是 | ❌ |

> 热度榜（沪深 `type=10`、港股、美股）复用端点 4，仅 `type` 参数不同。

### 已废弃端点

| 端点 | 状态 |
|------|------|
| `statuses/search.json` | 302 重定向（已废弃，可 follow_redirects） |
| 热帖 `hot.json` / `hot/list/v2-v3.json` | 404 |
| `friends_timeline.json` | 404 |
| `v4/statuses/recommend.json` | 未测试 |
| `industry/list` | 404 |

---

## 东方财富 (Eastmoney)

**Base URL:** `https://push2.eastmoney.com`（主）/ `https://push2delay.eastmoney.com`（CDN 备用）

> 适配器 `sources/eastmoney.py` 的 `_push2_get()` 会依次尝试主域名和备用 CDN，主域名被限流（返回空/000）时自动切到 `push2delay`。

### 认证方式

行情/资金/板块/公告 API 无需认证，只需 `User-Agent` 和 `Referer` 头。**龙虎榜**例外，需 Playwright 获取 Session Cookie（见端点 4）。

### 通用请求头

```
User-Agent: Mozilla/5.0 DailyHighlights/0.1
Referer: https://quote.eastmoney.com/
```

### 采集子类型（entry_url）

`EastmoneyAdapter` 按 `entry_url` 的 `eastmoney://` 后缀分派到不同处理器：

| entry_url | 处理器 | 外部 API |
|-----------|--------|----------|
| `eastmoney://sectors` | `_fetch_board` | push2 clist (概念板块) |
| `eastmoney://industry` | `_fetch_board` | push2 clist (行业板块) |
| `eastmoney://capital_flow` | `_fetch_capital_flow` | push2 clist (主力资金) |
| `eastmoney://indices` | `_fetch_indices` | 新浪 hq.sinajs.cn (指数) |
| `eastmoney://longhu` | `_fetch_longhu_datacenter` | datacenter-web (龙虎榜) |

> 概念/行业/资金/指数 还有一套展示期直连的实现 `services/adapters/eastmoney.py`（`fetch_sectors` 等），由看板直接调用并走 30s TTL 缓存；龙虎榜只走采集落库 → 看板读 `raw_items`。

---

### 端点 1：板块排行 (概念/行业)

```
GET /api/qt/clist/get
```

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `pn` | int | 页码 | `1` |
| `pz` | int | 每页条数 | `20` |
| `po` | int | 排序方向 (0=升序, 1=降序) | `1` |
| `np` | int | `1` | `1` |
| `fltt` | int | `2`（小数格式） | `2` |
| `invt` | int | `2` | `2` |
| `fid` | str | 排序字段 | `f3` (涨跌幅) |
| `fs` | str | 板块过滤 | `m:90+t:3` (概念), `m:90+t:2` (行业), `m:90+t:1` (地域) |
| `fields` | str | 返回字段 | `f2,f3,f4,f12,f14` |

**字段映射（`data.diff[]`）：**

| 字段 | 说明 |
|------|------|
| `f2` | 板块指数 |
| `f3` | 涨跌幅 % |
| `f4` | 涨跌值 |
| `f12` | 板块代码 (BK0890) |
| `f14` | 板块名称 |

**板块 URL：** `https://quote.eastmoney.com/bk/90.{f12}.html`

> 行业板块在展示期还会对每个板块发 `fs=b:{code}` 子请求取领涨股（N+1），拼进 summary。

---

### 端点 2：主力资金流向

```
GET /api/qt/clist/get
```

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `fid` | str | 排序字段 | `f62` (主力净流入) |
| `fs` | str | 市场过滤 | `m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23` (沪深A股) |
| `fields` | str | 返回字段 | `f2,f3,f12,f14,f62,f64,f66` |

**字段映射：**

| 字段 | 说明 |
|------|------|
| `f2` | 当前价 |
| `f3` | 涨跌幅 % |
| `f12` | 股票代码 |
| `f14` | 股票名称 |
| `f62` | 主力净流入（元） |
| `f64` | 超大单净流入（元） |
| `f66` | 大单净流入（元） |

**个股 URL：** `https://quote.eastmoney.com/{f12}.html`

---

### 端点 3：指数行情（经新浪）✅

push2 的指数接口不稳定且易封 IP，改用新浪财经行情 API。

```
GET https://hq.sinajs.cn/list={codes}
```

| 参数 | 说明 |
|------|------|
| `list` | 逗号分隔的新浪代码，如 `s_sh000001,s_sz399001` |

**请求头：** `Referer: https://finance.sina.com.cn/`（必须，否则 403）
**编码：** 响应为 **GBK**，需 `.decode("gbk")`

**已采集的指数：**

| 新浪代码 | 东财代码 | 指数 |
|----------|----------|------|
| `s_sh000001` | `000001` | 上证指数 |
| `s_sz399001` | `399001` | 深证成指 |
| `s_sz399006` | `399006` | 创业板指 |
| `s_sh000688` | `000688` | 科创50 |
| `s_sz399673` | `399673` | 创业板50 |
| `s_sh000300` | `000300` | 沪深300 |

**响应格式：** `var hq_str_s_sh000001="上证指数,3200.12,12.34,0.39,..."`，逗号分隔，`[0]`=名称 `[1]`=当前点位 `[3]`=涨跌幅%。

**指数 URL：** `https://quote.eastmoney.com/zs{code}.html`

---

### 端点 4：龙虎榜（datacenter-web）✅

```
GET https://datacenter-web.eastmoney.com/api/data/v1/get
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `reportName` | str | `RPT_ORGANIZATION_TRADE_DETAILSNEW` (个股汇总) 或 `RPT_DAILYBILLBOARD_PROFILE` (日榜单) |
| `columns` | str | `ALL` |
| `pageNumber` | int | 页码 |
| `pageSize` | int | 每页条数（取 100 后端再筛最新交易日） |
| `sortTypes` | str | `-1`=降序, `1`=升序 |
| `sortColumns` | str | `TRADE_DATE` (按日期) 或 `NET_BUY_AMT` (按净买额) |
| `source` | str | `WEB` |
| `client` | str | `WEB` |

**认证方式：** Playwright 无头浏览器访问 `data.eastmoney.com/stock/lhb.html`（`wait_until="domcontentloaded"` + 3s 等待）获取 Session Cookie（无需登录），Cookie 进程内缓存 30 分钟。注意 `datacenter-web.eastmoney.com` 与被限流的 `data.eastmoney.com` 是不同域名，前者带 Cookie 即可直连。

**关键字段（`result.data[]`，reportName=RPT_ORGANIZATION_TRADE_DETAILSNEW）：**

| 字段 | 说明 |
|------|------|
| `SECURITY_CODE` | 股票代码 |
| `SECURITY_NAME_ABBR` | 股票名称 |
| `CHANGE_RATE` | 涨跌幅% |
| `NET_BUY_AMT` | 净买额（元） |
| `BUY_AMT` | 买入额（元） |
| `SELL_AMT` | 卖出额（元，负值） |
| `EXPLANATION` | 上榜原因（如"日涨幅偏离值达到7%的前五只证券"） |
| `TRADE_DATE` | 交易日期 |
| `TURNOVERRATE` | 换手率% |

**注意：** API 返回历史全量数据（含多年前），采集时取 `TRADE_DATE` 最大值为"最新交易日"，仅保留当日记录并按 `NET_BUY_AMT` 绝对值降序，最多 20 条。

---

### 端点 5：A股公告

```
GET https://np-anotice-stock.eastmoney.com/api/security/ann
```

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `page_index` | int | 页码 | `1` |
| `page_size` | int | 每页条数 | `20` |
| `ann_type` | str | 公告类型 | `A` (A股) |
| `sort_name` | str | 排序字段 | `notice_date` |
| `sort_type` | str | 排序方向 | `desc` |

**字段映射（`data.list[]`）：**

| 字段 | 说明 |
|------|------|
| `title` | 公告标题 |
| `notice_date` | 公告日期 |
| `codes[].stock_code` | 关联股票代码 |
| `art_code` | 文章 ID |

**公告 URL：** `https://data.eastmoney.com/notices/detail/{art_code}.html`

---

### 已废弃端点

| 端点 | 状态 |
|------|------|
| A股涨幅榜 `clist/get` (`fs=沪深A股` 排序) | 已删除——用户反馈不实用，改用雪球热度榜 |
| 龙虎榜 push2 `clist/get` (`f152/f174/f176/f178`) | 误用——这些不是龙虎榜字段，已换 datacenter-web API |
| 指数 `ulist.np/get` | 接口下线，已换新浪 API |

---

## 同花顺 (Tonghuashun / 10jqka)

**Base URL:** `https://news.10jqka.com.cn`

> 同花顺多数数据（龙虎榜、行情）有较强反爬（chameleon JS 挑战），无公开 JSON API。**仅财经快讯**走移动端推送接口，可直连。其余数据建议用东方财富替代。

### 认证方式

无需认证、无需 Cookie。使用移动端 `User-Agent` 直连。

### 端点 1：财经快讯（移动端推送）✅

```
GET https://news.10jqka.com.cn/tapp/news/push/stock?page=1
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `page` | int | 页码 |

**请求头：**

```
User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)
```

> 必须用移动端 UA，桌面 UA 会触发反爬挑战。

**字段映射（`data.list[]`）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int/str | 快讯 ID（external_id = `ths_news_{id}`） |
| `title` | str | 标题 |
| `digest` | str | 摘要正文 |
| `url` | str | 原文链接 |
| `ctime` | str | 秒级时间戳（字符串，需 `int()`） |

**展示样式：** 时间线（`tonghuashun_news`），看板从 `raw_items` 读取，按 `published_at` 降序。

### 已废弃/不可用

| 端点 | 状态 |
|------|------|
| 龙虎榜 / 行情 网页接口 | chameleon JS 挑战，无法直连 |
| 股吧/社区接口 | 需登录 + 反爬 |

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
