# -*- coding: utf-8 -*-
"""
高德静态地图链接生成器（amap-map-link skill 核心工具）

用法:
    python build_link.py <data.json> [--no-check] [--out link.txt] [--http]

data.json 内容 = travel_plan.html 的 data 数组（POI/route 混排），如:
    [
      {"type":"poi","lnglat":[116.397029,39.917839],"sort":"风景名胜","text":"故宫博物院","remark":"..."},
      {"type":"route","routeType":"transfer","city":"北京","start":[...],"end":[...],"remark":"..."}
    ]

流程: JSON -> UTF-8 -> encodeURIComponent 等价编码 -> 拼演示页 -> GET 三查
三查: HTTP 200 / 页面标题含「兴趣点与路线规划展示」/ 正文无登录墙字样
三查不过 = 链接不可交付（服务端 200 不等于用户能打开）
"""
__version__ = "1.1.0"

import io
import json
import sys
from urllib.parse import quote

# Windows cmd 控制台中文保护
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_URL_HTTPS = "https://a.amap.com/jsapi_demo_show/static/openclaw/travel_plan.html?data="
BASE_URL_HTTP = "http://a.amap.com/jsapi_demo_show/static/openclaw/travel_plan.html?data="
EXPECTED_TITLE = "兴趣点与路线规划展示"
LOGIN_WALL_KEYWORDS = ("login", "登录", "passport")


def build_link(data, scheme="https"):
    """data: list[dict] -> 完整链接字符串；scheme: https(默认,安全) / http(贴http-only图床时用)"""
    if not isinstance(data, list):
        data = [data]  # 单对象自动转数组（与 demo 页容错逻辑一致）
    base = BASE_URL_HTTP if scheme == "http" else BASE_URL_HTTPS
    return base + quote(json.dumps(data, ensure_ascii=False, separators=(",", ":")), safe="")


def content_check(link):
    """交付前三查: 返回 (ok, 说明文本)。仅用标准库 urllib，零第三方依赖。"""
    import gzip
    import urllib.request
    import zlib
    req = urllib.request.Request(link, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Encoding": "gzip, deflate",  # 不请求 br（标准库无 brotli）
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        status = r.status
        final_url = r.geturl()
        data = r.read()
        enc = (r.headers.get("Content-Encoding") or "").lower()
    # urllib 不自动解压，须手动处理（requests 会自动解压，迁移时易漏）
    if "gzip" in enc:
        data = gzip.decompress(data)
    elif "deflate" in enc:
        try:
            data = zlib.decompress(data)
        except zlib.error:
            data = zlib.decompress(data, -zlib.MAX_WBITS)  # raw deflate 兜底
    text = data.decode("utf-8", errors="replace")
    status_ok = status == 200
    landed_ok = final_url.startswith(("https://a.amap.com/", "http://a.amap.com/"))
    title_ok = EXPECTED_TITLE in text
    no_login = not any(k in text for k in LOGIN_WALL_KEYWORDS)
    detail = f"HTTP={status} 落点正确={landed_ok} 标题匹配={title_ok} 无登录墙={no_login}"
    ok = status_ok and landed_ok and title_ok and no_login
    return ok, detail


def main():
    args = sys.argv[1:]
    if not args or args[0].startswith("--"):
        print("用法: python build_link.py <data.json> [--no-check] [--out link.txt] [--http]")
        print("  --http  页面链接用 http 协议（贴 http-only 图床的图片时用；默认 https）")
        sys.exit(1)

    json_path = args[0]
    out_path = None
    if "--out" in args:
        idx = args.index("--out")
        if idx + 1 >= len(args):
            print("错误: --out 后面缺文件名")
            sys.exit(1)
        out_path = args[idx + 1]

    try:
        with open(json_path, encoding="utf-8-sig") as f:  # utf-8-sig 兼容记事本 BOM
            data = json.load(f)
    except FileNotFoundError:
        print(f"错误: 找不到文件 {json_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"错误: {json_path} 不是合法 JSON（line {e.lineno} col {e.colno}: {e.msg}）")
        sys.exit(1)
    except UnicodeDecodeError:
        print(f"错误: {json_path} 不是 UTF-8 编码（记事本请「另存为」并选择 UTF-8 后重试）")
        sys.exit(1)

    if not isinstance(data, list):
        data = [data]  # 单对象自动转数组（与 demo 页容错逻辑一致）
    if not data or not all(isinstance(d, dict) for d in data):
        print("错误: data 须为非空数组，且每个元素都是对象（poi/route）")
        sys.exit(1)

    do_check = "--no-check" not in args
    scheme = "http" if "--http" in args else "https"

    # 契约：缺省 type 按 poi 处理（与 SKILL.md 及 demo 页容错逻辑一致）
    n_poi = sum(1 for d in data if (d.get("type") or "poi") == "poi")
    n_route = sum(1 for d in data if d.get("type") == "route")
    link = build_link(data, scheme=scheme)
    print(f"[build] 协议={scheme} 数据: {len(data)} 项 (poi={n_poi}, route={n_route})，链接长度 {len(link)} 字符")

    # 结构预检：transfer 必带 city / routeType 白名单 / poi 坐标格式
    problems = []
    known_types = {"driving", "walking", "riding", "transfer"}
    for i, d in enumerate(data):
        dtype = d.get("type") or "poi"  # 契约：缺省按 poi 处理
        if dtype == "route":
            if d.get("routeType") not in known_types:
                problems.append(f"第{i}项 routeType 非法: {d.get('routeType')}")
            if d.get("routeType") == "transfer" and not d.get("city"):
                problems.append(f"第{i}项 transfer 缺 city（缺省将默认'北京'！）")
            if not d.get("start") or not d.get("end"):
                problems.append(f"第{i}项 route 缺 start/end")
        elif dtype == "poi":
            ll = d.get("lnglat")
            if not isinstance(ll, (list, tuple)) or len(ll) != 2:
                problems.append(f"第{i}项 poi 缺 lnglat 或格式非 [经,纬]")
        else:
            problems.append(f"第{i}项 type 非法: {d.get('type')}（应为 poi/route）")
    if problems:
        print("[warn] 结构预检发现问题:")
        for p in problems:
            print("  - " + p)

    check_ok = None  # None=未验证(--no-check) / True=三查过 / False=三查未过或验证异常
    if do_check:
        try:
            ok, detail = content_check(link)
            check_ok = ok
            print(f"[check] {'PASS' if ok else 'FAIL'}: {detail}")
            if not ok:
                print("[check] 三查未全过，链接暂不可交付（请排查后再试）")
        except Exception as e:
            check_ok = False
            print(f"[check] 网络验证失败: {type(e).__name__}: {e}（确要强制导出可加 --no-check）")

    print("\n" + link + "\n")
    if out_path:
        if check_ok is False:
            print(f"[out] 三查未通过/未完成，按「三查不过不得交付」拦截，未写入 {out_path}"
                  f"（确要强制导出请加 --no-check）")
        else:
            try:
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(link)
                print(f"[out] 链接已另存: {out_path}")
            except OSError as e:
                print(f"[out] 写盘失败: {e.strerror or e}（检查目录是否存在/有写权限）")


if __name__ == "__main__":
    main()
