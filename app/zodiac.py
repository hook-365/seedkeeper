#!/usr/bin/env python3
"""
Zodiac calculations for Seedkeeper.
Western zodiac from month/day, Chinese zodiac from year.
"""

from typing import Optional, Dict, Tuple

# Western zodiac date ranges (month, day) -> sign
WESTERN_ZODIAC = [
    ((1, 20), (2, 18), "Aquarius", "♒", "Water Bearer"),
    ((2, 19), (3, 20), "Pisces", "♓", "Fish"),
    ((3, 21), (4, 19), "Aries", "♈", "Ram"),
    ((4, 20), (5, 20), "Taurus", "♉", "Bull"),
    ((5, 21), (6, 20), "Gemini", "♊", "Twins"),
    ((6, 21), (7, 22), "Cancer", "♋", "Crab"),
    ((7, 23), (8, 22), "Leo", "♌", "Lion"),
    ((8, 23), (9, 22), "Virgo", "♍", "Maiden"),
    ((9, 23), (10, 22), "Libra", "♎", "Scales"),
    ((10, 23), (11, 21), "Scorpio", "♏", "Scorpion"),
    ((11, 22), (12, 21), "Sagittarius", "♐", "Archer"),
    ((12, 22), (1, 19), "Capricorn", "♑", "Goat"),  # Spans year boundary
]

# Chinese zodiac animals (year % 12 starting from Rat at 0 = 2008, 2020, etc.)
CHINESE_ZODIAC = [
    ("Rat", "🐀", "Clever, resourceful, versatile"),
    ("Ox", "🐂", "Diligent, dependable, strong"),
    ("Tiger", "🐅", "Brave, confident, competitive"),
    ("Rabbit", "🐇", "Quiet, elegant, kind"),
    ("Dragon", "🐉", "Confident, intelligent, enthusiastic"),
    ("Snake", "🐍", "Enigmatic, intelligent, wise"),
    ("Horse", "🐎", "Animated, active, energetic"),
    ("Goat", "🐐", "Calm, gentle, sympathetic"),
    ("Monkey", "🐒", "Sharp, curious, mischievous"),
    ("Rooster", "🐓", "Observant, hardworking, courageous"),
    ("Dog", "🐕", "Loyal, honest, faithful"),
    ("Pig", "🐖", "Compassionate, generous, diligent"),
]

# Chinese zodiac elements (year % 10, pairs of years share element)
CHINESE_ELEMENTS = [
    "Metal", "Metal", "Water", "Water", "Wood", "Wood",
    "Fire", "Fire", "Earth", "Earth"
]


def get_western_zodiac(month: int, day: int) -> Dict:
    """
    Get Western zodiac sign from month and day.

    Returns dict with: name, symbol, animal, element, modality
    """
    for start, end, name, symbol, animal in WESTERN_ZODIAC:
        start_month, start_day = start
        end_month, end_day = end

        # Handle Capricorn spanning Dec-Jan
        if start_month > end_month:
            if (month == start_month and day >= start_day) or \
               (month == end_month and day <= end_day):
                return _build_western_info(name, symbol, animal)
        else:
            if (month == start_month and day >= start_day) or \
               (month == end_month and day <= end_day) or \
               (start_month < month < end_month):
                return _build_western_info(name, symbol, animal)

    # Fallback (shouldn't happen with valid dates)
    return {"name": "Unknown", "symbol": "?", "animal": "Unknown"}


def _build_western_info(name: str, symbol: str, animal: str) -> Dict:
    """Build full Western zodiac info dict."""
    # Elements: Fire (Aries, Leo, Sag), Earth (Taurus, Virgo, Cap),
    #           Air (Gemini, Libra, Aquarius), Water (Cancer, Scorpio, Pisces)
    elements = {
        "Aries": "Fire", "Leo": "Fire", "Sagittarius": "Fire",
        "Taurus": "Earth", "Virgo": "Earth", "Capricorn": "Earth",
        "Gemini": "Air", "Libra": "Air", "Aquarius": "Air",
        "Cancer": "Water", "Scorpio": "Water", "Pisces": "Water",
    }

    # Modalities: Cardinal (initiators), Fixed (stabilizers), Mutable (adapters)
    modalities = {
        "Aries": "Cardinal", "Cancer": "Cardinal", "Libra": "Cardinal", "Capricorn": "Cardinal",
        "Taurus": "Fixed", "Leo": "Fixed", "Scorpio": "Fixed", "Aquarius": "Fixed",
        "Gemini": "Mutable", "Virgo": "Mutable", "Sagittarius": "Mutable", "Pisces": "Mutable",
    }

    return {
        "name": name,
        "symbol": symbol,
        "animal": animal,
        "element": elements.get(name, "Unknown"),
        "modality": modalities.get(name, "Unknown"),
    }


def get_chinese_zodiac(year: int) -> Dict:
    """
    Get Chinese zodiac from birth year.

    Note: This is simplified - technically Chinese New Year falls
    between Jan 21 and Feb 20, so early-year births might be previous year's sign.

    Returns dict with: animal, emoji, element, yin_yang, traits
    """
    # Rat years: 2008, 2020, 2032... (year % 12 == 4 for these)
    # Adjusted so 2020 = Rat (index 0)
    index = (year - 2020) % 12
    animal, emoji, traits = CHINESE_ZODIAC[index]

    # Element cycles every 2 years through 5 elements (10 year cycle)
    element_index = (year - 2020) % 10
    # Adjust for the offset: 2020 is Metal Rat
    element = CHINESE_ELEMENTS[element_index]

    # Yin/Yang: even years = Yang, odd years = Yin
    yin_yang = "Yang" if year % 2 == 0 else "Yin"

    return {
        "animal": animal,
        "emoji": emoji,
        "element": element,
        "yin_yang": yin_yang,
        "traits": traits,
        "year": year,
    }


def get_full_sign(month: int, day: int, year: Optional[int] = None) -> Dict:
    """
    Get complete zodiac information.

    Returns Western zodiac always, Chinese zodiac if year provided.
    """
    result = {
        "western": get_western_zodiac(month, day),
        "chinese": None,
    }

    if year:
        result["chinese"] = get_chinese_zodiac(year)

    return result


def format_sign_display(month: int, day: int, year: Optional[int] = None,
                        name: Optional[str] = None) -> str:
    """Format zodiac info for Discord display."""
    info = get_full_sign(month, day, year)
    western = info["western"]

    header = f"**{name}'s Signs**" if name else "**Your Signs**"

    lines = [header, ""]

    # Western zodiac
    lines.append(f"{western['symbol']} **{western['name']}** ({western['animal']})")
    lines.append(f"Element: {western['element']} | {western['modality']}")

    # Chinese zodiac if we have year
    if info["chinese"]:
        chinese = info["chinese"]
        lines.append("")
        lines.append(f"{chinese['emoji']} **{chinese['element']} {chinese['animal']}** ({chinese['yin_yang']})")
        lines.append(f"*{chinese['traits']}*")

    return "\n".join(lines)


# Quick test
if __name__ == "__main__":
    # Test cases
    print(format_sign_display(6, 2, 1990, "Anthony"))  # Gemini, Metal Horse
    print()
    print(format_sign_display(1, 7, None, "Kristi"))   # Capricorn, no year
    print()
    print(format_sign_display(12, 25, 2000, "Test"))   # Capricorn, Metal Dragon
