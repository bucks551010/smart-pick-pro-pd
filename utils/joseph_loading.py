# ============================================================
# FILE: utils/joseph_loading.py
# PURPOSE: Joseph M. Smith animated loading screen that displays
#          fun NBA facts while pages load or analyses run.
#          Shows Joseph's avatar with a basketball-themed
#          background and rotating fun facts to keep users
#          entertained during wait times.
# CONNECTS TO: pages/helpers/joseph_live_desk.py (avatar loader),
#              styles/theme.py (theme consistency)
# ============================================================
"""Joseph M. Smith animated loading screen with rotating NBA fun facts.

Renders a full-screen glassmorphic overlay featuring Joseph's avatar,
a basketball spinner, and 582+ curated NBA fun facts that rotate on
a configurable interval.  Uses ``st.html()`` (not ``st.markdown``)
so the embedded ``<script>`` for fact rotation actually executes.

Functions
---------
get_random_facts
    Return *n* unique facts from :data:`NBA_FUN_FACTS`.
render_joseph_loading_screen
    Emit the full animated loading overlay via ``st.html()``.
joseph_loading_placeholder
    Create a dismissable Streamlit placeholder wrapping the loader.
"""

import html as _html
import json
import logging
import random

try:
    import streamlit as st
except ImportError:  # pragma: no cover – unit-test environments
    st = None

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

# ── Avatar loader (safe import) ──────────────────────────────
try:
    from pages.helpers.joseph_live_desk import (
        get_joseph_avatar_b64,
        get_joseph_avatar_spinning_b64,
    )
    _AVATAR_AVAILABLE = True
except ImportError:
    _AVATAR_AVAILABLE = False

    def get_joseph_avatar_b64() -> str:
        return ""

    def get_joseph_avatar_spinning_b64() -> str:
        return ""


# ═════════════════════════════════════════════════════════════
# NBA Fun Facts Pool — 582 facts about NBA history, players,
# coaches, records, and basketball culture
# ═════════════════════════════════════════════════════════════

NBA_FUN_FACTS = (
    # ── All-time records ─────────────────────────────────────
    "Wilt Chamberlain scored 100 points in a single game on March 2, 1962 — a record that still stands today.",
    "The longest NBA game ever lasted 78 minutes — Indianapolis Olympians vs. Rochester Royals in 1951 with 6 overtimes.",
    "Kareem Abdul-Jabbar held the all-time scoring record for 39 years before LeBron James broke it in 2023.",
    "The Golden State Warriors set the regular season record with 73 wins in the 2015-16 season.",
    "Wilt Chamberlain averaged 50.4 points per game for the entire 1961-62 season. Nobody has come close since.",
    "The Boston Celtics won 8 consecutive NBA championships from 1959 to 1966 — the longest streak in NBA history.",

    # ── Player legends ───────────────────────────────────────
    "Michael Jordan was cut from his high school varsity basketball team as a sophomore.",
    "LeBron James has played in 10 NBA Finals and was the first player to score 40,000 career points.",
    "Kobe Bryant scored 81 points against the Toronto Raptors on January 22, 2006 — the second-highest single-game total ever.",
    "Magic Johnson won the NBA Finals MVP as a rookie in 1980, playing center in place of the injured Kareem Abdul-Jabbar.",
    "Stephen Curry revolutionized basketball with the three-point shot, holding the record for most career three-pointers made.",
    "Shaquille O'Neal made only one three-pointer in his entire 19-year NBA career.",
    "Tim Duncan was originally a competitive swimmer and only started playing basketball at age 14 after a hurricane destroyed his pool.",
    "Allen Iverson, listed at just 6'0\", won four NBA scoring titles and was the 2001 MVP.",
    "Hakeem Olajuwon is the NBA's all-time leader in blocked shots with 3,830.",
    "Dennis Rodman led the league in rebounds per game for seven consecutive seasons (1992-1998).",
    "Oscar Robertson averaged a triple-double for an entire season in 1961-62 — a feat unmatched for 55 years until Russell Westbrook did it in 2017.",
    "Larry Bird won three consecutive MVP awards from 1984 to 1986.",
    "Dirk Nowitzki played his entire 21-year career with the Dallas Mavericks — the longest tenure with one team in NBA history.",
    "Vince Carter's career spanned 22 seasons and four decades (1998–2020), the longest in NBA history.",

    # ── Draft & young players ────────────────────────────────
    "Kobe Bryant was drafted straight out of high school at age 17 — the youngest player in NBA history at the time.",
    "LeBron James was the #1 overall pick in the 2003 NBA Draft, straight out of high school.",
    "The 1984 NBA Draft class included Michael Jordan, Hakeem Olajuwon, Charles Barkley, and John Stockton.",
    "The 1996 Draft class featured Kobe Bryant, Allen Iverson, Steve Nash, and Ray Allen.",
    "Giannis Antetokounmpo was the 15th pick in the 2013 Draft. He won back-to-back MVP awards in 2019 and 2020.",
    "Nikola Jokić was picked 41st overall in 2014 — the lowest draft position for a player who won MVP.",

    # ── Coaching legends ─────────────────────────────────────
    "Phil Jackson won 11 NBA championships as a head coach — 6 with the Bulls and 5 with the Lakers.",
    "Red Auerbach lit a victory cigar on the bench when he felt a win was secured. He won 9 titles with the Celtics.",
    "Pat Riley coined the term 'three-peat' and actually trademarked it.",
    "Gregg Popovich has coached the San Antonio Spurs since 1996 — the longest active tenure with one team in major North American sports.",
    "Steve Kerr has won NBA championships both as a player (5 rings) and as a head coach.",
    "Erik Spoelstra became the first Asian-American head coach in any major U.S. professional sport.",

    # ── Team history & culture ───────────────────────────────
    "The NBA was founded on June 6, 1946 as the Basketball Association of America (BAA).",
    "The Toronto Raptors are the only current NBA team based outside the United States.",
    "The original Celtics parquet floor was made from scraps of wood left over from World War II.",
    "The Los Angeles Lakers were originally from Minneapolis — the 'Land of 10,000 Lakes.'",
    "The Jazz moved from New Orleans to Utah in 1979, keeping their name despite Utah not being known for jazz music.",
    "The Cleveland Cavaliers were named through a fan contest in 1970.",
    "The Miami Heat retired Michael Jordan's #23 jersey even though he never played for them — out of respect.",
    "The Harlem Globetrotters were actually from Chicago, not Harlem.",

    # ── Rules & gameplay ─────────────────────────────────────
    "The three-point line was introduced to the NBA in the 1979-80 season.",
    "The shot clock was introduced in 1954 to prevent teams from stalling. It was set at 24 seconds.",
    "The NBA didn't allow zone defense until the 2001-02 season.",
    "A regulation NBA basketball must bounce between 49 and 54 inches when dropped from 6 feet.",
    "NBA courts are exactly 94 feet long and 50 feet wide.",
    "The basketball itself weighs between 20 and 22 ounces.",

    # ── Playoffs & Finals ────────────────────────────────────
    "The Boston Celtics have the most NBA championships with 17 titles.",
    "The 2016 NBA Finals saw the Cleveland Cavaliers come back from a 3-1 deficit — the only team to ever do so in Finals history.",
    "LeBron James's block on Andre Iguodala in Game 7 of the 2016 Finals is one of the most iconic plays in NBA history.",
    "Michael Jordan never lost an NBA Finals series — he was 6-0.",
    "Bill Russell won 11 championships in 13 seasons — the most by any player in NBA history.",
    "The 2014 Spurs defeated the Heat by an average margin of 14 points in the Finals — the most dominant performance in modern Finals history.",

    # ── Stat milestones ──────────────────────────────────────
    "Only five players have recorded a quadruple-double in NBA history.",
    "John Stockton holds the all-time assists record with 15,806 — nearly 4,000 more than second place.",
    "Reggie Miller scored 8 points in 8.9 seconds against the Knicks in the 1995 playoffs.",
    "Tracy McGrady scored 13 points in 35 seconds against the Spurs in 2004.",
    "Russell Westbrook holds the record for most triple-doubles in NBA history with 198+.",
    "Robert Horry won 7 NBA championships with three different teams — the most by a non-Celtic player.",

    # ── Modern era ───────────────────────────────────────────
    "The NBA's salary cap for the 2024-25 season is approximately $141 million.",
    "Victor Wembanyama was the #1 pick in 2023 — at 7'4\" he's one of the tallest #1 picks ever.",
    "Nikola Jokić became the first center to win MVP since Shaq in 2000 when he won it in 2021.",
    "Luka Dončić recorded a 60-point triple-double in 2022 — only the second in NBA history.",
    "Ja Morant recorded the highest-scoring game by a Grizzlies player with 52 points against the Spurs in 2023.",
    "The Phoenix Suns' Kevin Durant became the youngest player ever to reach 28,000 career points.",

    # ── Off-court & culture ──────────────────────────────────
    "The NBA ball is made by Wilson, who took over from Spalding starting in the 2021-22 season.",
    "NBA players run an average of 2.5 miles per game.",
    "The tallest player in NBA history was Gheorghe Mureșan at 7'7\".",
    "Muggsy Bogues, at 5'3\", is the shortest player in NBA history — and he blocked Patrick Ewing's shot.",
    "The NBA's longest winning streak is 33 games, set by the 1971-72 Los Angeles Lakers.",
    "Manute Bol and Muggsy Bogues were once teammates on the Washington Bullets — a 28-inch height difference.",

    # ── Fun trivia ───────────────────────────────────────────
    "The first NBA game was played on November 1, 1946 — the New York Knickerbockers vs. the Toronto Huskies.",
    "Wilt Chamberlain claims he never fouled out of an NBA game in his entire career.",
    "Kareem Abdul-Jabbar's skyhook is considered the most unstoppable shot in basketball history.",
    "Michael Jordan's 'Flu Game' in the 1997 Finals is one of the most legendary performances in sports history.",
    "The phrase 'and one' refers to a player being fouled while making a basket — getting the shot plus a free throw.",
    "The Boston Garden's famous parquet floor had dead spots that the Celtics memorized to gain a home-court advantage.",
    "A 'brick' in basketball slang means a badly missed shot that clangs off the rim.",
    "Charles Barkley once said 'I am not a role model' in a famous Nike commercial — sparking a national debate.",
    "The NBA Draft Lottery was introduced in 1985 after teams were accused of losing on purpose to get top picks.",
    "Shaq was so dominant that teams invented 'Hack-a-Shaq' — intentionally fouling him because he was a poor free throw shooter.",
    "The term 'triple-double' wasn't commonly used until Magic Johnson popularized the stat line in the 1980s.",
    "The NBA's G League was originally called the D-League (Development League) before Gatorade sponsored it.",
    "Klay Thompson once scored 37 points in a single quarter against the Sacramento Kings in 2015.",
    "Before the shot clock, the lowest-scoring NBA game was 19-18 (Fort Wayne Pistons vs. Minneapolis Lakers in 1950).",

    # ── Rivalries & iconic matchups ──────────────────────────
    "The Lakers-Celtics rivalry is the most storied in NBA history — they've met 12 times in the Finals.",
    "The 1990s Bulls-Knicks rivalry was so intense that their playoff games averaged under 90 points per team.",
    "Bird and Magic's rivalry began in the 1979 NCAA championship game and carried into the NBA for a decade.",
    "The Pistons' 'Bad Boys' era featured the 'Jordan Rules' — a set of physical defensive strategies designed to stop Michael Jordan.",
    "The 2002 Western Conference Finals between the Kings and Lakers is considered one of the most controversial series ever.",
    "The Knicks and Heat rivalry in the 1990s was so physical that it led to multiple rule changes about hand-checking.",
    "The Celtics-76ers rivalry dates back to the 1960s when Bill Russell and Wilt Chamberlain battled for Eastern supremacy.",
    "Tim Duncan's block on Shaq's dunk attempt in the 2003 playoffs is one of the greatest defensive plays in NBA history.",
    "The 'Malice at the Palace' brawl in 2004 between Pistons and Pacers led to the NBA's strictest-ever suspensions.",
    "LeBron James and Stephen Curry met in four consecutive NBA Finals from 2015 to 2018.",

    # ── International basketball & global impact ─────────────
    "Yao Ming was the #1 overall pick in 2002 and helped grow the NBA's popularity in China to over 300 million viewers.",
    "Dirk Nowitzki was the first European-born player to win NBA Finals MVP in 2011.",
    "The 1992 'Dream Team' featuring Jordan, Bird, and Magic is considered the greatest sports team ever assembled.",
    "Manu Ginóbili is the only player to have won an Olympic gold medal, a EuroLeague title, and an NBA championship.",
    "Luka Dončić won the EuroLeague MVP at age 19 before being drafted 3rd overall by the Dallas Mavericks.",
    "Giannis Antetokounmpo moved from Nigeria to Greece as a child and didn't start playing basketball until age 12.",
    "Tony Parker, born in Belgium and raised in France, won four NBA championships and a Finals MVP with the Spurs.",
    "Pau Gasol won two NBA championships with the Lakers and is Spain's all-time leading scorer in international play.",
    "Hakeem Olajuwon, born in Nigeria, learned basketball playing soccer — his footwork in the post was legendary.",
    "The NBA has featured players from over 40 different countries since 2000.",

    # ── Iconic individual moments ────────────────────────────
    "Michael Jordan's 'Last Shot' in the 1998 Finals — a pull-up jumper over Bryon Russell — clinched his sixth title.",
    "Kawhi Leonard's buzzer-beater against the 76ers in 2019 bounced four times on the rim before going in.",
    "Ray Allen's corner three-pointer in Game 6 of the 2013 Finals saved the Heat's season and is known as 'The Shot.'",
    "Derek Fisher hit a game-winning shot with 0.4 seconds left against the Spurs in the 2004 Western Conference Semis.",
    "Dame Lillard waved goodbye to the Thunder after hitting a 37-foot series-clinching three in the 2019 playoffs.",
    "Vince Carter's dunk over 7'2\" Frédéric Weis at the 2000 Olympics is called 'Le Dunk de la Mort' — the Dunk of Death.",
    "Julius Erving's baseline reverse layup in the 1980 Finals is one of the most replayed highlights in NBA history.",
    "Devin Booker scored 70 points against the Celtics in 2017, becoming the youngest player to reach that mark.",
    "Steph Curry hit 402 three-pointers in a single season in 2015-16, shattering his own record of 286.",
    "Willis Reed limped onto the court for Game 7 of the 1970 Finals despite a torn thigh muscle, inspiring the Knicks to a championship.",

    # ── Arenas, courts & venues ──────────────────────────────
    "Madison Square Garden in New York City is known as 'The Mecca of Basketball' and has been open since 1968.",
    "The Staples Center (now Crypto.com Arena) hosted both the Lakers and Clippers under the same roof for over 20 years.",
    "Oracle Arena in Oakland was nicknamed 'Roaracle' because Warriors fans were considered the loudest in the NBA.",
    "The Chicago Bulls play at the United Center, which features a bronze statue of Michael Jordan out front.",
    "The Boston Celtics' TD Garden hangs 17 championship banners from the rafters — more than any other NBA arena.",
    "The San Antonio Spurs' arena once had a resident bat colony that occasionally flew onto the court during games.",
    "Every NBA court is made of hard maple wood, specifically sugar maple from forests in the northern United States.",
    "The Milwaukee Bucks' Fiserv Forum was designed with the largest outdoor public plaza of any NBA arena.",
    "The Phoenix Suns' arena has a retractable roof section that can let in natural sunlight during daytime events.",
    "The NBA mandates specific court dimensions, but teams can customize the paint, logo, and sideline designs.",

    # ── Jerseys, shoes & style ───────────────────────────────
    "Michael Jordan's Air Jordan sneakers were originally banned by the NBA for violating uniform rules. Nike paid the fines.",
    "The NBA introduced the 'City Edition' jersey concept in 2017, allowing teams to create unique alternate designs each year.",
    "Allen Iverson's cultural impact extended beyond basketball — his cornrows and baggy clothes led to the NBA's dress code in 2005.",
    "LeBron James signed a lifetime deal with Nike worth over $1 billion — the largest athlete endorsement in history.",
    "Wilt Chamberlain wore #13 throughout his career, a number most players avoided due to superstition.",
    "The original NBA jerseys were made of wool, which made players incredibly hot during games.",
    "Chuck Taylor All-Stars were the most popular basketball shoe for decades before modern signature sneakers took over.",
    "The NBA switched from short shorts to baggy ones in the 1990s largely due to Michael Jordan's preference for longer shorts.",
    "Kobe Bryant wore #8 for his first 10 seasons, then switched to #24 — both numbers are retired by the Lakers.",
    "The NBA has no rule against the number 69. However, Dennis Rodman requested it and was denied by the league.",

    # ── Analytics & strategy evolution ────────────────────────
    "The Houston Rockets' 'Moreyball' era popularized the strategy of shooting only threes and layups, minimizing mid-range shots.",
    "In the 2022-23 season, NBA teams averaged 34.2 three-point attempts per game, up from 18.0 in the 2004-05 season.",
    "The 'Hack-a-Shaq' strategy led to rule changes limiting intentional fouling away from the ball in the final two minutes.",
    "PER (Player Efficiency Rating) was created by John Hollinger and became one of the first widely-used advanced stats.",
    "The Golden State Warriors' 'Death Lineup' small-ball unit changed NBA strategy by proving a team could win without a true center.",
    "True Shooting Percentage accounts for free throws and three-pointers, giving a more accurate picture than regular FG%.",
    "The concept of 'pace and space' — spreading the floor with shooters — has become the dominant offensive philosophy in modern NBA.",
    "Win Shares, developed by basketball statistician Dean Oliver, attempts to distribute credit for team wins among individual players.",
    "The corner three-pointer is the most efficient shot in basketball — it's the shortest three-point distance at 22 feet.",
    "Box Plus/Minus (BPM) estimates a player's contribution per 100 possessions relative to an average player.",

    # ── Records that may never be broken ─────────────────────
    "Wilt Chamberlain had 55 rebounds in a single game in 1960 — a record that seems virtually unbreakable.",
    "Scott Skiles dished out 30 assists in a single game in 1990 — nobody has come within 6 assists of that record since.",
    "The 1995-96 Bulls went 72-10, a record that stood for 20 years until the Warriors' 73-9 in 2015-16.",
    "John Stockton's 15,806 career assists are nearly 4,000 ahead of Jason Kidd in second place.",
    "Wilt Chamberlain averaged 48.5 minutes per game in the 1961-62 season — NBA games are only 48 minutes long.",
    "Bill Russell grabbed 51 rebounds in a single game in 1960 — modern big men rarely get 20 in a game.",
    "The Celtics' 8 consecutive championships from 1959-1966 is a record that no team will likely ever approach.",
    "Elgin Baylor scored 61 points in an NBA Finals game in 1962 — a Finals record that stood for over 30 years.",
    "AC Green played 1,192 consecutive games — the NBA's all-time 'Iron Man' streak spanning 16 seasons.",
    "Bob Cousy dished 28 assists in a game in 1959 — a record that stood for 31 years until Scott Skiles broke it.",

    # ── Basketball science & physicality ─────────────────────
    "The average NBA player can jump roughly 28 inches vertically; elite leapers like Zach LaVine exceed 46 inches.",
    "An NBA regulation basketball has a circumference of 29.5 inches and is inflated to between 7.5 and 8.5 PSI.",
    "Studies show NBA players make about 4,000 decisions per game involving passing, shooting, or movement.",
    "The fastest recorded sprint speed by an NBA player during a game is approximately 20.5 mph.",
    "NBA players experience forces of up to 7 times their body weight when landing from a dunk.",
    "The average NBA game features over 200 possessions combined between both teams.",
    "A perfectly shot basketball enters the hoop at an angle of roughly 45 degrees for the highest probability of going in.",
    "Professional basketball players typically have a wingspan-to-height ratio above 1.06 — longer arms than average.",
    "Studies have found that NBA players' reaction times average about 200 milliseconds — 30% faster than the general population.",
    "The 'hot hand' phenomenon in basketball was debated for decades until 2018 research confirmed it exists statistically.",

    # ── Front office, trades & business ──────────────────────
    "The NBA generates over $10 billion in annual revenue, with each franchise valued at over $2 billion on average.",
    "The most lopsided trade in NBA history is often cited as the 1996 deal that sent Kobe Bryant to the Lakers for Vlade Divac.",
    "The NBA's luxury tax system penalizes teams that exceed the salary cap, with repeat offenders paying quadruple the overage.",
    "The Boston Celtics fleeced the Brooklyn Nets in a 2013 trade that netted picks which became Jayson Tatum and Jaylen Brown.",
    "The Harden-for-everyone trade from OKC to Houston in 2012 is considered one of the worst trades for the Thunder.",
    "NBA teams spend millions on sports science departments including sleep specialists, nutritionists, and biomechanics experts.",
    "The NBA's two-way contract was introduced in 2017, allowing teams to shuttle players between the NBA and G League.",
    "The Cleveland Cavaliers won the #1 draft pick four times in a 14-year span (2003, 2011, 2013, 2014).",
    "The Golden State Warriors' value increased from $450 million in 2012 to over $7 billion by 2024.",
    "Pat Riley's 'Big Three' concept in Miami — assembling LeBron, Wade, and Bosh — changed how NBA superstars form teams.",

    # ── All-Star Game & celebrations ─────────────────────────
    "The NBA All-Star Game was first played in 1951 in Boston, with the East beating the West 111-94.",
    "The 2003 All-Star Game in Atlanta featured Michael Jordan's last All-Star appearance — he scored 20 points.",
    "The Slam Dunk Contest debuted in 1984 and was won by Larry Nance Sr. — but it became iconic when Jordan entered in 1987.",
    "Vince Carter's 2000 Slam Dunk Contest performance is widely considered the greatest dunk contest of all time.",
    "Kobe Bryant and Tim Duncan were co-MVPs of the 2001 All-Star Game — the last time the award was shared.",
    "The NBA Three-Point Contest has been won by Larry Bird, Craig Hodges, and Steph Curry — each winning it multiple times.",
    "The All-Star Weekend's Skills Challenge tests big men against guards in dribbling, passing, and shooting drills.",
    "The Rising Stars Challenge showcases the best rookies and sophomores — LeBron dominated it in both his appearances.",
    "Anthony Davis scored 52 points in the 2017 All-Star Game, breaking Wilt Chamberlain's All-Star scoring record of 42.",
    "In 2020, the NBA renamed the All-Star MVP award to the Kobe Bryant MVP Award after Kobe's tragic passing.",

    # ── Underdogs & sleeper stories ──────────────────────────
    "The 2011 Mavericks were the biggest underdog to win the title in modern NBA history, upsetting the LeBron-Wade-Bosh Heat.",
    "Jimmy Butler went undrafted out of high school, was homeless as a teen, and became a six-time All-Star.",
    "The 2004 Pistons had no player average over 17 points per game but won the championship through elite team defense.",
    "Isaiah Thomas (5'9\") averaged 28.9 PPG for the Celtics in 2016-17 despite being one of the shortest players in the league.",
    "Ben Wallace went undrafted in 1996 and became a four-time Defensive Player of the Year and NBA champion.",
    "The 1994 and 1995 Rockets won back-to-back titles — the only championships won without a top-2 seed in the West.",
    "Udonis Haslem went undrafted, played for a league in France, and came back to win three NBA championships with the Heat.",
    "The 2007 Warriors pulled off a historic first-round upset of the top-seeded Dallas Mavericks as the 8th seed.",
    "Fred VanVleet went undrafted in 2016 and became a key starter on the 2019 champion Toronto Raptors.",
    "The 1999 Knicks became the first 8th seed to reach the NBA Finals, led by Patrick Ewing's injured replacement, Allan Houston.",

    # ── Forgotten legends & hidden gems ──────────────────────
    "Pete Maravich averaged 44.2 PPG in college without a three-point line and a shot clock — still the NCAA record.",
    "George Mikan was so dominant in the 1940s-50s that the NBA widened the lane from 6 feet to 12 feet because of him.",
    "Nate Archibald is the only player in NBA history to lead the league in both scoring and assists in the same season.",
    "Bob Pettit was the first NBA player to score 20,000 career points and the first to win the All-Star Game MVP.",
    "Elvin Hayes scored 39 points against Lew Alcindor (Kareem) in the 1968 'Game of the Century' watched by 52,000 fans.",
    "Walt Frazier's Game 7 performance in the 1970 Finals — 36 points, 19 assists — is one of the greatest Finals games ever.",
    "Dave Cowens, at just 6'9\", won MVP in 1973 as one of the shortest centers to ever dominate the league.",
    "Moses Malone's famous '4-4-4' prediction for the 1983 playoffs almost came true — the Sixers went 12-1.",
    "Earl Monroe was nicknamed 'Black Jesus' for his mesmerizing playground-style moves that revolutionized guard play.",
    "Rick Barry shot free throws underhanded ('granny style') and holds one of the highest career free throw percentages ever.",

    # ── Coaching strategy & philosophy ────────────────────────
    "Phil Jackson used Zen Buddhism and Native American spirituality to motivate players — earning him the nickname 'Zen Master.'",
    "The 'Triangle Offense' used by Phil Jackson was actually created by assistant coach Tex Winter.",
    "Don Nelson pioneered 'Nellie Ball' — a fast-paced, three-point-heavy style that was decades ahead of its time.",
    "The Detroit Pistons' 'Bad Boys' defense under Chuck Daly was so physical it led to changes in how referees called fouls.",
    "Rick Carlisle is known for making more in-game adjustments than almost any other coach in NBA history.",
    "Doc Rivers earned his nickname from his grandmother and Julius Erving — it has nothing to do with his coaching style.",
    "Mike D'Antoni's 'Seven Seconds or Less' offense with the Suns in the mid-2000s was the precursor to today's pace-and-space NBA.",
    "Red Holzman's coaching philosophy was simple: 'See the ball, hit the open man' — it won two championships for the Knicks.",
    "Larry Brown is the only coach to win both an NCAA championship and an NBA championship.",
    "Tyronn Lue was the first rookie head coach to win an NBA title since Pat Riley in 1982.",

    # ── Wild stats & oddities ────────────────────────────────
    "In 1983, the Denver Nuggets and Detroit Pistons combined for 370 points in a triple-overtime game — the highest-scoring NBA game ever.",
    "The NBA once had a rule where the team that was behind could choose which basket to shoot at to start the 4th quarter.",
    "Rasheed Wallace holds the record for most technical fouls in a single season with 41 in 2000-01.",
    "Ron Artest (Metta World Peace) legally changed his name and thanked his psychiatrist in his championship acceptance speech.",
    "The NBA's shortest-ever game delay was caused by a bat flying around the court in San Antonio.",
    "Draymond Green is the only player in NBA history to record a triple-double without scoring in double figures.",
    "In 1998, the Vancouver Grizzlies and Toronto Raptors played an NBA game in Tokyo, Japan.",
    "Karl Malone and John Stockton played together for 18 seasons — the longest-tenured duo in NBA history.",
    "James Harden once recorded a 60-point triple-double, joining Wilt Chamberlain as the only players to do so at the time.",
    "The NBA once considered adding a 4-point line at 30 feet but ultimately rejected the idea.",

    # ── Expansion era & relocations ──────────────────────────
    "The Charlotte Hornets moved to New Orleans in 2002, and Charlotte got a new team (the Bobcats) in 2004 before reclaiming the Hornets name in 2014.",
    "The Seattle SuperSonics relocated to Oklahoma City in 2008 and became the Thunder — one of the most controversial moves in NBA history.",
    "The NBA expanded to Canada in 1995 with the Toronto Raptors and Vancouver Grizzlies. Only Toronto survived.",
    "The Sacramento Kings nearly moved to Seattle, Anaheim, and Virginia Beach before their new arena deal kept them in Sacramento.",
    "The Brooklyn Nets were originally the New Jersey Americans in the ABA before becoming the Nets and eventually moving to Brooklyn in 2012.",
    "The Memphis Grizzlies started as the Vancouver Grizzlies in 1995 and relocated to Memphis in 2001.",
    "The original Charlotte Hornets were one of the most popular expansion teams ever, selling out 364 consecutive games.",
    "The Oklahoma City Thunder made the playoffs in their third season after relocating — one of the fastest turnarounds for a relocated franchise.",
    "The New Orleans Pelicans were formerly the Hornets, who were formerly the Charlotte Hornets — one of the most confusing franchise name histories.",
    "The ABA-NBA merger in 1976 brought four teams into the NBA: the Nets, Pacers, Nuggets, and Spurs.",

    # ── Salary cap & contracts ───────────────────────────────
    "The first NBA salary cap was set at $3.6 million in 1984-85. By 2024-25 it had grown to approximately $141 million.",
    "Kevin Garnett's 6-year, $126 million extension in 1997 was so large it led directly to the 1998-99 NBA lockout.",
    "The 'supermax' contract extension, introduced in 2017, allows teams to offer their own players up to 35% of the salary cap.",
    "LeBron James's lifetime Nike deal, reportedly worth over $1 billion, dwarfs any NBA contract ever signed.",
    "The 'mid-level exception' allows teams over the salary cap to sign a free agent for a set amount — a key tool for contenders.",
    "The NBA's luxury tax was introduced in the 1999 CBA to penalize big-spending teams and promote competitive balance.",
    "Steph Curry signed a 4-year, $215 million extension in 2021 — the largest contract in NBA history at the time.",
    "The 'Bird Rights' rule, named after Larry Bird, allows teams to exceed the salary cap to re-sign their own players.",
    "Patrick Ewing's $33.5 million contract in 1996 was considered astronomical — today that's barely above the average NBA salary.",
    "The NBA's 'stretch provision' allows teams to waive a player and spread the dead money over twice the remaining years plus one.",

    # ── Mascots & entertainment ──────────────────────────────
    "The Chicago Bulls' mascot Benny the Bull is considered the best mascot in the NBA and has been performing since 1969.",
    "The Phoenix Suns' Gorilla became one of the first NBA mascots to go viral, famous for trampoline dunks during timeouts.",
    "The Toronto Raptors' mascot is called 'The Raptor' and once fell off his in-arena ATV during a performance.",
    "The San Antonio Spurs' Coyote once tried to distract opposing free throw shooters by eating a burrito on the baseline.",
    "Benny the Bull was inducted into the Mascot Hall of Fame in 2005 — the first NBA mascot to receive the honor.",
    "The Utah Jazz Bear has been suspended multiple times for overly aggressive antics with opposing fans and players.",
    "The Cleveland Cavaliers' mascot Moondog once lowered from the rafters on a wire to half-court — a signature entrance.",
    "The Brooklyn Nets are one of the few NBA teams that don't have an official mascot.",
    "The Phillie Phanatic inspired many NBA mascots — teams realized a great mascot could become a revenue-generating brand.",
    "The Miami Heat's Burnie has performed at every Heat home game since 1988 and is one of the longest-serving NBA mascots.",

    # ── Draft busts & what-ifs ───────────────────────────────
    "Sam Bowie was drafted #2 overall in 1984 — one pick ahead of Michael Jordan — and is often called the biggest draft bust in NBA history.",
    "Greg Oden, the #1 pick in 2007 over Kevin Durant, played only 105 NBA games due to chronic knee injuries.",
    "Len Bias, drafted #2 overall by the Celtics in 1986, tragically died of a cocaine overdose just two days after the draft.",
    "Darko Milicic was picked #2 in the legendary 2003 draft — ahead of Carmelo Anthony, Chris Bosh, and Dwyane Wade.",
    "Anthony Bennett became the first #1 overall pick to be waived by the team that drafted him (Cleveland, 2013).",
    "Kwame Brown, the #1 pick in 2001, was only 18 and became one of the most criticized top picks in NBA history.",
    "The Portland Trail Blazers passed on Michael Jordan AND Kevin Durant (#1 picks Sam Bowie in 1984 and Greg Oden in 2007).",
    "Hasheem Thabeet was drafted #2 in 2009 over James Harden and Steph Curry — he averaged just 2.2 PPG in his career.",
    "Michael Olowokandi, the #1 pick in 1998, averaged only 8.3 points per game over his nine-year career.",
    "LaRue Martin, the #1 pick in 1972, averaged just 5.3 PPG and is considered one of the worst top picks ever.",

    # ── Streaks & durability ─────────────────────────────────
    "The 1971-72 Lakers won 33 consecutive games — a record that stood for over 50 years.",
    "The 2015-16 Warriors started 24-0, the best start in NBA history.",
    "LeBron James played in 1,163 consecutive regular-season games without missing one between 2005 and 2012.",
    "The 2010-11 Cleveland Cavaliers lost 26 consecutive games — the longest losing streak in NBA history at the time.",
    "The Philadelphia 76ers went 9-73 in 1972-73, the worst record in NBA history until the 2015-16 76ers' tank job.",
    "The 2023-24 Detroit Pistons lost 28 consecutive games, breaking the all-time NBA losing streak record.",
    "Karl Malone played 18 seasons without missing more than one game in a single season until his final year.",
    "Robert Parish played until age 43, appearing in 1,611 regular-season games — the most in NBA history at the time.",
    "Kareem Abdul-Jabbar played 20 NBA seasons, the longest career for a #1 overall pick at the time.",
    "John Havlicek played all 16 of his NBA seasons with the Boston Celtics and never missed the playoffs.",

    # ── Halftime & off-court entertainment ────────────────────
    "The NBA All-Star Saturday Night features the Slam Dunk Contest, Three-Point Contest, and Skills Challenge.",
    "Red Panda, the famous halftime acrobat who balances bowls on her head while unicycling, has performed at over 1,500 NBA games.",
    "The Jabbawockeez dance crew has been the official halftime entertainment partner for multiple NBA teams.",
    "NBA arenas use 'decibel meters' during games — the loudest recorded crowd noise in an NBA arena exceeded 126 decibels.",
    "The T-shirt cannon was popularized in NBA arenas in the 1990s and is now a staple of every home game experience.",
    "Some NBA teams have had live animal mascots — the Bucks once had a real deer at their arena.",
    "The 'Kiss Cam' was first used in NBA arenas in the 1980s and has produced some of the most viral sports moments.",
    "NBA teams collectively spend over $50 million per year on in-arena entertainment and game-night production.",
    "The Golden State Warriors' 'Strength in Numbers' fan campaign became one of the most recognizable slogans in sports.",
    "The Philadelphia 76ers' 'Trust the Process' became a cultural phenomenon that transcended basketball.",

    # ── Training & preparation ───────────────────────────────
    "NBA teams now employ full-time sleep scientists to optimize player rest schedules during the grueling 82-game season.",
    "Kobe Bryant was famous for his '4 AM workouts' — arriving at the gym before dawn for extra practice sessions.",
    "LeBron James reportedly spends over $1.5 million per year on his body, including cryotherapy, hyperbaric chambers, and personal chefs.",
    "Stephen Curry's pregame shooting routine has become a viral spectacle, with fans arriving early to watch his tunnel shots.",
    "NBA teams use player-tracking cameras (Second Spectrum) that record every movement at 25 frames per second.",
    "The average NBA player consumes roughly 3,500-4,500 calories per day during the season to maintain peak performance.",
    "Many NBA players use float tanks (sensory deprivation tanks) for recovery and mental clarity between games.",
    "Tim Grover, Michael Jordan's personal trainer, also trained Kobe Bryant and Dwyane Wade.",
    "The NBA's 'load management' strategy — resting healthy stars — became controversial when Kawhi Leonard sat out games in 2019.",
    "Modern NBA shooters use video analysis tools that break down their shot mechanics frame by frame to identify micro-adjustments.",

    # ── Broadcasting & media ─────────────────────────────────
    "Marv Albert's 'Yes!' call is one of the most iconic catchphrases in NBA broadcasting history.",
    "The NBA signed an 11-year, $76 billion media deal in 2024 with Disney, NBC, and Amazon — the largest in sports history.",
    "Inside the NBA on TNT, featuring Charles Barkley, Shaquille O'Neal, Kenny Smith, and Ernie Johnson, is considered the best studio show in sports.",
    "The NBA was the first major U.S. sports league to embrace social media, launching official accounts on Twitter and Instagram early on.",
    "Mike Breen's 'BANG!' call during big three-pointers has become synonymous with clutch NBA moments.",
    "The NBA League Pass streaming service launched in 2003, making the NBA an early adopter of direct-to-consumer sports streaming.",
    "Ahmad Rashad's sideline interviews in the 1990s set the standard for in-game player access in NBA broadcasting.",
    "TNT's 'Players Only' broadcast experiment in 2018-19, using only former players as commentators, received mixed reviews.",
    "The NBA's official YouTube channel has over 20 million subscribers, making it one of the most-followed sports channels globally.",
    "Doris Burke became the first woman to serve as a full-time NBA game analyst for ESPN in 2020.",

    # ── Unusual rules & rare plays ───────────────────────────
    "A player can technically score 0 points but still record a triple-double with assists, rebounds, and steals or blocks.",
    "The 'Elam Ending' — removing the game clock and playing to a target score — was tested in the 2020 NBA All-Star Game.",
    "A 'natural shooting motion' foul has been debated for years — the NBA cracked down on non-basketball moves in 2021-22.",
    "The NBA's 'clear path' foul rule awards two free throws plus possession to the fouled team on fast-break fouls.",
    "An 'alley-oop' was originally considered showboating and was actually illegal in some early basketball rule sets.",
    "The NBA experimented with a 'no-charge zone' semicircle under the basket starting in the 1997-98 season.",
    "A 'flagrant 2' foul results in automatic ejection — the player is removed from the game and can be fined or suspended.",
    "The NBA's 'take foul' rule, introduced in 2022-23, awards one free throw plus possession on transition fouls.",
    "A 'double dribble' is one of the most basic violations but has been controversially missed in high-stakes playoff games.",
    "The NBA allows coaches to 'challenge' one call per game using instant replay — a rule introduced in the 2019-20 season.",

    # ── Fashion & pregame tunnels ─────────────────────────────
    "The NBA pregame tunnel walk became a fashion runway in the 2010s, with players wearing designer outfits documented by photographers.",
    "Russell Westbrook is widely considered the NBA's most fashion-forward player, often wearing avant-garde outfits to games.",
    "The NBA relaxed its strict dress code in 2023, allowing players to wear more casual attire during non-game appearances.",
    "Kyle Kuzma's giant pink sweater at a 2022 game went viral and became one of the most talked-about NBA fashion moments.",
    "LeBron James arrived at a 2018 playoff game wearing a custom Thom Browne suit valued at over $30,000.",
    "Jordan Brand generates over $5 billion in annual revenue — more than some NBA teams are worth.",
    "The 'players' tunnel' camera setup was pioneered by NBA photographer Andrew Bernstein in the early 2010s.",
    "Dwyane Wade is now a fashion mogul post-retirement, co-owning a clothing brand and attending Paris Fashion Week.",
    "P.J. Tucker is known as the NBA's 'Sneaker King,' owning over 5,000 pairs of rare sneakers.",
    "The NBA's Christmas Day games always feature special edition uniforms designed uniquely for the holiday matchups.",

    # ── International impact ──────────────────────────────────
    "Dirk Nowitzki became the first European-born player to win NBA MVP in 2007 and Finals MVP in 2011.",
    "Yao Ming's arrival in Houston in 2002 transformed the NBA into a global brand, especially across Asia.",
    "Giannis Antetokounmpo grew up in Athens, Greece, selling goods on the street before becoming a two-time NBA MVP.",
    "Luka Dončić won the EuroLeague MVP at age 19 before being drafted by the Dallas Mavericks in 2018.",
    "Hakeem Olajuwon, born in Lagos, Nigeria, didn't start playing basketball until age 15 and became an all-time great.",
    "Manu Ginóbili is widely considered the greatest international player in NBA history after a Hall of Fame career with the Spurs.",
    "Tony Parker, born in Belgium and raised in France, became the youngest Finals MVP at 25 in 2007.",
    "The NBA has had players from over 40 different countries play in the league.",
    "Nikola Jokić, from Sombor, Serbia, became the first player from the Balkans to win NBA MVP.",
    "Rui Hachimura became the first Japanese-born player drafted in the first round when Washington selected him in 2019.",

    # ── Iconic arenas & courts ────────────────────────────────
    "Madison Square Garden in New York City is known as 'The Mecca of Basketball' and has hosted NBA games since 1968.",
    "The Boston Celtics' parquet floor at the old Boston Garden had dead spots that only the home team knew about.",
    "Crypto.com Arena (formerly Staples Center) in LA hosted both the Lakers and Clippers until the Clippers moved to the Intuit Dome in 2024.",
    "The Toronto Raptors play at Scotiabank Arena — the only NBA arena located outside the United States.",
    "The Chicago Bulls' United Center is nicknamed 'The Madhouse on Madison' for its raucous home crowd atmosphere.",
    "The Phoenix Suns' Footprint Center was the site of one of the loudest playoff crowds ever recorded in 2021.",
    "The Milwaukee Bucks' Fiserv Forum opened in 2018 and helped keep the franchise from relocating to Las Vegas or Seattle.",
    "The Golden State Warriors moved from Oakland's Oracle Arena to the Chase Center in San Francisco in 2019.",
    "The Utah Jazz's Delta Center (now renamed) was known for having one of the most hostile atmospheres in the NBA.",
    "The Indiana Pacers' Gainbridge Fieldhouse was the first NBA arena to be named after a financial tech company.",

    # ── Playoff & Finals legends ──────────────────────────────
    "Michael Jordan's 'Flu Game' in the 1997 Finals — 38 points while visibly ill — is one of the most iconic performances in NBA history.",
    "LeBron James's chase-down block on Andre Iguodala in Game 7 of the 2016 Finals is considered the greatest block ever.",
    "Ray Allen's corner three-pointer in Game 6 of the 2013 Finals saved the Miami Heat from elimination and is the most clutch shot in Finals history.",
    "Tim Duncan's bank shot against the Suns in the 2008 playoffs was famously called 'The greatest bank shot ever' by commentators.",
    "Kawhi Leonard's buzzer-beater that bounced four times on the rim in Game 7 against the 76ers in 2019 is unforgettable.",
    "Willis Reed's inspirational walk onto the court in Game 7 of the 1970 Finals while injured rallied the Knicks to a championship.",
    "Robert Horry earned the nickname 'Big Shot Rob' for hitting clutch three-pointers in multiple NBA Finals for three different teams.",
    "Derek Fisher's 0.4-second shot against the Spurs in the 2004 playoffs remains one of the most improbable game-winners ever.",
    "Reggie Miller scored 8 points in 8.9 seconds against the Knicks in the 1995 playoffs — one of the greatest comebacks in postseason history.",
    "The 2016 Cavaliers became the first team in NBA history to overcome a 3-1 deficit in the Finals.",

    # ── Coaching legends ──────────────────────────────────────
    "Gregg Popovich has won 5 NBA championships with the Spurs and holds the record for most career wins by a head coach.",
    "Pat Riley coined the term 'three-peat' and trademarked it — he collects royalties whenever the phrase is used commercially.",
    "Red Auerbach celebrated victories by lighting a cigar on the bench — a tradition that became synonymous with Celtics dominance.",
    "Steve Kerr went from being a player with 5 championship rings to a coach with 4 more, totaling 9 rings.",
    "Erik Spoelstra is one of only a few coaches to have never played in the NBA and still win multiple championships.",
    "Lenny Wilkens is the only person in NBA history to be inducted into the Hall of Fame as both a player and a coach.",
    "Jack Ramsay coached the Portland Trail Blazers to their only championship in 1977 with the iconic Bill Walton-led team.",
    "Chuck Daly, coach of the 'Bad Boy' Pistons, was also the head coach of the original 1992 Olympic Dream Team.",
    "Rudy Tomjanovich's famous quote 'Don't ever underestimate the heart of a champion' came after the Rockets' 1995 title.",
    "Mike Budenholzer won Coach of the Year in 2015 and 2019, then led the Bucks to a championship in 2021.",

    # ── Draft night drama ─────────────────────────────────────
    "The 1996 NBA Draft produced Kobe Bryant, Allen Iverson, Steve Nash, and Ray Allen — arguably the greatest draft class ever.",
    "The 2003 Draft featured LeBron James, Carmelo Anthony, Chris Bosh, and Dwyane Wade — four future Hall of Famers.",
    "Kobe Bryant was drafted 13th overall by the Charlotte Hornets and immediately traded to the Lakers for Vlade Divac.",
    "The NBA Draft Lottery was introduced in 1985 after the league wanted to prevent teams from deliberately tanking.",
    "The 1984 Draft produced Hakeem Olajuwon, Michael Jordan, Charles Barkley, and John Stockton — four of the top 50 players ever.",
    "Stephen Curry was drafted 7th overall in 2009 — six teams passed on the greatest shooter in basketball history.",
    "Giannis Antetokounmpo was drafted 15th overall in 2013, with many teams underestimating his raw potential.",
    "The New York Knicks won the first-ever NBA Draft Lottery in 1985, selecting Patrick Ewing — sparking conspiracy theories that persist today.",
    "Tim Duncan was the consensus #1 pick in 1997 and is considered the safest draft pick in NBA history — delivering exactly as promised.",
    "Kevin Garnett was the first player drafted directly from high school in the modern era (1995), paving the way for Kobe, LeBron, and others.",

    # ── Rivalries & feuds ─────────────────────────────────────
    "The Lakers-Celtics rivalry is the most storied in NBA history — they've met in the Finals 12 times.",
    "The Michael Jordan vs. Isiah Thomas rivalry was so intense that Jordan reportedly kept Thomas off the 1992 Dream Team.",
    "Shaq and Kobe's feud nearly destroyed the Lakers dynasty — despite winning three championships together, they couldn't coexist.",
    "The 'Malice at the Palace' brawl between the Pacers and Pistons in 2004 led to the longest suspensions in NBA history.",
    "Larry Bird and Magic Johnson's rivalry, which began in the 1979 NCAA championship game, saved the NBA from declining ratings.",
    "The Knicks-Heat rivalry of the 1990s featured physical, hard-nosed basketball that defined an era of playoff intensity.",
    "Wilt Chamberlain and Bill Russell faced each other 142 times — Russell won 85 of those matchups.",
    "The Warriors-Cavaliers met in four consecutive NBA Finals (2015-2018) — the most by the same two teams in a row.",
    "Reggie Miller's trash-talking feud with Spike Lee during Knicks-Pacers games became one of the NBA's most entertaining subplots.",
    "Tim Duncan and Kevin Garnett had a quiet but fierce rivalry — two power forwards who defined the early 2000s in different ways.",

    # ── Analytics & modern strategy ───────────────────────────
    "The Houston Rockets under Daryl Morey pioneered the 'Moreyball' approach — emphasizing three-pointers and layups while avoiding mid-range shots.",
    "In 2023-24, NBA teams attempted an average of 35 three-pointers per game — up from just 18 per game a decade earlier.",
    "The 'pace and space' era transformed NBA offenses, with nearly every team now employing a five-out shooting lineup.",
    "Player Efficiency Rating (PER) was invented by John Hollinger and became one of the first widely used advanced stats.",
    "The concept of 'true shooting percentage' accounts for free throws and three-pointers, giving a more accurate picture of shooting efficiency.",
    "The NBA introduced the 'Hustle Stats' category in 2016 to track deflections, loose balls recovered, and charges drawn.",
    "Win Shares, a metric that estimates the number of wins a player contributes, was popularized by Basketball-Reference.",
    "The term 'floor spacing' became a coaching buzzword as the three-point revolution made it essential for every player to shoot.",
    "Box Plus/Minus (BPM) estimates a player's contribution per 100 possessions relative to league average.",
    "The 'hot hand' debate — whether shooters get streaky — has been studied for decades with no definitive conclusion.",

    # ── Nicknames & culture ───────────────────────────────────
    "Earvin Johnson got his 'Magic' nickname from a sportswriter after a 36-point, 16-rebound, 16-assist performance in high school.",
    "Karl Malone was nicknamed 'The Mailman' because he always delivered — except, critics note, in the biggest moments.",
    "Allen Iverson's 'The Answer' nickname reflected his ability to respond to every challenge thrown at him on the court.",
    "Julius Erving's 'Dr. J' nickname originated in his teenage years, reportedly given to him by a high school friend.",
    "Shaquille O'Neal had more nicknames than any NBA player — Shaq, Diesel, The Big Aristotle, Superman, and The Big Cactus, among others.",
    "Dwyane Wade was called 'Flash' early in his career for his lightning-quick drives to the basket.",
    "Tim Duncan was nicknamed 'The Big Fundamental' for his mastery of basic basketball skills — boring but devastatingly effective.",
    "Charles Barkley's 'Round Mound of Rebound' nickname highlighted his undersized frame and dominant rebounding.",
    "Kevin Durant earned 'Slim Reaper' and 'Easy Money Sniper' — two of the most admired nicknames in modern NBA history.",
    "Vince Carter's 'Vinsanity' nickname captured the electric, high-flying style that made him one of the most exciting dunkers ever.",

    # ── Record-breaking moments ───────────────────────────────
    "Klay Thompson scored 37 points in a single quarter against the Sacramento Kings in 2015 — an NBA record.",
    "Devin Booker scored 70 points against the Boston Celtics in 2017, becoming the youngest player to score 70 in a game.",
    "Scott Skiles recorded 30 assists in a single game in 1990 — a record that has stood for over 30 years.",
    "Wilt Chamberlain grabbed 55 rebounds in a single game in 1960 — a record that will almost certainly never be broken.",
    "Russell Westbrook broke Oscar Robertson's single-season triple-double record with 42 in the 2016-17 season.",
    "The 1995-96 Chicago Bulls went 72-10, a record that stood until the Warriors broke it with 73-9 in 2015-16.",
    "Stephen Curry made 402 three-pointers in the 2015-16 season — the first player to ever hit 300, let alone 400.",
    "LeBron James passed Kareem Abdul-Jabbar to become the NBA's all-time leading scorer on February 7, 2023.",
    "John Stockton's career assist record of 15,806 is considered one of the most unbreakable records in all of sports.",
    "Wilt Chamberlain once played an entire 48-minute game without committing a single foul — in an era of physical play.",

    # ── Off-season & summer league ────────────────────────────
    "The NBA Summer League in Las Vegas has become a major scouting event, attracting over 500 NBA executives and scouts annually.",
    "Many NBA stars spend their off-seasons training in exotic locations — Chris Paul famously runs camps in the U.S. Virgin Islands.",
    "The Drew League in Los Angeles is a legendary pro-am where NBA stars play pickup games during the off-season.",
    "NBA free agency typically begins on June 30th at 6 PM ET, and the first hours are a frenzy of signings and trades.",
    "The Jamal Crawford Pro-Am in Seattle has featured stars like LeBron James and Kevin Durant playing in a community gym.",
    "NBA players who are traded mid-season must physically relocate within 48 hours, often leaving everything behind.",
    "The concept of 'tampering' — teams contacting players before free agency — has led to multiple fines and investigations.",
    "Many NBA players take up surfing, golf, or wine-making during the off-season to decompress from the grind.",
    "The Rico Hines runs in LA have become the most famous off-season pickup games, attracting dozens of NBA players.",
    "NBA teams host 'minicamp' sessions in September before training camp, though player attendance is technically voluntary.",

    # ── Underdogs & Cinderella runs ──────────────────────────
    "The 1994-95 Houston Rockets are the only team in NBA history to win a championship as a 6th seed.",
    "The 2006-07 Golden State Warriors shocked the #1 seed Dallas Mavericks in the first round — the 'We Believe' Warriors.",
    "The 2010-11 Dallas Mavericks swept the defending champion Lakers and then beat the Miami Heat superteam for the title.",
    "The 1999 New York Knicks became the first (and only) 8th seed to reach the NBA Finals.",
    "Jimmy Butler's 2022-23 playoff run with the Heat as an 8-seed nearly toppled the Nuggets dynasty before it started.",
    "The 2003-04 Detroit Pistons won the title with no All-Stars on the roster — the ultimate team-first championship.",
    "The 1977 Portland Trail Blazers came back from 0-2 against the 76ers to win their only championship with Bill Walton.",
    "The 2019 Toronto Raptors became the first team outside the U.S. to win an NBA championship.",
    "The 2014 San Antonio Spurs dismantled the Heat with the most beautiful team basketball ever played in the Finals.",
    "Hakeem Olajuwon led the Rockets to back-to-back titles in 1994 and 1995 while Michael Jordan was playing baseball.",

    # ── Technology & innovation ───────────────────────────────
    "The NBA was the first major sports league to offer a virtual reality viewing experience, launching NextVR in 2016.",
    "NBA courts are now equipped with 'smart floors' that can detect player positioning and impact force in real time.",
    "The NBA's partnership with Microsoft Surface tablets on sidelines began in 2014, replacing traditional clipboard play diagrams.",
    "Second Spectrum's optical tracking cameras capture 25 frames per second, generating over 1 million data points per game.",
    "NBA 2K is the best-selling basketball video game franchise of all time, with over 120 million copies sold worldwide.",
    "The NBA introduced LED-lit basketball courts in 2018 for special events, allowing the court design to change dynamically.",
    "Wearable tech like Whoop bands and Catapult vests are now standard equipment during NBA practices for load monitoring.",
    "The NBA's official app supports augmented reality features that let fans virtually place trophies and players in their living rooms.",
    "Player-tracking data has shown that NBA players collectively run over 250,000 miles per season — roughly 10 trips around Earth.",
    "The NBA experimented with in-game betting integration during the 2023 In-Season Tournament broadcasts.",

    # ── Legendary duos & trios ───────────────────────────────
    "Magic Johnson and Kareem Abdul-Jabbar won five championships together — the most successful duo in Lakers history.",
    "Michael Jordan and Scottie Pippen combined for six championships and are considered the greatest duo in NBA history.",
    "Tim Duncan, Tony Parker, and Manu Ginóbili won four titles together — the winningest trio in modern NBA history.",
    "LeBron James and Dwyane Wade led the Miami Heat to four consecutive Finals appearances from 2011 to 2014.",
    "Steph Curry and Klay Thompson, the 'Splash Brothers,' combined for 484 three-pointers in the 2015-16 season.",
    "Shaquille O'Neal and Kobe Bryant won three consecutive championships from 2000 to 2002 despite constant internal conflict.",
    "Kevin Durant and Russell Westbrook led OKC to the 2012 Finals as a young duo before their partnership dissolved.",
    "Isiah Thomas and Joe Dumars anchored the 'Bad Boy' Pistons to back-to-back championships in 1989 and 1990.",
    "Chris Paul and Blake Griffin turned the Clippers from NBA laughingstock to 'Lob City' — one of the most entertaining teams ever.",
    "Stockton-to-Malone became synonymous with the pick-and-roll — they ran it to perfection over 18 seasons together.",

    # ── Court dimensions & equipment ─────────────────────────
    "An NBA court is exactly 94 feet long and 50 feet wide — dimensions that haven't changed since 1961.",
    "The three-point line is 23 feet 9 inches from the basket at the arc, and 22 feet at the corners.",
    "NBA basketballs are inflated to between 7.5 and 8.5 pounds per square inch and weigh about 22 ounces.",
    "The basketball hoop stands exactly 10 feet high — the same height James Naismith used when he invented the game in 1891.",
    "NBA backboards are made of tempered glass, measuring 6 feet wide and 3.5 feet tall, and can withstand tremendous force.",
    "The free-throw line is exactly 15 feet from the backboard — a distance that has remained constant since the game's invention.",
    "NBA courts use hard maple wood from forests in Michigan and Wisconsin — each court requires about 200 individual boards.",
    "The 'restricted area' arc beneath the basket has a radius of 4 feet and prevents charges from being drawn too close to the hoop.",
    "Each NBA team has 14 regulation basketballs available for each game, selected from a pool of 72 balls per team per season.",
    "The shot clock resets to 14 seconds after an offensive rebound — a rule change introduced in 2018-19 to speed up play.",

    # ── Game-day rituals & superstitions ──────────────────────
    "Michael Jordan wore his University of North Carolina shorts under his Bulls uniform for every single NBA game.",
    "LeBron James performs his signature chalk toss at center court before every home game — a ritual since his Cleveland days.",
    "Jason Kidd used to blow a kiss to the basket before every free throw attempt throughout his 19-year career.",
    "Karl Malone would talk to the basketball before shooting free throws, earning curious looks from opponents.",
    "Rajon Rondo would watch film of every opponent for at least 2 hours before each game — even regular-season matchups.",
    "Gilbert Arenas insisted on eating a full meal of pancakes exactly 4 hours before every game for his entire career.",
    "Kevin Garnett would headbutt the stanchion before every game — a pre-game ritual that left dents in arena equipment.",
    "Many NBA players refuse to shave during playoff runs — the 'playoff beard' tradition originated in hockey but spread to basketball.",
    "Steve Nash would wet his hands and run them through his hair before every free throw — a quirky ritual fans loved.",
    "Caron Butler used to chew on straws during games until the NBA banned them from the bench in 2010.",

    # ── Business & franchise values ──────────────────────────
    "The New York Knicks are the most valuable NBA franchise, worth approximately $7.5 billion as of 2024.",
    "The Golden State Warriors' value skyrocketed from $450 million in 2010 to over $7 billion by 2024.",
    "NBA total revenue exceeded $13 billion for the 2023-24 season — more than triple what it was a decade earlier.",
    "The average NBA team is now worth over $4 billion — up from $1.1 billion just ten years ago.",
    "Joe Lacob purchased the Warriors for $450 million in 2010 — it's now considered the best sports investment in modern history.",
    "The NBA's salary cap has grown from $3.6 million in 1984 to over $140 million — a nearly 40x increase.",
    "Michael Jordan bought the Charlotte Bobcats for $275 million in 2010 and sold the Hornets for $3 billion in 2023.",
    "NBA players collectively earn about $4.5 billion in salary annually — roughly 50% of basketball-related income.",
    "The NBA generates over $1.5 billion per year in merchandise sales, with LeBron James consistently the top jersey seller.",
    "Courtside seats at Madison Square Garden can cost over $10,000 per game — the most expensive in the NBA.",

    # ── Legendary performances ────────────────────────────────
    "LeBron James scored 25 straight points for the Cavaliers in the 4th quarter of Game 5 of the 2007 Eastern Conference Finals.",
    "Allen Iverson scored 48 points and crossed over Tyronn Lue in Game 1 of the 2001 Finals — the Sixers' lone victory.",
    "Isiah Thomas scored 25 third-quarter points on a severely sprained ankle in Game 6 of the 1988 Finals — one of the gutsiest performances ever.",
    "Tracy McGrady scored 13 points in 35 seconds against the Spurs in 2004 — the most improbable comeback by a single player.",
    "Damian Lillard's 37-foot buzzer-beater to eliminate the Thunder in the 2019 playoffs became an instant classic.",
    "Dirk Nowitzki averaged 26 PPG in the 2011 Finals while playing through a torn tendon in his left hand.",
    "Kevin Garnett's 32-point, 21-rebound Game 3 in the 2008 Finals cemented the Celtics' dominance over the Lakers.",
    "Hakeem Olajuwon's 'Dream Shake' destroyed David Robinson in the 1995 Western Conference Finals — the most dominant post moves ever.",
    "Stephen Curry scored 17 points in overtime against the Thunder in 2016 — capped by a 37-foot buzzer-beating three.",
    "Jaylen Brown's 40-point Game 3 in the 2024 Finals helped the Celtics sweep the Mavericks for their 18th championship.",

    # ── Trades that changed history ──────────────────────────
    "The Celtics trading for Kevin Garnett and Ray Allen in 2007 created the modern NBA 'Big Three' superteam model.",
    "The Pau Gasol trade from Memphis to the Lakers in 2008 gave Kobe Bryant the co-star he needed for two more titles.",
    "The James Harden trade from OKC to Houston in 2012 sent a future MVP for Kevin Martin and draft picks — considered one of the worst trades ever.",
    "The Chris Paul trade veto by David Stern in 2011 (as NBA-owned Hornets' decision-maker) was the most controversial non-trade in NBA history.",
    "The Kawhi Leonard trade from San Antonio to Toronto in 2018 resulted in a championship — and then Leonard left for the Clippers.",
    "The Wilt Chamberlain trade to the Lakers in 1968 united him with Jerry West and created one of the first superteams.",
    "The Charles Barkley trade to Phoenix in 1992 immediately made the Suns a title contender and Barkley an MVP.",
    "The Kevin Durant sign-and-trade to the Warriors in 2016 created the most stacked roster in modern NBA history.",
    "The Carmelo Anthony trade from Denver to New York in 2011 gutted the Knicks' roster for a star who never won a playoff series there.",
    "The Luka Dončić draft-night trade — Dallas sent the #5 pick (Trae Young) to Atlanta for the #3 pick — reshuffled two franchises' futures.",

    # ── Jerseys & uniforms ───────────────────────────────────
    "The Miami Heat's 'Vice' City Edition jerseys became the best-selling alternate uniform in NBA history when launched in 2018.",
    "Michael Jordan's #23 Bulls jersey is the best-selling NBA jersey of all time across all eras.",
    "The NBA's 'City Edition' uniform program, introduced in 2017, lets teams create unique jerseys inspired by their home city's culture.",
    "The Toronto Raptors' purple dinosaur jersey from the 1990s is now one of the most sought-after retro jerseys in the NBA.",
    "Nike took over as the NBA's official uniform supplier in 2017, replacing Adidas after an 11-year partnership.",
    "The 1972 Portland Trail Blazers' pinstripe uniform is considered one of the worst jersey designs in NBA history.",
    "LeBron James' #6 jersey became the NBA's top seller within weeks of his move to that number with the Lakers in 2021.",
    "The Golden State Warriors' 'The Town' jersey paying homage to Oakland sold out within hours of its release.",
    "NBA jerseys now feature a 2.5-inch sponsor patch on the chest — a practice that began in the 2017-18 season.",
    "The Charlotte Hornets' original teal-and-purple color scheme was one of the most popular in 1990s sports culture.",

    # ── Comebacks & collapses ────────────────────────────────
    "The Clippers blew a 3-1 series lead to the Rockets in the 2015 Western Conference Semifinals — part of their 'cursed' history.",
    "The Warriors blew a 3-1 lead in the 2016 Finals — the only team in NBA Finals history to lose after leading 3-1.",
    "The Celtics came back from 0-3 to force a Game 7 against the 76ers in the 1968 Eastern Division Finals — the ultimate comeback.",
    "The Rockets came back from 20 points down in the second half to beat the Clippers in Game 6 of the 2015 playoffs.",
    "The Trail Blazers blew a 15-point fourth-quarter lead against the Lakers in Game 7 of the 2000 Western Conference Finals.",
    "The Nuggets came back from 3-1 down against the Clippers in the 2020 bubble playoffs — then did it again against the Jazz.",
    "The Cavaliers' historic 3-1 Finals comeback in 2016 is considered the greatest championship run in NBA history.",
    "The Pacers blew an 8-point lead with 19 seconds left against the Knicks in Game 1 of the 1995 Eastern Conference Semifinals.",
    "The Spurs' epic collapse in Game 6 of the 2013 Finals — blowing a 5-point lead with 28 seconds left — still haunts San Antonio.",
    "The Celtics trailed the Warriors 2-1 in the 2022 Finals but couldn't close, losing the last three games by a combined 44 points.",

    # ── Rookie sensations ───────────────────────────────────
    "Wilt Chamberlain averaged 37.6 points and 27.0 rebounds per game in his rookie season — both still rookie records.",
    "LeBron James won Rookie of the Year in 2004, averaging 20.9 points, 5.5 rebounds, and 5.9 assists per game.",
    "Blake Griffin's poster dunk over Timofey Mozgov in 2011 became the defining image of his Rookie of the Year campaign.",
    "Luka Dončić won Rookie of the Year unanimously in 2019, the first European player to do so.",
    "David Robinson averaged 24.3 points per game as a rookie in 1990, earning him Rookie of the Year honors.",
    "Patrick Ewing was the first overall pick in 1985 and won Rookie of the Year, averaging 20.0 points per game.",
    "Ben Simmons won Rookie of the Year in 2018, despite being drafted in 2016 — he missed his first season entirely with a foot injury.",
    "Pau Gasol became the first non-American to win NBA Rookie of the Year in 2002.",

    # ── Legendary clutch moments ─────────────────────────────
    "Ray Allen's corner three-pointer in Game 6 of the 2013 Finals saved the Heat's season and is considered the greatest shot in Finals history.",
    "Kyrie Irving's three-pointer over Stephen Curry with 53 seconds left sealed the Cavaliers' 2016 championship.",
    "Robert Horry earned the nickname 'Big Shot Rob' for hitting seven game-winning shots in the playoffs across three different teams.",
    "Reggie Miller scored 8 points in 8.9 seconds against the Knicks in the 1995 Eastern Conference Semifinals.",
    "Derek Fisher hit a buzzer-beating shot with 0.4 seconds left against the Spurs in Game 5 of the 2004 Western Conference Semifinals.",
    "Damian Lillard's series-ending three-pointer over Paul George from 37 feet in 2019 sent the Thunder home and became an iconic moment.",
    "John Havlicek's steal at the end of the 1965 Eastern Conference Finals prompted the famous call: 'Havlicek stole the ball!'",
    "Michael Jordan's last shot as a Bull — the 1998 Finals Game 6 winner over Bryon Russell — is simply known as 'The Last Shot.'",

    # ── All-Star weekend lore ────────────────────────────────
    "The NBA Slam Dunk Contest began in 1984 and was won by Larry Nance in its inaugural year.",
    "Vince Carter's 2000 Slam Dunk Contest performance — featuring an elbow-in-the-rim dunk — is widely regarded as the greatest ever.",
    "Michael Jordan won the 1988 Slam Dunk Contest with his iconic free-throw line dunk, beating Dominique Wilkins.",
    "The 2020 Slam Dunk Contest saw Aaron Gordon and Derrick Jones Jr. trade perfect 50s in one of the most controversial finishes ever.",
    "Nate Robinson is the only player in NBA history to win the Slam Dunk Contest three times.",
    "Craig Hodges won three consecutive Three-Point Contests from 1990 to 1992 — the longest winning streak in the event's history.",
    "Magic Johnson scored 22 points in the 1992 All-Star Game despite having retired months earlier, winning his second All-Star MVP.",
    "Kobe Bryant scored 28 points in the 2001 All-Star Game and had some of the most memorable moments in All-Star history.",

    # ── Franchise origins & oddities ─────────────────────────
    "The Toronto Raptors got their name from a nationwide 'Name Game' contest inspired by the popularity of Jurassic Park in 1994.",
    "The Sacramento Kings are the oldest franchise in the NBA, founded as the Rochester Royals in 1923.",
    "The Jazz got their name while located in New Orleans — the name stuck even after the team moved to Utah in 1979.",
    "The Lakers were named for Minnesota's famous lakes — the name stayed when they relocated to Los Angeles in 1960.",
    "The Memphis Grizzlies were originally the Vancouver Grizzlies, Canada's first NBA expansion team in 1995.",
    "The Oklahoma City Thunder were previously the Seattle SuperSonics — one of the most controversial relocations in NBA history.",
    "The Pelicans replaced the Hornets name in New Orleans in 2013 when Charlotte reclaimed its original Hornets identity.",
    "The Brooklyn Nets moved from New Jersey in 2012, playing their first season at Barclays Center.",

    # ── Defensive dominance ──────────────────────────────────
    "Ben Wallace won the Defensive Player of the Year award four times in five seasons (2002-2006) despite being undrafted.",
    "Dikembe Mutombo's finger wag after blocking a shot became one of the NBA's most iconic celebrations.",
    "The 2004 Detroit Pistons held opponents to under 84 points per game in the playoffs en route to their championship.",
    "Bill Russell won five MVP awards largely because of his defensive prowess and shot-blocking, despite blocks not being officially tracked.",
    "Gary Payton is the only point guard ever to win the NBA Defensive Player of the Year award, earning it in 1996.",
    "Kawhi Leonard won back-to-back Defensive Player of the Year awards in 2015 and 2016, the first perimeter player to do so since Sidney Moncrief.",
    "Marcus Camby led the NBA in blocks per game three times and averaged 3.3 blocks per game in the 2006-07 season.",
    "The 1996 Chicago Bulls allowed just 92.9 points per game while winning 72 games — an elite defensive squad.",

    # ── Milestone moments ────────────────────────────────────
    "LeBron James became the youngest player in NBA history to reach 30,000 career points, doing so at age 33.",
    "Karl Malone finished his career with 36,928 points — second all-time until LeBron passed him in 2023.",
    "John Stockton holds the all-time assists record with 15,806 — nearly 4,000 more than second-place Jason Kidd.",
    "Robert Parish played in 1,611 NBA games — the most in league history — across 21 seasons.",
    "Wilt Chamberlain grabbed 55 rebounds in a single game against the Boston Celtics in 1960 — the all-time single-game record.",
    "Kareem Abdul-Jabbar played 20 NBA seasons and appeared in the All-Star Game 19 times.",

    # ── Playoff drama & upsets ──────────────────────────────
    "The 2007 Golden State Warriors, as an 8-seed, upset the top-seeded Dallas Mavericks — the first 8-over-1 upset since 1999.",
    "The 2011 Dallas Mavericks, led by Dirk Nowitzki, defeated the Miami Heat's 'Big Three' to win the championship as underdogs.",
    "The 1994 Houston Rockets are the only 6-seed to ever win the NBA Championship, sweeping Shaq's Orlando Magic in the Finals.",
    "The New York Knicks, as an 8-seed in 1999, reached the NBA Finals — the lowest seed ever to make it that far.",
    "The 2004 Detroit Pistons upset the heavily favored Los Angeles Lakers in five games — one of the biggest Finals upsets ever.",
    "The 1969 Boston Celtics, as a 4-seed in the East, defeated the Lakers to win the championship in Bill Russell's final season.",

    # ── Longevity & endurance ────────────────────────────────
    "Kareem Abdul-Jabbar scored 24,000 of his career points using his signature skyhook — the most unstoppable move in NBA history.",
    "Kevin Garnett played 21 seasons in the NBA and was named to 15 All-Star teams, the most by any power forward.",
    "A.C. Green played in 1,192 consecutive NBA games — the longest ironman streak in league history.",
    "LeBron James has played in more career playoff minutes than any player in NBA history, surpassing 12,000 minutes.",
    "Udonis Haslem played 20 seasons — all with the Miami Heat — the longest single-team tenure by an undrafted player.",
    "Jason Terry played 19 NBA seasons, appearing in 1,410 games and winning a championship with the Mavericks in 2011.",
)

# Number of facts to embed in each loading screen.
# Set to the full pool size so facts never repeat within a session.
_FACTS_PER_SCREEN = len(NBA_FUN_FACTS)


# ═════════════════════════════════════════════════════════════
# CSS — loading screen styles (glassmorphic dark theme)
# ═════════════════════════════════════════════════════════════

JOSEPH_LOADING_CSS = """<style>
/* ── Joseph Loading Screen ────────────────────────────────── */
@keyframes josephBounceIn {
    0%   { opacity:0; transform:scale(0.3) translateY(40px); }
    40%  { opacity:1; transform:scale(1.12) translateY(-12px); }
    65%  { transform:scale(0.95) translateY(4px); }
    85%  { transform:scale(1.03) translateY(-2px); }
    100% { opacity:1; transform:scale(1) translateY(0); }
}
@keyframes josephPulseGlow {
    0%, 100% { box-shadow:0 0 20px rgba(255,94,0,0.35),
                          0 0 60px rgba(255,94,0,0.08),
                          inset 0 0 15px rgba(255,94,0,0.05); }
    50%      { box-shadow:0 0 35px rgba(255,94,0,0.55),
                          0 0 90px rgba(255,94,0,0.15),
                          inset 0 0 20px rgba(255,94,0,0.10); }
}
@keyframes avatarRingRotate {
    0%   { transform:translate(-50%,-50%) rotate(0deg); border-color:rgba(255,94,0,0.6) rgba(0,240,255,0.4) rgba(255,94,0,0.3) rgba(0,240,255,0.2); }
    25%  { transform:translate(-50%,-50%) rotate(90deg); border-color:rgba(0,240,255,0.4) rgba(255,94,0,0.6) rgba(0,240,255,0.2) rgba(255,94,0,0.3); }
    50%  { transform:translate(-50%,-50%) rotate(180deg); border-color:rgba(255,94,0,0.3) rgba(0,240,255,0.2) rgba(255,94,0,0.6) rgba(0,240,255,0.4); }
    75%  { transform:translate(-50%,-50%) rotate(270deg); border-color:rgba(0,240,255,0.2) rgba(255,94,0,0.3) rgba(0,240,255,0.4) rgba(255,94,0,0.6); }
    100% { transform:translate(-50%,-50%) rotate(360deg); border-color:rgba(255,94,0,0.6) rgba(0,240,255,0.4) rgba(255,94,0,0.3) rgba(0,240,255,0.2); }
}
@keyframes basketballBounce {
    0%, 100% { transform:translateY(0) rotate(0deg); }
    25%      { transform:translateY(-14px) rotate(90deg); }
    50%      { transform:translateY(0) rotate(180deg); }
    75%      { transform:translateY(-8px) rotate(270deg); }
}
@keyframes basketballSpin {
    0%   { transform:rotate(0deg); }
    100% { transform:rotate(360deg); }
}
@keyframes factFadeIn {
    0%   { opacity:0; transform:translateY(12px); }
    100% { opacity:1; transform:translateY(0); }
}
@keyframes factFadeOut {
    0%   { opacity:1; transform:translateY(0); }
    100% { opacity:0; transform:translateY(-12px); }
}
@keyframes dotsAnimation {
    0%   { content:'.'; }
    33%  { content:'..'; }
    66%  { content:'...'; }
}
@keyframes courtLineGlow {
    0%, 100% { opacity:0.12; }
    50%      { opacity:0.28; }
}
@keyframes particleDrift {
    0%   { transform:translateY(0) translateX(0) scale(1); opacity:0; }
    15%  { opacity:0.6; }
    85%  { opacity:0.3; }
    100% { transform:translateY(-200px) translateX(40px) scale(0.3); opacity:0; }
}
@keyframes shimmerSlide {
    0%   { background-position:-200% center; }
    100% { background-position:200% center; }
}
@keyframes progressPulse {
    0%, 100% { opacity:0.7; width:20%; }
    50%      { opacity:1; width:60%; }
}
@keyframes glowBreath {
    0%, 100% { filter:blur(30px) brightness(0.8); }
    50%      { filter:blur(45px) brightness(1.2); }
}

/* ── Outer wrapper ───────────────────────────────────────── */
.joseph-loading-overlay {
    position:relative;
    width:100%;
    min-height:460px;
    background:
        radial-gradient(ellipse at 50% 0%, rgba(255,94,0,0.08) 0%, transparent 50%),
        radial-gradient(ellipse at 80% 80%, rgba(0,240,255,0.05) 0%, transparent 40%),
        radial-gradient(ellipse at 20% 90%, rgba(200,0,255,0.04) 0%, transparent 40%),
        linear-gradient(180deg, #060a14 0%, #0a1020 35%, #0d1428 65%, #101830 100%);
    border:1px solid rgba(255,94,0,0.22);
    border-radius:24px;
    overflow:hidden;
    display:flex;
    flex-direction:column;
    align-items:center;
    justify-content:center;
    padding:40px 32px 36px;
    margin:16px 0;
    backdrop-filter:blur(2px);
    -webkit-backdrop-filter:blur(2px);
    box-shadow:0 8px 40px rgba(0,0,0,0.45),
               0 0 80px rgba(255,94,0,0.04),
               inset 0 1px 0 rgba(255,255,255,0.03);
}

/* ── Ambient glow behind avatar ──────────────────────────── */
.joseph-loading-ambient-glow {
    position:absolute;
    top:30%; left:50%;
    width:300px; height:300px;
    border-radius:50%;
    background:radial-gradient(circle,
        rgba(255,94,0,0.25) 0%,
        rgba(255,94,0,0.10) 30%,
        rgba(0,240,255,0.05) 50%,
        transparent 70%);
    transform:translate(-50%,-50%);
    animation:glowBreath 4s ease-in-out infinite;
    pointer-events:none;
    z-index:0;
}

/* ── Basketball court lines (decorative background) ──────── */
.joseph-loading-overlay::before {
    content:'';
    position:absolute;
    top:50%; left:50%;
    width:200px; height:200px;
    border:2px solid rgba(255,94,0,0.08);
    border-radius:50%;
    transform:translate(-50%,-50%);
    animation:courtLineGlow 3.5s ease-in-out infinite;
    pointer-events:none;
}
.joseph-loading-overlay::after {
    content:'';
    position:absolute;
    top:0; left:50%;
    width:1px; height:100%;
    background:linear-gradient(180deg,
        transparent 0%,
        rgba(255,94,0,0.07) 25%,
        rgba(255,94,0,0.07) 75%,
        transparent 100%);
    animation:courtLineGlow 3.5s ease-in-out infinite 1.5s;
    pointer-events:none;
}

/* ── Free-throw semi-circle ──────────────────────────────── */
.joseph-loading-court-ft {
    position:absolute;
    top:50%; left:50%;
    width:120px; height:60px;
    border:1.5px solid rgba(255,94,0,0.06);
    border-bottom:none;
    border-radius:120px 120px 0 0;
    transform:translate(-50%,-70%);
    animation:courtLineGlow 3.5s ease-in-out infinite 0.8s;
    pointer-events:none;
}

/* ── Three-point arc ─────────────────────────────────────── */
.joseph-loading-court-arc {
    position:absolute;
    top:50%; left:50%;
    width:280px; height:140px;
    border:1.5px solid rgba(255,94,0,0.04);
    border-bottom:none;
    border-radius:280px 280px 0 0;
    transform:translate(-50%,-55%);
    animation:courtLineGlow 3.5s ease-in-out infinite 2s;
    pointer-events:none;
}

/* ── Floating particles ──────────────────────────────────── */
.joseph-loading-particles {
    position:absolute; inset:0;
    overflow:hidden; pointer-events:none; z-index:0;
}
.joseph-loading-particle {
    position:absolute;
    width:3px; height:3px;
    border-radius:50%;
    background:rgba(255,94,0,0.35);
    animation:particleDrift 6s ease-in-out infinite;
}
.joseph-loading-particle:nth-child(2) {
    left:20%; bottom:10%; animation-delay:1s; animation-duration:7s;
    background:rgba(0,240,255,0.25); width:2px; height:2px;
}
.joseph-loading-particle:nth-child(3) {
    left:70%; bottom:20%; animation-delay:2.5s; animation-duration:8s;
    background:rgba(255,94,0,0.25);
}
.joseph-loading-particle:nth-child(4) {
    left:85%; bottom:5%; animation-delay:0.5s; animation-duration:5.5s;
    background:rgba(0,240,255,0.20); width:2px; height:2px;
}
.joseph-loading-particle:nth-child(5) {
    left:35%; bottom:15%; animation-delay:3.5s; animation-duration:9s;
    background:rgba(200,0,255,0.15);
}
.joseph-loading-particle:nth-child(6) {
    left:55%; bottom:8%; animation-delay:4s; animation-duration:6.5s;
    background:rgba(255,94,0,0.20); width:2px; height:2px;
}

/* ── Basketball emoji ────────────────────────────────────── */
.joseph-loading-ball {
    font-size:1.8rem;
    animation:basketballBounce 2s ease-in-out infinite;
    margin-bottom:6px;
    filter:drop-shadow(0 0 10px rgba(255,140,0,0.5));
    z-index:1;
}

/* ── Avatar container ────────────────────────────────────── */
.joseph-loading-avatar-wrap {
    position:relative;
    animation:josephBounceIn 0.9s cubic-bezier(0.34,1.56,0.64,1) both;
    margin-bottom:16px;
    z-index:1;
}
/* Animated ring around avatar */
.joseph-loading-avatar-ring {
    position:absolute;
    top:50%; left:50%;
    width:204px; height:244px;
    border-radius:30px;
    border:2px solid transparent;
    border-top:2px solid rgba(255,94,0,0.6);
    border-right:2px solid rgba(0,240,255,0.4);
    border-bottom:2px solid rgba(255,94,0,0.3);
    border-left:2px solid rgba(0,240,255,0.2);
    animation:avatarRingRotate 4s linear infinite;
    pointer-events:none;
}
.joseph-loading-avatar {
    width:184px; height:220px;
    border-radius:24px;
    object-fit:cover;
    object-position:center 10%;
    border:3px solid rgba(255,94,0,0.5);
    animation:josephPulseGlow 3s ease-in-out infinite;
    background:linear-gradient(180deg, #141c30 0%, #0d1425 100%);
}

/* ── Name badge ──────────────────────────────────────────── */
.joseph-loading-name {
    font-family:'Orbitron','Montserrat',sans-serif;
    font-size:1.0rem;
    font-weight:700;
    color:#ff5e00;
    letter-spacing:2.5px;
    text-transform:uppercase;
    margin-bottom:3px;
    text-shadow:0 0 20px rgba(255,94,0,0.40),
                0 0 40px rgba(255,94,0,0.15);
    z-index:1;
}
.joseph-loading-subtitle {
    font-family:'Montserrat',sans-serif;
    font-size:0.68rem;
    font-weight:500;
    color:rgba(0,240,255,0.60);
    letter-spacing:3.5px;
    text-transform:uppercase;
    margin-bottom:14px;
    z-index:1;
    text-shadow:0 0 12px rgba(0,240,255,0.15);
}

/* ── "Did you know?" label ───────────────────────────────── */
.joseph-loading-label {
    font-family:'Montserrat',sans-serif;
    font-size:0.7rem;
    font-weight:700;
    color:#00f0ff;
    letter-spacing:2.5px;
    text-transform:uppercase;
    margin-bottom:10px;
    opacity:0.9;
    z-index:1;
    text-shadow:0 0 10px rgba(0,240,255,0.2);
}

/* ── Fun fact card (glassmorphic) ────────────────────────── */
.joseph-loading-fact-container {
    position:relative;
    min-height:88px;
    max-width:620px;
    width:100%;
    display:flex;
    align-items:center;
    justify-content:center;
    text-align:center;
    z-index:1;
}
.joseph-loading-fact {
    font-family:'Montserrat',sans-serif;
    font-size:0.95rem;
    line-height:1.65;
    color:#e8edf5;
    padding:18px 28px;
    background:rgba(255,255,255,0.035);
    backdrop-filter:blur(14px);
    -webkit-backdrop-filter:blur(14px);
    border:1px solid rgba(255,94,0,0.14);
    border-radius:16px;
    transition:opacity 0.5s ease, transform 0.5s ease;
    width:100%;
    box-shadow:0 6px 32px rgba(0,0,0,0.30),
               0 0 24px rgba(255,94,0,0.03),
               inset 0 1px 0 rgba(255,255,255,0.05);
    position:relative;
    overflow:hidden;
}
/* Holographic shimmer overlay on fact card */
.joseph-loading-fact::before {
    content:'';
    position:absolute; inset:0;
    background:linear-gradient(110deg,
        transparent 20%,
        rgba(255,94,0,0.04) 40%,
        rgba(0,240,255,0.03) 60%,
        transparent 80%);
    background-size:200% 100%;
    animation:shimmerSlide 6s linear infinite;
    pointer-events:none;
    border-radius:14px;
}

/* ── Animated progress bar ───────────────────────────────── */
.joseph-loading-progress-wrap {
    width:100%;
    max-width:380px;
    height:4px;
    background:rgba(255,255,255,0.06);
    border-radius:4px;
    margin-top:20px;
    overflow:hidden;
    z-index:1;
}
.joseph-loading-progress-bar {
    height:100%;
    border-radius:4px;
    background:linear-gradient(90deg,
        rgba(255,94,0,0.8),
        rgba(0,240,255,0.7),
        rgba(255,94,0,0.8));
    background-size:200% 100%;
    animation:progressPulse 3s ease-in-out infinite,
             shimmerSlide 2s linear infinite;
}

/* ── Status text below fact ──────────────────────────────── */
.joseph-loading-status {
    font-family:'Montserrat',sans-serif;
    font-size:0.73rem;
    color:rgba(226,232,240,0.45);
    margin-top:10px;
    letter-spacing:0.5px;
    z-index:1;
}
.joseph-loading-status::after {
    content:'...';
    animation:dotsAnimation 1.5s steps(3,end) infinite;
}

/* ── Responsive adjustments ──────────────────────────────── */
@media (max-width: 600px) {
    .joseph-loading-overlay { min-height:380px; padding:28px 16px 24px; }
    .joseph-loading-avatar { width:140px; height:168px; border-radius:20px; }
    .joseph-loading-avatar-ring { width:160px; height:188px; border-radius:24px; }
    .joseph-loading-fact { font-size:0.86rem; padding:14px 18px; }
    .joseph-loading-name { font-size:0.85rem; }
    .joseph-loading-fact-container { max-width:95%; }
}
</style>"""


# ═════════════════════════════════════════════════════════════
# Public API
# ═════════════════════════════════════════════════════════════

def get_random_facts(count: int = _FACTS_PER_SCREEN) -> list:
    """Return *count* unique random NBA fun facts from the pool."""
    pool = list(NBA_FUN_FACTS)
    random.shuffle(pool)
    return pool[:count]


def render_joseph_loading_screen(
    status_text: str = "Crunching the numbers",
    fact_count: int = _FACTS_PER_SCREEN,
    rotation_seconds: int = 10,
) -> None:
    """Render Joseph's animated loading screen with rotating NBA fun facts.

    Parameters
    ----------
    status_text : str
        The action label shown below the fact (e.g. "Running analysis").
    fact_count : int
        Number of fun facts to embed (cycled via JavaScript).
    rotation_seconds : int
        Seconds between fact rotations (default 10).
    """
    if st is None:
        return  # pragma: no cover

    # ── Load avatar (prefer Spinning Basketball variant) ────────
    avatar_b64 = ""
    if _AVATAR_AVAILABLE:
        avatar_b64 = get_joseph_avatar_spinning_b64() or get_joseph_avatar_b64()
    if avatar_b64:
        avatar_html = (
            f'<img class="joseph-loading-avatar" '
            f'src="data:image/png;base64,{avatar_b64}" '
            f'alt="Joseph M. Smith" />'
        )
    else:
        # Fallback: basketball emoji if avatar isn't available
        avatar_html = (
            '<div class="joseph-loading-avatar" '
            'style="display:flex;align-items:center;justify-content:center;'
            'font-size:3rem;">🏀</div>'
        )

    # ── Pick random facts ────────────────────────────────────
    clamped = max(1, min(fact_count, len(NBA_FUN_FACTS)))
    facts = get_random_facts(clamped)
    safe_status = _html.escape(status_text)

    # Build JSON-safe facts list (escape for JS embedding)
    facts_json = json.dumps(facts)

    # Unique ID to avoid collisions if multiple loading screens exist
    uid = f"jl_{random.randint(10000, 99999)}"

    html_block = f"""{JOSEPH_LOADING_CSS}
<div class="joseph-loading-overlay" id="{uid}_overlay">
    <!-- Decorative court elements -->
    <div class="joseph-loading-court-ft"></div>
    <div class="joseph-loading-court-arc"></div>
    <div class="joseph-loading-ambient-glow"></div>
    <!-- Floating particles -->
    <div class="joseph-loading-particles">
        <div class="joseph-loading-particle" style="left:10%;bottom:5%"></div>
        <div class="joseph-loading-particle"></div>
        <div class="joseph-loading-particle"></div>
        <div class="joseph-loading-particle"></div>
        <div class="joseph-loading-particle"></div>
        <div class="joseph-loading-particle"></div>
    </div>
    <div class="joseph-loading-ball">🏀</div>
    <div class="joseph-loading-avatar-wrap">
        <div class="joseph-loading-avatar-ring"></div>
        {avatar_html}
    </div>
    <div class="joseph-loading-name">Joseph M. Smith</div>
    <div class="joseph-loading-subtitle">Your NBA Analytics Expert</div>
    <div class="joseph-loading-label">🏀 Did You Know? 🏀</div>
    <div class="joseph-loading-fact-container">
        <div class="joseph-loading-fact" id="{uid}_fact">
            {_html.escape(facts[0])}
        </div>
    </div>
    <div class="joseph-loading-progress-wrap">
        <div class="joseph-loading-progress-bar"></div>
    </div>
    <div class="joseph-loading-status">{safe_status}</div>
</div>
<script>
(function() {{
    var facts = {facts_json};
    var idx = 0;
    var el = document.getElementById("{uid}_fact");
    if (!el || facts.length < 2) return;
    var tid = setInterval(function() {{
        if (!document.contains(el)) {{ clearInterval(tid); return; }}
        if (idx + 1 >= facts.length) {{ clearInterval(tid); return; }}
        el.style.opacity = "0";
        el.style.transform = "translateY(-12px)";
        setTimeout(function() {{
            if (!document.contains(el)) {{ clearInterval(tid); return; }}
            idx = idx + 1;
            el.textContent = facts[idx];
            el.style.transform = "translateY(12px)";
            /* Force reflow before animating in */
            void el.offsetWidth;
            el.style.opacity = "1";
            el.style.transform = "translateY(0)";
        }}, 500);
    }}, {rotation_seconds * 1000});
}})();
</script>"""

    st.html(html_block)


def joseph_loading_placeholder(
    status_text: str = "Crunching the numbers",
    fact_count: int = _FACTS_PER_SCREEN,
    rotation_seconds: int = 10,
):
    """Create a Streamlit placeholder with Joseph's loading screen.

    Returns the ``st.empty()`` placeholder so callers can clear it
    when the operation completes::

        loader = joseph_loading_placeholder("Running analysis")
        # ... do work ...
        loader.empty()

    Parameters
    ----------
    status_text : str
        Action label shown below the fact card.
    fact_count : int
        Number of fun facts to embed.
    rotation_seconds : int
        Seconds between fact rotations.

    Returns
    -------
    streamlit.delta_generator.DeltaGenerator
        The ``st.empty()`` container (call ``.empty()`` to dismiss).
    """
    if st is None:
        return None  # pragma: no cover

    placeholder = st.empty()
    with placeholder.container():
        render_joseph_loading_screen(
            status_text=status_text,
            fact_count=fact_count,
            rotation_seconds=rotation_seconds,
        )
    return placeholder
