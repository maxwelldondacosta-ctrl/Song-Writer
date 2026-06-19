from collections import Counter
from statistics import mean

from songwriter.api.validation import RuleOutcome, ValidationContext
from songwriter.api.validation.tokenizer import WordToken
from songwriter.api.vocab_resolver import classify_emotion_hardness


def check_line(tokens: list[WordToken], ctx: ValidationContext) -> RuleOutcome:
    known = [t for t in tokens if not t.unknown]
    if not known:
        return RuleOutcome("warn", ["no recognized words on line"])
    avg_density = mean(t.consonant_density for t in known)
    attacks = Counter(t.first_syllable_attack for t in known)
    dominant_attack = attacks.most_common(1)[0][0]

    # Hardness for any emotion — preset words hit a static fast path,
    # custom emotions get an LLM classification (cached per-process).
    hardness = classify_emotion_hardness(ctx.emotion or "")

    if hardness == "soft":
        if avg_density > 0.45:
            return RuleOutcome("warn", [
                f"consonant density {avg_density:.2f} too hard for emotion {ctx.emotion!r}"
            ])
        if dominant_attack == "hard":
            return RuleOutcome("warn", [f"hard attack mismatches soft emotion {ctx.emotion!r}"])
        return RuleOutcome("pass", [])
    if hardness == "hard":
        if avg_density < 0.30:
            return RuleOutcome("warn", [
                f"consonant density {avg_density:.2f} too soft for emotion {ctx.emotion!r}"
            ])
        return RuleOutcome("pass", [])
    return RuleOutcome("pass", [])
