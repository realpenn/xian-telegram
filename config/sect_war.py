"""宗门战 / 据点配置（v2 M4）。"""

# 据点战开放窗口：每周六 20:00–21:00（上海时区，固定 UTC+8，无夏令时）。
WAR_TZ_OFFSET_SECONDS = 8 * 3600
WAR_WEEKDAY = 5          # Monday=0 … Saturday=5
WAR_START_HOUR = 20
WAR_END_HOUR = 21        # 左闭右开：[20:00, 21:00)

OUTPOSTS = {
    "cave": {"name": "洞府据点", "buff": {"seclusion_pct": 0.08}},
    "mine": {"name": "矿脉据点", "buff": {"drop_pct": 0.05}},
    "altar": {"name": "祭坛据点", "buff": {"stat_pct": 0.05}},
}
