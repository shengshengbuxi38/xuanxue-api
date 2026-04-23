"""八字排盘核心模块 - 薄封装 lunar_python"""

from lunar_python import Solar


# 常用城市经度 (东经)
CITY_LONGITUDE = {
    "北京": 116.4, "上海": 121.5, "广州": 113.3, "深圳": 114.1,
    "成都": 104.1, "重庆": 106.5, "武汉": 114.3, "杭州": 120.2,
    "南京": 118.8, "天津": 117.2, "西安": 108.9, "长沙": 113.0,
    "郑州": 113.7, "济南": 117.0, "沈阳": 123.4, "哈尔滨": 126.6,
    "长春": 125.3, "大连": 121.6, "青岛": 120.4, "苏州": 120.6,
    "厦门": 118.1, "福州": 119.3, "昆明": 102.7, "贵阳": 106.7,
    "南宁": 108.3, "海口": 110.3, "石家庄": 114.5, "太原": 112.5,
    "合肥": 117.3, "南昌": 115.9, "兰州": 103.8, "银川": 106.3,
    "西宁": 101.8, "呼和浩特": 111.7, "乌鲁木齐": 87.6, "拉萨": 91.1,
}

# 均时差表 (每月第15天的近似值，单位：分钟)
# 正值表示真太阳时比平太阳时快，负值表示慢
EQUATION_OF_TIME = {
    1: -9, 2: -14, 3: -8, 4: 0, 5: 4, 6: 2,
    7: -4, 8: -6, 9: 0, 10: 10, 11: 16, 12: 11,
}


def calc_true_solar_time(year, month, day, hour, minute, longitude):
    """
    计算真太阳时

    Args:
        year, month, day, hour, minute: 公历时间
        longitude: 所在地经度 (东经为正)

    Returns:
        (校正后的小时, 校正后的分钟)
    """
    # 经度差校正: 以北京时间 120°E 为基准
    # 每1度经度差 = 4分钟时间差
    longitude_correction = (longitude - 120) * 4  # 分钟

    # 均时差校正
    eot = EQUATION_OF_TIME.get(month, 0)

    # 总校正量
    total_correction = longitude_correction + eot

    # 转换为小时和分钟
    total_minutes = hour * 60 + minute + total_correction

    # 处理跨日
    while total_minutes < 0:
        total_minutes += 24 * 60
    while total_minutes >= 24 * 60:
        total_minutes -= 24 * 60

    return int(total_minutes // 60), int(total_minutes % 60)


def get_bazi(year, month, day, hour, minute, gender=1, longitude=None):
    """
    获取完整八字排盘

    Args:
        year, month, day, hour, minute: 公历时间
        gender: 1=男, 0=女
        longitude: 所在地经度 (可选, 自动计算真太阳时)

    Returns:
        dict: 完整八字命盘数据
    """
    # 真太阳时校正
    true_hour, true_minute = hour, minute
    longitude_used = longitude
    if longitude is not None:
        true_hour, true_minute = calc_true_solar_time(year, month, day, hour, minute, longitude)

    solar = Solar.fromYmdHms(year, month, day, true_hour, true_minute, 0)
    lunar = solar.getLunar()
    eight_char = lunar.getEightChar()

    # 四柱
    pillars = {
        "year": eight_char.getYear(),
        "month": eight_char.getMonth(),
        "day": eight_char.getDay(),
        "time": eight_char.getTime(),
    }

    # 天干地支
    gan_zhi = {
        "year_gan": eight_char.getYearGan(),
        "year_zhi": eight_char.getYearZhi(),
        "month_gan": eight_char.getMonthGan(),
        "month_zhi": eight_char.getMonthZhi(),
        "day_gan": eight_char.getDayGan(),
        "day_zhi": eight_char.getDayZhi(),
        "time_gan": eight_char.getTimeGan(),
        "time_zhi": eight_char.getTimeZhi(),
    }

    # 十神
    shi_shen = {
        "year": eight_char.getYearShiShenGan(),
        "month": eight_char.getMonthShiShenGan(),
        "day": eight_char.getDayShiShenGan(),
        "time": eight_char.getTimeShiShenGan(),
    }

    # 藏干
    hide_gan = {
        "year": eight_char.getYearHideGan(),
        "month": eight_char.getMonthHideGan(),
        "day": eight_char.getDayHideGan(),
        "time": eight_char.getTimeHideGan(),
    }

    # 纳音
    na_yin = {
        "year": eight_char.getYearNaYin(),
        "month": eight_char.getMonthNaYin(),
        "day": eight_char.getDayNaYin(),
        "time": eight_char.getTimeNaYin(),
    }

    # 五行
    wu_xing = {
        "year": eight_char.getYearWuXing(),
        "month": eight_char.getMonthWuXing(),
        "day": eight_char.getDayWuXing(),
        "time": eight_char.getTimeWuXing(),
    }

    # 大运
    yun = eight_char.getYun(gender)
    da_yun_list = []
    for dy in yun.getDaYun():
        gan_zhi_str = dy.getGanZhi()
        liu_nian_list = []
        for ln in dy.getLiuNian():
            liu_nian_list.append({
                "year": ln.getYear(),
                "gan_zhi": ln.getGanZhi(),
                "age": ln.getAge(),
            })
        da_yun_list.append({
            "start_year": dy.getStartYear(),
            "end_year": dy.getEndYear(),
            "gan_zhi": gan_zhi_str,
            "liu_nian": liu_nian_list,
        })

    return {
        "solar_time": f"{year}年{month}月{day}日 {hour:02d}:{minute:02d}",
        "true_solar_time": f"{year}年{month}月{day}日 {true_hour:02d}:{true_minute:02d}",
        "longitude": longitude_used,
        "lunar_date": lunar.toString(),
        "gender": "男" if gender == 1 else "女",
        "pillars": pillars,
        "gan_zhi": gan_zhi,
        "shi_shen": shi_shen,
        "hide_gan": hide_gan,
        "na_yin": na_yin,
        "wu_xing": wu_xing,
        "dayun_start": {
            "year": yun.getStartYear(),
            "month": yun.getStartMonth(),
            "day": yun.getStartDay(),
        },
        "dayun_forward": yun.isForward(),
        "da_yun": da_yun_list,
        "raw_string": eight_char.toString(),
    }


def get_two_bazi_match(data1, data2):
    """
    双人八字合盘比较

    Args:
        data1: 第一个人的八字数据 (get_bazi 返回的 dict)
        data2: 第二个人的八字数据

    Returns:
        dict: 合盘比较结果
    """
    return {
        "person1": {
            "day_gan": data1["gan_zhi"]["day_gan"],
            "day_zhi": data1["gan_zhi"]["day_zhi"],
            "wu_xing": data1["wu_xing"],
            "na_yin": data1["na_yin"],
        },
        "person2": {
            "day_gan": data2["gan_zhi"]["day_gan"],
            "day_zhi": data2["gan_zhi"]["day_zhi"],
            "wu_xing": data2["wu_xing"],
            "na_yin": data2["na_yin"],
        },
        "raw1": data1["raw_string"],
        "raw2": data2["raw_string"],
    }


def bazi_to_text(bazi_data):
    """
    将八字数据格式化为AI可读的文本描述

    Args:
        bazi_data: get_bazi 返回的 dict

    Returns:
        str: 格式化的文本
    """
    lines = []
    lines.append(f"性别: {bazi_data['gender']}")
    lines.append(f"公历: {bazi_data['solar_time']}")
    lines.append(f"真太阳时: {bazi_data['true_solar_time']}")
    lines.append(f"农历: {bazi_data['lunar_date']}")
    lines.append("")
    lines.append("四柱八字:")
    lines.append(f"  年柱: {bazi_data['pillars']['year']} ({bazi_data['na_yin']['year']})")
    lines.append(f"  月柱: {bazi_data['pillars']['month']} ({bazi_data['na_yin']['month']})")
    lines.append(f"  日柱: {bazi_data['pillars']['day']} ({bazi_data['na_yin']['day']})")
    lines.append(f"  时柱: {bazi_data['pillars']['time']} ({bazi_data['na_yin']['time']})")
    lines.append("")
    lines.append("十神配置:")
    lines.append(f"  年柱: {bazi_data['shi_shen']['year']}")
    lines.append(f"  月柱: {bazi_data['shi_shen']['month']}")
    lines.append(f"  日柱: {bazi_data['shi_shen']['day']}")
    lines.append(f"  时柱: {bazi_data['shi_shen']['time']}")
    lines.append("")
    lines.append("五行分布:")
    for pillar in ["year", "month", "day", "time"]:
        lines.append(f"  {pillar}: {bazi_data['wu_xing'][pillar]}")
    lines.append("")
    lines.append("藏干:")
    for pillar in ["year", "month", "day", "time"]:
        lines.append(f"  {pillar}: {' '.join(bazi_data['hide_gan'][pillar])}")
    lines.append("")
    lines.append("大运:")
    for dy in bazi_data["da_yun"]:
        if dy["gan_zhi"]:
            lines.append(f"  {dy['start_year']}-{dy['end_year']}: {dy['gan_zhi']}")
    lines.append("")
    lines.append(f"起运: 出生后{bazi_data['dayun_start']['year']}年{bazi_data['dayun_start']['month']}月{bazi_data['dayun_start']['day']}日")
    lines.append(f"大运方向: {'顺排' if bazi_data['dayun_forward'] else '逆排'}")

    return "\n".join(lines)
