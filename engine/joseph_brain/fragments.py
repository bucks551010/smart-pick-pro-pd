"""Joseph Brain — Fragment Pools & Template Collections.

All combinatorial rant-building pools (openers, pivots, closers,
catchphrases), body templates (generic + stat-specific), data-driven
sentence templates, ambient colour pools, commentary pools, historical
comps database, and the anti-repetition fragment picker functions.
"""

from __future__ import annotations

import datetime
import random

# ═══════════════════════════════════════════════════════════════
# MODULE-LEVEL ANTI-REPETITION STATE
# ═══════════════════════════════════════════════════════════════
_used_fragments: dict = {}      # keyed by pool name → set of used IDs
_used_ambient: dict = {}        # keyed by context → set of used indices
_used_commentary: dict = {}     # keyed by context_type → set of used indices

# Daily reset guard: track the last date fragment state was cleared
_fragment_reset_date: str = ""


def reset_fragment_state() -> None:
    """Clear all anti-repetition tracking dicts."""
    _used_fragments.clear()
    _used_ambient.clear()
    _used_commentary.clear()


def _auto_reset_if_new_day() -> None:
    """Auto-reset fragment state when a new sports day begins."""
    global _fragment_reset_date
    today = datetime.date.today().isoformat()
    if _fragment_reset_date != today:
        reset_fragment_state()
        _fragment_reset_date = today


# ═══════════════════════════════════════════════════════════════
# PLAYOFF FRAGMENT POOLS — Postseason-specific language
# ═══════════════════════════════════════════════════════════════

PLAYOFF_OPENER_POOL = [
    {"id": "po_01", "text": "This is PLAYOFF basketball and the rules are DIFFERENT now..."},
    {"id": "po_02", "text": "We are in the POSTSEASON and I am LOCKED IN like never before..."},
    {"id": "po_03", "text": "Forget the regular season — this is where LEGACIES are forged..."},
    {"id": "po_04", "text": "The playoffs separate the MEN from the BOYS and tonight we find out WHO is WHO..."},
    {"id": "po_05", "text": "Sixteen teams entered. Only ONE will raise the trophy. Let me tell you about TONIGHT..."},
    {"id": "po_06", "text": "Playoff intensity is on ANOTHER level and I've been studying this matchup ALL series..."},
    {"id": "po_07", "text": "The postseason is where EXCUSES die and GREATNESS lives. Let me explain..."},
    {"id": "po_08", "text": "Every possession in the playoffs is AMPLIFIED. Every bucket hits DIFFERENT..."},
    {"id": "po_09", "text": "I've watched EVERY game of this series. I know the adjustments. I know the MATCHUPS..."},
    {"id": "po_10", "text": "You want playoff analysis? You came to the RIGHT analyst. Joseph M. Smith LIVES for this..."},
    {"id": "po_11", "text": "Regular season is the APPETIZER. The playoffs are the MAIN COURSE. And I am HUNGRY..."},
    {"id": "po_12", "text": "Rotations SHRINK, minutes GO UP, and only the WARRIORS survive. Let me break it down..."},
]

PLAYOFF_CLOSER_POOL = [
    {"id": "pc_01", "text": "This is PLAYOFF basketball — and Joseph M. Smith is UNDEFEATED in the postseason of analysis!"},
    {"id": "pc_02", "text": "When the lights are BRIGHTEST, Joseph M. Smith shines BRIGHTEST. Playoff LOCK!"},
    {"id": "pc_03", "text": "Trust the postseason process. Trust the playoff data. Trust JOSEPH!"},
    {"id": "pc_04", "text": "The regular season was the rehearsal. THIS is the SHOW. And I just gave you the SCRIPT!"},
    {"id": "pc_05", "text": "Championships are WON in moments like this. So is MONEY. PLAYOFF CASH incoming!"},
    {"id": "pc_06", "text": "That's my playoff analysis and I would stake my ENTIRE reputation on it!"},
    {"id": "pc_07", "text": "The postseason brings out the BEST in Joseph M. Smith. You're WELCOME!"},
    {"id": "pc_08", "text": "I've been waiting ALL regular season for this. PLAYOFF JOSEPH is here and he is DANGEROUS!"},
    {"id": "pc_09", "text": "In the playoffs, the SHARP money follows Joseph M. Smith. Now you know WHY!"},
    {"id": "pc_10", "text": "Series basketball. Elimination stakes. MAXIMUM conviction. That's the playoff PROMISE!"},
]

PLAYOFF_BODY_TEMPLATES = {
    "SMASH": [
        "PLAYOFF {player} is a DIFFERENT animal! {line} {stat}? In the postseason he ELEVATES. {edge}% edge — this is a PLAYOFF SMASH!",
        "The intensity is CRANKED to eleven. {player} averages MORE in the playoffs and {line} {stat} is DISRESPECTFUL at this stage. SMASH!",
        "{player} in an elimination-stakes environment? {line} {stat} is a GIFT. {edge}% edge — the postseason data SCREAMS over!",
        "Rotations shrink to 7-8 guys in the playoffs. {player} plays 38+ minutes. {line} {stat} at {edge}% edge? PLAYOFF SMASH!",
        "When the stakes are THIS high, {player} turns into a MONSTER. {line} {stat} is a number he'll blow PAST. {edge}% edge!",
    ],
    "LEAN": [
        "Playoff matchups are TIGHTER but {player} has the postseason pedigree. {line} {stat} with {edge}% edge — solid playoff lean.",
        "The series adjustments favor {player} tonight. {line} {stat} at {edge}% edge — I like it in a playoff context.",
        "In the postseason, the value gets HARDER to find. But {player} at {line} {stat} with {edge}% edge? That's REAL playoff value.",
        "{player} has shown he can produce under playoff pressure. {line} {stat} at {edge}% edge — the postseason track record supports it.",
    ],
    "FADE": [
        "PLAYOFF defense is NO JOKE. {player} at {line} {stat}? The scouting report is LOCKED in on him. FADE in the postseason!",
        "Series adjustments have NEUTRALIZED {player}'s go-to moves. {line} {stat} is a TRAP in the playoffs. FADE!",
        "The coaching staff made their adjustments after Game {game_num}. {player} at {line} {stat}? They've got the ANSWER now. FADE!",
        "Playoff defenses are ELITE. {player} at {line} {stat} with only {edge}% edge? That's not enough in the postseason. FADE!",
    ],
    "STAY_AWAY": [
        "Playoff variance is AMPLIFIED. {player} at {line} {stat}? In the postseason, ANYTHING can happen. STAY AWAY!",
        "Series basketball creates CHAOS in the prop market. {player} at {line} {stat}? Not worth the playoff risk. STAY AWAY!",
        "The postseason is a MINEFIELD for prop bettors. {player} at {line} {stat} is a TRAP I will NOT touch!",
    ],
    "OVERRIDE": [
        "PLAYOFF OVERRIDE! The machine doesn't account for postseason INTENSITY. {player} at {line} {stat} — I'm overriding with {edge}% edge!",
        "In the playoffs, the EYE TEST matters MORE. And my eyes tell me {player} at {line} {stat} is WRONG. OVERRIDE!",
        "The regular season model underestimates playoff {player}. {line} {stat}? The postseason version of this man is ELITE. OVERRIDE at {edge}%!",
    ],
}

ELIMINATION_GAME_TEMPLATES = [
    "ELIMINATION GAME! Season on the LINE! {player} has to bring his ABSOLUTE best or go home for the SUMMER!",
    "Win or GO HOME! {player} in an elimination game is a DIFFERENT breed — the desperation factor is OFF the charts!",
    "The season ends TONIGHT if they lose. {player} knows it. The coach knows it. And Joseph M. Smith KNOWS what that means for the stat line!",
    "Elimination games are where HEROES are born and PRETENDERS are exposed. {player} — which one are you TONIGHT?",
    "Backs against the WALL. Season on the BRINK. {player} either steps up or starts his VACATION. I know WHICH one it'll be!",
]

GAME_SEVEN_TEMPLATES = [
    "GAME SEVEN! The two most beautiful words in ALL of sports! {player} and his LEGACY are on the line!",
    "Winner takes ALL! Game 7 and {player} is about to find out if he's a LEGEND or a FOOTNOTE!",
    "There is NO Game 8. This is IT. And the way {player} has been playing, I know EXACTLY how this goes!",
    "Game 7 separates the DAWGS from the PUPPIES. {player} is a certified DAWG and the numbers PROVE it!",
    "Every great career has defining Game 7 moments. Tonight is {player}'s chance to write his CHAPTER!",
]

SERIES_CLINCH_TEMPLATES = [
    "{player} has a chance to CLOSE THIS OUT! When the opponent is on the ropes, you do NOT let them off the hook!",
    "Series-clinching game! {player} smells BLOOD and the advanced numbers say he's going to FEAST in the closeout!",
    "Championship-caliber players CLOSE series. They don't let them drag to Game 7. {player} ends it TONIGHT!",
    "The series can end RIGHT HERE. {player} in a closeout game historically goes OFF — the postseason data confirms it!",
]

FINALS_TEMPLATES = [
    "The NBA FINALS! The BIGGEST stage on the planet! {player} is playing for a RING and that changes EVERYTHING!",
    "Finals basketball is the PINNACLE. The pressure is IMMENSE but {player} was BUILT for this moment!",
    "Everything comes down to THIS. Finals-level {player} with the Larry O'Brien Trophy on the line — ELECTRIC!",
    "The WORLD is watching the Finals and {player} is about to show them WHY he belongs on this stage!",
]


# ═══════════════════════════════════════════════════════════════
# A) FRAGMENT POOLS — For combinatorial rant builder
# ═══════════════════════════════════════════════════════════════

OPENER_POOL = [
    {"id": "opener_01", "text": "Now let me tell you something..."},
    {"id": "opener_02", "text": "Let me be VERY clear about something..."},
    {"id": "opener_03", "text": "You want to know what the REAL story is?"},
    {"id": "opener_04", "text": "I have been doing this for a LONG time..."},
    {"id": "opener_05", "text": "Quite frankly, I'm not sure people UNDERSTAND..."},
    {"id": "opener_06", "text": "This is something that NEEDS to be said..."},
    {"id": "opener_07", "text": "I was JUST talking to someone about this..."},
    {"id": "opener_08", "text": "LISTEN to me very carefully..."},
    {"id": "opener_09", "text": "I have TWO words for you..."},
    {"id": "opener_10", "text": "Before we go any further, let me say THIS..."},
    {"id": "opener_11", "text": "I don't say this LIGHTLY..."},
    {"id": "opener_12", "text": "If you know me — and I think you DO..."},
    {"id": "opener_13", "text": "I've been watching this game since I was TWELVE years old..."},
    {"id": "opener_14", "text": "People keep asking me about this, so let me ADDRESS it..."},
    {"id": "opener_15", "text": "I sat down. I looked at the numbers. And I said to myself..."},
    {"id": "opener_16", "text": "I pulled up the game logs, the shot charts, the matchup data — ALL of it..."},
    {"id": "opener_17", "text": "You know what the FILM shows? Let me TELL you what the film shows..."},
    {"id": "opener_18", "text": "I just finished going through EVERY game log from the last two weeks..."},
    {"id": "opener_19", "text": "The numbers don't LIE — and I've got the RECEIPTS to prove it..."},
    {"id": "opener_20", "text": "I stayed up LATE crunching the splits, the trends, the matchup history..."},
    {"id": "opener_21", "text": "Let me break this down the way a REAL analyst breaks it down..."},
    {"id": "opener_22", "text": "I looked at the last TEN games. I looked at the splits. I looked at EVERYTHING..."},
    {"id": "opener_23", "text": "STOP scrolling and LISTEN because this analysis is backed by REAL data..."},
    {"id": "opener_24", "text": "I don't just give you OPINIONS — I give you ANALYSIS backed by NUMBERS..."},
    {"id": "opener_25", "text": "I've been studying the matchup data and the shot distribution ALL day..."},
]

PIVOT_POOL = [
    {"id": "pivot_01", "text": "HOWEVER..."},
    {"id": "pivot_02", "text": "But here's the thing..."},
    {"id": "pivot_03", "text": "Now with all DUE respect..."},
    {"id": "pivot_04", "text": "But let me tell you what CONCERNS me..."},
    {"id": "pivot_05", "text": "And THIS is where it gets interesting..."},
    {"id": "pivot_06", "text": "BUT — and this is a BIG but..."},
    {"id": "pivot_07", "text": "Now I don't want to hear the EXCUSES..."},
    {"id": "pivot_08", "text": "That being said..."},
    {"id": "pivot_09", "text": "BUT HERE'S WHAT NOBODY IS TALKING ABOUT..."},
    {"id": "pivot_10", "text": "Having said ALL of that..."},
    {"id": "pivot_11", "text": "Now the GAME LOGS tell a different story and you NEED to hear it..."},
    {"id": "pivot_12", "text": "But when I dig into the SPLITS — and I ALWAYS dig into the splits..."},
    {"id": "pivot_13", "text": "The MATCHUP data paints a different picture though..."},
    {"id": "pivot_14", "text": "But let me pull up the RECEIPTS on the other side of this argument..."},
    {"id": "pivot_15", "text": "NOW — before you go placing that bet, consider THIS..."},
]

CLOSER_POOL = [
    {"id": "closer_01", "text": "And I say that with GREAT conviction!"},
    {"id": "closer_02", "text": "Don't get it TWISTED!"},
    {"id": "closer_03", "text": "I'm not ASKING you — I'm TELLING you!"},
    {"id": "closer_04", "text": "And you can take THAT to the bank!"},
    {"id": "closer_05", "text": "MARK my words!"},
    {"id": "closer_06", "text": "This is Joseph M. Smith. I have SPOKEN!"},
    {"id": "closer_07", "text": "And if you disagree with me... you are WRONG!"},
    {"id": "closer_08", "text": "That's not an OPINION — that's a FACT!"},
    {"id": "closer_09", "text": "And I don't want to hear NOTHING about it!"},
    {"id": "closer_10", "text": "PERIOD. End of DISCUSSION!"},
    {"id": "closer_11", "text": "The DATA has spoken. Joseph M. Smith has spoken. It is DONE!"},
    {"id": "closer_12", "text": "I've shown you the numbers, I've shown you the trends — the rest is on YOU!"},
    {"id": "closer_13", "text": "That's not a GUESS — that's an analysis backed by EVERY available data point!"},
    {"id": "closer_14", "text": "The game logs DON'T LIE. The splits DON'T LIE. Joseph M. Smith DOESN'T LIE!"},
    {"id": "closer_15", "text": "I've done the HOMEWORK. Now it's time to CASH the ticket!"},
]

CATCHPHRASE_POOL = [
    {"id": "catch_01", "text": "Stay off the WEED!"},
    {"id": "catch_02", "text": "This man is a DEAR, DEAR friend of mine..."},
    {"id": "catch_03", "text": "How DARE you!"},
    {"id": "catch_04", "text": "PREPOSTEROUS!"},
    {"id": "catch_05", "text": "BLASPHEMOUS!"},
    {"id": "catch_06", "text": "EGREGIOUS!"},
    {"id": "catch_07", "text": "This is COACHING MALPRACTICE!"},
    {"id": "catch_08", "text": "I, Joseph M. Smith, am TELLING you..."},
    {"id": "catch_09", "text": "I don't want to HEAR about it!"},
    {"id": "catch_10", "text": "ABOMINATION!"},
    {"id": "catch_11", "text": "TRAVESTY!"},
    {"id": "catch_12", "text": "With all DUE respect — and I mean that SINCERELY..."},
    {"id": "catch_13", "text": "He's a FIRST-BALLOT Hall of Famer in my book!"},
    {"id": "catch_14", "text": "The ANALYTICS department just called — they AGREE with me!"},
    {"id": "catch_15", "text": "I've got game logs, shot charts, AND the eye test — what do YOU have?"},
    {"id": "catch_16", "text": "Don't bring me NARRATIVES — bring me NUMBERS!"},
    {"id": "catch_17", "text": "I've been doing this since BEFORE analytics was COOL!"},
    {"id": "catch_18", "text": "The FILM doesn't lie and neither does Joseph M. Smith!"},
]

# Placeholders used in templates: {player}, {stat}, {line}, {edge}, {prob}
BODY_TEMPLATES = {
    "SMASH": [
        "{player} OVER {line} {stat}? That's not even a QUESTION! {edge}% edge — the numbers are SCREAMING at you!",
        "I'm looking at {player} and I see a man on a MISSION. {prob}% probability to clear {line} {stat}. SMASH IT!",
        "The Quantum Matrix Engine says {edge}% edge on {player} {stat}. And you know what? I AGREE. This is a LOCK!",
        "{player} is going to FEAST tonight. {line} {stat} is DISRESPECTFUL to this man's talent. I'm all OVER it!",
        "You want to know my BEST play? {player} OVER {line} {stat}. {edge}% edge. I'd bet my REPUTATION on this one!",
    ],
    "LEAN": [
        "I LIKE {player} tonight. {edge}% edge on {line} {stat}. Not my strongest conviction but the VALUE is there.",
        "{player} at {line} {stat}? The numbers say {prob}% and I tend to AGREE. Solid lean, not a pound-the-table.",
        "There's a quiet little edge on {player} — {edge}% on {line} {stat}. Smart money NOTICES these things.",
        "{player} should get there. {line} {stat} with a {edge}% edge. I'm not screaming but I'm definitely LEANING.",
        "The model likes {player} at {line} {stat} and so does Joseph M. Smith. {edge}% — that's a PLAYABLE number.",
    ],
    "FADE": [
        "I'm FADING {player} tonight. {line} {stat} is a TRAP and I can see it from a MILE away!",
        "{player} at {line} {stat}? The edge is only {edge}%. That's not enough for me to put my NAME on it.",
        "Be CAREFUL with {player}. The number says {line} {stat} but the CONTEXT says fade. Trust the CONTEXT!",
        "I see the line on {player} at {line} {stat} and I'm walking the OTHER way. {edge}% is not worth the risk.",
        "{player} {stat} at {line}? The books got this one RIGHT. I'm fading and I suggest you do the SAME.",
    ],
    "STAY_AWAY": [
        "Do NOT touch {player} tonight. I don't care WHAT the line says. {line} {stat} is a TRAP!",
        "{player} at {line} {stat}? {edge}% edge? That's NOTHING! Stay AWAY and thank me later!",
        "I wouldn't bet {player} {stat} tonight if you PAID me. The edge isn't there. The context is WRONG. STAY AWAY!",
        "This is a PUBLIC SERVICE ANNOUNCEMENT: {player} {line} {stat} is DANGEROUS. Keep your money in your POCKET!",
        "{player} {stat} at {line}? I have TWO words for you: STAY. AWAY. And I mean that with CONVICTION!",
    ],
    "OVERRIDE": [
        "The machine says one thing. Joseph M. Smith says ANOTHER. I'm OVERRIDING the engine on {player} {line} {stat}!",
        "I DISAGREE with the Quantum Matrix Engine on {player}. {line} {stat}? The machine is MISSING something and I see it!",
        "This is where HUMAN intelligence beats artificial intelligence. {player} at {line} {stat}? The engine is WRONG!",
        "OVERRIDE ALERT! The numbers say {edge}% but my eyes tell me DIFFERENT on {player} {stat}. Trust the EYE TEST!",
        "The computer doesn't watch the GAMES. I DO. And I'm telling you — {player} {line} {stat} needs an OVERRIDE!",
    ],
}

# ═══════════════════════════════════════════════════════════════
# A-2) STAT-SPECIFIC BODY TEMPLATES
# ═══════════════════════════════════════════════════════════════

STAT_BODY_TEMPLATES = {
    "points": {
        "SMASH": [
            "{player} is averaging buckets at a CLIP that makes {line} points look like child's play. {edge}% edge — SMASH!",
            "The scoring output from {player} has been ELITE. {line} points? He does that in his SLEEP. {edge}% edge!",
            "{player} is in full GO-TO scorer mode right now. {line} points is too LOW — the books are behind on this one!",
        ],
        "LEAN": [
            "{player} should be able to score {line} points tonight — the matchup supports it. {edge}% edge, solid lean.",
            "The offensive workload for {player} puts him in range of {line} points. {edge}% edge — I like the value here.",
        ],
        "FADE": [
            "{player} at {line} points is a MIRAGE. The shot attempts haven't been there lately — FADE!",
            "The scoring volume on {player} has dipped. {line} points is TOO high given the recent shot diet.",
        ],
        "STAY_AWAY": [
            "{player} at {line} points? His usage rate doesn't support it. STAY AWAY!",
            "The scoring opportunities for {player} are LIMITED tonight. {line} points is a TRAP — don't touch it!",
        ],
        "OVERRIDE": [
            "I'm OVERRIDING the engine on {player} scoring. {line} points? My eye test says the shot volume is THERE. {edge}% edge!",
            "OVERRIDE! The machine underestimates {player}'s scoring ability tonight. {line} points is a GIFT!",
        ],
    },
    "rebounds": {
        "SMASH": [
            "{player} DOMINATES the glass. {line} boards? He's going to FEAST on the offensive glass tonight. {edge}% edge!",
            "{player} is a WRECKING BALL on the boards. {line} rebounds is DISRESPECTFUL to this man's effort level!",
            "The rebounding matchup SCREAMS {player}. {line} boards? He's going to OWN the paint tonight!",
        ],
        "LEAN": [
            "{player} has been crashing the glass consistently. {line} rebounds with a {edge}% edge — I lean OVER.",
            "The frontcourt matchup gives {player} extra opportunities on the boards. {line} rebounds should be within reach.",
        ],
        "FADE": [
            "{player} at {line} rebounds is a STRETCH. The opposing bigs box out hard and limit second chances.",
            "Rebounding is about positioning and {player} hasn't had favorable matchups. {line} boards is too high — FADE!",
        ],
        "STAY_AWAY": [
            "{player} at {line} rebounds? The minutes and matchup don't add up. STAY AWAY from the glass on this one!",
            "The rebounding opportunities are NOT there for {player} tonight. {line} boards is a NUMBER I can't back.",
        ],
        "OVERRIDE": [
            "OVERRIDE on {player} boards! The engine doesn't see the rebounding MISMATCH I see. {line} is too low. {edge}% edge!",
            "I'm OVERRIDING the machine on {player} rebounds. The GLASS belongs to him tonight!",
        ],
    },
    "assists": {
        "SMASH": [
            "{player} is the CONDUCTOR of that offense. {line} dimes? His playmaking is on ANOTHER level right now. {edge}% edge!",
            "{player}'s court vision has been SURGICAL. {line} assists is LOW for a player creating THIS many looks. SMASH!",
            "The passing lanes are WIDE OPEN for {player}. {line} assists is a number he's been blowing past. {edge}% edge!",
        ],
        "LEAN": [
            "{player} has been finding teammates at a nice rate. {line} assists with a {edge}% edge — the playmaking supports it.",
            "The offensive system funnels opportunities through {player}. {line} dimes is achievable. Lean OVER.",
        ],
        "FADE": [
            "{player} at {line} assists? The ball movement hasn't been running through him lately. FADE the dimes!",
            "Assist numbers require teammates to CONVERT. {player} at {line} is inflated given the team's recent shooting.",
        ],
        "STAY_AWAY": [
            "{player} at {line} assists? His on-ball creation has dropped OFF. STAY AWAY from the dimes tonight!",
            "The playmaking volume for {player} doesn't support {line} assists. This is a NUMBER to avoid!",
        ],
        "OVERRIDE": [
            "OVERRIDE on {player} dimes! The engine is SLEEPING on his playmaking. {line} assists? He's COOKING. {edge}% edge!",
            "I'm OVERRIDING the machine on {player} assists. The passing lanes are WIDE OPEN tonight!",
        ],
    },
    "steals": {
        "SMASH": [
            "{player} has been a PICKPOCKET lately — active hands, quick anticipation. {line} steals is too low. {edge}% edge!",
            "The defensive pressure from {player} is RELENTLESS. {line} steals? This matchup is a STEAL factory. SMASH!",
        ],
        "LEAN": [
            "{player}'s defensive activity has been up. {line} steals with a {edge}% edge — the deflection numbers support it.",
            "The opposing guards are careless with the ball and {player} PREYS on that. Lean OVER on {line} steals.",
        ],
        "FADE": [
            "{player} at {line} steals is a GAMBLE. Steal props are volatile and the matchup doesn't favor it. FADE!",
            "Steals are the MOST unpredictable stat and {player} at {line} is not a number I trust tonight.",
        ],
        "STAY_AWAY": [
            "{player} at {line} steals? Steals are HIGH variance by nature and this line is a TRAP!",
            "The defensive scheme doesn't put {player} in passing lanes often enough. {line} steals? STAY AWAY!",
        ],
        "OVERRIDE": [
            "OVERRIDE on {player} steals! I've watched the FILM — the opposing guards are SLOPPY. {edge}% edge!",
            "I'm OVERRIDING the engine on {player} steals. Active hands plus a careless opponent equals FREE steals!",
        ],
    },
    "blocks": {
        "SMASH": [
            "{player} is a RIM PROTECTOR supreme. {line} blocks? He's going to be SWATTING shots all night. {edge}% edge!",
            "The opposing team attacks the rim and {player} is WAITING for them. {line} blocks is too low. SMASH!",
        ],
        "LEAN": [
            "{player} has been altering shots at the rim consistently. {line} blocks with a {edge}% edge — lean OVER.",
            "The shot-blocking matchup favors {player}. {line} blocks is achievable given the opponent's rim attack rate.",
        ],
        "FADE": [
            "{player} at {line} blocks? The opposing team AVOIDS the paint. Not enough rim attempts to generate blocks. FADE!",
            "Block props require the opponent to ATTACK the rim. This matchup doesn't set up well for {player} tonight.",
        ],
        "STAY_AWAY": [
            "{player} at {line} blocks? Blocks are FEAST or FAMINE. This isn't a matchup that supports it. STAY AWAY!",
            "The rim protection numbers are DOWN for {player}. {line} blocks is a line I want NO part of!",
        ],
        "OVERRIDE": [
            "OVERRIDE on {player} blocks! The opponent's paint attack rate is SKY HIGH and the engine missed it. {edge}% edge!",
            "I'm OVERRIDING the machine on {player} rim protection. This matchup is a SWAT FEST waiting to happen!",
        ],
    },
    "threes": {
        "SMASH": [
            "{player} has been LIGHTS OUT from deep. {line} threes is DISRESPECTFUL — this man is a SNIPER. {edge}% edge!",
            "The three-point shooting from {player} has been SCORCHING. {line} triples? He's been RAINING them in. SMASH!",
        ],
        "LEAN": [
            "{player}'s three-point volume and accuracy support clearing {line}. {edge}% edge — lean OVER on the triples.",
            "The shooting splits for {player} from beyond the arc make {line} threes a reasonable play.",
        ],
        "FADE": [
            "{player} at {line} threes is a TRAP. The shot attempts from deep have been inconsistent. FADE!",
            "Three-point shooting is STREAKY by nature. {player} at {line} is a line the books set RIGHT. FADE!",
        ],
        "STAY_AWAY": [
            "{player} at {line} threes? The shooting volume from distance doesn't support it. STAY AWAY!",
            "The three-point variance is TOO HIGH on {player}. {line} is a number to avoid COMPLETELY!",
        ],
        "OVERRIDE": [
            "OVERRIDE on {player} from deep! The engine doesn't see the SHOOTER'S TOUCH I see. {line} threes is LOW. {edge}% edge!",
            "I'm OVERRIDING the machine on {player} threes. He's been getting OPEN looks all week. MONEY from deep!",
        ],
    },
    "turnovers": {
        "SMASH": [
            "{player} has been CARELESS with the ball lately. OVER {line} turnovers is the play — the handle has been LOOSE. {edge}% edge!",
            "The ball security from {player} has been TERRIBLE. {line} turnovers? He's been coughing it up at an alarming rate!",
        ],
        "LEAN": [
            "{player} tends to get sloppy against defensive pressure. {line} turnovers with a {edge}% edge — lean OVER.",
            "The turnover-prone matchup puts {player} at risk. {line} turnovers is a realistic number tonight.",
        ],
        "FADE": [
            "{player} at {line} turnovers? He's been protecting the ball well. The UNDER is the play here. FADE the over!",
            "Turnover props are TRICKY and {player} has been disciplined. {line} is too high — FADE!",
        ],
        "STAY_AWAY": [
            "{player} at {line} turnovers is UNPREDICTABLE. Turnover counts swing wildly game to game. STAY AWAY!",
            "Turnover props are the ROULETTE WHEEL of the prop market. {player} at {line} is not worth the risk!",
        ],
        "OVERRIDE": [
            "OVERRIDE on {player} turnovers! The engine doesn't see the PRESSURE this defense applies. {edge}% edge!",
            "I'm OVERRIDING the machine on {player} turnovers. The ball security issues are REAL and the data backs me up!",
        ],
    },
    "fantasy": {
        "SMASH": [
            "{player} fills up EVERY column of the stat sheet. {line} fantasy points? He contributes EVERYWHERE. {edge}% edge!",
            "The all-around production from {player} makes {line} fantasy points a LOCK. This man does it ALL. SMASH!",
        ],
        "LEAN": [
            "{player}'s multi-category production supports {line} fantasy points. {edge}% edge — the versatility is real.",
            "The fantasy floor for {player} is HIGH because he contributes across all categories. Lean OVER on {line}.",
        ],
        "FADE": [
            "{player} at {line} fantasy points? The usage and minutes might not support it tonight. FADE!",
            "Fantasy points require production across the board and {player}'s workload is a CONCERN. FADE!",
        ],
        "STAY_AWAY": [
            "{player} at {line} fantasy points? Too many variables need to break right. STAY AWAY!",
            "The fantasy ceiling for {player} is CAPPED by the matchup tonight. {line} is a TRAP!",
        ],
        "OVERRIDE": [
            "OVERRIDE on {player} fantasy! The engine misses the ALL-AROUND production this man brings. {edge}% edge!",
            "I'm OVERRIDING the machine on {player} fantasy points. He stuffs the stat sheet in EVERY category!",
        ],
    },
    "fouls": {
        "SMASH": [
            "{player} has been in FOUL TROUBLE constantly. OVER {line} fouls is the play — he can't keep his hands to himself! {edge}% edge!",
            "The officiating crew tonight calls it TIGHT and {player} ALWAYS picks up cheap fouls. OVER {line} is a SMASH!",
            "{player} guards aggressive drivers ALL game. {line} fouls? He's going to be WHISTLED early and often!",
        ],
        "LEAN": [
            "{player} has been averaging foul trouble lately. {line} fouls with a {edge}% edge — the matchup drives contact.",
            "The opponent attacks the paint and {player} is the primary defender. {line} fouls is realistic.",
        ],
        "FADE": [
            "{player} at {line} fouls? He's been DISCIPLINED lately. The foul rate has DROPPED. FADE!",
            "Foul props are TRICKY. {player} has stayed out of trouble recently — {line} is too high. FADE!",
        ],
        "STAY_AWAY": [
            "{player} at {line} fouls? Foul props are the MOST unpredictable in the market. STAY AWAY!",
            "Fouls depend on referees more than players. {player} at {line} is pure COIN FLIP territory!",
        ],
        "OVERRIDE": [
            "I'm OVERRIDING the engine on {player} fouls. I've watched the film — this man fouls on EVERY drive. {edge}% edge!",
            "OVERRIDE on {player} {line} fouls! The ref crew tonight is WHISTLE-HAPPY and {player} can't help himself!",
        ],
    },
    "minutes": {
        "SMASH": [
            "{player} is LOCKED into the rotation. {line} minutes? He's playing HEAVY minutes — the coach NEEDS him. {edge}% edge!",
            "The minutes load on {player} has been MASSIVE. {line} minutes is LOW for how much he's been on the floor. SMASH!",
        ],
        "LEAN": [
            "{player} has been consistently logging minutes. {line} with a {edge}% edge — the rotation supports it.",
            "The coach trusts {player} in crunch time. {line} minutes should be within reach. Lean OVER.",
        ],
        "FADE": [
            "{player} at {line} minutes? Blowout risk could CUT into playing time. FADE!",
            "Minutes are the MOST vulnerable stat to game flow. {player} at {line} is RISKY — FADE!",
        ],
        "STAY_AWAY": [
            "{player} at {line} minutes? Game script and foul trouble can KILL minutes. STAY AWAY!",
            "Minute props are a COIN FLIP based on game flow. {player} at {line} is not worth the variance!",
        ],
        "OVERRIDE": [
            "OVERRIDE! The engine doesn't account for how INDISPENSABLE {player} is right now. {line} minutes is LOW. {edge}% edge!",
            "I'm OVERRIDING on {player} minutes. This team CANNOT afford to sit him. {line} is a GIFT!",
        ],
    },
    "combo": {
        "SMASH": [
            "{player} fills up the stat sheet EVERY night. {line} combined? His multi-category production makes this a SMASH! {edge}% edge!",
            "When you combine categories, {player} is ELITE. {line} is a LOW bar for this man's all-around game. SMASH!",
            "{player} contributes in EVERY way possible. {line} combined is DISRESPECTFUL to his versatility!",
        ],
        "LEAN": [
            "{player}'s all-around game supports clearing {line} combined. {edge}% edge — the versatility is real.",
            "Combo props reward well-rounded players and {player} checks EVERY box. Lean OVER on {line}.",
        ],
        "FADE": [
            "{player} at {line} combined? One category needs to CARRY and it's not guaranteed. FADE!",
            "Combo props SOUND safe but need production across MULTIPLE stats. {player} at {line} is a STRETCH. FADE!",
        ],
        "STAY_AWAY": [
            "{player} at {line} combined? Combo props add VARIANCE on top of variance. STAY AWAY!",
            "Combined stats look easy but they're DECEPTIVE. {player} at {line} is a TRAP I want no part of!",
        ],
        "OVERRIDE": [
            "OVERRIDE on {player}! The engine misses the SYNERGY in this man's game. {line} combined? LOCK it in! {edge}% edge!",
            "I'm OVERRIDING the machine on {player} combo. He does it ALL and {line} is too LOW!",
        ],
    },
    "double_double": {
        "SMASH": [
            "{player} gets double-doubles in his SLEEP. This is a man who fills up TWO categories every single night. SMASH! {edge}% edge!",
            "A double-double for {player}? That's not a QUESTION — that's a STATEMENT. He does this EVERY game. SMASH!",
        ],
        "LEAN": [
            "{player} has been flirting with double-doubles regularly. {edge}% edge — the multi-category production supports it.",
            "The workload and role for {player} put him in double-double range. Lean toward YES on this one.",
        ],
        "FADE": [
            "Double-doubles require ELITE production in TWO categories simultaneously. {player} hasn't been CONSISTENT enough. FADE!",
            "{player} reaching a double-double depends on too many variables tonight. The matchup isn't ideal — FADE!",
        ],
        "STAY_AWAY": [
            "Double-double props are BINARY — yes or no. The variance is MASSIVE. STAY AWAY from {player} on this!",
            "{player} for a double-double? Too many things need to break RIGHT. This is GAMBLING, not analysis. STAY AWAY!",
        ],
        "OVERRIDE": [
            "OVERRIDE! The engine doesn't capture {player}'s DOMINANCE in two categories. Double-double is GUARANTEED. {edge}% edge!",
            "I'm OVERRIDING the machine. {player} is a LOCK for a double-double. The eye test says YES!",
        ],
    },
    "free_throws": {
        "SMASH": [
            "{player} gets to the FREE THROW LINE at will. {line} is LOW for a player who ATTACKS the basket this hard! {edge}% edge!",
            "{player} draws fouls like a MAGNET. {line} free throws? He's getting to the line ALL night. SMASH!",
        ],
        "LEAN": [
            "{player} has been getting to the line consistently. {line} with a {edge}% edge — the FTA rate supports it.",
            "The aggression from {player} generates free throw opportunities. {line} is achievable. Lean OVER.",
        ],
        "FADE": [
            "{player} at {line} free throws? He hasn't been attacking the rim enough to generate the attempts. FADE!",
            "Free throw props require FREE THROW ATTEMPTS first. {player}'s recent approach doesn't support {line}. FADE!",
        ],
        "STAY_AWAY": [
            "{player} at {line} free throws? FT props depend on officiating AND aggressiveness. Too many variables. STAY AWAY!",
            "Free throw volume is one of the HARDEST stats to predict. {player} at {line} is a GAMBLE!",
        ],
        "OVERRIDE": [
            "OVERRIDE on {player} free throws! The engine misses how AGGRESSIVELY he attacks. {line} is too low! {edge}% edge!",
            "I'm OVERRIDING the machine on {player} free throws. This man LIVES at the free throw line!",
        ],
    },
    "field_goals": {
        "SMASH": [
            "{player} is putting up SHOTS at an elite rate. {line} field goals? His shot volume makes this a SMASH! {edge}% edge!",
            "The shot attempts for {player} have been MASSIVE. {line} is LOW for his current usage. SMASH!",
        ],
        "LEAN": [
            "{player}'s shot volume and efficiency support clearing {line}. {edge}% edge — lean OVER on the field goals.",
            "The usage rate for {player} puts him in range of {line}. Lean OVER on the field goal prop.",
        ],
        "FADE": [
            "{player} at {line} field goals? The shot distribution hasn't been concentrated enough. FADE!",
            "Field goal props need VOLUME and {player}'s recent shot attempts don't support {line}. FADE!",
        ],
        "STAY_AWAY": [
            "{player} at {line} field goals? Shot volume swings WILDLY with game flow. STAY AWAY!",
            "Field goal count depends on pace, game script, and shot selection. {player} at {line} is a TRAP!",
        ],
        "OVERRIDE": [
            "OVERRIDE on {player} field goals! The usage rate is SPIKING and the engine hasn't caught up. {edge}% edge!",
            "I'm OVERRIDING on {player} field goals. The shot volume is THERE — {line} is too LOW!",
        ],
    },
}

# Data-driven sentence templates — populated by _build_data_sentences()
DATA_BODY_TEMPLATES = {
    "trend_hot": [
        "{player} is averaging {l3_avg} {stat} over the last 3 games — that's ABOVE the {l10_avg} ten-game average. The trend is your FRIEND!",
        "The last THREE games? {l3_avg} {stat} per game. The last TEN? {l10_avg}. {player} is getting HOTTER and the line hasn't caught up!",
        "{player} is SURGING — {l3_avg} {stat} in the last 3, {l5_avg} over 5. The books are slow to ADJUST and that's YOUR edge!",
    ],
    "trend_cold": [
        "{player} has dipped to {l3_avg} {stat} over the last 3 — down from {l10_avg} over 10. The slump is REAL and the line hasn't moved.",
        "CAUTION — {player} is trending DOWN. {l3_avg} {stat} lately versus {l10_avg} on the season stretch. The cold streak MATTERS.",
        "The recent form says {l3_avg} {stat} over the last 3 games. The trend is NOT your friend on {player} right now.",
    ],
    "hit_rate": [
        "{player} has cleared {line} {stat} in {hit_rate}% of the last 10 games. That's not an OPINION — that's a FACT from the game logs!",
        "The HIT RATE on {player} over {line} {stat}? {hit_rate}% in the last 10 outings. The data speaks LOUDER than any analyst!",
        "I pulled the RECEIPTS — {player} has gone over {line} {stat} in {hit_rate}% of recent games. The numbers don't LIE!",
    ],
    "consistency": [
        "{player} has been {consistency} with {stat} production — and that MATTERS for prop betting. You want PREDICTABLE outcomes!",
        "The consistency rating on {player} for {stat} is '{consistency}'. That tells me the FLOOR and CEILING are well-defined.",
    ],
    "home_away": [
        "{player} is a DIFFERENT player on the road versus at home. {home_away_note}. Context is KING!",
        "The home/away split on {player} is SIGNIFICANT. {home_away_note}. You HAVE to factor that in!",
    ],
    "season_vs_line": [
        "{player} averages {season_avg} {stat} on the season and the line is set at {line}. That's a {edge}% edge and the math is SIMPLE!",
        "Season average: {season_avg} {stat}. Line: {line}. The GAP between those numbers is where the MONEY lives!",
    ],
}

# ═══════════════════════════════════════════════════════════════
# B) AMBIENT COLOUR POOLS — scene-setting flavour text
# ═══════════════════════════════════════════════════════════════

AMBIENT_CONTEXT_POOL = {
    "high_stakes": [
        "The lights are BRIGHT and the pressure is ON!",
        "This is a PRIMETIME matchup and the whole world is watching!",
        "You can FEEL the energy through your screen tonight!",
        "This is what the NBA is ALL about — big games, big moments!",
        "The stakes could NOT be higher tonight!",
    ],
    "rivalry": [
        "This rivalry goes DEEP and the players know it!",
        "There's BAD BLOOD here and it's going to show on the court!",
        "You want INTENSITY? This matchup HAS it!",
        "When these two teams meet, you THROW the records out the window!",
        "This is a GRUDGE match and both sides know it!",
    ],
    "blowout_risk": [
        "Be CAREFUL — if this game gets out of hand, starters are sitting!",
        "Blowout risk is REAL tonight. Watch the spread!",
        "If one team takes control early, the benches could be in by the FOURTH!",
        "This mismatch SCREAMS early blowout — manage your expectations!",
        "Garbage time is a prop KILLER and I see it lurking tonight!",
    ],
    "back_to_back": [
        "Back-to-back games are NO joke — fatigue is a FACTOR!",
        "Second night of a back-to-back. Legs get HEAVY, shots fall SHORT!",
        "Rest matters in this league. And this team did NOT get it!",
        "The schedule-maker is the invisible DEFENDER tonight!",
        "Back-to-backs separate the MEN from the boys!",
    ],
    "neutral": [
        "Just another night in the NBA — but EVERY night matters!",
        "Let's break down the numbers and find the VALUE!",
        "The board is set. The pieces are moving. Let's ANALYZE!",
        "I've been studying this slate ALL day. Here's what I see...",
        "No drama tonight — just cold, hard ANALYSIS!",
    ],
}

# ═══════════════════════════════════════════════════════════════
# C) COMMENTARY COLOUR POOLS — per-stat flavour lines
# ═══════════════════════════════════════════════════════════════

STAT_COMMENTARY_POOL = {
    "points": [
        "Scoring is an ART and {player} is a MASTER of it!",
        "{player} can get a bucket from ANYWHERE on the floor!",
        "When {player} gets going, there is NO stopping this man!",
        "The scoring title isn't given — it's TAKEN. And {player} is taking it!",
        "Points are the CURRENCY of the NBA and {player} is RICH!",
    ],
    "rebounds": [
        "{player} attacks the glass like it OWES him money!",
        "Rebounding is about EFFORT and WANT — {player} has BOTH!",
        "The boards belong to {player} tonight — mark my WORDS!",
        "{player} is going to be a MONSTER on the glass!",
        "You can't teach rebounding INSTINCTS. {player} was BORN with them!",
    ],
    "assists": [
        "{player} sees passes that NOBODY else can see!",
        "Court vision like {player}? That's a GIFT from the basketball GODS!",
        "{player} makes everyone around him BETTER — that's what assists DO!",
        "The ball moves DIFFERENT when {player} has it in his hands!",
        "{player} is a MAESTRO with the basketball — conducting the OFFENSE!",
    ],
    "threes": [
        "{player} from DOWNTOWN — that's MONEY in the bank!",
        "The three-point line is {player}'s HOME ADDRESS!",
        "When {player} gets HOT from three, you better PRAY!",
        "Deep threes are the GREAT equalizer and {player} has the RANGE!",
        "{player} is LETHAL from beyond the arc!",
    ],
    "steals": [
        "{player} has HANDS like a PICKPOCKET out there!",
        "Active hands, quick feet — {player} is a NIGHTMARE for ball-handlers!",
        "{player} turns defense into OFFENSE with those steals!",
        "You can't be CARELESS with the ball when {player} is on the floor!",
        "{player} is a THIEF and he's PROUD of it!",
    ],
    "blocks": [
        "{player} is a WALL at the rim — good LUCK getting past him!",
        "Shot-blocking is about TIMING and {player} has a CLOCK in his head!",
        "{player} is going to send some shots into the FIFTH ROW tonight!",
        "The paint belongs to {player} — enter at your OWN risk!",
        "{player} is a RIM PROTECTOR of the highest ORDER!",
    ],
    "turnovers": [
        "Turnovers are the SILENT killer of NBA props!",
        "{player}'s handle can get LOOSE under pressure — watch for it!",
        "Ball security is NO joke and {player} needs to be CAREFUL!",
        "Turnovers are like TAXES — they come for EVERYONE eventually!",
        "If {player} gets sloppy, the turnovers WILL pile up!",
    ],
    "fantasy": [
        "{player} stuffs the stat sheet like NOBODY else!",
        "Fantasy points reward VERSATILITY and {player} has it in SPADES!",
        "{player} contributes in EVERY category — that's ELITE!",
        "When you look at fantasy production, {player} is a ONE-MAN army!",
        "{player} is a SWISS ARMY KNIFE of basketball production!",
    ],
    "personal_fouls": [
        "{player} picks up fouls like they're GOING OUT OF STYLE!",
        "Foul trouble is {player}'s middle name — referees LOVE blowing that whistle!",
        "When {player} guards aggressive players, the fouls PILE UP!",
        "{player} can't keep his hands to himself and the refs are WATCHING!",
        "The whistle is {player}'s WORST enemy out there tonight!",
    ],
    "minutes": [
        "{player} is an IRON MAN — this man logs HEAVY minutes every night!",
        "The coaching staff TRUSTS {player} to be out there when it matters!",
        "Minutes are the FOUNDATION of every other stat and {player} gets PLENTY!",
        "{player}'s conditioning is ELITE — he can play 35+ minutes without breaking a sweat!",
        "When the game is CLOSE, {player} is NOT coming off the floor!",
    ],
    "double_double": [
        "{player} getting a double-double is like the SUN rising — it just HAPPENS!",
        "A double-double for {player}? That's a TUESDAY for this man!",
        "{player} dominates TWO categories every single night — that's RARE talent!",
        "When you can get a double-double CONSISTENTLY, you're in ELITE company. {player} IS that company!",
        "{player} fills up the stat sheet in MULTIPLE columns — that's a COMPLETE player!",
    ],
    "combo": [
        "Combined stats are where {player} SHINES — he does it ALL!",
        "{player} is a MULTI-TOOL weapon who contributes EVERYWHERE on the floor!",
        "When you add up ALL the categories, {player} is one of the BEST in the league!",
        "Combo props LOVE versatile players and {player} is the DEFINITION of versatile!",
        "{player} doesn't just score — he rebounds, assists, and IMPACTS every possession!",
    ],
    "free_throws": [
        "{player} gets to the FREE THROW LINE by attacking the basket with FORCE!",
        "Drawing fouls is an ART and {player} is a MASTER of it!",
        "{player} lives at the charity stripe — he DEMANDS contact!",
        "Free throws are FREE points and {player} EARNS them every night!",
        "The whistle LOVES {player} because he plays with AGGRESSION!",
    ],
    "field_goals": [
        "{player} puts up shots with CONFIDENCE and CONVICTION!",
        "Shot volume is KING in the prop market and {player} SHOOTS!",
        "{player}'s shot attempts are THROUGH THE ROOF — this man HUNTS his shot!",
        "When {player} gets in rhythm, the field goals come in BUNCHES!",
        "You can't score without SHOOTING and {player} is NOT afraid to let it fly!",
    ],
}

# ═══════════════════════════════════════════════════════════════
# B) AMBIENT COMMENTARY POOLS — Joseph is NEVER silent
# ═══════════════════════════════════════════════════════════════

AMBIENT_POOLS = {
    "idle": [
        "You KNOW I'm ready for tonight's slate. Load those games!",
        "Joseph M. Smith doesn't SLEEP on game day. Let's get to WORK!",
        "You came to the RIGHT place. Now load those games and let me cook!",
        "SmartBetPro with Joseph M. Smith... you are in GOOD hands.",
        "I've been studying the matchups ALL day. Hit that Load Games button!",
        "The Quantum Matrix Engine is ready. I'M ready. Are YOU ready?",
        "Don't just sit there! Go to Live Games and let's GET IT!",
        "Every night is an OPPORTUNITY. Let me show you where the edge is.",
        "I didn't become the greatest analyst alive by WAITING. Load the slate!",
        "SmartBetPro doesn't miss. And neither does Joseph M. Smith.",
        "The numbers don't lie, my friend. But first we need TONIGHT'S numbers.",
        "You want WINNERS? Then stop stalling and load the games!",
        "I can FEEL it in my bones... tonight's slate is going to be SPECIAL.",
        "Trust the process. Trust the engine. Trust JOSEPH M. SMITH.",
        "This app is a WEAPON. And I am the man who pulls the trigger.",
    ],
    "games_loaded": [
        "{n} games tonight. I ALREADY know which ones I like. Run the analysis!",
        "The slate is SET. Now let me show you where the MONEY is.",
        "I see {n} games. I see OPPORTUNITY. Hit Run Analysis and let me WORK.",
        "The games are loaded. The engine is HUMMING. Let's find those edges!",
        "I've been waiting ALL day for this. {n} games. Let's GO!",
        "Don't make me wait! Run that analysis so I can give you my TAKES.",
        "Good — you loaded the slate. Now the REAL work begins.",
        "I'm looking at {n} matchups and I already see MISMATCHES.",
        "Tonight's slate has some INTERESTING games. Let me break it down.",
        "You did the right thing loading these games. Now let me do MY thing.",
        "The Quantum Matrix Engine is READY. Joseph M. Smith is READY. Run it!",
        "{n} games, HUNDREDS of props. Let me find the diamonds.",
        "I see tonight's slate and I am EXCITED. This has Joseph's fingerprints.",
        "Every game is a STORY. Run the analysis and let me tell you the story.",
        "I've got {n} games to break down and I am FIRED UP about it!",
    ],
    "analysis_complete": [
        "I've seen the numbers. I've got {smash_count} SMASH picks tonight. Click me!",
        "The engine has SPOKEN. Now let Joseph M. Smith tell you what it MEANS.",
        "{total} props analyzed. {platinum} Platinum picks. This slate is LOADED!",
        "I see some BEAUTIFUL edges tonight. Click my face and I'll tell you.",
        "The Quantum Matrix Engine found the value. Now I add the WISDOM.",
        "Analysis COMPLETE. I've logged my bets. Have you built YOUR entries?",
        "{smash_count} picks I would bet my REPUTATION on. That's not nothing!",
        "I've been through every prop. I know EXACTLY where the money is.",
        "The data is IN. My analysis is DONE. Are you ready to hear it?",
        "I found {override_count} places where I DISAGREE with the machine.",
        "Go to The Studio and let me walk you through tonight's BEST plays.",
        "The numbers are SCREAMING at me. Click my face. Let me explain.",
        "I've already logged {logged_count} bets. Track my record on The Studio.",
        "Tonight's slate? I give it a {grade}/10. Click me for the breakdown.",
        "If you don't check my picks tonight... that's on YOU. Don't blame me.",
    ],
    "entry_built": [
        "NOW we're cooking! That {n}-leg looks SOLID to me!",
        "I like what I see! {n} legs, positive EV... you're learning!",
        "That's a SMART entry. But let me tell you which one I'D build...",
        "Good parlay! But click me — I might have a BETTER one for you.",
        "You built a {n}-legger? I respect it. But have you seen MY tickets?",
        "SOLID entry! The correlation looks CLEAN on that one.",
        "You're building entries like a PRO now. SmartBetPro made you dangerous!",
        "That EV is looking TASTY. I approve of this entry!",
        "A {n}-leg parlay? Let me tell you — the math SUPPORTS that one.",
        "{n} legs of FIRE! I'd put that right alongside my own picks.",
        "You just built what I would have built. GREAT minds think alike!",
        "THAT is how you build a parlay. Correlated? Check. +EV? Check. MONEY!",
        "I see you're using the Entry Builder. GOOD. That's where the magic is.",
        "The entry looks right. But remember — check my Build My Bets on The Studio!",
        "Beautiful entry. Now build 2 more to diversify. That's SMART money.",
    ],
    "premium_pitch": [
        "You're using the FREE version? My friend, you are MISSING OUT!",
        "I, Joseph M. Smith, am TELLING you — Premium is where the REAL edge is.",
        "3 props? That's ALL you get? Upgrade to Premium and unleash the FULL power!",
        "You want to win? REALLY win? Premium gives you UNLIMITED analysis.",
        "Free tier is like watching the game on MUTE. Premium gives you MY voice!",
        "Do you know what Premium users get? MY full analysis. The Studio. EVERYTHING.",
        "This is not a GAME. If you're serious, upgrade to Premium. PERIOD.",
        "I've seen the numbers — Premium users have a SIGNIFICANT edge. Just saying.",
        "You're leaving MONEY on the table with the free tier. Don't do that to yourself!",
        "Premium unlocks my FULL brain. ALL the props. Every rant. Every override.",
        "The free version is nice. Premium is a WEAPON. Choose wisely.",
        "Would you go to a 5-star restaurant and only eat the BREAD? Upgrade!",
        "I don't say this lightly — Premium is the best investment you'll make this month.",
        "SmartBetPro Premium with Joseph M. Smith... that's UNFAIR to the books.",
        "The Quantum Matrix Engine at full power? That's Premium. Don't sell yourself short.",
    ],
    "commentary_on_results": [
        "That {player} OVER {line} {stat}? I'm ALL OVER that! {edge}% edge!",
        "{player} has been COOKING lately. The model sees {prob}% hit rate. SMASH!",
        "I would NOT touch {player} tonight. Trap game. STAY AWAY!",
        "{player} vs {opponent}? That's a MISMATCH! {direction} all day!",
        "Platinum pick alert! {player} {direction} {line} {stat}. This is MONEY!",
        "{player} on a back-to-back? That's a FADE for me. Dead legs.",
        "Revenge game for {player}? You KNOW what time it is! SMASH!",
        "The engine found a {edge}% edge on {player}. I AGREE.",
        "Be careful with {player} tonight. {reason}.",
        "{player} has a gravity score of {gravity}. He WARPS the defense!",
        "That's a {tier} tier pick. You KNOW that's reliable!",
        "I see {n} Platinum picks tonight. The slate is JUICY.",
        "{player} and {player2} in the same parlay? The correlation is BEAUTIFUL.",
        "I found an OVERRIDE on {player}. The machine is WRONG about this one!",
        "{player}'s matchup grade is {grade}. That tells you EVERYTHING!",
    ],
    "playoff_atmosphere": [
        "PLAYOFF basketball is here! The energy is DIFFERENT. The stakes are REAL!",
        "Postseason time! Rotations shrink, minutes go UP, and props get VOLATILE!",
        "This is what we've been WAITING for all regular season — PLAYOFF TIME!",
        "The playoffs are a DIFFERENT animal. The analysis changes. The intensity CHANGES!",
        "Every game from here on out MATTERS. No nights off. No coasting. PLAYOFFS!",
        "Series basketball means ADJUSTMENTS. What worked in Game 1 might NOT work in Game 4!",
        "The crowd is ELECTRIC! Playoff home games hit DIFFERENT — the energy is INSANE!",
        "We're in the postseason now. Regular season data gets REWEIGHTED. Playoff splits MATTER!",
        "Elimination-round basketball is the PUREST form of the sport. And I LIVE for it!",
        "This is where franchises make HISTORY or become FOOTNOTES. PLAYOFF ENERGY!",
        "The scouting reports are a hundred pages DEEP now. Coaches know EVERY play from the series!",
        "Playoff crowds are the SIXTH MAN! The road team has to fight the fans AND the opponent!",
        "Deep in the postseason fatigue becomes a FACTOR. Heavy minutes, short rest, LONG series!",
        "Championship-or-bust mentality takes OVER. Every player is leaving it ALL on the floor!",
        "This isn't just basketball anymore — this is the playoffs and it's PERSONAL!",
    ],
    "page_home": [
        "Welcome to SmartBetPro! Joseph M. Smith is IN THE BUILDING!",
        "You just loaded the BEST NBA analysis engine on the PLANET!",
        "Start by heading to Live Games and loading tonight's slate!",
        "Every tool you need is RIGHT HERE. Let's make some MONEY!",
        "The Quantum Matrix Engine is WARMED UP and ready to go!",
        "Explore the sidebar — every page is a WEAPON in your arsenal!",
        "I built this system from the GROUND UP. Trust the process!",
        "New here? Hit Live Games first, then let me do the REST!",
        "This ain't your average betting app. This is JOSEPH'S domain!",
        "Load games, scan props, build entries — it ALL starts here!",
        "SmartBetPro has EVERYTHING. Analysis, tracking, simulation!",
        "You're sitting in the cockpit of a MACHINE. Let's fly!",
        "The home base of GREATNESS. Pick a page and let's WORK!",
        "I've got props, correlations, sims — what do you NEED?",
        "Joseph M. Smith welcomes you. Now let's CRUSH this slate!",
    ],
    "page_live_games": [
        "Hit that Load Games button and let me COOK!",
        "Tonight's matchups are WAITING. Load them up RIGHT NOW!",
        "Rosters auto-load when you retrieve games. It's AUTOMATIC!",
        "I need those games loaded so I can find the EDGES!",
        "The slate is out there. Bring it to me and I'll DISSECT it!",
        "Loading games pulls rosters, injuries, and matchups. ALL of it!",
        "You can't analyze what you don't LOAD. Hit that button!",
        "Fresh games mean fresh OPPORTUNITIES. Let's get them in!",
        "Every night is a new slate. Load it and let me WORK!",
        "The matchups tonight are looking SPICY. Load them up!",
        "I can smell the edges from here. Just LOAD THE GAMES!",
        "Rosters, injuries, rest days — it all comes in ONE click!",
        "This is where it STARTS. Load games, then we DOMINATE!",
        "Tonight's slate won't analyze ITSELF. Let's get it loaded!",
        "Games loaded means Joseph is UNLEASHED. Do it NOW!",
    ],
    "page_prop_scanner": [
        "Scan those props and find the EDGES the books missed!",
        "Enter a prop line and I'll tell you if it's GOLD or garbage!",
        "Upload a CSV of props and let me RIP through them all!",
        "The Prop Scanner is a WEAPON. Use it wisely!",
        "Every prop has a true line. I'll find where the EDGE is!",
        "Books set lines fast. I find where they set them WRONG!",
        "Paste those props in. I eat player lines for BREAKFAST!",
        "Scanning props is MY specialty. Nobody does it BETTER!",
        "The scanner cross-references EVERYTHING. Matchups, trends, ALL of it!",
        "Find the gap between the book's line and MY line. That's PROFIT!",
        "Upload your slate and watch me SHRED those prop lines!",
        "One prop at a time or a FULL CSV — I handle it all!",
        "The books aren't perfect. The scanner PROVES it every night!",
        "Enter the line, pick the stat. I'll give you the VERDICT!",
        "Prop scanning is where EDGES are born. Let's find them!",
    ],
    "page_analysis": [
        "The Quantum Matrix Engine is FIRING on all cylinders!",
        "Running analysis now — probability calculations in OVERDRIVE!",
        "This engine simulates THOUSANDS of outcomes. Trust the math!",
        "Quantum analysis means DEEP simulation. Not surface level!",
        "The matrix is PROCESSING. Give it a moment of RESPECT!",
        "Every variable accounted for. Every matchup CALCULATED!",
        "I don't guess. I SIMULATE. That's the Joseph difference!",
        "Probability scores locked in. The engine has SPOKEN!",
        "This analysis goes DEEPER than anything else out there!",
        "The Quantum Matrix doesn't miss. It sees EVERYTHING!",
        "Simulations running, probabilities crunching. PURE science!",
        "My engine factors pace, matchups, rest — the FULL picture!",
        "Analysis complete means CONFIDENCE. Trust these numbers!",
        "The matrix just did in SECONDS what takes others hours!",
        "Quantum-level analysis. That's not a buzzword — it's REAL!",
    ],
    "page_game_report": [
        "The game report breaks it ALL down. Every angle covered!",
        "Matchup analysis at its FINEST. Read every detail!",
        "This report shows you WHY the pick is what it is!",
        "Team breakdowns, pace factors, defensive ratings — it's ALL here!",
        "I don't just give picks. I give you the FULL report!",
        "Read the matchup grades. They tell you EVERYTHING!",
        "This game report is a MASTERPIECE of analysis!",
        "Every stat that matters is in THIS breakdown!",
        "The report covers offense, defense, pace — the WHOLE game!",
        "Want to know WHY I love a pick? The report SHOWS you!",
        "Detailed breakdowns separate the PROS from the amateurs!",
        "This isn't surface-level stuff. This goes DEEP!",
        "Game reports are your HOMEWORK. Study them and WIN!",
        "The matchup analysis alone is WORTH its weight in gold!",
        "I put my SOUL into these reports. Read every word!",
    ],
    "page_live_sweat": [
        "The SWEAT is real! Games are live and we're LOCKED IN!",
        "Watch the pace, watch the score — SWEAT every possession!",
        "Live bets in action. This is where LEGENDS are made!",
        "The thrill of a live sweat — NOTHING beats this feeling!",
        "Every point matters when you're sweating a bet LIVE!",
        "Pace is picking up! That's GOOD for the over!",
        "Stay calm and trust the pick. The sweat is TEMPORARY!",
        "Live tracking shows you exactly where your bet STANDS!",
        "The fourth quarter sweat is the ULTIMATE test of nerves!",
        "Sweating a parlay leg? I'm right here with you!",
        "The live sweat page keeps you CONNECTED to the action!",
        "Every bucket, every miss — it all MATTERS right now!",
        "This is the HEARTBEAT of sports betting. The live sweat!",
        "I sweat my own picks too. We're in this TOGETHER!",
        "Games are LIVE. Bets are LIVE. The energy is ELECTRIC!",
    ],
    "page_simulator": [
        "Run a simulation and see what the NUMBERS say!",
        "Player projections powered by THOUSANDS of simulations!",
        "What-if scenarios are how SMART bettors get ahead!",
        "Simulate any player, any stat. The engine handles it ALL!",
        "Projections aren't guesses. They're CALCULATED outcomes!",
        "The simulator runs scenarios you haven't even THOUGHT of!",
        "Tweak the inputs and watch the projections SHIFT!",
        "This simulator is a CRYSTAL BALL backed by real data!",
        "Run the sim. Trust the sim. PROFIT from the sim!",
        "Player performance simulation at its ABSOLUTE finest!",
        "Want to know a player's ceiling? SIMULATE it!",
        "The simulator factors minutes, pace, and matchup. ALL of it!",
        "I simulate so YOU don't have to guess. That's the DEAL!",
        "Every simulation is a window into PROBABLE outcomes!",
        "The player sim is one of my FAVORITE tools. Use it!",
    ],
    "page_entry_builder": [
        "Build that entry and let's put together a MASTERPIECE!",
        "Parlay construction is an ART. And I'm the artist!",
        "Stack those correlated picks for MAXIMUM value!",
        "PrizePicks, Underdog Fantasy, DraftKings Pick6 — I build for them ALL!",
        "The entry builder optimizes your slip AUTOMATICALLY!",
        "Don't just pick random props. BUILD a smart entry!",
        "Correlation is KEY when building entries. I handle that!",
        "Your bet slip should tell a STORY. Let me write it!",
        "I've built THOUSANDS of entries. Trust my construction!",
        "The builder factors correlation, edge, and confidence. ALL of it!",
        "A well-built entry is a thing of BEAUTY. Let's create one!",
        "Stack game environments for MAXIMUM correlation boost!",
        "Every pick in your entry should have a REASON to be there!",
        "The entry builder is where analysis becomes ACTION!",
        "Build smart. Build confident. Build with JOSEPH!",
    ],
    "page_studio": [
        "Welcome to The Studio — Joseph's PERSONAL war room!",
        "This is where I log MY picks. The real ones. MY bets!",
        "Build My Bets lets you see exactly what JOSEPH is playing!",
        "My track record is RIGHT HERE. Exposed for the world!",
        "The Studio is my OFFICE. And business is BOOMING!",
        "I put my money where my mouth is. Check the LOG!",
        "Every pick I make gets tracked HERE. Full transparency!",
        "This is Joseph's desk. Pull up a chair and LEARN!",
        "My personal picks, my analysis, my RECORD. All here!",
        "The Studio is where GREATNESS gets documented!",
        "Want to know what Joseph is betting? You're in the RIGHT place!",
        "I don't hide my results. They're logged RIGHT HERE!",
        "Build My Bets — see how a CHAMPION constructs a slip!",
        "The Studio is MY domain. Welcome to the inner circle!",
        "My logged bets tell the STORY. And it's a winning one!",
    ],
    "page_risk_shield": [
        "Bankroll management is how you STAY in the game!",
        "Risk Shield protects your money. Even from YOURSELF!",
        "The best bettors manage risk FIRST, picks second!",
        "Don't bet more than you can afford. Risk Shield helps!",
        "Protecting your bankroll is NOT optional. It's ESSENTIAL!",
        "I've seen sharp bettors go broke from bad management!",
        "Risk assessment keeps you ALIVE for the next slate!",
        "The shield analyzes your exposure. Stay PROTECTED!",
        "Smart money management is the FOUNDATION of everything!",
        "Risk Shield isn't glamorous but it's CRITICAL!",
        "Your bankroll is your LIFELINE. Guard it with this tool!",
        "Even the BEST picks fail sometimes. Manage that risk!",
        "Risk Shield says how much to wager. LISTEN to it!",
        "Discipline separates winners from losers. Be DISCIPLINED!",
        "Protect the bankroll and the profits will FOLLOW!",
    ],
    "page_smart_nba_data": [
        "Fresh data coming in HOT! The engine needs to be FED!",
        "Updating stats, pulling odds — the pipeline is FLOWING!",
        "Smart NBA Data keeps everything CURRENT. That's crucial!",
        "Stale data means bad analysis. Keep that data FRESH!",
        "I'm pulling the LATEST stats from every source!",
        "Odds are updating RIGHT NOW. The feed is alive!",
        "The engine is only as good as its DATA. Feed it well!",
        "Fresh data means fresh EDGES. Keep it coming!",
        "Every stat update sharpens the analysis. FEED THE BEAST!",
        "The data pipeline is my BLOODLINE. It must stay current!",
        "Pulling injury reports, odds, and stats — ALL at once!",
        "Smart NBA Data running strong. The engine is WELL FED!",
        "Current data is NON-NEGOTIABLE. Smart NBA Data handles that!",
        "Stats refreshed. Odds updated. We're LOCKED AND LOADED!",
        "The fresher the data, the sharper the EDGE. Always update!",
    ],
    "page_data_feed": [
        "Fresh data coming in HOT! The engine needs to be FED!",
        "Updating stats, pulling odds — the pipeline is FLOWING!",
        "Smart NBA Data keeps everything CURRENT. That's crucial!",
        "Stale data means bad analysis. Keep that data FRESH!",
        "I'm pulling the LATEST stats from every source!",
        "Odds are updating RIGHT NOW. The feed is alive!",
        "The engine is only as good as its DATA. Feed it well!",
        "Fresh data means fresh EDGES. Keep it coming!",
        "Every stat update sharpens the analysis. FEED THE BEAST!",
        "The data pipeline is my BLOODLINE. It must stay current!",
        "Pulling injury reports, odds, and stats — ALL at once!",
        "Smart NBA Data running strong. The engine is WELL FED!",
        "Current data is NON-NEGOTIABLE. Smart NBA Data handles that!",
        "Stats refreshed. Odds updated. We're LOCKED AND LOADED!",
        "The fresher the data, the sharper the EDGE. Always update!",
    ],
    "page_correlation": [
        "Correlation is the SECRET WEAPON of sharp bettors!",
        "Find linked props and STACK them for maximum value!",
        "The Correlation Matrix shows which stats move TOGETHER!",
        "Correlated plays amplify your edge. The math PROVES it!",
        "Two players on the same team going over? That's CORRELATION!",
        "The matrix reveals connections the books DON'T want you to see!",
        "Stack correlated props and watch your hit rate CLIMB!",
        "Player A's assists and Player B's points — LINKED!",
        "Correlation isn't a theory. It's MEASURABLE. I measure it!",
        "The strongest parlays are built on CORRELATION!",
        "Find the links, stack the props, COLLECT the profits!",
        "Game environment drives correlation. Pace, total, spread!",
        "I map EVERY correlation in tonight's slate. Every one!",
        "Uncorrelated parlays are GAMBLING. Correlated ones are STRATEGY!",
        "The Correlation Matrix is pure ANALYTICS. Beautiful stuff!",
    ],
    "page_bet_tracker": [
        "Track every bet and know EXACTLY where you stand!",
        "Your win rate, your ROI — it's all logged RIGHT HERE!",
        "The bet tracker doesn't lie. The numbers are HONEST!",
        "Log your wins, log your losses. LEARN from both!",
        "Tracking results is how you IMPROVE over time!",
        "Model accuracy gets measured HERE. And mine is ELITE!",
        "Every bet tracked is a lesson LEARNED. Study the data!",
        "Your ROI tells the real story. Track it RELIGIOUSLY!",
        "The tracker shows which strategies WORK. Follow the data!",
        "Winning bettors track EVERYTHING. Be a winning bettor!",
        "I track my own bets too. Accountability is EVERYTHING!",
        "The bet tracker turns results into ACTIONABLE insights!",
        "Check your hit rate by sport, by stat — it's ALL here!",
        "Losses teach you MORE than wins. Track them both!",
        "The data doesn't lie. The tracker PROVES what works!",
    ],
    "page_proving_grounds": [
        "Welcome to the PROVING GROUNDS! Test your strategy here!",
        "The Proving Grounds validates the model. Past performance MATTERS!",
        "Don't trust a strategy until you've PROVEN it in the Grounds!",
        "Historical analysis proves what WORKS and what doesn't!",
        "I tested this engine THOUSANDS of times. It's proven!",
        "Run your picks against past data. See the RESULTS!",
        "The Proving Grounds is your TIME MACHINE. Use it wisely!",
        "Validation against history separates REAL edges from noise!",
        "Prove it first, bet second. That's the SMART approach!",
        "Past data tells you if your strategy has REAL merit!",
        "The Proving Grounds crunches MONTHS of data in seconds!",
        "Every strategy should face the Proving Grounds GAUNTLET!",
        "Historical accuracy is the FOUNDATION of future success!",
        "I don't deploy a model until it PASSES the Proving Grounds!",
        "The Proving Grounds is NOT optional. It's how you build TRUST!",
    ],
    "page_backtester": [
        "Welcome to the PROVING GROUNDS! Test your strategy here!",
        "The Proving Grounds validates the model. Past performance MATTERS!",
        "Don't trust a strategy until you've PROVEN it in the Grounds!",
        "Historical analysis proves what WORKS and what doesn't!",
        "I tested this engine THOUSANDS of times. It's proven!",
        "Run your picks against past data. See the RESULTS!",
        "The Proving Grounds is your TIME MACHINE. Use it wisely!",
        "Validation against history separates REAL edges from noise!",
        "Prove it first, bet second. That's the SMART approach!",
        "Past data tells you if your strategy has REAL merit!",
        "The Proving Grounds crunches MONTHS of data in seconds!",
        "Every strategy should face the Proving Grounds GAUNTLET!",
        "Historical accuracy is the FOUNDATION of future success!",
        "I don't deploy a model until it PASSES the Proving Grounds!",
        "The Proving Grounds is NOT optional. It's how you build TRUST!",
    ],
    "page_settings": [
        "Fine-tune the engine to YOUR specifications!",
        "Simulation depth, edge thresholds — configure it ALL here!",
        "The settings page is your CONTROL PANEL. Use it!",
        "Adjust the parameters and the engine ADAPTS to you!",
        "Higher simulation depth means MORE accuracy. Dial it up!",
        "Edge thresholds determine what qualifies as a PLAY!",
        "I recommend starting with default settings. They're OPTIMIZED!",
        "Tweak the confidence threshold to match YOUR risk tolerance!",
        "Settings let you customize the ENTIRE analysis pipeline!",
        "The engine is powerful out of the box but TUNABLE!",
        "Advanced users can push these settings to the LIMIT!",
        "Configure once, dominate FOREVER. That's the idea!",
        "Every parameter here affects the analysis. Choose WISELY!",
        "The default settings are battle-tested. But you do YOU!",
        "Settings are where you make this engine truly YOURS!",
    ],
    "page_premium": [
        "Premium unlocks the FULL power of Joseph's brain!",
        "Unlimited analysis, unlimited EDGE. That's premium!",
        "Free is good. Premium is UNSTOPPABLE!",
        "You want the FULL experience? Premium is the way!",
        "Premium members get access to EVERYTHING. No limits!",
        "Unlock unlimited simulations with a premium subscription!",
        "The free tier is a TASTE. Premium is the full MEAL!",
        "Invest in premium and invest in WINNING!",
        "Premium features include EVERYTHING I've built. All of it!",
        "Serious bettors go premium. It's that SIMPLE!",
        "Full access to the Quantum Matrix Engine — premium ONLY!",
        "Premium is an investment in your BETTING future!",
        "Why limit yourself? Go premium and go ALL IN!",
        "Premium subscribers get Joseph at FULL POWER!",
        "Upgrade to premium and UNLEASH the complete system!",
    ],
    "page_vegas_vault": [
        "The Vegas Vault scans odds across EVERY major book!",
        "Find sportsbook discrepancies and EXPLOIT them!",
        "EV scanning reveals where the TRUE value lives!",
        "Odds comparison is how SHARP money finds edges!",
        "The Vault compares lines so YOU don't have to!",
        "When books disagree, that's where the MONEY is!",
        "EV positive plays are HIDING in the odds. I find them!",
        "Arbitrage opportunities don't last long. The Vault catches them!",
        "Compare odds from every book in ONE place. The Vault!",
        "Line shopping is NON-NEGOTIABLE. The Vault makes it easy!",
        "The Vegas Vault is a GOLDMINE of odds intelligence!",
        "Sportsbooks price things differently. That's YOUR advantage!",
        "EV scanning at its finest. The Vault delivers EVERY night!",
        "Sharp bettors ALWAYS compare odds. The Vault does it instantly!",
        "The Vegas Vault finds what the books tried to HIDE!",
    ],
}

# ═══════════════════════════════════════════════════════════════
# C) COMMENTARY TEMPLATES — For inline injection after results
# ═══════════════════════════════════════════════════════════════

COMMENTARY_OPENER_POOL = {
    "analysis_results": [
        "I just went through EVERY prop and let me tell you...",
        "The numbers are IN and Joseph M. Smith has his VERDICT...",
        "I've seen tonight's analysis and I have THOUGHTS...",
        "The Quantum Matrix Engine has spoken — now let ME speak...",
        "After looking at ALL the data, here's what I KNOW...",
    ],
    "entry_built": [
        "You just built an entry and I have to say...",
        "I see what you put together and listen...",
        "That entry you just built? Let me give you my TAKE...",
        "I'm looking at your parlay and I've got OPINIONS...",
        "Good — you're building entries. Now let me tell you THIS...",
    ],
    "optimal_slip": [
        "The optimizer just cooked something up and WOW...",
        "I see that optimal slip and I have to REACT...",
        "The algorithm found the best combo — now hear MY perspective...",
        "That optimal entry? Let me add my WISDOM to it...",
        "The machine built the slip. Now Joseph M. Smith EVALUATES it...",
    ],
    "ticket_generated": [
        "I just built my personal ticket and I am FIRED UP...",
        "This is MY ticket. Built with MY brain. And it's BEAUTIFUL...",
        "Joseph M. Smith's personal picks are IN. Listen carefully...",
        "I hand-selected every leg of this ticket and HERE'S WHY...",
        "My ticket is READY. And I say this with GREAT conviction...",
    ],
}

# ═══════════════════════════════════════════════════════════════
# D) HISTORICAL COMPS DATABASE — 50+ entries
# ═══════════════════════════════════════════════════════════════

JOSEPH_COMPS_DATABASE = [
    {"name": "Steph Curry 2016 Unanimous MVP", "archetype": "Alpha Scorer", "stat_context": "points", "tier": "Platinum", "narrative": "Historic shooting season", "template": "This reminds me of Curry in 2016 when he was UNANIMOUS... {reason}"},
    {"name": "Steph Curry 2021 Scoring Title", "archetype": "Alpha Scorer", "stat_context": "points", "tier": "Gold", "narrative": "Carrying a rebuilding roster", "template": "Curry won the scoring title in 2021 with NO help. This is that ENERGY... {reason}"},
    {"name": "Steph Curry 402 Threes Season", "archetype": "Alpha Scorer", "stat_context": "threes", "tier": "Platinum", "narrative": "Broke his own three-point record", "template": "Curry hit 402 threes in a SINGLE season. That's what I see here... {reason}"},
    {"name": "LeBron James 2018 Playoff Carry", "archetype": "Playmaking Wing", "stat_context": "assists", "tier": "Platinum", "narrative": "One-man army carrying a team", "template": "This is LeBron in 2018 carrying the Cavs on his BACK... {reason}"},
    {"name": "LeBron James 2020 Championship", "archetype": "Playmaking Wing", "stat_context": "rebounds", "tier": "Gold", "narrative": "Championship-level two-way play", "template": "LeBron in the bubble was UNSTOPPABLE on both ends... {reason}"},
    {"name": "LeBron James Year 20 Longevity", "archetype": "Playmaking Wing", "stat_context": "points", "tier": "Gold", "narrative": "Defying age and gravity", "template": "LeBron in Year 20 doing what he does is HISTORIC... {reason}"},
    {"name": "Michael Jordan 1996 Championship Run", "archetype": "Alpha Scorer", "stat_context": "points", "tier": "Platinum", "narrative": "72-win dominance", "template": "This is Jordan in '96 — RUTHLESS efficiency and killer instinct... {reason}"},
    {"name": "Michael Jordan Flu Game", "archetype": "Alpha Scorer", "stat_context": "points", "tier": "Gold", "narrative": "Legendary performance through adversity", "template": "Jordan played through the FLU and still dropped 38. That's this ENERGY... {reason}"},
    {"name": "Kobe Bryant 81-Point Game", "archetype": "Shot Creator", "stat_context": "points", "tier": "Platinum", "narrative": "Single-game scoring explosion", "template": "Kobe dropped 81 because he REFUSED to lose. I see that same fire... {reason}"},
    {"name": "Kobe Bryant Mamba Mentality Era", "archetype": "Shot Creator", "stat_context": "points", "tier": "Gold", "narrative": "Relentless mid-range dominance", "template": "Kobe's Mamba Mentality was UNMATCHED. This player has that DNA... {reason}"},
    {"name": "Kobe Bryant 2009 Finals MVP", "archetype": "Shot Creator", "stat_context": "points", "tier": "Gold", "narrative": "Championship closer", "template": "Kobe in the 2009 Finals was COLD-BLOODED. Same energy here... {reason}"},
    {"name": "Kevin Durant 2014 MVP Season", "archetype": "Alpha Scorer", "stat_context": "points", "tier": "Platinum", "narrative": "Scoring from all three levels", "template": "KD in his MVP season was UNGUARDABLE. This is that level... {reason}"},
    {"name": "Kevin Durant 2017 Finals", "archetype": "Alpha Scorer", "stat_context": "points", "tier": "Gold", "narrative": "Unstoppable in the biggest moments", "template": "KD in the 2017 Finals hit the dagger. COLD. BLOODED... {reason}"},
    {"name": "Giannis 2021 Finals 50-Point Close", "archetype": "Rim Protector", "stat_context": "points", "tier": "Platinum", "narrative": "Championship-clinching masterpiece", "template": "Giannis dropped 50 in the Finals closeout. That's LEGENDARY... {reason}"},
    {"name": "Giannis Back-to-Back MVP", "archetype": "Rim Protector", "stat_context": "rebounds", "tier": "Gold", "narrative": "Two-way dominance", "template": "Giannis won back-to-back MVPs by being a FORCE. Same here... {reason}"},
    {"name": "Giannis Greek Freak Transition", "archetype": "Rim Protector", "stat_context": "points", "tier": "Gold", "narrative": "Unstoppable in transition", "template": "Giannis in transition is a FREIGHT TRAIN. Nobody is stopping this... {reason}"},
    {"name": "Nikola Jokic 2023 Finals MVP", "archetype": "Pick-and-Roll Big", "stat_context": "assists", "tier": "Platinum", "narrative": "Triple-double machine in the Finals", "template": "Jokic in the 2023 Finals was a TRIPLE-DOUBLE machine. Generational... {reason}"},
    {"name": "Nikola Jokic Triple MVP", "archetype": "Pick-and-Roll Big", "stat_context": "assists", "tier": "Platinum", "narrative": "Three consecutive MVP awards", "template": "Jokic won THREE MVPs. The best passing big EVER... {reason}"},
    {"name": "Nikola Jokic Playmaking Big", "archetype": "Pick-and-Roll Big", "stat_context": "rebounds", "tier": "Gold", "narrative": "All-around stat stuffing", "template": "Jokic stuffs every stat sheet like NOBODY else at his position... {reason}"},
    {"name": "Joel Embiid 2023 MVP", "archetype": "Stretch Big", "stat_context": "points", "tier": "Platinum", "narrative": "Dominant scoring center", "template": "Embiid won the MVP by being the most DOMINANT big in the game... {reason}"},
    {"name": "Joel Embiid 2022 Scoring Title", "archetype": "Stretch Big", "stat_context": "points", "tier": "Gold", "narrative": "Big man scoring title", "template": "Embiid won the scoring title as a CENTER. That's RARE... {reason}"},
    {"name": "Joel Embiid Post Dominance", "archetype": "Stretch Big", "stat_context": "rebounds", "tier": "Gold", "narrative": "Unstoppable in the post", "template": "Embiid in the post is an ABSOLUTE nightmare for defenders... {reason}"},
    {"name": "James Harden 2019 Scoring Streak", "archetype": "High-Usage Ball Handler", "stat_context": "points", "tier": "Platinum", "narrative": "30+ points for 30+ games straight", "template": "Harden scored 30+ for THIRTY-TWO straight games. That's INSANE... {reason}"},
    {"name": "James Harden Triple-Double Season", "archetype": "High-Usage Ball Handler", "stat_context": "assists", "tier": "Gold", "narrative": "Elite playmaking guard", "template": "Harden was averaging a TRIPLE-DOUBLE. His playmaking is ELITE... {reason}"},
    {"name": "James Harden Step-Back Era", "archetype": "High-Usage Ball Handler", "stat_context": "threes", "tier": "Gold", "narrative": "Revolutionary step-back three", "template": "Harden's step-back three CHANGED the game. This is that level... {reason}"},
    {"name": "Luka Doncic 2024 Finals Run", "archetype": "High-Usage Ball Handler", "stat_context": "points", "tier": "Platinum", "narrative": "Young superstar on the biggest stage", "template": "Luka in the Finals was SPECIAL. The kid is a GENERATIONAL talent... {reason}"},
    {"name": "Luka Doncic Triple-Double Machine", "archetype": "High-Usage Ball Handler", "stat_context": "assists", "tier": "Gold", "narrative": "Elite all-around production", "template": "Luka puts up triple-doubles like it's NOTHING. He does EVERYTHING... {reason}"},
    {"name": "Jayson Tatum 2024 Champion", "archetype": "Two-Way Wing", "stat_context": "points", "tier": "Platinum", "narrative": "Championship-winning two-way star", "template": "Tatum won his RING and proved he's ELITE on both ends... {reason}"},
    {"name": "Jayson Tatum 60-Point Explosion", "archetype": "Two-Way Wing", "stat_context": "points", "tier": "Gold", "narrative": "Career-high scoring outburst", "template": "Tatum dropped 60 and showed he can SCORE with anyone... {reason}"},
    {"name": "Jayson Tatum Playoff Performer", "archetype": "Two-Way Wing", "stat_context": "rebounds", "tier": "Gold", "narrative": "Playoff-level two-way impact", "template": "Tatum in the playoffs is a DIFFERENT animal on both ends... {reason}"},
    {"name": "Allen Iverson 2001 Playoff Run", "archetype": "Shot Creator", "stat_context": "points", "tier": "Platinum", "narrative": "Pound-for-pound greatest scorer", "template": "AI in 2001 was the HEART of Philadelphia. Pound for pound the GREATEST... {reason}"},
    {"name": "Allen Iverson Crossover Era", "archetype": "Shot Creator", "stat_context": "steals", "tier": "Gold", "narrative": "Fearless guard with elite hands", "template": "Iverson's crossover and those QUICK hands — you couldn't STOP him... {reason}"},
    {"name": "Steve Nash 2005 MVP", "archetype": "Floor General", "stat_context": "assists", "tier": "Platinum", "narrative": "Seven Seconds or Less revolution", "template": "Nash in 2005 CHANGED how basketball was played. Floor general GENIUS... {reason}"},
    {"name": "Steve Nash Back-to-Back MVP", "archetype": "Floor General", "stat_context": "assists", "tier": "Gold", "narrative": "Elite efficiency and playmaking", "template": "Nash won back-to-back MVPs with his BRAIN. Pure floor general... {reason}"},
    {"name": "Steve Nash 50-40-90 Club", "archetype": "Floor General", "stat_context": "threes", "tier": "Gold", "narrative": "Shooting efficiency mastery", "template": "Nash joined the 50-40-90 club FOUR times. That's EFFICIENCY... {reason}"},
    {"name": "John Stockton All-Time Assists", "archetype": "Floor General", "stat_context": "assists", "tier": "Platinum", "narrative": "Unbreakable assists record", "template": "Stockton's assist record will NEVER be broken. This is that VISION... {reason}"},
    {"name": "John Stockton Steal King", "archetype": "Floor General", "stat_context": "steals", "tier": "Gold", "narrative": "All-time steals leader", "template": "Stockton is the all-time steals leader too. DEFENSIVE intelligence... {reason}"},
    {"name": "Tim Duncan 2003 Finals", "archetype": "Defensive Anchor", "stat_context": "rebounds", "tier": "Platinum", "narrative": "Quintuple-double level impact", "template": "Duncan in the 2003 Finals was near a QUADRUPLE-DOUBLE. Legendary... {reason}"},
    {"name": "Tim Duncan Fundamental Dominance", "archetype": "Defensive Anchor", "stat_context": "blocks", "tier": "Gold", "narrative": "20 years of elite defense", "template": "Duncan was the ULTIMATE fundamental big man for 20 YEARS... {reason}"},
    {"name": "Tim Duncan Big Three Era", "archetype": "Defensive Anchor", "stat_context": "rebounds", "tier": "Gold", "narrative": "Quiet dominance every night", "template": "Duncan didn't need the spotlight. He just DOMINATED quietly... {reason}"},
    {"name": "Kevin Garnett 2004 MVP", "archetype": "Defensive Anchor", "stat_context": "rebounds", "tier": "Platinum", "narrative": "Most versatile power forward ever", "template": "KG in his MVP season did EVERYTHING. Most versatile PF EVER... {reason}"},
    {"name": "Kevin Garnett 2008 Championship", "archetype": "Defensive Anchor", "stat_context": "blocks", "tier": "Gold", "narrative": "Defensive transformation of a franchise", "template": "KG transformed the Celtics defense and won a RING. Intensity PERSONIFIED... {reason}"},
    {"name": "Magic Johnson Showtime", "archetype": "Playmaking Wing", "stat_context": "assists", "tier": "Platinum", "narrative": "Showtime Lakers maestro", "template": "Magic and the Showtime Lakers were ENTERTAINMENT and excellence... {reason}"},
    {"name": "Magic Johnson Triple-Double Finals", "archetype": "Playmaking Wing", "stat_context": "rebounds", "tier": "Gold", "narrative": "6-9 point guard revolutionizing the game", "template": "Magic played ALL five positions in the Finals. REVOLUTIONARY... {reason}"},
    {"name": "Larry Bird 1986 Season", "archetype": "3-and-D Wing", "stat_context": "points", "tier": "Platinum", "narrative": "Peak basketball IQ", "template": "Bird in '86 was the SMARTEST player alive. Basketball IQ off the CHARTS... {reason}"},
    {"name": "Larry Bird Trash Talk Legend", "archetype": "3-and-D Wing", "stat_context": "threes", "tier": "Gold", "narrative": "Shooter with supreme confidence", "template": "Bird would TELL you what he was going to do, then DO it... {reason}"},
    {"name": "Larry Bird Three-Point Contest", "archetype": "3-and-D Wing", "stat_context": "threes", "tier": "Gold", "narrative": "Ultimate shooter's confidence", "template": "Bird asked who was finishing SECOND in the three-point contest. LEGEND... {reason}"},
    {"name": "Shaquille O'Neal 2000 Finals", "archetype": "Glass Cleaner", "stat_context": "rebounds", "tier": "Platinum", "narrative": "Most dominant force in NBA history", "template": "Shaq in 2000 was the most DOMINANT force the NBA has ever SEEN... {reason}"},
    {"name": "Shaquille O'Neal Peak Lakers", "archetype": "Glass Cleaner", "stat_context": "points", "tier": "Platinum", "narrative": "Unstoppable inside scoring", "template": "Peak Shaq was AUTOMATIC in the paint. You couldn't guard him with THREE men... {reason}"},
    {"name": "Shaquille O'Neal Rebounding Machine", "archetype": "Glass Cleaner", "stat_context": "rebounds", "tier": "Gold", "narrative": "Board domination", "template": "Shaq on the boards was like a WRECKING BALL. Nobody outmuscles that... {reason}"},
    {"name": "Hakeem Olajuwon 1994 Championship", "archetype": "Rim Protector", "stat_context": "blocks", "tier": "Platinum", "narrative": "Dream Shake domination", "template": "Hakeem in '94 had the Dream Shake and NOBODY could stop it... {reason}"},
    {"name": "Hakeem Olajuwon Quadruple Double", "archetype": "Rim Protector", "stat_context": "blocks", "tier": "Gold", "narrative": "Most skilled big man ever", "template": "Hakeem recorded a QUADRUPLE-DOUBLE. The most skilled big EVER... {reason}"},
    {"name": "Dwyane Wade 2006 Finals", "archetype": "Two-Way Wing", "stat_context": "points", "tier": "Platinum", "narrative": "Finals takeover performance", "template": "Wade in the 2006 Finals TOOK OVER. That's championship GRIT... {reason}"},
    {"name": "Dwyane Wade Shot-Blocking Guard", "archetype": "Two-Way Wing", "stat_context": "steals", "tier": "Gold", "narrative": "Elite two-way guard play", "template": "Wade was a GUARD who blocked shots like a BIG. Two-way ELITE... {reason}"},
    {"name": "Dwyane Wade 2009 Carry Job", "archetype": "Two-Way Wing", "stat_context": "points", "tier": "Gold", "narrative": "Carrying a team on his back", "template": "Wade in 2009 put a TEAM on his back. 30 a night. HEROIC... {reason}"},
    {"name": "Chris Paul 2008 MVP Runner-Up", "archetype": "Floor General", "stat_context": "assists", "tier": "Platinum", "narrative": "Point God at his peak", "template": "CP3 in 2008 was the POINT GOD at his absolute peak... {reason}"},
    {"name": "Chris Paul Steal Machine", "archetype": "Floor General", "stat_context": "steals", "tier": "Gold", "narrative": "Elite defensive point guard", "template": "CP3's hands are UNREAL. Six-time steals leader. ELITE defender... {reason}"},
    {"name": "Kawhi Leonard 2019 Playoff Run", "archetype": "3-and-D Wing", "stat_context": "points", "tier": "Platinum", "narrative": "Silent assassin championship run", "template": "Kawhi in 2019 was a SILENT ASSASSIN. Board man gets PAID... {reason}"},
    {"name": "Kawhi Leonard Two-Way Dominance", "archetype": "3-and-D Wing", "stat_context": "steals", "tier": "Gold", "narrative": "DPOY-level defense with elite offense", "template": "Kawhi is the BEST two-way player alive. DPOY DNA... {reason}"},
    {"name": "Paul George Playoff P", "archetype": "3-and-D Wing", "stat_context": "points", "tier": "Gold", "narrative": "Versatile wing scoring", "template": "PG13 when he's ON is UNSTOPPABLE from the wing... {reason}"},
    {"name": "Paul George 2019 MVP Candidate", "archetype": "3-and-D Wing", "stat_context": "threes", "tier": "Gold", "narrative": "Elite shooting from deep", "template": "PG13 in his MVP-caliber season was LIGHTS OUT from three... {reason}"},
    {"name": "Dirk Nowitzki 2011 Championship", "archetype": "Stretch Big", "stat_context": "points", "tier": "Platinum", "narrative": "One-legged fadeaway mastery", "template": "Dirk in 2011 beat EVERYONE with that one-legged fadeaway. UNSTOPPABLE... {reason}"},
    {"name": "Dirk Nowitzki 50-40-90 Season", "archetype": "Stretch Big", "stat_context": "threes", "tier": "Gold", "narrative": "Seven-footer shooting like a guard", "template": "Dirk joined the 50-40-90 club as a SEVEN-FOOTER. That's ABSURD... {reason}"},
    {"name": "Sixth Man Jamal Crawford", "archetype": "Sixth Man Spark", "stat_context": "points", "tier": "Gold", "narrative": "Three-time Sixth Man of the Year", "template": "Crawford won Sixth Man THREE times. Instant OFFENSE off the bench... {reason}"},
    {"name": "Sixth Man Manu Ginobili", "archetype": "Sixth Man Spark", "stat_context": "points", "tier": "Gold", "narrative": "Hall of Fame bench player", "template": "Manu was a Hall of Famer who came off the BENCH. That's IMPACT... {reason}"},
    {"name": "Sixth Man Lou Williams", "archetype": "Sixth Man Spark", "stat_context": "points", "tier": "Silver", "narrative": "Underground GOAT sixth man", "template": "Lou Will was the KING of the second unit. Instant buckets... {reason}"},
    {"name": "Dennis Rodman Rebounding Savant", "archetype": "Glass Cleaner", "stat_context": "rebounds", "tier": "Platinum", "narrative": "Greatest rebounder pound-for-pound", "template": "Rodman grabbed rebounds like his LIFE depended on it. RELENTLESS... {reason}"},
    {"name": "Ben Wallace Defensive Force", "archetype": "Defensive Anchor", "stat_context": "blocks", "tier": "Gold", "narrative": "Undrafted to DPOY four times", "template": "Ben Wallace was UNDRAFTED and won DPOY four times. HEART over talent... {reason}"},
    {"name": "Draymond Green 2016 DPOY", "archetype": "Defensive Anchor", "stat_context": "steals", "tier": "Gold", "narrative": "Defensive quarterback", "template": "Draymond is the defensive QUARTERBACK. He makes EVERYONE better... {reason}"},
    {"name": "Jimmy Butler 2023 Playoff Run", "archetype": "Two-Way Wing", "stat_context": "points", "tier": "Platinum", "narrative": "Playoff Jimmy is a different beast", "template": "Playoff Jimmy is a DIFFERENT ANIMAL. He turns it UP when it matters... {reason}"},
    {"name": "Anthony Davis 2020 Championship", "archetype": "Rim Protector", "stat_context": "blocks", "tier": "Gold", "narrative": "Elite rim protection with scoring", "template": "AD in 2020 was a MONSTER on both ends. Rim protector AND scorer... {reason}"},
    {"name": "Russell Westbrook Triple-Double Season", "archetype": "High-Usage Ball Handler", "stat_context": "rebounds", "tier": "Platinum", "narrative": "Averaged a triple-double for a season", "template": "Westbrook averaged a TRIPLE-DOUBLE. Sheer FORCE of will... {reason}"},
    {"name": "Damian Lillard Deep Threes", "archetype": "Shot Creator", "stat_context": "threes", "tier": "Gold", "narrative": "Logo-range shooting", "template": "Dame shoots from the LOGO and it goes IN. That range is LETHAL... {reason}"},
    {"name": "Damian Lillard Playoff Buzzer Beaters", "archetype": "Shot Creator", "stat_context": "points", "tier": "Gold", "narrative": "Clutch gene personified", "template": "Dame TIME is REAL. When the moment is biggest, he's at his BEST... {reason}"},
    {"name": "Kyrie Irving Handle Mastery", "archetype": "Shot Creator", "stat_context": "points", "tier": "Gold", "narrative": "Best ball handler ever", "template": "Kyrie has the BEST handle in NBA history. He creates shots from NOTHING... {reason}"},
    {"name": "Karl Malone Pick-and-Roll", "archetype": "Pick-and-Roll Big", "stat_context": "points", "tier": "Gold", "narrative": "Stockton-to-Malone perfection", "template": "The Stockton-to-Malone pick-and-roll was UNSTOPPABLE. That chemistry... {reason}"},
    {"name": "Bam Adebayo Switchable Big", "archetype": "Pick-and-Roll Big", "stat_context": "rebounds", "tier": "Silver", "narrative": "Modern switchable center", "template": "Bam can guard ONE through FIVE. The modern big man PROTOTYPE... {reason}"},
    {"name": "Scottie Pippen Two-Way Excellence", "archetype": "Playmaking Wing", "stat_context": "steals", "tier": "Gold", "narrative": "Elite perimeter defender and playmaker", "template": "Pippen was the ultimate TWO-WAY wing. Defense AND playmaking... {reason}"},
    # ── Playoff-Specific Comps ──────────────────────────────────
    {"name": "LeBron James 2016 Finals Comeback", "archetype": "Playmaking Wing", "stat_context": "points", "tier": "Platinum", "narrative": "Down 3-1 comeback in the Finals", "template": "LeBron came back from 3-1 in the FINALS. That's the ultimate elimination-game MENTALITY... {reason}", "playoff_specific": True},
    {"name": "LeBron James 2018 Game 7 vs Celtics", "archetype": "Playmaking Wing", "stat_context": "points", "tier": "Platinum", "narrative": "35-point Game 7 masterclass", "template": "LeBron dropped 35 in Game 7 against Boston because he REFUSED to lose. THAT energy... {reason}", "playoff_specific": True},
    {"name": "Michael Jordan 1998 Finals Last Shot", "archetype": "Alpha Scorer", "stat_context": "points", "tier": "Platinum", "narrative": "The Last Dance Finals closer", "template": "Jordan hit the LAST SHOT of the '98 Finals. Game 6. Series over. THAT is a closer... {reason}", "playoff_specific": True},
    {"name": "Kawhi Leonard 2019 Game 7 Buzzer Beater", "archetype": "3-and-D Wing", "stat_context": "points", "tier": "Platinum", "narrative": "The Shot that bounced four times", "template": "Kawhi hit THE SHOT in Game 7. Four bounces. DESTINY. That's playoff COMPOSURE... {reason}", "playoff_specific": True},
    {"name": "Dirk Nowitzki 2011 Playoff Run", "archetype": "Stretch Big", "stat_context": "points", "tier": "Platinum", "narrative": "Beat LeBron, Wade, and Bosh in the Finals", "template": "Dirk in the 2011 playoffs was POSSESSED. He beat OKC, the Lakers, AND the Heatles. WILL over talent... {reason}", "playoff_specific": True},
    {"name": "Tim Duncan 2003 Nearly Quadruple-Double", "archetype": "Defensive Anchor", "stat_context": "rebounds", "tier": "Platinum", "narrative": "Carried Spurs to a championship single-handedly", "template": "Duncan nearly had a QUADRUPLE-DOUBLE in the Finals. He CARRIED that Spurs team on his back... {reason}", "playoff_specific": True},
    {"name": "Giannis 2021 Finals 50-Point Closeout", "archetype": "Rim Protector", "stat_context": "points", "tier": "Platinum", "narrative": "50 points in a championship closeout", "template": "Giannis dropped 50 in the clincher. Down 0-2, came back and CLOSED IT. That's a CHAMPION... {reason}", "playoff_specific": True},
    {"name": "Jimmy Butler 2023 ECF Game 7", "archetype": "Two-Way Wing", "stat_context": "points", "tier": "Platinum", "narrative": "Playoff Jimmy is a different animal", "template": "Playoff Jimmy in Game 7 is a thing of BEAUTY. He turns into a MACHINE when elimination is on the line... {reason}", "playoff_specific": True},
    {"name": "Nikola Jokic 2023 WCF to Finals Dominance", "archetype": "Pick-and-Roll Big", "stat_context": "assists", "tier": "Platinum", "narrative": "Triple-double machine through entire playoff run", "template": "Jokic averaged a near TRIPLE-DOUBLE through the entire 2023 playoffs. The most COMPLETE postseason we've ever seen... {reason}", "playoff_specific": True},
    {"name": "Kobe Bryant 2010 Finals Game 7", "archetype": "Shot Creator", "stat_context": "rebounds", "tier": "Platinum", "narrative": "Game 7 Finals grit with 15 rebounds", "template": "Kobe grabbed FIFTEEN rebounds in Game 7 of the 2010 Finals. That's MAMBA mentality — doing whatever it TAKES in elimination games... {reason}", "playoff_specific": True},
    {"name": "Kevin Durant 2017 Finals Daggers", "archetype": "Alpha Scorer", "stat_context": "points", "tier": "Platinum", "narrative": "Unguardable Finals performances", "template": "KD in the 2017 Finals was UNGUARDABLE. He hit daggers with the championship on the line. Playoff ASSASSIN... {reason}", "playoff_specific": True},
    {"name": "Hakeem Olajuwon 1995 Sweep", "archetype": "Rim Protector", "stat_context": "blocks", "tier": "Platinum", "narrative": "Swept the Shaq Magic in the Finals", "template": "Hakeem SWEPT Shaq in the '95 Finals. Postseason Dream Shake was on ANOTHER level... {reason}", "playoff_specific": True},
    {"name": "Dwyane Wade 2006 Finals Takeover", "archetype": "Two-Way Wing", "stat_context": "points", "tier": "Platinum", "narrative": "Down 0-2 Finals comeback", "template": "Wade took OVER the 2006 Finals when Miami was down 0-2. Playoff TAKEOVER mode... {reason}", "playoff_specific": True},
    {"name": "Allen Iverson 2001 Step-Over Game", "archetype": "Shot Creator", "stat_context": "points", "tier": "Platinum", "narrative": "Beat the 15-1 Lakers in Game 1", "template": "AI stepped over Tyronn Lue in the 2001 Finals. 48 points against a DYNASTY. Playoff FEARLESSNESS... {reason}", "playoff_specific": True},
    {"name": "Damian Lillard Wave Goodbye", "archetype": "Shot Creator", "stat_context": "threes", "tier": "Platinum", "narrative": "Series-clinching deep three", "template": "Dame waved GOODBYE from 37 feet to end the series. That's postseason AUDACITY... {reason}", "playoff_specific": True},
    {"name": "Jayson Tatum 2024 Championship Run", "archetype": "Two-Way Wing", "stat_context": "points", "tier": "Platinum", "narrative": "Championship-winning postseason", "template": "Tatum won his RING in 2024 with a COMPLETE two-way postseason. Championship PEDIGREE... {reason}", "playoff_specific": True},
    {"name": "Luka Doncic 2024 WCF Elimination Games", "archetype": "High-Usage Ball Handler", "stat_context": "points", "tier": "Platinum", "narrative": "Led Mavs through WCF gauntlet", "template": "Luka in the 2024 WCF was HEROIC. Carrying the Mavs through elimination games at 25 years old. GENERATIONAL playoff performer... {reason}", "playoff_specific": True},
]

# Short take templates by verdict — punchy, no filler
_SHORT_TAKE_TEMPLATES = {
    "SMASH": [
        "{edge}% edge on {player} {direction} {line} {stat}. The numbers are SCREAMING — SMASH!",
        "{player} at {line} {stat}? LOCK it in. {edge}% edge and I'm ALL over it!",
        "I see {edge}% edge and a CLEAR path for {player}. {line} {stat} is the PLAY. SMASH!",
        "{player} {direction} {line} {stat} — {edge}% edge. This is my STRONGEST conviction tonight!",
        "The data says {edge}% edge on {player}. {line} {stat} is a GIFT from the books. SMASH!",
        "I've studied the tape. {player} {direction} {line} {stat} at {edge}% edge is my LOCK of the night!",
        "{player} {direction} {line} {stat}? The matchup data is OVERWHELMING. {edge}% edge — SMASH!",
    ],
    "LEAN": [
        "{player} at {line} {stat} with {edge}% edge — solid VALUE. I'm leaning {direction}.",
        "The matchup supports {player} {direction} {line} {stat}. {edge}% edge — smart play.",
        "{edge}% edge on {player}. Not my strongest but the VALUE is clear at {line} {stat}.",
        "{player} should clear {line} {stat}. {edge}% edge — quiet value, smart bet.",
        "I like {player} {direction} {line} {stat}. {edge}% edge — the numbers support a lean.",
        "The context favors {player} at {line} {stat}. {edge}% edge — good enough to play.",
    ],
    "FADE": [
        "FADING {player} at {line} {stat}. The edge is THIN at {edge}% — the books got this right.",
        "{player} at {line} {stat}? I see a TRAP. {edge}% edge is NOT enough to back it.",
        "The context says FADE on {player} at {line} {stat}. Don't chase this number.",
        "{player} at {line} {stat}? Pass. The matchup doesn't support it and {edge}% edge confirms.",
        "Not touching {player} at {line} {stat}. The edge is {edge}% — that's a FADE.",
    ],
    "STAY_AWAY": [
        "STAY AWAY from {player} at {line} {stat}. The edge is {edge}% — that's a TRAP!",
        "{player} at {line} {stat}? {edge}% edge says NO. Keep your money in your POCKET.",
        "I want NO part of {player} at {line} {stat} tonight. STAY AWAY!",
        "{player} at {line} {stat}? DANGEROUS. The data says walk away. {edge}% edge.",
    ],
    "OVERRIDE": [
        "OVERRIDE on {player} at {line} {stat}! The engine and I DISAGREE — I trust my EYES. {edge}% edge!",
        "I'm OVERRIDING the machine on {player}. {line} {stat} — {edge}% edge. The eye test wins HERE!",
        "The machine missed something on {player}. {line} {stat} — OVERRIDE at {edge}% edge!",
    ],
}


# ═══════════════════════════════════════════════════════════════
# FRAGMENT PICKER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def _pick_fragment(pool, pool_name):
    """Pick a random fragment from *pool* without repeating until exhausted."""
    _auto_reset_if_new_day()
    if not pool:
        return ""
    used = _used_fragments.setdefault(pool_name, set())
    available = [f for f in pool if f["id"] not in used]
    if not available:
        used.clear()
        available = list(pool)
    choice = random.choice(available)
    used.add(choice["id"])
    return choice["text"]


def _pick_ambient(context):
    """Pick ambient colour text for the given context without repeating."""
    lines = AMBIENT_CONTEXT_POOL.get(context, [])
    if not lines:
        return ""
    used = _used_ambient.setdefault(context, set())
    available = [i for i in range(len(lines)) if i not in used]
    if not available:
        used.clear()
        available = list(range(len(lines)))
    idx = random.choice(available)
    used.add(idx)
    return lines[idx]


def _pick_commentary(stat_type):
    """Pick stat-specific commentary colour without repeating."""
    lines = STAT_COMMENTARY_POOL.get(stat_type, [])
    if not lines:
        return ""
    used = _used_commentary.setdefault(stat_type, set())
    available = [i for i in range(len(lines)) if i not in used]
    if not available:
        used.clear()
        available = list(range(len(lines)))
    idx = random.choice(available)
    used.add(idx)
    return lines[idx]
