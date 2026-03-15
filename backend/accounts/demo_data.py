from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class ChinaLocationSeed:
    province: str
    city: str
    latitude: float
    longitude: float


CHINA_LOCATION_SEEDS = [
    ChinaLocationSeed('北京市', '北京市', 39.9042, 116.4074),
    ChinaLocationSeed('上海市', '上海市', 31.2304, 121.4737),
    ChinaLocationSeed('广东省', '广州市', 23.1291, 113.2644),
    ChinaLocationSeed('广东省', '深圳市', 22.5431, 114.0579),
    ChinaLocationSeed('浙江省', '杭州市', 30.2741, 120.1551),
    ChinaLocationSeed('江苏省', '南京市', 32.0603, 118.7969),
    ChinaLocationSeed('四川省', '成都市', 30.5728, 104.0668),
    ChinaLocationSeed('湖北省', '武汉市', 30.5928, 114.3055),
    ChinaLocationSeed('陕西省', '西安市', 34.3416, 108.9398),
    ChinaLocationSeed('山东省', '济南市', 36.6512, 117.1201),
    ChinaLocationSeed('福建省', '厦门市', 24.4798, 118.0894),
    ChinaLocationSeed('辽宁省', '沈阳市', 41.8057, 123.4315),
    ChinaLocationSeed('重庆市', '重庆市', 29.5630, 106.5516),
    ChinaLocationSeed('湖南省', '长沙市', 28.2282, 112.9388),
    ChinaLocationSeed('河南省', '郑州市', 34.7473, 113.6249),
]

CHINA_IP_PREFIXES = [
    36,
    39,
    42,
    47,
    58,
    59,
    60,
    61,
    101,
    106,
    110,
    111,
    112,
    113,
    114,
    115,
    116,
    117,
    118,
    119,
    120,
    121,
    122,
    123,
    124,
    125,
    139,
    171,
    175,
    180,
    182,
    183,
    202,
    210,
    211,
    218,
    219,
    220,
    221,
    222,
]

SURNAMES = [
    '张',
    '李',
    '王',
    '赵',
    '刘',
    '陈',
    '杨',
    '黄',
    '周',
    '吴',
    '徐',
    '孙',
    '胡',
    '朱',
    '高',
]

GIVEN_NAMES = [
    '伟',
    '芳',
    '娜',
    '敏',
    '静',
    '丽',
    '强',
    '磊',
    '军',
    '洋',
    '勇',
    '艳',
    '杰',
    '涛',
    '明',
    '超',
    '婷',
    '鑫',
]


def random_china_login_context() -> dict[str, object]:
    seed = random.choice(CHINA_LOCATION_SEEDS)
    return {
        'ip': generate_china_public_ip(),
        'country_name': 'China',
        'region': seed.province,
        'city': seed.city,
        'latitude': seed.latitude,
        'longitude': seed.longitude,
    }


def generate_china_public_ip() -> str:
    prefix = random.choice(CHINA_IP_PREFIXES)
    return '.'.join(
        [
            str(prefix),
            str(random.randint(1, 254)),
            str(random.randint(1, 254)),
            str(random.randint(1, 254)),
        ]
    )


def random_cn_name() -> tuple[str, str]:
    surname = random.choice(SURNAMES)
    given_name = random.choice(GIVEN_NAMES) + random.choice(GIVEN_NAMES)
    return surname, given_name
