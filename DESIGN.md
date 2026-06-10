---
name: 今日看点
description: Multi-source real-time information dashboard with professional terminal aesthetics
colors:
  deep-teal: "#1DB8A8"
  deep-teal-foreground: "#062324"
  signal-gold: "#F5A623"
  signal-gold-foreground: "#1A0D00"
  terminal-bg: "#0F1419"
  terminal-card: "#131A21"
  terminal-muted: "#181F29"
  terminal-ink: "#EAF2F4"
  terminal-ink-muted: "#A1AAB5"
  terminal-border: "#242E3A"
  destructive-red: "#7D1C1C"
  destructive-red-foreground: "#F5E6E6"
typography:
  body:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    letterSpacing: "normal"
  title:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.35
  data:
    fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    fontFeature: "'tnum' 1, 'cv02' 1, 'cv03' 1, 'cv04' 1"
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
  xl: "16px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.deep-teal}"
    textColor: "{colors.deep-teal-foreground}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
    typography: "{typography.label}"
  button-primary-hover:
    backgroundColor: "hsl(174 72% 48%)"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.terminal-ink-muted}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  button-ghost-hover:
    backgroundColor: "hsl(214 30% 20%)"
  card-default:
    backgroundColor: "{colors.terminal-card}"
    rounded: "{rounded.xl}"
    padding: "{spacing.lg}"
  input-default:
    backgroundColor: "{colors.terminal-bg}"
    textColor: "{colors.terminal-ink}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
---

# Design System: 今日看点

## 1. Overview

**Creative North Star: "终端操盘室"**

一个人面对终端屏幕。深色背景上的数据流、等宽数字、颜色编码的状态变化。安静、精准、不废话。每增一像素装饰，就减一分信息密度。修饰是噪音，数据是信号。

系统扎根于 shadcn/ui 的语义 token 骨架（`primary / secondary / muted / accent / destructive / border`），但朝专业工具方向收紧：更暗的底色、更高的前景对比度、等宽数字、极简的层级变化。深潮青（`#1DB8A8`）是主锚点——按钮、选中态、聚焦环——占比不超过任何屏幕的 10%。信号金（`#F5A623`）作第二信号：置顶标记、排行榜金银铜、AI 摘要徽标，不用于常规 UI。

不接受 SaaS 白/奶油风、不接受玻璃拟态和炫技动画。Bloomberg 终端是精神参照，不是视觉副本。

**Key Characteristics:**
- 深色原生（`html { color-scheme: dark; }`），亮色模式存在但非默认
- 色调分层代替阴影——card、popover、muted 通过背景深浅区分，不是通过投影
- 等宽数字（`tnum`）全局开启；数字右对齐、千分位格式化
- 状态编码用颜色，不用图标（红跌绿涨、直播闪烁）
- 单一字体家族 Inter，通过字重区分层级

## 2. Colors

深海底色上的潮青和信号金。主色克制，强调色精准。

### Primary
- **Deep Teal** (`#1DB8A8`, hsl(174 72% 42%)): 主按钮背景、选中态、聚焦环、链接、AI 分析徽标。出现在 ≤10% 的表面像素上。
- **Deep Teal Foreground** (`#062324`, hsl(180 72% 8%)): 主按钮上的文字。极深的潮青色调，确保 ≥7:1 对比度。

### Secondary
- **Terminal Muted** (`#181F29`, hsl(214 30% 14%)): 表格表头背景、代码块、骨架屏。比卡片深一层，形成后退感。
- **Muted Foreground** (`#A1AAB5`, hsl(212 16% 68%)): 辅助文字、占位符、元信息。不在非交互元素上使用更浅的灰色。

### Tertiary (Signal)
- **Signal Gold** (`#F5A623`, hsl(38 92% 54%)): 置顶标记、排行榜金牌行、AI 摘要徽标、重要通知。只用于「值得注意」的信号，不用于常规 UI 装饰。
- **Signal Gold Foreground** (`#1A0D00`): 金色背景上的文字。

### Neutral
- **Terminal Background** (`#0F1419`, hsl(215 38% 6%)): 页面底色。接近黑但不是纯黑——保留微弱的蓝调暗示屏幕发光。
- **Terminal Card** (`#131A21`, hsl(214 34% 9%)): 卡片、面板、表格容器。比背景亮一层。
- **Terminal Ink** (`#EAF2F4`, hsl(190 30% 94%)): 正文、标题。≥7:1 对比度对底色。
- **Terminal Ink Muted** (`#A1AAB5`): 辅助文字。≥4.5:1 对卡片底色。
- **Terminal Border** (`#242E3A`, hsl(212 28% 19%)): 分割线、输入框边框、表格边框。存在但不喧宾夺主。
- **Destructive Red** (`#7D1C1C`, hsl(0 62.8% 30.6%)): 删除按钮、错误状态、下跌。

### Named Rules
**The 10% Rule.** 深潮青在任何屏幕上占据的像素不超过 10%。主按钮、选中态、聚焦环、链接——用完配额就停。稀缺性是其力量。

**The Gold Only Signals Rule.** 信号金只在「值得注意」的语义信号上使用——置顶、排行榜金/银/铜、AI 徽标。不作为常规 UI 装饰、图标颜色或背景色。如果用户扫一眼屏幕注意不到金色在哪里，那金色就在正确的位置。

## 3. Typography

**Body / Label / Title / Data Font:** Inter (with ui-sans-serif, system-ui, sans-serif fallback)

**Character:** 单一家族，通过字重和字号建立层级。不做字体配对——Inter 的清晰度和 x-height 在数据密度场景下表现稳定。全局开启 `tnum`（等宽数字）+ `cv02/cv03/cv04`（Inter 的字符变体），确保数字对齐和标点清晰。

### Hierarchy
- **Title** (600, 1rem / 16px, 1.35): 方块标题、卡片标题。仅比 body 大一级——工具型 UI 不需要戏剧性的尺寸跳跃。
- **Body** (400, 0.875rem / 14px, 1.6): 正文、表格单元格、摘要文本。行高 1.6 确保多行信息的可读性。最大行长 75ch。
- **Label** (500, 0.75rem / 12px): 表单标签、表头、徽标、辅助元信息。不做全大写追踪展开。
- **Data** (400, 0.875rem / 14px, `tnum`): 数字专用角色。等宽数字 + 右对齐 + 千分位分隔。用于价格、涨跌幅、token 计数、积分。

### Named Rules
**The One Voice Rule.** Inter 处理所有文本角色。不加第二个字体。层级通过字号（0.75 / 0.875 / 1rem）和字重（400 / 500 / 600）区分，不通过字体切换。

## 4. Elevation

色调分层，不是阴影分层。系统是扁平的——深度通过背景色明度表达，不是通过投影。

- **Terminal Background** (`#0F1419`): 地基。页面底色。
- **Terminal Card** (`#131A21`): 抬升一层。卡片、面板、图表容器。比背景亮 ~4% L。
- **Terminal Muted** (`#181F29`): 表头、代码块。比卡片深一层，产生后退感。

阴影只在两种情况下出现：模态框/抽屉的 `shadow-2xl`（物理上的「浮在上面」），以及排行榜金/银/铜行的 `box-shadow: inset 2px 0`（嵌入信号条）。卡片和按钮在 hover 时不做 lift 动画——色调已足够区分状态。

### Named Rules
**The Flat-By-Default Rule.** 表面平面放置。阴影只在模态、抽屉和排行榜行标记上使用。hover 不做 lift。

## 5. Components

### Buttons
- **Shape:** 6px 圆角 (`--radius: 0.5rem` 的 `rounded-md`)。不是圆角胶囊。
- **Primary:** 深潮青底色 + 深色文字，内边距 8px 16px。hover 时亮度提升 6%。
- **Ghost:** 透明底色 + muted 文字，hover 时背景变为 `hsl(214 30% 20%)`。用于表格内操作、工具栏图标按钮。
- **Outline:** 透明底色 + border 边框 + muted 文字，hover 时切换为 accent 背景。用于次要 CTA。
- **Destructive:** 破坏性红色底色，hover 时加深。仅用于删除、禁用等不可逆操作。
- **Disabled:** `opacity: 0.5` + `pointer-events: none`。充分降低但不隐藏——用户需要知道它存在只是不可用。
- **Size tokens:** `sm` (h-9), `default` (h-10), `lg` (h-11), `icon` (h-10 w-10)。

### Cards
- **Corner Style:** 12-16px 圆角（`rounded-xl`）。有弧度但不圆。
- **Background:** `Terminal Card` (`#131A21`)。永远不嵌套另一个 card 在内部。
- **Border:** 0.5-1px `Terminal Border` 描边。没有阴影。
- **Internal Padding:** 16px 或 24px，取决于内容密度。

### Inputs / Fields
- **Style:** `Terminal Background` 底色 + `Terminal Border` 1px 描边 + 8px 圆角。
- **Focus:** 深潮青聚焦环（`ring`），2px offset。
- **Placeholder:** `Terminal Ink Muted`（`#A1AAB5`），≥4.5:1 对底色。

### Tags / Badges
- **Default:** 深潮青 10% 透明度底色 + 深潮青文字。用于「已启用」「AI」「默认」等状态标签。
- **Secondary:** Terminal Muted 底色 + muted 文字。用于「禁用」「未配置」等非活跃状态。
- **Destructive:** 破坏性红 10% 底色 + 红色文字。用于「失败」「错误」。
- **Signal Gold:** 金色 10% 底色 + 金色文字。用于「置顶」「金牌」。

### Tables
- **Header:** `Terminal Muted` 底色 + Label 字重 + muted 文字。
- **Body rows:** 透明底色，hover 时 `bg-muted/30`。
- **Border:** `border-b` 底部分割，无垂直分割线。
- **Numbers:** 右对齐 + `tabular-nums` + 千分位分隔。

### Navigation (Admin Sidebar)
- **Style:** 深色侧边栏，当前页用深潮青底色 + 白色文字，其他用 muted 文字 + hover 时变亮。
- **Icons:** Lucide React，18-20px，与文字同色。
- **Mobile:** 折叠为仅图标（w-16），展开时 w-60。

### The AI Analysis Drawer
- **Desktop:** 右侧固定 480-520px 宽，从右滑入（`translateX`）。半透明 backdrop。
- **Mobile:** 底部 Sheet，`max-h-[82dvh]`，`rounded-t-2xl`。
- **Motion:** Framer Motion，200ms ease-out，x 位移 + opacity。

## 6. Do's and Don'ts

### Do:
- **Do** 使用 `tabular-nums` 展示所有数字——价格、涨跌幅、token 计数、积分、排名。
- **Do** 数字右对齐，千分位用 `toLocaleString()`。
- **Do** 深潮青仅用于主按钮、选中态、聚焦环、链接——≤10% 表面像素。
- **Do** 信号金仅用于置顶标记、排行榜金/银/铜、AI 徽标——不做常规 UI 装饰。
- **Do** 卡片用色调分层（`bg-card` vs `bg-muted` vs `bg-background`）建立层级，不用阴影。
- **Do** 表格行 hover 时背景变为 `bg-muted/30`，不改变边框。
- **Do** 维持 Inter 单一字体家族——层级通过字号和字重，不通过字体切换。

### Don't:
- **Don't** 使用大面积白色/奶油色背景。深色是原生的（`html { color-scheme: dark; }`）。亮色模式只作为备选存在。
- **Don't** 在非交互元素上使用低于 `muted-foreground` 亮度的灰色。灰底灰字 = 不可读。
- **Don't** 使用 `border-left` > 1px 作为彩色装饰条。用背景色 tint 或嵌入阴影代替。
- **Don't** 使用渐变文字（`background-clip: text`）。
- **Don't** 使用玻璃拟态或 backdrop-blur 作为默认卡片样式。
- **Don't** 使用 `text-[10px]` 作为正文（仅限极短标签和徽标）。
- **Don't** 在同一页面使用两个以上的圆角值。系统有四个（6/8/12/16），每次选一个。
- **Don't** 嵌套卡片。
