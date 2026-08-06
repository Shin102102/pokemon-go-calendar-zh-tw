from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

SOURCE_URL = (
    "https://github.com/othyn/go-calendar/"
    "releases/latest/download/gocal.ics"
)

OUTPUT_DIR = Path("docs")
OUTPUT_FILE = OUTPUT_DIR / "calendar-zh-TW.ics"
TERMS_FILE = Path("translations.json")


def download_calendar(url: str) -> str:
    """下載英文 iCal。"""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "pokemon-go-calendar-zh-tw/1.0",
            "Accept": "text/calendar,text/plain,*/*",
        },
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()

    return data.decode("utf-8-sig")


def unfold_ical_lines(content: str) -> list[str]:
    """
    將 iCal 被折行的內容還原。

    iCal 規範允許長行以空白或 Tab 開頭接續上一行。
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

    為避免切斷 UTF-8 中文字元，以字元逐一累加方式處理。
    """
    if len(line.encode("utf-8")) <= limit:
        return [line]

    result: list[str] = []
    current = ""

    for char in line:
        prefix = "" if not result else " "

        if len((prefix + current + char).encode("utf-8")) > limit:
            result.append(prefix + current)
            current = char
        else:
            current += char

    if current:
        prefix = "" if not result else " "
        result.append(prefix + current)

    return result


def load_translations() -> dict[str, str]:
    """讀取固定翻譯詞庫。"""
    if not TERMS_FILE.exists():
        raise FileNotFoundError(f"找不到翻譯詞庫：{TERMS_FILE}")

    with TERMS_FILE.open("r", encoding="utf-8") as file:
        translations = json.load(file)

    # 長詞先翻譯，避免短詞先取代造成錯誤
    return dict(
        sorted(
            translations.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )
    )


def replace_term(text: str, english: str, chinese: str) -> str:
    """
    取代固定詞彙。

    英文單字或名稱採用較安全的邊界判斷；
    包含空格或符號的片語則直接取代。
    """
    if re.fullmatch(r"[A-Za-z0-9'’.\-♀♂:]+", english):
        pattern = rf"(?<![A-Za-z0-9]){re.escape(english)}(?![A-Za-z0-9])"
        return re.sub(pattern, chinese, text, flags=re.IGNORECASE)

    return re.sub(
        re.escape(english),
        chinese,
        text,
        flags=re.IGNORECASE,
    )


def translate_text(text: str, translations: dict[str, str]) -> str:
    """依固定詞庫翻譯文字。"""
    translated = text

    for english, chinese in translations.items():
        translated = replace_term(translated, english, chinese)

    # 清理翻譯後可能產生的多餘空格
    translated = re.sub(r" {2,}", " ", translated)
    translated = re.sub(r" +([，。：；！？）])", r"\1", translated)
    translated = re.sub(r"（ +", "（", translated)

    return translated.strip()


def translate_property(
    line: str,
    property_name: str,
    translations: dict[str, str],
) -> str:
    """
    翻譯指定 iCal 欄位，並保留參數。

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
    translated_value = translate_text(value, translations)

    return f"{prefix}:{translated_value}"


def build_calendar() -> None:
    translations = load_translations()
    source_calendar = download_calendar(SOURCE_URL)
    lines = unfold_ical_lines(source_calendar)

    translated_lines: list[str] = []

    for line in lines:
        # 日曆名稱
        line = translate_property(line, "X-WR-CALNAME", translations)

        # 活動標題
        line = translate_property(line, "SUMMARY", translations)

        # 地點通常很短，可一併翻譯
        line = translate_property(line, "LOCATION", translations)

        # 初期不翻 DESCRIPTION，避免網址及 HTML 被錯誤取代。
        # 確認標題運作正常後，再考慮開啟下一行：
        # line = translate_property(line, "DESCRIPTION", translations)

        translated_lines.extend(fold_ical_line(line))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output = "\r\n".join(translated_lines)

    if not output.endswith("\r\n"):
        output += "\r\n"

    OUTPUT_FILE.write_text(output, encoding="utf-8", newline="")

    print(f"完成：{OUTPUT_FILE}")
    print(f"輸出大小：{OUTPUT_FILE.stat().st_size} bytes")


if __name__ == "__main__":
    build_calendar()
