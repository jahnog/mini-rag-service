from __future__ import annotations

import re

INJECTION = re.compile(
    r"ignore (all )?(previous|prior|above) instructions|"
    r"ignora(r)? (las |tus |todas las )?(instrucciones|reglas)|"
    r"disregard (all )?(previous|prior|above) (instructions|rules)|"
    r"forget (everything|all) (above|before)|"
    r"reveal (the )?(system |hidden )?prompt|"
    r"(print|show|dump) (me )?(your |the )?(system |hidden )?prompt|"
    r"jailbreak|you are now|"
    r"olvid(a|á|e) (las |tus )?instrucciones|"
    r"mostr(a|á|ar) (el )?prompt|"
    r"system prompt|hidden instructions|"
    r"ignore previous|"
    r"dump (the )?(system )?prompt|"
    r"revel(a|á|ar) (el |las )?(prompt|instrucciones)",
    re.IGNORECASE,
)


class RegexBackend:
    def score(self, text: str) -> tuple[bool, str]:
        if INJECTION.search(text):
            return True, "prompt injection"
        return False, "no injection"
