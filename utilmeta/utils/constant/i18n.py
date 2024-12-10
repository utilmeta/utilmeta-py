from utilmeta.utils.datastructure import Static
from typing import Union, List


class Language(Static):
    af = "af"
    ar = "ar"
    az = "az"
    be = "be"
    bg = "bg"
    bs = "bs"
    ca = "ca"
    cs = "cs"
    cy = "cy"
    da = "da"
    de = "de"
    dv = "dv"
    el = "el"
    en = "en"
    eo = "eo"
    es = "es"
    et = "et"
    eu = "eu"
    fa = "fa"
    fi = "fi"
    fo = "fo"
    fr = "fr"
    gl = "gl"
    gu = "gu"
    he = "he"
    hi = "hi"
    hr = "hr"
    hu = "hu"
    hy = "hy"
    id = "id"
    it = "it"
    ja = "ja"
    ka = "ka"
    kk = "kk"
    kn = "kn"
    ko = "ko"
    ky = "ky"
    lt = "lt"
    lv = "lv"
    mi = "mi"
    mk = "mk"
    mn = "mn"
    mr = "mr"
    ms = "ms"
    mt = "mt"
    nb = "nb"
    nl = "nl"
    nn = "nn"
    ns = "ns"
    pa = "pa"
    pl = "pl"
    pt = "pt"
    qu = "qu"
    ro = "ro"
    ru = "ru"
    sa = "sa"
    se = "se"
    sk = "sk"
    sl = "sl"
    sq = "sq"
    sr = "sr"
    sv = "sv"
    sw = "sw"
    ta = "ta"
    te = "te"
    th = "th"
    tl = "tl"
    tn = "tn"
    tr = "tr"
    ts = "ts"
    tt = "tt"
    uk = "uk"
    ur = "ur"
    uz = "uz"
    vi = "vi"
    xh = "xh"
    zh = "zh"
    zu = "zu"


class Locale(Static):
    ZA = "ZA"
    AE = "AE"
    BH = "BH"
    DZ = "DZ"
    EG = "EG"
    IQ = "IQ"
    JO = "JO"
    KW = "KW"
    LB = "LB"
    LY = "LY"
    MA = "MA"
    OM = "OM"
    QA = "QA"
    SA = "SA"
    SY = "SY"
    TN = "TN"
    YE = "YE"
    AZ = "AZ"
    BY = "BY"
    BG = "BG"
    BA = "BA"
    ES = "ES"
    CZ = "CZ"
    GB = "GB"
    DK = "DK"
    AT = "AT"
    CH = "CH"
    DE = "DE"
    LI = "LI"
    LU = "LU"
    MV = "MV"
    GR = "GR"
    AU = "AU"
    BZ = "BZ"
    CA = "CA"
    CB = "CB"
    IE = "IE"
    JM = "JM"
    NZ = "NZ"
    PH = "PH"
    TT = "TT"
    US = "US"
    ZW = "ZW"
    AR = "AR"
    BO = "BO"
    CL = "CL"
    CO = "CO"
    CR = "CR"
    DO = "DO"
    EC = "EC"
    GT = "GT"
    HN = "HN"
    MX = "MX"
    NI = "NI"
    PA = "PA"
    PE = "PE"
    PR = "PR"
    PY = "PY"
    SV = "SV"
    UY = "UY"
    VE = "VE"
    EE = "EE"
    IR = "IR"
    FI = "FI"
    FO = "FO"
    BE = "BE"
    FR = "FR"
    MC = "MC"
    IN = "IN"
    IL = "IL"
    HR = "HR"
    HU = "HU"
    AM = "AM"
    ID = "ID"
    IS = "IS"
    IT = "IT"
    JP = "JP"
    GE = "GE"
    KZ = "KZ"
    KR = "KR"
    KG = "KG"
    LT = "LT"
    LV = "LV"
    MK = "MK"
    MN = "MN"
    BN = "BN"
    MY = "MY"
    MT = "MT"
    NO = "NO"
    NL = "NL"
    PL = "PL"
    BR = "BR"
    PT = "PT"
    RO = "RO"
    RU = "RU"
    SE = "SE"
    SK = "SK"
    SI = "SI"
    AL = "AL"
    SP = "SP"
    KE = "KE"
    TH = "TH"
    TR = "TR"
    UA = "UA"
    PK = "PK"
    UZ = "UZ"
    VN = "VN"
    CN = "CN"
    HK = "HK"  # HongKong (China)
    MO = "MO"
    SG = "SG"
    TW = "TW"  # Taiwan (China)

    @classmethod
    def language(cls, locale: str, single: bool = True) -> Union[List[str], str]:
        result = []
        for key, values in LANGUAGE_LOCALE_MAP.items():
            if locale in values:
                if single:
                    return key
                result.append(key)
        return result


class TimeZone(Static, ignore_duplicate=True):
    UTC = "UTC"
    GMT = "UTC"
    WET = "WET"
    CET = "CET"
    MET = "CET"
    ECT = "CET"
    EET = "EET"
    MIT = "Pacific/Apia"
    HST = "Pacific/Honolulu"
    AST = "America/Anchorage"
    PST = "America/Los_Angeles"
    LOS_ANGELES = "America/Los_Angeles"
    MST = "America/Denver"
    PNT = "America/Phoenix"
    CST = "America/Chicago"
    CHICAGO = "America/Chicago"
    EST = "America/New_York"
    NEW_YORK = "America/New_York"
    IET = "America/Indiana/Indianapolis"
    PRT = "America/Puerto_Rico"
    CNT = "America/St_Johns"
    AGT = "America/Argentina/Buenos_Aires"
    BET = "America/Sao_Paulo"
    ART = "Africa/Cairo"
    CAT = "Africa/Harare"
    EAT = "Africa/Addis_Ababa"
    NET = "Asia/Yerevan"
    PLT = "Asia/Karachi"
    IST = "Asia/Kolkata"
    BST = "Asia/Dhaka"
    VST = "Asia/Ho_Chi_Minh"
    CTT = "Asia/Shanghai"
    SHANGHAI = "Asia/Shanghai"
    JST = "Asia/Tokyo"
    TOKYO = "Asia/Tokyo"
    ACT = "Australia/Darwin"
    DARWIN = "Australia/Darwin"
    AET = "Australia/Sydney"
    SYDNEY = "Australia/Sydney"
    SST = "Pacific/Guadalcanal"
    NST = "Pacific/Auckland"


LANGUAGE_LOCALE_MAP = {
    "af": ["ZA"],
    "ar": [
        "AE",
        "BH",
        "DZ",
        "EG",
        "IQ",
        "JO",
        "KW",
        "LB",
        "LY",
        "MA",
        "OM",
        "QA",
        "SA",
        "SY",
        "TN",
        "YE",
    ],
    "az": ["AZ", "AZ"],
    "be": ["BY"],
    "bg": ["BG"],
    "bs": ["BA"],
    "ca": ["ES"],
    "cs": ["CZ"],
    "cy": ["GB"],
    "da": ["DK"],
    "de": ["AT", "CH", "DE", "LI", "LU"],
    "dv": ["MV"],
    "el": ["GR"],
    "en": [
        "AU",
        "BZ",
        "CA",
        "CB",
        "GB",
        "IE",
        "JM",
        "NZ",
        "PH",
        "TT",
        "US",
        "ZA",
        "ZW",
    ],
    "es": [
        "AR",
        "BO",
        "CL",
        "CO",
        "CR",
        "DO",
        "EC",
        "ES",
        "ES",
        "GT",
        "HN",
        "MX",
        "NI",
        "PA",
        "PE",
        "PR",
        "PY",
        "SV",
        "UY",
        "VE",
    ],
    "et": ["EE"],
    "eu": ["ES"],
    "fa": ["IR"],
    "fi": ["FI"],
    "fo": ["FO"],
    "fr": ["BE", "CA", "CH", "FR", "LU", "MC"],
    "gl": ["ES"],
    "gu": ["IN"],
    "he": ["IL"],
    "hi": ["IN"],
    "hr": ["BA", "HR"],
    "hu": ["HU"],
    "hy": ["AM"],
    "id": ["ID"],
    "is": ["IS"],
    "it": ["CH", "IT"],
    "ja": ["JP"],
    "ka": ["GE"],
    "kk": ["KZ"],
    "kn": ["IN"],
    "ko": ["KR"],
    "ky": ["KG"],
    "lt": ["LT"],
    "lv": ["LV"],
    "mi": ["NZ"],
    "mk": ["MK"],
    "mn": ["MN"],
    "mr": ["IN"],
    "ms": ["BN", "MY"],
    "mt": ["MT"],
    "nb": ["NO"],
    "nl": ["BE", "NL"],
    "nn": ["NO"],
    "ns": ["ZA"],
    "pa": ["IN"],
    "pl": ["PL"],
    "pt": ["BR", "PT"],
    "qu": ["BO", "EC", "PE"],
    "ro": ["RO"],
    "ru": ["RU"],
    "sa": ["IN"],
    "se": ["FI", "NO", "SE"],
    "sk": ["SK"],
    "sl": ["SI"],
    "sq": ["AL"],
    "sr": ["BA", "SP"],
    "sv": ["FI", "SE"],
    "sw": ["KE"],
    "ta": ["IN"],
    "te": ["IN"],
    "th": ["TH"],
    "tl": ["PH"],
    "tn": ["ZA"],
    "tr": ["TR"],
    "tt": ["RU"],
    "uk": ["UA"],
    "ur": ["PK"],
    "uz": ["UZ", "UZ"],
    "vi": ["VN"],
    "xh": ["ZA"],
    "zh": ["CN", "HK", "MO", "SG", "TW"],
    "zu": ["ZA"],
}

LANGUAGES = Language.gen()
LOCALES = Locale.gen()
