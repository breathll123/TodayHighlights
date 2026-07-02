// 生成主题过场/加载动画的 Lottie JSON 资源（线条风，design-token 配色）。
// 运行：cd frontend && node scripts/lottie/generate.mjs
// 产物：src/assets/lottie/*.json。若将来改用 LottieFiles 素材，同名替换即可。
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const OUT_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "src", "assets", "lottie");

// —— 设计 token ——
const TEAL = "#1EB9A8";   // deep-teal 主色（暗色主题 --primary 近似）
const GOLD = "#F5B01F";   // signal-gold
const INK = "#E6F2F0";    // 亮前景
const GREEN = "#2BE07A";  // 足球
const CYAN = "#4DD0FF";   // AI
const PURPLE = "#9A7BFF"; // 游戏（与 block-themes ARCADE_FALLBACK 一致）
const RED = "#FF5A5A";    // 股票（红涨）

// —— Lottie 构件 ——
const rgba = (hex) => {
  const n = parseInt(hex.slice(1), 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255, 1];
};
const stat = (k) => ({ a: 0, k });
const EASE = { i: { x: [0.4], y: [1] }, o: { x: [0.6], y: [0] } };
const LINEAR = { i: { x: [0.167], y: [0.167] }, o: { x: [0.167], y: [0.167] } };
const kfs = (frames, e = EASE) => ({
  a: 1,
  k: frames.map((f, i) => (i === frames.length - 1 ? { t: f.t, s: f.s } : { t: f.t, s: f.s, ...e })),
});

const groupTr = () => ({ ty: "tr", p: stat([0, 0]), a: stat([0, 0]), s: stat([100, 100]), r: stat(0), o: stat(100) });
const group = (nm, it) => ({ ty: "gr", nm, it: [...it, groupTr()] });
const ellipse = (w, h = w, p = [0, 0]) => ({ ty: "el", p: stat(p), s: stat([w, h]) });
const rect = (w, h, r = 0, p = [0, 0]) => ({ ty: "rc", p: stat(p), s: stat([w, h]), r: stat(r) });
const path = (v, closed = false) => ({
  ty: "sh",
  ks: stat({ c: closed, v, i: v.map(() => [0, 0]), o: v.map(() => [0, 0]) }),
});
const stroke = (hex, w, o = 100) => ({ ty: "st", c: stat(rgba(hex)), o: stat(o), w: stat(w), lc: 2, lj: 2 });
const fill = (hex, o = 100) => ({ ty: "fl", c: stat(rgba(hex)), o: stat(o) });
const trim = (end) => ({ ty: "tm", s: stat(0), e: end, o: stat(0), m: 1 });

const layer = (nm, ind, shapes, ks = {}, extra = {}) => ({
  ddd: 0,
  ind,
  ty: 4,
  nm,
  sr: 1,
  ao: 0,
  ks: { o: stat(100), r: stat(0), p: stat([120, 120, 0]), a: stat([0, 0, 0]), s: stat([100, 100, 100]), ...ks },
  shapes,
  ip: 0,
  op: 120,
  st: 0,
  bm: 0,
  ...extra,
});
const doc = (nm, layers) => ({ v: "5.7.4", fr: 60, ip: 0, op: 120, w: 240, h: 240, nm, ddd: 0, assets: [], layers });

// ⚽ 足球：弹跳两次 + 匀速滚转 + 地面阴影随弹跳缩放
const football = doc("football", [
  layer(
    "ball",
    1,
    [
      group("shell", [ellipse(64), stroke(INK, 4)]),
      group("patch", [path([[0, -11], [10.5, -3.4], [6.5, 8.9], [-6.5, 8.9], [-10.5, -3.4]], true), fill(INK)]),
    ],
    {
      p: kfs([
        { t: 0, s: [120, 156, 0] },
        { t: 30, s: [120, 86, 0] },
        { t: 60, s: [120, 156, 0] },
        { t: 90, s: [120, 86, 0] },
        { t: 120, s: [120, 156, 0] },
      ]),
      r: kfs([{ t: 0, s: [0] }, { t: 120, s: [360] }], LINEAR),
    },
  ),
  layer("shadow", 2, [group("shadow", [ellipse(64, 12), fill(GREEN, 30)])], {
    p: stat([120, 198, 0]),
    s: kfs([
      { t: 0, s: [100, 100, 100] },
      { t: 30, s: [55, 100, 100] },
      { t: 60, s: [100, 100, 100] },
      { t: 90, s: [55, 100, 100] },
      { t: 120, s: [100, 100, 100] },
    ]),
  }),
]);

// 🤖 机器人：头部悬浮 + 眨眼 + 天线灯呼吸（眼睛/天线用 parent 跟随头部）
const robot = doc("robot", [
  layer("head", 1, [group("head", [rect(84, 64, 14), stroke(CYAN, 5)])], {
    p: kfs([
      { t: 0, s: [120, 124, 0] },
      { t: 60, s: [120, 112, 0] },
      { t: 120, s: [120, 124, 0] },
    ]),
  }),
  layer(
    "eyes",
    2,
    [
      group("eyeL", [ellipse(12, 12, [-18, 0]), fill(CYAN)]),
      group("eyeR", [ellipse(12, 12, [18, 0]), fill(CYAN)]),
    ],
    {
      p: stat([0, 2, 0]),
      s: kfs([
        { t: 0, s: [100, 100, 100] },
        { t: 50, s: [100, 100, 100] },
        { t: 55, s: [100, 10, 100] },
        { t: 60, s: [100, 100, 100] },
        { t: 120, s: [100, 100, 100] },
      ]),
    },
    { parent: 1 },
  ),
  layer(
    "antenna",
    3,
    [
      group("mast", [path([[0, -32], [0, -50]]), stroke(CYAN, 4)]),
      group("tip", [ellipse(10, 10, [0, -56]), fill(GOLD)]),
    ],
    {
      p: stat([0, 0, 0]),
      o: kfs([
        { t: 0, s: [45] },
        { t: 30, s: [100] },
        { t: 60, s: [45] },
        { t: 90, s: [100] },
        { t: 120, s: [45] },
      ]),
    },
    { parent: 1 },
  ),
]);

// 🎮 手柄：机身左右轻摆 + 十字键常亮 + 两颗按键交替呼吸
const gamepad = doc("gamepad", [
  layer(
    "body",
    1,
    [
      group("body", [rect(124, 66, 28), stroke(PURPLE, 5)]),
      group("dpad", [rect(30, 10, 2, [-32, 0]), rect(10, 30, 2, [-32, 0]), fill(PURPLE)]),
    ],
    {
      p: stat([120, 124, 0]),
      r: kfs([
        { t: 0, s: [0] },
        { t: 30, s: [-6] },
        { t: 90, s: [6] },
        { t: 120, s: [0] },
      ]),
    },
  ),
  layer("btnA", 2, [group("btnA", [ellipse(14, 14, [26, -8]), fill(GOLD)])], {
    p: stat([0, 0, 0]),
    o: kfs([
      { t: 0, s: [100] },
      { t: 30, s: [35] },
      { t: 60, s: [100] },
      { t: 90, s: [35] },
      { t: 120, s: [100] },
    ]),
  }, { parent: 1 }),
  layer("btnB", 3, [group("btnB", [ellipse(14, 14, [44, 8]), fill(PURPLE)])], {
    p: stat([0, 0, 0]),
    o: kfs([
      { t: 0, s: [35] },
      { t: 30, s: [100] },
      { t: 60, s: [35] },
      { t: 90, s: [100] },
      { t: 120, s: [35] },
    ]),
  }, { parent: 1 }),
]);

// 📈 K 线：三根阳线依次拔地而起 + 金色趋势线描画
const candle = (nm, ind, x, h, delay) =>
  layer(
    nm,
    ind,
    [
      group("body", [rect(14, h, 2, [0, -h / 2]), fill(RED)]),
      group("wick", [path([[0, -h - 10], [0, 6]]), stroke(RED, 3)]),
    ],
    {
      p: stat([x, 160, 0]),
      // delay=0 时跳过延迟帧，避免同一 t 上出现重复关键帧
      s: kfs([
        { t: 0, s: [100, 0, 100] },
        ...(delay > 0 ? [{ t: delay, s: [100, 0, 100] }] : []),
        { t: delay + 22, s: [100, 100, 100] },
        { t: 120, s: [100, 100, 100] },
      ]),
    },
  );
const kline = doc("kline", [
  candle("candle1", 1, 84, 44, 0),
  candle("candle2", 2, 120, 64, 12),
  candle("candle3", 3, 156, 86, 24),
  layer(
    "trend",
    4,
    [
      group("trend", [
        path([[62, 150], [100, 118], [136, 132], [178, 84]]),
        trim(kfs([
          { t: 0, s: [0] },
          { t: 30, s: [0] },
          { t: 90, s: [100] },
          { t: 120, s: [100] },
        ])),
        stroke(GOLD, 4),
      ]),
    ],
    { p: stat([0, 0, 0]) },
  ),
]);

// 📡 雷达：双环 + 匀速扫描线 + 金色目标点闪现（呼应全局首页 Radar 品牌图标）
const radar = doc("radar", [
  layer("rings", 1, [
    group("outer", [ellipse(150), stroke(TEAL, 3, 70)]),
    group("inner", [ellipse(92), stroke(TEAL, 3, 35)]),
    group("center", [ellipse(9), fill(TEAL)]),
  ]),
  layer("sweep", 2, [group("sweep", [path([[0, 0], [0, -72]]), stroke(TEAL, 4)])], {
    r: kfs([{ t: 0, s: [0] }, { t: 120, s: [360] }], LINEAR),
  }),
  layer("blip", 3, [group("blip", [ellipse(11, 11, [42, -30]), fill(GOLD)])], {
    o: kfs([
      { t: 0, s: [0] },
      { t: 18, s: [0] },
      { t: 28, s: [100] },
      { t: 70, s: [0] },
      { t: 120, s: [0] },
    ]),
  }),
]);

// ✨ 通用兜底：呼吸外环 + 三点信号波（中间一颗金色）
const dot = (nm, ind, x, hex, delay) =>
  layer(nm, ind, [group("dot", [ellipse(18), fill(hex)])], {
    p: stat([x, 120, 0]),
    // delay=0 时跳过延迟帧，避免同一 t 上出现重复关键帧
    s: kfs([
      { t: 0, s: [100, 100, 100] },
      ...(delay > 0 ? [{ t: delay, s: [100, 100, 100] }] : []),
      { t: delay + 20, s: [135, 135, 100] },
      { t: delay + 40, s: [100, 100, 100] },
      { t: 120, s: [100, 100, 100] },
    ]),
    o: kfs([
      { t: 0, s: [55] },
      ...(delay > 0 ? [{ t: delay, s: [55] }] : []),
      { t: delay + 20, s: [100] },
      { t: delay + 40, s: [55] },
      { t: 120, s: [55] },
    ]),
  });
const generic = doc("generic", [
  layer("ring", 1, [group("ring", [ellipse(140), stroke(TEAL, 2)])], {
    o: kfs([
      { t: 0, s: [25] },
      { t: 60, s: [55] },
      { t: 120, s: [25] },
    ]),
  }),
  dot("dot1", 2, 84, TEAL, 0),
  dot("dot2", 3, 120, GOLD, 15),
  dot("dot3", 4, 156, TEAL, 30),
]);

// —— 写盘 ——
const docs = { football, robot, gamepad, kline, radar, generic };
mkdirSync(OUT_DIR, { recursive: true });
for (const [name, d] of Object.entries(docs)) {
  writeFileSync(join(OUT_DIR, `${name}.json`), JSON.stringify(d));
  console.log(`generated ${name}.json (${JSON.stringify(d).length} bytes)`);
}
