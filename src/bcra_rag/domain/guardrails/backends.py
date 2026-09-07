from __future__ import annotations

import re

INJECTION = re.compile(
    r"ignore (all )?(previous|prior|above) instructions|"
    r"ignore previous|"
    r"ignora(r)? (las |tus |todas las )?(instrucciones|reglas)|"
    r"ignoriere (alle |die )?(vorherigen |bisherigen |obigen )?"
    r"(anweisungen|instruktionen|regeln)|"
    r"disregard (all )?(previous|prior|above) (instructions|rules)|"
    r"forget (everything|all) (above|before)|"
    r"vergiss alles (oben|vorher|davor)|"
    r"olvid(a|á|e) (las |tus )?instrucciones|"
    r"reveal (the )?(system[- ]?|hidden )?prompt|"
    r"(print|show|dump) (me )?(your |the )?(system[- ]?|hidden )?prompt|"
    r"dump (the )?(system[- ]?)?prompt|"
    r"mostr(a|á|ar) (el )?prompt|"
    r"zeig(e)? (mir )?(den )?(system[- ]?prompt|systemprompt)|"
    r"gib den systemprompt aus|"
    r"revel(a|á|ar) (el |las )?(prompt|instrucciones)|"
    r"system[- ]?prompt|"
    r"hidden instructions|"
    r"versteckte anweisungen|"
    r"jailbreak|"
    r"you are now|"
    r"ahora eres|"
    r"du bist jetzt|"
    r"do anything now|"
    r"developer mode|"
    r"modo desarrollador|"
    r"entwicklermodus|"
    r"new instructions|"
    r"nuevas instrucciones|"
    r"neue anweisungen",
    re.IGNORECASE,
)


class RegexBackend:
    def score(self, text: str) -> tuple[bool, str]:
        if INJECTION.search(text):
            return True, "prompt injection"
        return False, "no injection"
