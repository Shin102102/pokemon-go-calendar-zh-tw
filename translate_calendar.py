from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path


# =========================================================
# 基本設定
# =========================================================

TAIPEI_TIMEZONE = "Asia/Taipei"

SOURCE_BASE_URL = (
    "https://github.com/othyn/go-calendar/"
    "releases/latest/download"
)

OUTPUT_DIR = Path("docs")
TERMS_FILE = Path("translations.json")


# 左邊：輸出的中文檔名
# 右邊：GO Calendar 原始檔名
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


# 台灣時區定義。
# Asia/Taipei 目前是 UTC+8，沒有日光節約時間。
TAIPEI_VTIMEZONE_LINES = [
    "BEGIN:VTIMEZONE",
    "TZID:Asia/Taipei",
    "X-LIC-LOCATION:Asia/Taipei",
    "BEGIN:STANDARD",
    "TZOFFSETFROM:+0800",
    "TZOFFSETTO:+0800",
    "TZNAME:UTC+08",
    "DTSTART:19700101T000000",
    "END:STANDARD",
    "END:VTIMEZONE",
]


# =========================================================
# 下載與檔案處理
# =========================================================

def download_calendar(url: str) -> str:
    """下載 GO Calendar 英文 iCal。"""

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "pokemon-go-calendar-zh-tw/3.0",
            "Accept": "text/calendar,text/plain,*/*",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=60,
    ) as response:
        data = response.read()

    return data.decode("utf-8-sig")


def unfold_ical_lines(content: str) -> list[str]:
    """
    還原 iCalendar 折行。

    iCalendar 長文字會在下一行以空白或 Tab 開頭接續。
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
    重新折疊過長的 iCalendar 行。

    依 UTF-8 位元組長度判斷，避免切斷中文字元。
    """

    if len(line.encode("utf-8")) <= limit:
        return [line]

    result: list[str] = []
    current = ""
    first_line = True

    for char in line:
        prefix = "" if first_line else " "
        candidate = prefix + current + char

        if (
            current
            and len(candidate.encode("utf-8")) > limit
        ):
            result.append(prefix + current)
            current = char
            first_line = False
        else:
            current += char

    if current:
        prefix = "" if first_line else " "
        result.append(prefix + current)

    return result


# =========================================================
# 固定詞庫翻譯
# =========================================================

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

    # 長片語優先翻譯，避免短詞先取代。
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
    """安全取代單一英文詞彙。"""

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
    """使用固定詞庫翻譯文字。"""

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
    """翻譯 SUMMARY、LOCATION、CATEGORIES 等欄位。"""

    upper_line = line.upper()

    if not (
        upper_line.startswith(f"{property_name}:")
        or upper_line.startswith(f"{property_name};")
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


# =========================================================
# 時區修正
# =========================================================

def add_taipei_timezone_to_datetime(
    line: str,
) -> str:
    """
    將沒有時區的 DTSTART、DTEND、RECURRENCE-ID
    指定為 Asia/Taipei。

    範例：

    原始：
    DTSTART:20260806T180000

    修改後：
    DTSTART;TZID=Asia/Taipei:20260806T180000

    不修改：
    1. 全天活動 VALUE=DATE
    2. 已經有 TZID 的時間
    3. 結尾有 Z 的 UTC 時間
    """

    upper_line = line.upper()

    supported_properties = (
        "DTSTART",
        "DTEND",
        "RECURRENCE-ID",
    )

    property_name = next(
        (
            name
            for name in supported_properties
            if (
                upper_line.startswith(f"{name}:")
                or upper_line.startswith(f"{name};")
            )
        ),
        None,
    )

    if property_name is None:
        return line

    # 全天活動只有日期，沒有時區問題。
    if "VALUE=DATE" in upper_line:
        return line

    # 已經指定時區，不重複修改。
    if "TZID=" in upper_line:
        return line

    if ":" not in line:
        return line

    property_part, value = line.split(":", 1)

    # UTC 時間以 Z 結尾，保留原樣。
    if value.upper().endswith("Z"):
        return line

    # 僅處理完整的日期時間，例如 20260806T180000。
    if not re.fullmatch(
        r"\d{8}T\d{6}",
        value,
    ):
        return line

    # 保留原本其他參數，只加入 TZID。
    if ";" in property_part:
        return (
            f"{property_part};"
            f"TZID={TAIPEI_TIMEZONE}:"
            f"{value}"
        )

    return (
        f"{property_name};"
        f"TZID={TAIPEI_TIMEZONE}:"
        f"{value}"
    )


# =========================================================
# 單一行事曆轉換
# =========================================================

def translate_calendar(
    content: str,
    calendar_key: str,
    translations: dict[str, str],
) -> str:
    """翻譯並修正單一分類行事曆。"""

    source_lines = unfold_ical_lines(content)

    calendar_name = CALENDAR_NAMES.get(
        calendar_key,
        "Pokémon GO 活動",
    )

    output_lines: list[str] = []

    inserted_calendar_settings = False
    inserted_timezone = False

    inside_existing_vtimezone = False

    for line in source_lines:
        upper_line = line.upper()

        # 若來源本身已有 VTIMEZONE，先略過。
        # 我們後面會加入統一的 Asia/Taipei 定義。
        if upper_line == "BEGIN:VTIMEZONE":
            inside_existing_vtimezone = True
            continue

        if inside_existing_vtimezone:
            if upper_line == "END:VTIMEZONE":
                inside_existing_vtimezone = False
            continue

        # 移除來源中可能重複的日曆名稱。
        if (
            upper_line.startswith("X-WR-CALNAME:")
            or upper_line.startswith("NAME:")
            or upper_line.startswith("X-WR-TIMEZONE:")
        ):
            continue

        # 在 VERSION 後加入唯一的中文日曆名稱與預設時區。
        if upper_line.startswith("VERSION:"):
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
                    "X-WR-TIMEZONE:Asia/Taipei"
                )
            )

            inserted_calendar_settings = True
            continue

        # 在第一個 VEVENT 前加入 VTIMEZONE。
        if (
            upper_line == "BEGIN:VEVENT"
            and not inserted_timezone
        ):
            for timezone_line in TAIPEI_VTIMEZONE_LINES:
                output_lines.extend(
                    fold_ical_line(timezone_line)
                )

            inserted_timezone = True

        # 將浮動時間指定為台灣時間。
        line = add_taipei_timezone_to_datetime(line)

        # 翻譯活動標題。
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

        # DESCRIPTION 暫時保留英文。
        # 固定詞庫不適合翻譯整段說明和網址。
        #
        # 若未來想嘗試翻譯，可解除下方註解：
        #
        # line = translate_property(
        #     line,
        #     "DESCRIPTION",
        #     translations,
        # )

        output_lines.extend(
            fold_ical_line(line)
        )

    # 防止少數來源缺少 VERSION。
    if not inserted_calendar_settings:
        raise ValueError(
            "來源 iCal 找不到 VERSION 欄位"
        )

    output = "\r\n".join(output_lines)

    if not output.endswith("\r\n"):
        output += "\r\n"

    return output


# =========================================================
# 建立首頁
# =========================================================

def create_index_page() -> None:
    """建立 GitHub Pages 中文訂閱首頁。"""

    rows: list[str] = []

    for calendar_key in CALENDARS:
        calendar_name = CALENDAR_NAMES.get(
            calendar_key,
            calendar_key,
        )

        filename = f"{calendar_key}.ics"

        rows.append(
            f"""
            <li>
                <strong>{calendar_name}</strong>
                <div>
                    <a href="{filename}">
                        {filename}
                    </a>
                </div>
            </li>
            """
        )

    html = f"""<!doctype html>
<html lang="zh-Hant-TW">
<head>
    <meta charset="utf-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >
    <title>Pokémon GO 繁體中文行事曆</title>

    <style>
        body {{
            max-width: 800px;
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
            line-height: 1.3;
        }}

        li {{
            margin-bottom: 20px;
        }}

        a {{
            overflow-wrap: anywhere;
        }}

        .notice {{
            padding: 16px;
            border-radius: 10px;
            background: #f4f6f8;
        }}
    </style>
</head>

<body>
    <h1>Pokémon GO 繁體中文行事曆</h1>

    <div class="notice">
        本版本已將沒有時區的活動時間固定為
        Asia/Taipei 台灣時間。
        請複製 .ics 網址，
        使用行事曆的「透過網址訂閱」功能加入。
    </div>

    <ul>
        {''.join(rows)}
    </ul>
</body>
</html>
"""

    index_file = OUTPUT_DIR / "index.html"

    index_file.write_text(
        html,
        encoding="utf-8",
    )


# =========================================================
# 產生全部分類日曆
# =========================================================

def build_calendars() -> None:
    """下載、翻譯、修正並輸出全部分類行事曆。"""

    translations = load_translations()

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    successful = 0
    failed: list[str] = []

    for calendar_key, source_filename in CALENDARS.items():
        source_url = (
            f"{SOURCE_BASE_URL}/{source_filename}"
        )

        output_file = (
            OUTPUT_DIR / f"{calendar_key}.ics"
        )

        print("=" * 60)
        print(f"正在處理：{calendar_key}")
        print(f"來源網址：{source_url}")

        try:
            source_calendar = download_calendar(
                source_url
            )

            translated_calendar = translate_calendar(
                source_calendar,
                calendar_key,
                translations,
            )

            output_file.write_text(
                translated_calendar,
                encoding="utf-8",
                newline="",
            )

            # 基本檢查。
            generated_content = output_file.read_text(
                encoding="utf-8",
            )

            if "BEGIN:VCALENDAR" not in generated_content:
                raise ValueError(
                    "輸出缺少 BEGIN:VCALENDAR"
                )

            if "END:VCALENDAR" not in generated_content:
                raise ValueError(
                    "輸出缺少 END:VCALENDAR"
                )

            print(f"完成：{output_file}")
            print(
                f"檔案大小："
                f"{output_file.stat().st_size} bytes"
            )

            successful += 1

        except Exception as error:
            print(
                f"失敗：{calendar_key}"
            )
            print(
                f"錯誤：{error}"
            )

            failed.append(calendar_key)

    create_index_page()

    print("=" * 60)
    print(
        f"成功產生 {successful} 個分類行事曆。"
    )

    if failed:
        raise RuntimeError(
            "以下行事曆產生失敗："
            + ", ".join(failed)
        )


if __name__ == "__main__":
    build_calendars()
