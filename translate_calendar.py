from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.request
from pathlib import Path


# ============================================================
# 基本設定
# ============================================================

TARGET_TIMEZONE = "Asia/Taipei"

SOURCE_BASE_URL = (
    "https://github.com/othyn/go-calendar/"
    "releases/latest/download"
)

OUTPUT_DIR = Path("docs")
TERMS_FILE = Path("translations.json")


# GO Calendar 的分類檔案
# 左側：中文版輸出檔名
# 右側：GO Calendar 原始檔名
CALENDARS = {
    "all": "gocal.ics",
    "choose-your-path": "gocal__choose_your_path.ics",
    "community-day": "gocal__community_day.ics",
    "event": "gocal__event.ics",
    "go-battle-league": "gocal__go_battle_league.ics",
    "go-pass": "gocal__go_pass.ics",
    "max-mondays": "gocal__max_mondays.ics",
    "pokemon-go-fest": "gocal__pokemon_go_fest.ics",
    "spotlight-hour": "gocal__pokemon_spotlight_hour.ics",
    "raid-battles": "gocal__raid_battles.ics",
    "raid-day": "gocal__raid_day.ics",
    "raid-hour": "gocal__raid_hour.ics",
    "research": "gocal__research.ics",
    "season": "gocal__season.ics",
}


CALENDAR_NAMES = {
    "all": "Pokémon GO 全部活動",
    "choose-your-path": "Pokémon GO 選擇你的道路",
    "community-day": "Pokémon GO 社群日",
    "event": "Pokémon GO 一般活動",
    "go-battle-league": "Pokémon GO 對戰聯盟",
    "go-pass": "Pokémon GO GO Pass",
    "max-mondays": "Pokémon GO 極巨星期一",
    "pokemon-go-fest": "Pokémon GO Fest",
    "spotlight-hour": "Pokémon GO 聚焦時刻",
    "raid-battles": "Pokémon GO 團體戰",
    "raid-day": "Pokémon GO 團體戰日",
    "raid-hour": "Pokémon GO 團體戰約會",
    "research": "Pokémon GO 調查活動",
    "season": "Pokémon GO 賽季",
}


# ============================================================
# Asia/Taipei 時區定義
#
# 台灣目前全年 UTC+8，沒有日光節約時間。
# 加入 VTIMEZONE 可提高 Google、Apple、Outlook 相容性。
# ============================================================

TAIPEI_VTIMEZONE = [
    "BEGIN:VTIMEZONE",
    "TZID:Asia/Taipei",
    "X-LIC-LOCATION:Asia/Taipei",
    "BEGIN:STANDARD",
    "TZOFFSETFROM:+0800",
    "TZOFFSETTO:+0800",
    "TZNAME:CST",
    "DTSTART:19700101T000000",
    "END:STANDARD",
    "END:VTIMEZONE",
]


# ============================================================
# 下載與 iCal 行處理
# ============================================================

def download_calendar(url: str) -> str:
    """下載指定的英文 iCalendar 檔案。"""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "pokemon-go-calendar-zh-tw/3.0",
            "Accept": "text/calendar,text/plain,*/*",
        },
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()

    return data.decode("utf-8-sig")


def unfold_ical_lines(content: str) -> list[str]:
    """
    還原 iCalendar 折行。

    iCalendar 長行的下一行會以一個空白或 Tab 開頭，
    必須先接回上一行，才能正確翻譯與修改。
    """
    normalized = (
        content
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )

    source_lines = normalized.split("\n")
    unfolded: list[str] = []

    for line in source_lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)

    return unfolded


def fold_ical_line(
    line: str,
    limit: int = 73,
) -> list[str]:
    """
    將過長的 iCalendar 行重新折行。

    使用 UTF-8 位元組計算，避免中文字被切壞。
    """
    if len(line.encode("utf-8")) <= limit:
        return [line]

    result: list[str] = []
    current = ""
    is_first_line = True

    for character in line:
        prefix = "" if is_first_line else " "
        candidate = prefix + current + character

        if (
            current
            and len(candidate.encode("utf-8")) > limit
        ):
            result.append(prefix + current)
            current = character
            is_first_line = False
        else:
            current += character

    if current:
        prefix = "" if is_first_line else " "
        result.append(prefix + current)

    return result


# ============================================================
# 翻譯詞庫
# ============================================================

def load_translations() -> dict[str, str]:
    """讀取 translations.json。"""
    if not TERMS_FILE.exists():
        raise FileNotFoundError(
            f"找不到翻譯詞庫：{TERMS_FILE}"
        )

    with TERMS_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        translations = json.load(file)

    if not isinstance(translations, dict):
        raise ValueError(
            "translations.json 必須是 JSON 物件。"
        )

    # 長片語優先，避免短詞先取代。
    return dict(
        sorted(
            translations.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )
    )


def replace_term(
    text: str,
    english: str,
    chinese: str,
) -> str:
    """安全取代英文詞彙。"""
    if re.fullmatch(
        r"[A-Za-z0-9'’.\-♀♂:]+",
        english,
    ):
        pattern = (
            rf"(?<![A-Za-z0-9])"
            rf"{re.escape(english)}"
            rf"(?![A-Za-z0-9])"
        )

        return re.sub(
            pattern,
            chinese,
            text,
            flags=re.IGNORECASE,
        )

    return re.sub(
        re.escape(english),
        chinese,
        text,
        flags=re.IGNORECASE,
    )


def translate_text(
    text: str,
    translations: dict[str, str],
) -> str:
    """依固定詞庫翻譯文字。"""
    translated = text

    for english, chinese in translations.items():
        translated = replace_term(
            translated,
            english,
            chinese,
        )

    translated = re.sub(
        r" {2,}",
        " ",
        translated,
    )

    translated = re.sub(
        r" +([，。：；！？）])",
        r"\1",
        translated,
    )

    translated = re.sub(
        r"（ +",
        "（",
        translated,
    )

    return translated.strip()


def translate_property(
    line: str,
    property_name: str,
    translations: dict[str, str],
) -> str:
    """
    翻譯指定 iCalendar 欄位，
    並保留欄位參數。
    """
    upper_line = line.upper()

    if not (
        upper_line.startswith(
            f"{property_name}:"
        )
        or upper_line.startswith(
            f"{property_name};"
        )
    ):
        return line

    if ":" not in line:
        return line

    prefix, value = line.split(":", 1)

    translated_value = translate_text(
        value,
        translations,
    )

    return f"{prefix}:{translated_value}"


# ============================================================
# 時區修正
# ============================================================

def add_taipei_timezone_to_floating_time(
    line: str,
) -> str:
    """
    將沒有 TZID、沒有 Z 的浮動時間，
    明確指定為 Asia/Taipei。

    處理：
    - DTSTART
    - DTEND
    - RECURRENCE-ID
    - EXDATE
    - RDATE

    不處理：
    - 全天日期 VALUE=DATE
    - UTC 時間（結尾 Z）
    - 已有 TZID 的時間
    - DTSTAMP、CREATED、LAST-MODIFIED
    """
    if ":" not in line:
        return line

    property_part, value = line.split(":", 1)
    property_name = property_part.split(";", 1)[0].upper()

    timezone_properties = {
        "DTSTART",
        "DTEND",
        "RECURRENCE-ID",
        "EXDATE",
        "RDATE",
    }

    if property_name not in timezone_properties:
        return line

    upper_property_part = property_part.upper()
    upper_value = value.upper()

    # 全天活動不需要時區。
    if "VALUE=DATE" in upper_property_part:
        return line

    # 已有時區，不重複加入。
    if "TZID=" in upper_property_part:
        return line

    # UTC 時間保留 Z，讓 Google 自動依使用者時區換算。
    #
    # EXDATE 或 RDATE 可能包含多個逗號分隔值，
    # 只要所有值都是 Z 結尾，就視為 UTC。
    values = [
        item.strip()
        for item in upper_value.split(",")
        if item.strip()
    ]

    if values and all(
        item.endswith("Z")
        for item in values
    ):
        return line

    # 確認是日期時間，而不是其他格式。
    #
    # 支援：
    # 20260806T180000
    # 20260806T1800
    # 多筆逗號分隔日期時間
    datetime_pattern = re.compile(
        r"^\d{8}T\d{4}(?:\d{2})?$"
    )

    if not values:
        return line

    if not all(
        datetime_pattern.fullmatch(item)
        for item in values
    ):
        return line

    # 保留原有參數，再加入 TZID。
    return (
        f"{property_part};"
        f"TZID={TARGET_TIMEZONE}:"
        f"{value}"
    )


def replace_calendar_timezone(line: str) -> str:
    """將日曆預設時區設定成 Asia/Taipei。"""
    upper_line = line.upper()

    if upper_line.startswith("X-WR-TIMEZONE:"):
        return f"X-WR-TIMEZONE:{TARGET_TIMEZONE}"

    return line


# ============================================================
# 清除重複日曆名稱與既有 VTIMEZONE
# ============================================================

def remove_existing_vtimezone(
    lines: list[str],
) -> list[str]:
    """
    移除來源檔案既有 VTIMEZONE。

    後續會加入統一的 Asia/Taipei VTIMEZONE。
    """
    result: list[str] = []
    inside_vtimezone = False

    for line in lines:
        upper_line = line.upper()

        if upper_line == "BEGIN:VTIMEZONE":
            inside_vtimezone = True
            continue

        if upper_line == "END:VTIMEZONE":
            inside_vtimezone = False
            continue

        if not inside_vtimezone:
            result.append(line)

    return result


def remove_duplicate_calendar_metadata(
    lines: list[str],
) -> list[str]:
    """
    移除來源中重複的：
    - NAME
    - X-WR-CALNAME
    - X-WR-TIMEZONE

    後續由程式統一加入。
    """
    result: list[str] = []

    for line in lines:
        upper_line = line.upper()

        if upper_line.startswith("NAME:"):
            continue

        if upper_line.startswith("X-WR-CALNAME:"):
            continue

        if upper_line.startswith("X-WR-TIMEZONE:"):
            continue

        result.append(line)

    return result


# ============================================================
# 單一行事曆轉換
# ============================================================

def translate_calendar(
    content: str,
    calendar_key: str,
    translations: dict[str, str],
) -> str:
    """翻譯並修正單一分類行事曆。"""
    lines = unfold_ical_lines(content)
    lines = remove_existing_vtimezone(lines)
    lines = remove_duplicate_calendar_metadata(lines)

    calendar_name = CALENDAR_NAMES.get(
        calendar_key,
        "Pokémon GO 活動",
    )

    output_lines: list[str] = []
    inserted_calendar_metadata = False
    inserted_timezone_component = False

    for line in lines:
        upper_original_line = line.upper()

        # VERSION 後加入統一日曆名稱與預設時區。
        if (
            upper_original_line.startswith("VERSION:")
            and not inserted_calendar_metadata
        ):
            output_lines.extend(
                fold_ical_line(line)
            )

            output_lines.extend(
                fold_ical_line(
                    f"NAME:{calendar_name}"
                )
            )

            output_lines.extend(
                fold_ical_line(
                    f"X-WR-CALNAME:{calendar_name}"
                )
            )

            output_lines.extend(
                fold_ical_line(
                    f"X-WR-TIMEZONE:{TARGET_TIMEZONE}"
                )
            )

            inserted_calendar_metadata = True
            continue

        # 第一筆 VEVENT 前加入 VTIMEZONE。
        if (
            upper_original_line == "BEGIN:VEVENT"
            and not inserted_timezone_component
        ):
            for timezone_line in TAIPEI_VTIMEZONE:
                output_lines.extend(
                    fold_ical_line(timezone_line)
                )

            inserted_timezone_component = True

        # 修正 floating time。
        line = add_taipei_timezone_to_floating_time(
            line
        )

        # 若來源還有 X-WR-TIMEZONE，統一改掉。
        line = replace_calendar_timezone(line)

        # 翻譯標題。
        line = translate_property(
            line,
            "SUMMARY",
            translations,
        )

        # 翻譯地點。
        line = translate_property(
            line,
            "LOCATION",
            translations,
        )

        # 翻譯分類。
        line = translate_property(
            line,
            "CATEGORIES",
            translations,
        )

        # 翻譯提醒文字，避免通知仍出現英文。
        #
        # 注意：活動 DESCRIPTION 通常包含網址及完整英文說明，
        # 目前仍不做全文翻譯。
        if upper_original_line.startswith(
            "DESCRIPTION:"
        ):
            # 只會進行詞庫固定取代，
            # 網址通常不受影響。
            line = translate_property(
                line,
                "DESCRIPTION",
                translations,
            )

        output_lines.extend(
            fold_ical_line(line)
        )

    # 沒有 VEVENT 的日曆，也需要加入 VTIMEZONE。
    if not inserted_timezone_component:
        final_lines: list[str] = []

        for line in output_lines:
            if line.upper() == "END:VCALENDAR":
                for timezone_line in TAIPEI_VTIMEZONE:
                    final_lines.extend(
                        fold_ical_line(timezone_line)
                    )

            final_lines.append(line)

        output_lines = final_lines

    output = "\r\n".join(output_lines)

    if not output.endswith("\r\n"):
        output += "\r\n"

    return output


# ============================================================
# 檢查輸出
# ============================================================

def validate_calendar(
    content: str,
    calendar_key: str,
) -> None:
    """檢查輸出的基本結構與時區。"""
    required_markers = [
        "BEGIN:VCALENDAR",
        "END:VCALENDAR",
        "VERSION:2.0",
        "X-WR-TIMEZONE:Asia/Taipei",
        "BEGIN:VTIMEZONE",
        "TZID:Asia/Taipei",
        "END:VTIMEZONE",
    ]

    for marker in required_markers:
        if marker not in content:
            raise ValueError(
                f"{calendar_key} 缺少必要內容："
                f"{marker}"
            )

    # 有 VEVENT 時，檢查每筆結構是否成對。
    begin_events = content.count("BEGIN:VEVENT")
    end_events = content.count("END:VEVENT")

    if begin_events != end_events:
        raise ValueError(
            f"{calendar_key} 的 VEVENT 數量不一致："
            f"{begin_events} / {end_events}"
        )


# ============================================================
# 建立首頁
# ============================================================

def create_index_page() -> None:
    """建立中文版訂閱首頁。"""
    rows: list[str] = []

    for calendar_key in CALENDARS:
        calendar_name = CALENDAR_NAMES.get(
            calendar_key,
            calendar_key,
        )

        filename = f"{calendar_key}.ics"

        rows.append(
            f"""
            <li class="calendar-item">
                <div class="calendar-name">
                    {html.escape(calendar_name)}
                </div>

                <div class="calendar-link">
                    <a href="{html.escape(filename)}">
                        {html.escape(filename)}
                    </a>
                </div>
            </li>
            """
        )

    page = f"""<!doctype html>
<html lang="zh-Hant-TW">
<head>
    <meta charset="utf-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <title>Pokémon GO 繁體中文行事曆</title>

    <style>
        :root {{
            color-scheme: light dark;
        }}

        body {{
            max-width: 820px;
            margin: 40px auto;
            padding: 0 20px;
            font-family:
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                "Noto Sans TC",
                sans-serif;
            line-height: 1.7;
        }}

        h1 {{
            margin-bottom: 8px;
            line-height: 1.3;
        }}

        .notice {{
            margin: 24px 0;
            padding: 16px 18px;
            border: 1px solid #ccc;
            border-radius: 10px;
        }}

        .calendar-list {{
            padding: 0;
            list-style: none;
        }}

        .calendar-item {{
            margin-bottom: 14px;
            padding: 16px 18px;
            border: 1px solid #ccc;
            border-radius: 10px;
        }}

        .calendar-name {{
            margin-bottom: 4px;
            font-weight: 700;
        }}

        .calendar-link {{
            overflow-wrap: anywhere;
        }}
    </style>
</head>

<body>
    <h1>Pokémon GO 繁體中文行事曆</h1>

    <p>
        所有未指定時區的活動，
        已統一設定為台灣時區 Asia/Taipei。
    </p>

    <div class="notice">
        請複製 .ics 網址，
        使用 Google 日曆的「透過網址」功能訂閱。
        不建議先下載後再匯入，否則不會持續自動更新。
    </div>

    <ul class="calendar-list">
        {''.join(rows)}
    </ul>
</body>
</html>
"""

    index_file = OUTPUT_DIR / "index.html"

    index_file.write_text(
        page,
        encoding="utf-8",
    )


# ============================================================
# 主程式
# ============================================================

def build_calendars() -> None:
    """下載、翻譯並產生所有分類行事曆。"""
    translations = load_translations()

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    successful: list[str] = []
    failed: list[str] = []

    for calendar_key, source_filename in CALENDARS.items():
        source_url = (
            f"{SOURCE_BASE_URL}/"
            f"{source_filename}"
        )

        output_file = (
            OUTPUT_DIR /
            f"{calendar_key}.ics"
        )

        print("=" * 60)
        print(f"正在處理：{calendar_key}")
        print(f"來源：{source_url}")

        try:
            source_calendar = download_calendar(
                source_url
            )

            translated_calendar = translate_calendar(
                source_calendar,
                calendar_key,
                translations,
            )

            validate_calendar(
                translated_calendar,
                calendar_key,
            )

            output_file.write_text(
                translated_calendar,
                encoding="utf-8",
                newline="",
            )

            print(f"完成：{output_file}")
            print(
                "大小："
                f"{output_file.stat().st_size} bytes"
            )

            print(
                "活動數："
                f"{translated_calendar.count('BEGIN:VEVENT')}"
            )

            successful.append(calendar_key)

        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            OSError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            print(
                f"失敗：{calendar_key}："
                f"{type(error).__name__}: {error}"
            )

            failed.append(calendar_key)

    create_index_page()

    print("=" * 60)
    print(
        f"成功產生 {len(successful)} 個行事曆。"
    )

    if failed:
        raise RuntimeError(
            "以下行事曆產生失敗："
            + ", ".join(failed)
        )


if __name__ == "__main__":
    build_calendars()
