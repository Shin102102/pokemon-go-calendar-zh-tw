from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path


# GO Calendar 已經分類好的行事曆
# 左側是輸出的中文檔名，右側是來源檔名
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

SOURCE_BASE_URL = (
    "https://github.com/othyn/go-calendar/"
    "releases/latest/download"
)

OUTPUT_DIR = Path("docs")
TERMS_FILE = Path("translations.json")


# 各分類的繁體中文行事曆名稱
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


def download_calendar(url: str) -> str:
    """下載指定英文 iCal。"""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "pokemon-go-calendar-zh-tw/2.0",
            "Accept": "text/calendar,text/plain,*/*",
        },
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()

    return data.decode("utf-8-sig")


def unfold_ical_lines(content: str) -> list[str]:
    """
    還原 iCal 折行。

    iCal 長行可能會在下一行以空白或 Tab 開頭接續。
    """
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    unfolded: list[str] = []

    for line in lines:
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)

    return unfolded


def fold_ical_line(line: str, limit: int = 73) -> list[str]:
    """
    將過長的 iCal 行重新折行。

    以 UTF-8 位元組計算，避免中文字被截斷。
    """
    if len(line.encode("utf-8")) <= limit:
        return [line]

    result: list[str] = []
    current = ""

    for char in line:
        continuation_prefix = "" if not result else " "

        candidate = continuation_prefix + current + char

        if len(candidate.encode("utf-8")) > limit and current:
            result.append(continuation_prefix + current)
            current = char
        else:
            current += char

    if current:
        continuation_prefix = "" if not result else " "
        result.append(continuation_prefix + current)

    return result


def load_translations() -> dict[str, str]:
    """讀取 translations.json 固定翻譯詞庫。"""
    if not TERMS_FILE.exists():
        raise FileNotFoundError(f"找不到翻譯詞庫：{TERMS_FILE}")

    with TERMS_FILE.open("r", encoding="utf-8") as file:
        translations = json.load(file)

    # 長片語先處理，避免短詞先取代
    return dict(
        sorted(
            translations.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )
    )


def replace_term(text: str, english: str, chinese: str) -> str:
    """依英文詞彙特性進行安全取代。"""
    if re.fullmatch(r"[A-Za-z0-9'’.\-♀♂:]+", english):
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

    # 清理翻譯後多餘空格
    translated = re.sub(r" {2,}", " ", translated)
    translated = re.sub(
        r" +([，。：；！？）])",
        r"\1",
        translated,
    )
    translated = re.sub(r"（ +", "（", translated)

    return translated.strip()


def translate_property(
    line: str,
    property_name: str,
    translations: dict[str, str],
) -> str:
    """
    翻譯指定 iCal 欄位，並保留欄位參數。

    例如：
    SUMMARY;LANGUAGE=en:Kyogre Raid Hour
    """
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


def set_calendar_name(
    line: str,
    calendar_name: str,
) -> str:
    """替換日曆顯示名稱。"""
    upper_line = line.upper()

    if upper_line.startswith("X-WR-CALNAME:"):
        return f"X-WR-CALNAME:{calendar_name}"

    if upper_line.startswith("NAME:"):
        return f"NAME:{calendar_name}"

    return line


def translate_calendar(
    content: str,
    calendar_key: str,
    translations: dict[str, str],
) -> str:
    """翻譯單一分類行事曆。"""
    lines = unfold_ical_lines(content)
    translated_lines: list[str] = []

    calendar_name = CALENDAR_NAMES.get(
        calendar_key,
        "Pokémon GO 活動",
    )

    has_calendar_name = False

    for line in lines:
        upper_line = line.upper()

        if upper_line.startswith("X-WR-CALNAME:"):
            has_calendar_name = True

        line = set_calendar_name(
            line,
            calendar_name,
        )

        line = translate_property(
            line,
            "SUMMARY",
            translations,
        )

        line = translate_property(
            line,
            "LOCATION",
            translations,
        )

        line = translate_property(
            line,
            "CATEGORIES",
            translations,
        )

        # 暫時不翻譯 DESCRIPTION，避免網址或 HTML 被改壞。
        # 確定運作正常後，可解除下一段註解。
        #
        # line = translate_property(
        #     line,
        #     "DESCRIPTION",
        #     translations,
        # )

        # 原始檔若沒有 X-WR-CALNAME，
        # 就在 VERSION 後加入中文名稱
        translated_lines.extend(fold_ical_line(line))

        if (
            not has_calendar_name
            and upper_line.startswith("VERSION:")
        ):
            translated_lines.extend(
                fold_ical_line(
                    f"X-WR-CALNAME:{calendar_name}"
                )
            )
            has_calendar_name = True

    output = "\r\n".join(translated_lines)

    if not output.endswith("\r\n"):
        output += "\r\n"

    return output


def create_index_page() -> None:
    """建立簡單的中文訂閱連結頁面。"""
    rows = []

    for calendar_key in CALENDARS:
        name = CALENDAR_NAMES.get(
            calendar_key,
            calendar_key,
        )

        filename = f"{calendar_key}.ics"

        rows.append(
            f"""
            <li>
                <strong>{name}</strong><br>
                <a href="{filename}">
                    下載或訂閱 {filename}
                </a>
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
            max-width: 760px;
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
            margin-bottom: 18px;
        }}

        a {{
            overflow-wrap: anywhere;
        }}

        .notice {{
            padding: 16px;
            background: #f4f4f4;
            border-radius: 8px;
        }}
    </style>
</head>
<body>
    <h1>Pokémon GO 繁體中文行事曆</h1>

    <p class="notice">
        請複製下方 .ics 網址，
        使用 Google 日曆、Apple 行事曆或 Outlook
        的「透過網址訂閱」功能加入。
    </p>

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


def build_calendars() -> None:
    """下載、翻譯並輸出所有分類行事曆。"""
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

        print(
            f"正在處理：{calendar_key}"
        )
        print(
            f"來源：{source_url}"
        )

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

            print(
                f"完成：{output_file}"
            )
            print(
                f"大小：{output_file.stat().st_size} bytes"
            )

            successful += 1

        except Exception as error:
            print(
                f"失敗：{calendar_key}：{error}"
            )
            failed.append(calendar_key)

    create_index_page()

    print(
        f"成功產生 {successful} 個行事曆。"
    )

    if failed:
        raise RuntimeError(
            "以下行事曆產生失敗："
            + ", ".join(failed)
        )


if __name__ == "__main__":
    build_calendars()
