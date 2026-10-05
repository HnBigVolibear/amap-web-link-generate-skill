---
name: amap-web-link-generate
version: 1.1.0
description: 生成高德官方静态展示页的免key免登录地图分享链接，支持23类彩色图钉、驾车/步行/骑行/公交真实路线、弹窗富文本贴图。Use when user wants to 生成可分享地图链接、行程单、行程展示、路线展示页，或提到 高德地图链接、travel_plan、打点、路线可视化、静态地图、地图分享、带图行程单。数据采集可用 amap-maps MCP、高德 REST API 或任意地理编码手段。
metadata:
  requires:
    bins: ["python"]
---

# 高德 Web 地图链接生成器（amap-web-link-generate）

生成形如 `https://a.amap.com/jsapi_demo_show/static/openclaw/travel_plan.html?data=<URL编码JSON>` 的地图可视化链接。

**原理**：该页面是高德官方公开的静态演示资产（约 22KB 纯 HTML），收到 `data` 后**实时调用高德路径规划服务**（AMap.Driving/Walking/Riding/Transfer 四插件）绘制真实道路/公交几何——不是画起终点直线。地图渲染用的 JSAPI key 内置于页面且绑定 a.amap.com 域名白名单，因此：

> ✅ **链接的生成与打开全程零 key、零登录、零依赖**。数据如何采集是调用方自己的事（见 Step 1 的三条路径），与本技能的链接生成环节无关。

## 标准工作流（4 步）

### Step 1 — 采集真实数据（三条路径任选）

| 路径 | 适用 | 手段 |
|---|---|---|
| A. amap-maps MCP | 本机已挂该 MCP 时首选 | `maps_text_search`（地名→id）→ `maps_search_detail`（精确坐标 lnglat、评分、开放时间、**高德官方实拍图 URL**）；公交方案 `maps_direction_transit_integrated`（**必须传 city**）；驾车 `maps_direction_driving` |
| B. 高德 Web 服务 REST API | 无 MCP 的其他 agent | `restapi.amap.com/v3/geocode/geo`（地理编码）、`/v3/place/text` 或 `/v5/place/text`（POI）、`/v3/direction/transit/integrated`（公交），需自备 Web Service key，请求带 `Referer: https://a.amap.com/` 更稳 |
| C. 任意地理编码手段 | 兜底 | 手头有任何能给出「经度,纬度」的方式即可；甚至可跳过坐标，直接用 Step 2 的 keyword 格式 |

⚠️ 所有高德接口**串行调用、每请求间隔 ≥1 秒**——并发会撞 `CUQPS_HAS_EXCEEDED_THE_LIMIT` 限流（个人开发者并发=1）。

### Step 2 — 构造 data JSON 数组（契约见下文「data 接口契约」）

把 POI 与 route 混排进一个数组，顺序即叙事顺序（第 1 站→路线→第 2 站→路线→…）。

### Step 3 — 运行脚本生成链接（编码 + 结构预检 + 三查验证一体）

```bash
python "<base_dir>/scripts/build_link.py" <data.json>            # 生成 + 三查验证
python "<base_dir>/scripts/build_link.py" <data.json> --out link.txt   # 另存链接
python "<base_dir>/scripts/build_link.py" <data.json> --no-check       # 跳过网络验证（三查未过时可强制写盘）
python "<base_dir>/scripts/build_link.py" <data.json> --http           # 页面链接用 http（贴 http-only 图床图片时用，见坑#2；默认 https）
```

脚本自动完成：编码拼接 → 结构预检（transfer 缺 city / routeType 非法 / 坐标格式错都会报警）→ **交付三查**（HTTP 200 / 落点仍是 a.amap.com / 页面标题含「兴趣点与路线规划展示」/ 无登录墙字样）。**三查不过不得交付**——脚本会在三查未过/网络验证失败时**自动拦截 `--out` 写盘**，确要强制导出才加 `--no-check`。

### Step 4 — 交付

链接放**代码框**发用户（长链接经 markdown 渲染易截断），提示双击全选复制、别漏尾部 `%5D`。

生成成功即交付完成，**无需再打开链接做渲染验证**——本页渲染逻辑由高德官方演示页保证，三查通过即视为交付成功。

## data 接口契约

数组元素两类，可任意混排：

### POI 项

```json
{"type": "poi", "lnglat": [116.397029, 39.917839], "sort": "风景名胜",
 "text": "故宫博物院", "remark": "5A景区·世界遗产，评分4.9<br><b>旺季 08:30-17:00（周一闭馆）</b>"}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| type | - | `poi`（缺省时页面也按 poi 处理） |
| lnglat | ✅ | `[经度, 纬度]`，注意经度在前 |
| sort | 建议 | **必须是 23 类标准类目名**（决定图钉图标与颜色，见下表）；写自定义词=落回默认📌 |
| text | ✅ | 名称（弹窗标题） |
| remark | 建议 | 描述文字，**支持 HTML**：`<br>` 换行、`<b>` 加粗、`<img src='https://...' width='210'>` 贴图（推荐用高德图床 URL，即 detail 接口返回的 photo 字段；http 开头必须改 https） |

### route 项

```json
{"type": "route", "routeType": "transfer", "city": "北京",
 "start": [116.397029, 39.917839], "end": [116.275179, 39.999617],
 "remark": "第①程：步行约800米至神武门站→101/103路3站至西四路口东→地铁4号线13站至北宫门站，全程约92分钟"}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| routeType | ✅ | `driving` / `walking` / `riding` / `transfer`（决定线型语义，见下表） |
| start / end | ✅ | 双格式：`[lng,lat]` 坐标 **或** `{"keyword":"地名","city":"城市"}` 关键字对象（页面自动地理编码，可省查坐标步骤） |
| city | transfer 必带 | 公交规划城市。**缺省时页面默认"北京"，跨城使用必须显式传！** |
| remark | 建议 | 方案文字（点路线弹窗会展示）；弹窗同时显示规划服务**实算**的距离/耗时（非 remark 里的数字），driving 加显过路费、transfer 加显票价 |
| policy | 可选 | 驾车/骑行策略（demo 页默认 0） |
| nightflag | 可选 | 公交夜班车（true/false） |
| waypoints | 可选 | 驾车途经点数组（≤16 个 `[lng,lat]`），一线串多点做顺路游 |

## 线条样式系统（routeType → 视觉，自动套用无需配置）

| routeType | 样式 | 颜色 | 视觉语义 |
|---|---|---|---|
| `driving` | 绿色实线 + **白色方向箭头流**（showDir），weight 6 | #22c55e | 驾车/打车 |
| `walking` | 蓝色虚线 dasharray[12,8]，weight 5 | #3b82f6 | 步行 |
| `riding` | 橙色虚线，weight 5 | #f97316 | 骑行 |
| `transfer` | 乘车段浅蓝实线(上层) + 步行接驳短虚线[10,5](下层) | #38bdf8 | 地铁/公交 |

多式混合行程按段拆多条 route（地铁段 transfer + 打车段 driving），线型自动区分语义。所有线双层描边 + 圆角转折，导航级质感。

## POI 分类图钉字典（sort 必须写标准类目名，23 类）

| 类目 | 图钉 | 类目 | 图钉 |
|---|---|---|---|
| 餐饮服务 | 🍑汉堡 🟢绿 | 购物服务 | 🛍️ 青绿 |
| 生活服务 | 💇 青 | 体育休闲服务 | ⚽ 青 |
| 医疗保健服务 | 🏥 天蓝 | 住宿服务 | 🛏️ 蓝 |
| 风景名胜 | ⛲ 靛蓝 | 商务住宅 | 🏢 紫 |
| 科教文化服务 | 🏫 品红 | 交通设施服务 | 🚌 粉 |
| 金融保险服务 | 💵 玫红 | 公司企业 | 💼 灰 |
| 政府机构及社会团体 | 🏛️ 亮紫 | 汽车服务 | 🚗 红 |
| 汽车销售 | 🚘 橙 | 汽车维修 | 🔧 黄 |
| 摩托车服务 | 🏍️ 黄绿 | 道路附属设施 | 🛣️ 灰 |
| 地名地址信息 | 📍 灰 | 公共设施 | 🚾 暖灰 |
| 事件活动 | 🎪 红 | 室内设施 | 🚪 橙 |
| 通行设施 | 🚧 暗黄 | （未命中） | 📌 靛蓝默认 |

⚠️ sort 写"5A景区·第1站"这类自定义词匹配不到字典=全落默认📌。想突出等级/编号，写进 remark。

🎁 **自动化技巧**：这 23 类 = 高德官方 POI 分类大类，与 `maps_search_detail` 返回的 `type` 字段（格式"大类;中类;小类"如"餐饮服务;中餐厅;中餐厅"）**第一段完全对齐**——批量生成时 `sort = type.split(';')[0]` 即可全自动命中彩色图钉，无需人工挑类目。

## 📌 打点配图策略（官方图默认带 · 无图默认净 · 扩展须用户明示）

**默认规则（无需询问用户）**：

1. 每个地点的打点**默认尝试带图**，但图片来源**仅限高德官方 POI 自带图**——`maps_search_detail` 返回的 `photo` 字段（高德官方图床，公开可访问、无防盗链、稳定）
2. **官方有图 → 按下方「三步嵌入」上图片**
3. **官方无图（`photo` 为空）→ 默认不带图**，弹窗保持纯文字净版（图钉图标、名称、彩色分类标签、描述文字俱全，完整可用；部分 POI 无图属正常现象，勿视为故障，也**不要擅自自行找图补上**）

**⚠️ 仅当用户明确要求"打点必须要带图"时**，才走扩展流程，且**必须先询问用户选择获取途径、征得同意后再执行**（或者用户已经直接提供了相关配图的URL等来源信息，那也可以直接使用）。获取图片的扩展方式可选包括：

- 方式A：使用 **当前Agent 自带的图片生成能力**，按该地点的类型与特征绘制一张示意图；
- 方式B：进行**联网搜索**，尝试获取该地点的公开网图（遵守在线信息获取安全过滤规则：疑似山寨/仿冒/境外不可靠图源一律不采，仅取可靠公开渠道图片）。

用户选定方式的图片落地为**公网可访问 URL** 后，同样按「三步嵌入」写入 remark。

⚠️ **协议匹配法则：外部来源图片允许 https**——图片是 **https 直链 → 最终页面链接必须保持 https**（默认即是）；仅当图片是 **http-only 图床**时，才把页面链接改为 http（见坑#2）。图片插入前必须实测该 URL 匿名 HTTP 200 且 Content-Type 为图片类型，否则回退净版。

### 官方图三步嵌入

**不需要自己找图**——高德自家接口就带：

1. **取图**：`maps_search_detail`（传 POI id，id 从 `maps_text_search` 拿）→ 响应中的 **`photo` 字段**即高德官方图床 URL（域名 `store.is.autonavi.com` / `aos-comment.amap.com` 等，公开可访问、无防盗链、长期稳定）
2. **协议匹配规则（2026-10-04 实测修正，关键）**：页面 URL 协议决定图片能否显示——
   - **https 页面**下，http 图片会被浏览器自动升级/拦截：图床**支持 https** 才能显示（高德图床实测双协议皆可，改 https 零成本）
   - **http 页面**（`http://a.amap.com/...`，实测服务器双协议直接服役、**不强制跳转 https**）下无混合内容拦截：**任意图床的 http 图片都能正常显示**——贴 http-only 图床的图时，把页面链接写成 http 开头即可
   - 权衡：http 页面浏览器地址栏会标"不安全"（不影响功能与渲染），按需选用
3. **嵌入**：写进该 POI 的 remark——

```json
{"type": "poi", "lnglat": [116.397029, 39.917839], "sort": "科教文化服务", "text": "故宫博物院",
 "remark": "【5A景区·世界遗产】评分4.9<br><b>旺季 08:30-17:00（周一闭馆）</b><br><img src='https://store.is.autonavi.com/showpic/2f968490d105bb2741e17f90b85c6b79' width='210'>"}
```

三个要点：
- HTML 属性用**单引号**（remark 整体在 JSON 双引号字符串里，避免转义地狱）
- **`width='210'` 限宽**（弹窗内容区约 208px，不限宽大图会撑破窗体）
- 一个 remark 可贴**多张图**（多个 img 标签串排），图片URL失效时仅破图、文字照常（优雅降级）

## 完整示例（examples/ 目录五件套，均为实测数据，覆盖全部玩法谱系）

| 示例文件 | 演示玩法 |
|---|---|
| `lunch_circle_poi_only.json` | **基础打点**：纯 POI，标准类目彩色图钉 + HTML 富文本（换行/加粗），POI-only 自动 setFitView |
| `beijing_day_trip.json` | **多段换乘**：3 景点 + 2 段 transfer(city) 公交/地铁方案，分段浅蓝实线+步行虚线，弹窗带实算距离耗时 |
| `beijing_richtext_multimodal.json` | **完全体·富文本混合交通**：三种不同类目图钉（🏫⛲🛍️）+ remark 贴高德图床实拍图 + 公交 transfer 与打车 driving 混合（绿箭头线与浅蓝线同图分层） |
| `route_styles_four_types.json` | **四线型环线全家福**：一条链接里 driving/walking/riding/transfer 四种线型同图 + **keyword 起终点格式**（免查坐标）示范，闭合环线游 |
| `waypoints_scenic_drive.json` | **驾车顺路游**：单条 driving + waypoints 数组一线串 3 点（出发地→天坛→前门→故宫），点折线弹窗看总里程 |

生成命令示例：

```bash
python "<base_dir>/scripts/build_link.py" "<base_dir>/examples/beijing_day_trip.json"
```

选用指引：只想发几个地点→示例1；行程单带换乘→示例2；要好看要贴图→示例3；想展示全部线型或用 keyword 省事→示例4；多点顺路一线绘→示例5。

## 红线与坑

1. **transfer 缺 city = 默认"北京"**（demo 页 421 行）——跨城必须显式带
2. **图片协议默认须与页面协议一致**：混合内容是唯一裁决项，与图床是谁无关——**https 图片（含任意外部图床的 https 直链）→ 页面链接保持 https**；**http-only 图片 → 浏览器在 https 页面会自动升级/拦截，须把页面链接改用 `http://a.amap.com/jsapi_demo_show/...`**（实测服务器双协议直接服役、无强制跳转）。高德自家图床双协议皆可、怎么写都显示。
3. **高德接口串行调用**：并发撞 QPS 限流（`CUQPS_HAS_EXCEEDED_THE_LIMIT`），个人开发者并发配额=1
4. **sort 必须用标准类目名**：自定义词=放弃彩色图钉
5. **无 data 参数时**高德页面会默认展示内置北京演示数据（故宫/三里屯/北大→清华），勿误认为自己的数据渲染失败
6. **链接长度**：建议控制在十 KB 内；超长行程可拆多条链接
7. **区分"页面实算"与"remark 文字"**：弹窗里的距离/耗时/费用来自规划服务实算，remark 只是方案说明文字，两者可互补勿混淆
8. **两处固定文案 data 不可自定义**：标签页标题「兴趣点与路线规划展示」与面板标题「地理数据展示面板」是页面写死的，本技能只负责生成链接，不涉及页面定制

## 相关官方页面形态（按需选用）

- 关键词搜索入口：`https://www.amap.com/search?query={关键词}`
- 带坐标周边搜索入口：`https://ditu.amap.com/search?query={类别}&query_type=RQBXY&longitude={lng}&latitude={lat}&range={米}`
- 热力图展示：`https://a.amap.com/jsapi_demo_show/static/openclaw/heatmap.html?mapStyle=grey|light&dataUrl={公网JSON的URL编码}`——dataUrl 需要**数据先放到公网可访问地址**，与内嵌模式不同
- 高德网页版 URI API（uri.amap.com/navigation 等）：会 302 进需登录的高德网页版，"发链接直接看"场景**不推荐**，因此本skill最终采取的是使用高德官方的该静态页面方式。
