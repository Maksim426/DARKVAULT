import math
import random
import pygame
from bosses import (
    BOSS_BASE_CONFIG,
    FLOOR_BOSS_POOLS,
    MINIBOSS_KEYS,
    PLAYABLE_BOSS_KEYS,
    _GRAVITY_PULL_KEYS,
    _TELEPORT_BOSS_KEYS,
)
from cutscene import draw_boss_portrait, draw_hero_portrait
from enemy import REGULAR_ENEMY_TYPES, draw_enemy_visual
from heroes import HERO_ROSTER
from console import CONSOLE_DOC_ENTRIES
from i18n import get_lang, tr, tr_boss, tr_boss_subtitle, tr_room
from items import ITEM_POOL_65, ITEM_REGISTRY, draw_item_icon, tr_item_desc, tr_item_name
from room import NPC_KEYS, draw_npc_visual
from settings import (
    ENEMY_BASE_STATS,
    PALETTE,
    ROOM_COLOR_SCHEMES,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    blit_text_fitted,
    clamp,
    draw_aa_circle,
    draw_aa_ellipse,
    draw_aa_poly,
    draw_aa_ring,
    ease_out_cubic,
    fit_text_surf,
    get_glow_surf,
    get_panel_surf,
    get_particle_surf,
    get_shadow_surf,
    get_view_width,
    get_world_offset_x,
    render_text_cached,
)

CHRONICLE_CHAPTERS = [
    {
        "id": "ch1",
        "title": "Глава I. Ключ под пеплом",
        "title_en": "Chapter I. Key Beneath the Ash",
        "body": (
            "Когда верхний люк захлопнулся с тяжестью надгробной плиты, архивариус оставил на стене лишь одну строку мелом: "
            "«Тьма здесь не пуста — она помнит каждого, кто погасил фонарь». Подвал дышит сыростью старых труб и тихим "
            "звоном капель. Где-то за запертой решёткой щёлкает бобина древнего терминала — кто-то всё ещё крутит старые "
            "записи внизу, хотя лестницы наверх давно нет."
        ),
        "body_en": (
            "When the overhead hatch slammed shut like a gravestone, the archivist left a single chalk line upon the damp brick: "
            "'The dark below is never empty—it remembers every lantern snuffed.' Cold pipes weep in the silence of the Basement, "
            "yet behind rusted bars a tape-deck terminal hums softly. Someone down here is still spinning old reels, though the "
            "ladder back to daylight has long since turned to dust."
        ),
    },
    {
        "id": "ch2",
        "title": "Глава II. Двадцать два лица",
        "title_en": "Chapter II. Twenty-Two Faces",
        "body": (
            "В Бездну спускаются не герои, а беглецы от собственного имени. Корвин сжимает Куб Перековки в дрожащих ладонях; "
            "Костяной Страж стучит косой по камню; слепая Никс прислушивается к шёпоту эха; Хронос сверяет "
            "трещины на стекле монокля, а Бледный Серафим тащит обломанные крылья по пыли. Каждый несёт свой грех, но "
            "пламя в глубине у всех одного цвета — белёсого, как пепел."
        ),
        "body_en": (
            "No true saints descend into the Vault—only fugitives outrunning their own names. Corvin clutches a trembling reforge "
            "cube; Marrow raps bone against flagstone; blind Nyx follows the breathing of her echo; Chronos checks fractures "
            "across a cracked monocle while the Pale Seraph drags broken feathers through soot. Every wanderer bears a different "
            "sin, yet every lantern burns the same cold bone-white."
        ),
    },
    {
        "id": "ch3",
        "title": "Глава III. Шаг сквозь пустоту",
        "title_en": "Chapter III. Step Through the Gap",
        "body": (
            "Старые разведчики говорили: «Не пытайся перебежать рой — стань тенью на долю удара сердца». Мгновенный рывок "
            "разрывает воздух, оставляя за спиной призрачный силуэт из сажи, а невидимость прячет след даже от многоглазых "
            "часовых. Но пустота берёт плату за каждый прыжок: слишком частый шаг сквозь тень истончает дыхание, и сам "
            "камень начинает тянуть путника вниз."
        ),
        "body_en": (
            "Veteran delvers left a brief rule etched into pillar bases: 'Never outrun the swarm—slip between heartbeats.' A crisp "
            "shadow-dash tears cleanly through incoming volleys, leaving only grey soot in your silhouette, while stealth blinds "
            "even many-eyed sentries. Still, the void keeps quiet tallies: abuse the leap too recklessly and stone itself begins "
            "to pull at your heels."
        ),
    },
    {
        "id": "ch4",
        "title": "Глава IV. Клеймо реликвий",
        "title_en": "Chapter IV. Forged in Relics",
        "body": (
            "У каждого артефакта Подземелья есть бывший владелец, не дошедший до порога. Одни слёзы превращаются в серные "
            "лучи, другие вязнут вихрем или раскалываются костяными осколками. Замёрзшие часы останавливают падение стрел "
            "прямо в воздухе, а обломки затмения жгут темноту вокруг ладони. Не собирай бездумно — реликвии шепчутся между "
            "собой и переписывают саму плоть."
        ),
        "body_en": (
            "Every relic resting on a velvet pedestal once belonged to someone who failed to return. Some bend tears into sulfur "
            "beams, others shatter into bone splinters or pull nearby light into gravity wells. A cracked hourglass halts bullets "
            "mid-flight; eclipse shards scorch shadows at a finger's snap. Choose carefully—artifacts converse behind your ribs "
            "and rewrite what you are."
        ),
    },
    {
        "id": "ch5",
        "title": "Глава V. Голоса за стеной",
        "title_en": "Chapter V. Voices in the Caves",
        "body": (
            "На втором ярусе стены больше не кажутся мёртвыми. Пещеры Тишины пронизаны нитями Ткачей, а из-под плит "
            "доносится глухой звон Полых Колоколов. Путники находили здесь старые аудиотерминалы с позывным «ПЕПЕЛ FM» — "
            "из треснувших динамиков лилась приглушённая музыка, будто кто-то вёл передачу с глубины, куда ещё не ступала "
            "ни одна живая нога."
        ),
        "body_en": (
            "By the second floor the walls no longer feel dead. Silk lines of Shadow Weavers cross the Caves of Silence, and "
            "Hollow Bells toll softly beneath cracked slabs. Here travelers discovered dusty terminals tuned to 'ASH FM'—muffled "
            "synth melodies drifting through static as if someone were broadcasting from depths no living boot had yet reached."
        ),
    },
    {
        "id": "ch6",
        "title": "Глава VI. Костяная перекличка",
        "title_en": "Chapter VI. Roll Call of Bone",
        "body": (
            "Третий ярус пахнет старым воском и ржавым железом. С потолка свисают цепи, а в нишах притаились каменные лавочники "
            "с пустыми глазницами и бродяги, протягивающие дрожащую ладонь за монетой. В библиотеках Катакомб страницы книг "
            "написаны не чернилами, а выцарапаны иглой по пергаменту: все имена стражей повторяются, словно колесо прокручивает "
            "одну и ту же ночь."
        ),
        "body_en": (
            "The third floor smells of guttering tallow and cold iron. Chains hang from vaulted ceilings where petrified shopkeepers "
            "wait behind counters and hooded beggars trade secrets for copper coins. In Catacomb libraries, margins are scratched "
            "with needles rather than ink: the wardens' names keep repeating across decades, as though a single night were trapped "
            "on an endless reel."
        ),
    },
    {
        "id": "ch7",
        "title": "Глава VII. Камень и Кровь",
        "title_en": "Chapter VII. Stone and Blood",
        "body": (
            "Древние монолиты в залах загораются при прикосновении: их руны возвращают искру угасающему фонарю и заряжают "
            "реликвии, но взамен оставляют в памяти чужое воспоминание. Рядом стоят Алтари Жертв — шипастые плиты, которые "
            "не торгуются за золото. Они требуют живой крови, открывая путь к сундукам душ или вызывая клинки возмездия прямо "
            "в центр зала."
        ),
        "body_en": (
            "Carved monoliths awaken at a touch, pouring pale light back into dying lanterns and charging tired relics—yet every "
            "monolith trades an echo of someone else's memory. Elsewhere, Sacrifice Spikes refuse all gold. Step upon their iron "
            "teeth with open veins and they may answer with soul hearts, sudden treasure, or the blinding descent of judgment blades."
        ),
    },
    {
        "id": "ch8",
        "title": "Глава VIII. Чёрное солнце Некрополя",
        "title_en": "Chapter VIII. Black Sun of Necropolis",
        "body": (
            "Четвёртый ярус встречает мягким слоем серого пепла по щиколотку. Сюда не доходит ветер, но каждый шаг поднимает "
            "в воздух серебристую пыль павших отрядов. Среди колонн дежурят Всадники Засухи, Войны и Смерти, а в боковых "
            "камерах застыли семь каменных идолов Грехов. Даже двойники-мимики притворяются пьедесталами, ожидая доверчивой "
            "руки."
        ),
        "body_en": (
            "Ashen Necropolis buries every flagstone under an inch of silver dust. No wind blows down on Floor Four, yet each "
            "footstep lifts the ghosts of earlier expeditions into the beam of your lamp. Horsemen patrol broken colonnades while "
            "the Seven Sins linger in side crypts and Mimic Doubles pose silently as glowing relic pedestals."
        ),
    },
    {
        "id": "ch9",
        "title": "Глава IX. Зал тысячи волн",
        "title_en": "Chapter IX. Hall of a Thousand Waves",
        "body": (
            "Говорят, Бесконечная Арена была построена до самого Подвала как испытание для тех, кто отказался выбирать сторону. "
            "Двери там заварены изнутри. Волна сменяет волну под бой невидимого метронома, и между каждыми пятью натисками "
            "из пола поднимается одинокий пьедестал. Выжить там — значит научиться читать ритм роя быстрее собственного страха."
        ),
        "body_en": (
            "Rumors say the Endless Arena was carved even deeper and older than the Vault itself, built for wanderers who refused "
            "both salvation and pact. Its doors are welded shut from within. Surge follows surge to an unseen metronome, pausing "
            "only long enough to raise a single relic between wardens. Survival belongs to whoever reads the swarm faster than panic."
        ),
    },
    {
        "id": "ch10",
        "title": "Глава X. Рогатая дверь",
        "title_en": "Chapter X. The Horned Door",
        "body": (
            "Пройти ярус без царапины — редкое чудо, и Бездна замечает его немедленно. За спиной павшего босса в стене "
            "проступает рогатая арка из чёрного стекла. За ней нет сундуков с монетами — только тишина сделки. Торговец в "
            "капюшоне называет цену в целых сердцах, и тот, кто отдаёт часть своей жизни, уносит силу, способную расколоть "
            "сам Шеол."
        ),
        "body_en": (
            "Crossing an entire floor untouched draws the Abyss's quiet admiration. Behind a slain guardian, a horned arch of "
            "black obsidian sometimes bleeds out of solid stone. No coin pouches wait inside—only the silence of a Dark Pact. "
            "Pay in living heart containers and walk back out wielding forbidden power sharp enough to split Sheol open."
        ),
    },
    {
        "id": "ch11",
        "title": "Глава XI. Сердце Шеола",
        "title_en": "Chapter XI. Core of Sheol",
        "body": (
            "На пятом ярусе темнота становится плотной, как чернила, и фонарь дрожит в руке. Зодчий Бездны возводит преграды "
            "прямо посреди боя, Страж Затмения гасит свет, Хроно-Жнец рвёт время в клочья, а Бесформенное Безумие меняет "
            "личины с каждым ударом. Здесь не спасает удача — только связка реликвий, выверенная дистанция и двое спина к спине."
        ),
        "body_en": (
            "On Floor Five the darkness thickens like India ink until lantern glass trembles. The Void Architect raises pillars "
            "mid-duel, the Eclipse Warden swallows sight, Chrono Reaper tears timing apart, and Delirium shifts faces between hits. "
            "Luck fails here—only honed builds, clean spacing, or two allies fighting back-to-back can break the seal."
        ),
    },
    {
        "id": "ch12",
        "title": "Глава XII. Рассвет или Петля",
        "title_en": "Chapter XII. Dawn or the Loop",
        "body": (
            "Когда пятый страж рассыпается пеплом, в зале открываются два пути. Налево — белые Врата Рассвета, ведущие "
            "обратно к забытому небу. Направо — люк в Бесконечный Спуск, на шестой ярус и ниже, где действуют Проклятия "
            "Пепла и Пустоты. И те, кто уже видел рассвет, всё равно возвращаются к старому терминалу, чтобы нажать «Пуск» "
            "ещё раз."
        ),
        "body_en": (
            "When the fifth warden dissolves into cinders, two exits wake in the chamber. To one side shimmers Dawn's Gate back to "
            "a half-forgotten sky; to the other yawns the hatch of Endless Descent into cursed Floor 6 and beyond. Yet even those "
            "who step into morning eventually hear the basement terminal humming again—and descend one more time."
        ),
    },
]

ENEMY_LORE_CUSTOM = {
    "fly": {
        "ru": "Крылатый падальщик с составными фасетчатыми глазами и вибрирующими полупрозрачными крыльями. Кружат по синусоиде, сближаясь вплотную.",
        "en": "Winged crypt scavenger with bulging compound eyes and fluttering translucent wings. Drifts along erratic sinusoidal arcs.",
        "ability_ru": "СПОСОБНОСТЬ: Свободный полёт над ямами и камнями, роение на ближней дистанции.",
        "ability_en": "ABILITY: Ignores pits and rocks; swarms unpredictably at close range.",
    },
    "spider": {
        "ru": "Шестилапый арахнид с четырьмя зоркими глазами и жвалами. Натягивает лапки перед резким рваным рывком к путнику.",
        "en": "Six-legged abyss arachnid with quad eyes and jagged fangs. Coils before lunging in sudden diagonal bursts.",
        "ability_ru": "СПОСОБНОСТЬ: Серии резких рывков с короткими паузами-замираниями.",
        "ability_en": "ABILITY: Executes sudden high-speed lunges interspersed with brief freezes.",
    },
    "pooter": {
        "ru": "Раздутая летающая муха с пухлым брюшком, жалобной пастью и усиками. Парит на средней дистанции, выцеливая героя.",
        "en": "Swollen airborne fly with bloated abdomen, antennae, and drooping maw. Hovers at mid-range to spit dark tears.",
        "ability_ru": "СПОСОБНОСТЬ: Полёт + прицельные выстрелы с отскоком от преград.",
        "ability_en": "ABILITY: Flight + aimed projectile volleys while keeping distance.",
    },
    "gaper": {
        "ru": "Бродячий урод с разверстой бездонной пастью и плачущими провалами глаз. Клонится вперёд, впадая в бешенство от ран.",
        "en": "Weeping husk with hollow eye sockets and a gaping vertical scream. Hunches forward and rushes faster once wounded.",
        "ability_ru": "СПОСОБНОСТЬ: Ярость ранения — заметно ускоряется, потеряв часть ОЗ.",
        "ability_en": "ABILITY: Enrages when injured, gaining burst pursuit speed.",
    },
    "maggot": {
        "ru": "Панцирная хитиновая гусеница с сегментированным брюшком и бронированным тылом. Ползёт по сетке зала.",
        "en": "Chitin-plated burrow worm with heavy dorsal armor plates protecting its rear segments.",
        "ability_ru": "СПОСОБНОСТЬ: Спинной панцирь (-45% урона в тыл). Стреляйте навстречу в голову!",
        "ability_en": "ABILITY: Rear chitin shell (-45% damage from behind). Strike head-on!",
    },
    "clot": {
        "ru": "Пульсирующий сгусток живой слизи со студенистым контуром. Оставляет брызги и раскалывается при уничтожении.",
        "en": "Pulsating clot of dark ichor with bubbling lobes. Quivers forward and splits violently upon death.",
        "ability_ru": "СПОСОБНОСТЬ: Расщепление — при гибели делится на двух юрких мини-сгустков.",
        "ability_en": "ABILITY: Mitosis — splits into two fast mini-clots when destroyed.",
    },
    "hopper": {
        "ru": "Длинноногий прыгун с согнутыми пружинистыми коленями и искривлённой улыбкой. Подпрыгивает высоко в воздух на позицию героя.",
        "en": "Long-legged crypt leaper with coiled hind limbs and crooked grin. Vaults high over pits to slam onto the player.",
        "ability_ru": "СПОСОБНОСТЬ: Высокий прыжок (airborne) через препятствия с неуязвимостью в полёте.",
        "ability_en": "ABILITY: High vault over rocks and pits, briefly untargetable mid-air.",
    },
    "horf": {
        "ru": "Мясистая костяная турель с вытянутыми челюстями и глубокой пастью-дулом. Замирает в камне и плюёт очередью при виде цели.",
        "en": "Rooted skull-head turret with distended jaw and hollow bore throat. Unloads fast shots when aligned.",
        "ability_ru": "СПОСОБНОСТЬ: Прицельные скоростные залпы без передвижения.",
        "ability_en": "ABILITY: Stationary turret firing fast aimed shots on sightlines.",
    },
    "bony": {
        "ru": "Иссушённый скелет с зазубренным черепом и метательной костью в руке. Отступает от врага, швыряя вращающиеся кости.",
        "en": "Rattling bone thrower clutching a jagged femur club. Backpedals swiftly while hurling spinning bones.",
        "ability_ru": "СПОСОБНОСТЬ: Держит дистанцию и бросает костяные снаряды.",
        "ability_en": "ABILITY: Kiting AI — retreats on approach while hurling high-velocity bones.",
    },
    "vis": {
        "ru": "Огромный безголовый торс с вертикально рассечённой грудью и пастью в животе. Копит энергию серы перед мощным выстрелом.",
        "en": "Hulking headless torso split open vertically across the chest cavity. Charges sulfur beams from its torso maw.",
        "ability_ru": "СПОСОБНОСТЬ: Дальнобойные скоростные выстрелы Серы вдоль осей комнаты.",
        "ability_en": "ABILITY: Fires heavy high-speed Brimstone shots along cardinal lines.",
    },
    "boil": {
        "ru": "Живой пульсирующий нарыв с кратерами-язвами и ореолом испарений. Надувается волнами, выстреливая кольцом слёз.",
        "en": "Swollen bubbling pustule covered in weeping craters. Expands rhythmically before erupting radial tear bursts.",
        "ability_ru": "СПОСОБНОСТЬ: Пульсация — раздувается и выпускает круговой залп из 6 слёз.",
        "ability_en": "ABILITY: Swells under pressure and bursts radial 6-tear rings.",
    },
    "leech": {
        "ru": "Узкий зубчатый кровосос с раскрытой круглой пастью и шипами вдоль спины. Бросается на добычу, едва та окажется на линии.",
        "en": "Razor-mawed blood leech lined with dorsal ridges. Streaks forward like a dart along sightlines.",
        "ability_ru": "СПОСОБНОСТЬ: Мгновенное ускорение и таран по прямой.",
        "ability_en": "ABILITY: Sudden sightline dash and ferocious charge.",
    },
    "shadow_weaver": {
        "ru": "Тёмный шестилапый ткач с короной глаз, острой головогрудью и серебристой паутинной нитью на лапах.",
        "en": "Six-legged obsidian arachnid bearing a crown of pale eyes and silver silk threads.",
        "ability_ru": "СПОСОБНОСТЬ: Выпускает веер из 3 замедляющих снарядов и резко меняет фланги.",
        "ability_en": "ABILITY: Casts 3-shot shadow fans while strafing sideways.",
    },
    "whispering_phantom": {
        "ru": "Окутанный белым дымом призрак в рваном саване с мерцающими провалами глаз. Оставляет за собой шлейф туманных частиц.",
        "en": "Drifting wraith clad in tattered mist-shroud with hollow glowing sockets and trailing smoke.",
        "ability_ru": "СПОСОБНОСТЬ: Полёт + медленные самонаводящиеся сгустки шёпота.",
        "ability_en": "ABILITY: Flight + fires slow homing whisper orbs.",
    },
    "mimic_double": {
        "ru": "Коварный двойник с зубастой трещиной маскировки и четырьмя теневыми щупальцами, вырывающимися при засаде.",
        "en": "Deceptive shapeshifter hiding behind a cracked stone pedestal mask before sprouting 4 shadow tentacles.",
        "ability_ru": "СПОСОБНОСТЬ: Засада — спит под видом пьедестала, затем бросается и стреляет веером.",
        "ability_en": "ABILITY: Ambush — disguises as a relic pedestal until approached.",
    },
    "many_eyed_watcher": {
        "ru": "Парящая сфера с гигантским зрячим оком в центре и восемью живыми глазами-спутниками, вращающимися по орбите.",
        "en": "Floating ocular sphere with a central glaring pupil surrounded by 8 orbiting satellite eyes.",
        "ability_ru": "СПОСОБНОСТЬ: Спиральные 8-лучевые залпы слёз при полном обзоре арены.",
        "ability_en": "ABILITY: Full flight + rotating 8-way spiral tear barrages.",
    },
    "ash_stalker": {
        "ru": "Остроухий пепельный силуэт с загнутыми когтями и светящимся разрезом глаз. Скользит зигзагами с дымчатым следом.",
        "en": "Horned ashen predator with curved claws and a luminous eye-slit, trailing dark shadow embers.",
        "ability_ru": "СПОСОБНОСТЬ: Стремительные фланговые рывки зигзагом со следом.",
        "ability_en": "ABILITY: High-speed zig-zag ambushes from flank angles.",
    },
    "hollow_bell": {
        "ru": "Подвешенный кованый колокол с треснувшим ободом, железным языком и светящейся руной звука.",
        "en": "Suspended iron funeral bell etched with a glowing chime rune and heavy swinging clapper.",
        "ability_ru": "СПОСОБНОСТЬ: Резонансный набат — звонит с ударным кольцом и выпускает 10-лучевой залп.",
        "ability_en": "ABILITY: Rings with a visible shockwave ring, unleashing 10-way acoustic volleys.",
    },
    "thread_serpent": {
        "ru": "Рогатая змеевидная тварь с огранённой головой и цепочкой сегментированных позвонков в шлейфе.",
        "en": "Horned facet-headed serpent trailing a chain of articulated skeletal vertebrae across the room.",
        "ability_ru": "СПОСОБНОСТЬ: Синусоидальное скольжение и веерные плевки ядом.",
        "ability_en": "ABILITY: Sinuous weaving pursuit with aimed spread volleys.",
    },
}

NPC_CUSTOM = {
    "pale_wanderer": {
        "name": "Бледный Странник",
        "name_en": "Pale Wanderer",
        "desc": "Высокий путник в плаще, короне ветвей и с посохом-фонарём. Бескорыстно делится Сердцем души и разжигает угасающий фонарь.",
        "desc_en": "Cloaked pilgrim bearing a branch crown and glowing lantern staff. Freely grants a Soul Heart and lantern fuel.",
        "stats_ru": "ЦЕНА: БЕСПЛАТНО  ·  НАГРАДА: +1 СЕРДЦЕ ДУШИ + ПЛАМЯ ФОНАРЯ",
        "stats_en": "COST: FREE  ·  REWARD: +1 SOUL HEART + LANTERN FUEL",
    },
    "silent_shadow": {
        "name": "Молчаливая Тень",
        "name_en": "Silent Shadow",
        "desc": "Тёмный безмолвный силуэт в мантии с яркой звездой лба и четырьмя зрячими очами. За 2 монеты или 0.5 сердца дарит Чёрное сердце и силу.",
        "desc_en": "Cloaked dark silhouette with glowing forehead star and twin eyes. Trades 2 coins or half a heart for Black Heart + DMG.",
        "stats_ru": "ЦЕНА: 2 МОНЕТЫ / 0.5 ХП  ·  НАГРАДА: +0.85 УРОН + ЧЁРНОЕ СЕРДЦЕ",
        "stats_en": "COST: 2 COINS / 0.5 HP  ·  REWARD: +0.85 DMG + BLACK HEART",
    },
    "ancient_oracle": {
        "name": "Древний Оракул",
        "name_en": "Ancient Oracle",
        "desc": "Парящий провидец с третьим глазом и вращающимся лунным ореолом. Раскрывает всю карту яруса и дарует случайный артефакт.",
        "desc_en": "Floating seer crowned with a third eye and spinning crescent halo. Reveals the entire floor map and drops a relic.",
        "stats_ru": "ЦЕНА: ВСТРЕЧА  ·  НАГРАДА: ВСЯ КАРТА ЭТАЖА + ПЬЕДЕСТАЛ",
        "stats_en": "COST: ENCOUNTER  ·  REWARD: FULL MAP REVEAL + RELIC PEDESTAL",
    },
    "lore_monolith": {
        "name": "Древний Монолит",
        "name_en": "Lore Monolith",
        "desc": "Треугольная рунная стела из тёмного базальта. При касании делится хроникой, полностью заряжает реликвию и питает фонарь.",
        "desc_en": "Carved basalt obelisk etched with glowing runes. Whispers lore, recharges active relics, and feeds your lantern.",
        "stats_ru": "ЦЕНА: КАСАНИЕ  ·  НАГРАДА: ЗАРЯД РЕЛИКВИИ + ТОПЛИВО + ЛОР",
        "stats_en": "COST: TOUCH  ·  REWARD: FULL RELIC CHARGE + LANTERN + LORE",
    },
    "coin_beggar": {
        "name": "Нищий Монет",
        "name_en": "Coin Beggar",
        "desc": "Сгорбленный проситель в лохмотьях с чашей для милостыни. Принимает монеты и при насыщении дарит пьедестал с реликвией.",
        "desc_en": "Hunched beggar clutching a tin bowl. Collects coins for pickups before vanishing behind a free passive relic pedestal.",
        "stats_ru": "ЦЕНА: 1 МОНЕТА  ·  ШАНС: ~28% НА ПЬЕДЕСТАЛ АРТЕФАКТА",
        "stats_en": "COST: 1 COIN  ·  CHANCE: ~28% RELIC PEDESTAL PAYOUT",
    },
    "devil_beggar": {
        "name": "Демонический Нищий",
        "name_en": "Devil Beggar",
        "desc": "Рогатый проситель в капюшоне. Питается жизненной силой странника, взамен порождая ресурсы или запретные реликвии.",
        "desc_en": "Horned shrouded beggar craving life force. Accepts half a heart per tribute to drop pickups or dark relics.",
        "stats_ru": "ЦЕНА: 0.5 СЕРДЦА  ·  НАГРАДА: ПРИПАСЫ ИЛИ РЕЛИКВИЯ",
        "stats_en": "COST: 0.5 HEART  ·  REWARD: PICKUPS OR RELIC PEDESTAL",
    },
    "key_master": {
        "name": "Хранитель Ключей",
        "name_en": "Key Master",
        "desc": "Мастер в зубчатой короне со связкой отмычек. Меняет ключи на сундуки, припасы и редкие пьедесталы.",
        "desc_en": "Key-crowned keeper clutching ring keys. Exchanges keys for pickups, chests, and hidden relic pedestals.",
        "stats_ru": "ЦЕНА: 1 КЛЮЧ  ·  НАГРАДА: ПРИПАСЫ ИЛИ ПЬЕДЕСТАЛ",
        "stats_en": "COST: 1 KEY  ·  REWARD: PICKUPS OR RELIC PEDESTAL",
    },
    "bomb_bum": {
        "name": "Подрывник",
        "name_en": "Bomb Bum",
        "desc": "Подрывник в очках с фитилём в руках. Собирает бомбы и осыпает пол трофеями или пассивным артефактом.",
        "desc_en": "Goggled demolitions hermit holding a burning fuse. Collects bombs in return for pickups or a relic pedestal.",
        "stats_ru": "ЦЕНА: 1 БОМБА  ·  НАГРАДА: ПРИПАСЫ ИЛИ АРТЕФАКТ",
        "stats_en": "COST: 1 BOMB  ·  REWARD: PICKUPS OR RELIC PEDESTAL",
    },
    "rotten_beggar": {
        "name": "Гнилой Попрошайка",
        "name_en": "Rotten Beggar",
        "desc": "Повелитель роя в плаще с крылышками мух. За каждую монету призывает двух верных Синих Мух-союзников и сердца.",
        "desc_en": "Fly-wreathed hermit draped in tattered cloth. Each coin summons two loyal Blue Fly allies and bonus hearts.",
        "stats_ru": "ЦЕНА: 1 МОНЕТА  ·  НАГРАДА: 2 СИНИЕ МУХИ + СЕРДЦА / РЕЛИКВИЯ",
        "stats_en": "COST: 1 COIN  ·  REWARD: 2 BLUE FLY ALLIES + HEARTS / RELIC",
    },
    "battery_bum": {
        "name": "Энергетический Бродяга",
        "name_en": "Battery Bum",
        "desc": "Искра-бродяга в катушечной шапке. За 2 монеты мгновенно заряжает активную реликвию и может оставить активный том.",
        "desc_en": "Spark-crowned tinkerer. For 2 coins instantly recharges your active relic and may award an active item pedestal.",
        "stats_ru": "ЦЕНА: 2 МОНЕТЫ  ·  НАГРАДА: ПОЛНЫЙ ЗАРЯД + АКТИВНЫЙ ПЬЕДЕСТАЛ",
        "stats_en": "COST: 2 COINS  ·  REWARD: FULL ACTIVE CHARGE + ACTIVE RELIC",
    },
    "relic_beggar": {
        "name": "Святой Паломник",
        "name_en": "Relic Beggar",
        "desc": "Паломник со свитками и нимбом. Принимает по 2 монеты и обладает повышенным шансом выдать пассивный артефакт (36%).",
        "desc_en": "Haloed scroll-bearer accepting 2-coin offerings with an elevated 36% pedestal payout rate.",
        "stats_ru": "ЦЕНА: 2 МОНЕТЫ  ·  ШАНС: 36% ПОВЫШЕННЫЙ ВЫБРОС РЕЛИКВИИ",
        "stats_en": "COST: 2 COINS  ·  CHANCE: 36% HIGH RELIC PAYOUT",
    },
    "blood_bank_keeper": {
        "name": "Хранитель Крови",
        "name_en": "Blood Bank Keeper",
        "desc": "Мрачный алхимик с капельной колбой. Выменивает половину сердца на горсть звенящих монет или редкий предмет.",
        "desc_en": "Alchemist carrying a glass blood vial. Exchanges half a heart for coins or an eventual relic pedestal.",
        "stats_ru": "ЦЕНА: 0.5 СЕРДЦА  ·  НАГРАДА: 1-2 МОНЕТЫ / ПЬЕДЕСТАЛ",
        "stats_en": "COST: 0.5 HEART  ·  REWARD: 1-2 COINS / PEDESTAL",
    },
    "shopkeeper": {
        "name": "Лавочник",
        "name_en": "Shopkeeper",
        "desc": "Окаменелый хранитель лавки (4 уникальных обличия: классический, алчный, безмолвный и близнец). Взрыв бомбой роняет монеты или пауков.",
        "desc_en": "Petrified merchant (4 variants: classic, greedy, silent, twin). Bombing drops either coins or angry spiders.",
        "stats_ru": "ТИП: ТОРГОВЕЦ  ·  4 ОБЛИКА  ·  БОМБА: МОНЕТЫ ИЛИ ПАУКИ",
        "stats_en": "TYPE: MERCHANT  ·  4 VARIANTS  ·  BOMB: COINS OR SPIDERS",
    },
    "slot_machine": {
        "name": "Игровой Автомат",
        "name_en": "Slot Machine",
        "desc": "Резной однорукий бандит с барабанами. За 1 монету выкидывает монеты, сердца, бомбы, ключи или взрывается джекпотом.",
        "desc_en": "Ornate single-arm bandit machine. Spins for 1 coin to yield pickups or explode with a prize jackpot.",
        "stats_ru": "ЦЕНА: 1 МОНЕТА  ·  БОМБА: ДРОП 3 ПРИПАСОВ",
        "stats_en": "COST: 1 COIN  ·  BOMB: DROPS 3 PICKUPS",
    },
    "blood_donation": {
        "name": "Аппарат Донорства",
        "name_en": "Blood Donation Machine",
        "desc": "Медицинский насос с сосудом крови и манометром. Превращает 0.5 сердца в 1-3 монеты и с шансом даёт Пакет крови.",
        "desc_en": "Medical pump with glass blood reservoir. Converts 0.5 heart into 1-3 coins and a chance at Blood Bag.",
        "stats_ru": "ЦЕНА: 0.5 СЕРДЦА  ·  НАГРАДА: МОНЕТЫ + ШАНС 'ПАКЕТА КРОВИ'",
        "stats_en": "COST: 0.5 HEART  ·  REWARD: COINS + 'BLOOD BAG' CHANCE",
    },
    "fortune_teller": {
        "name": "Гадалка",
        "name_en": "Fortune Teller",
        "desc": "Хрустальный шар прорицания на резном постаменте. За 1 монету открывает пророчество, дарует Сердца души и карты удачи.",
        "desc_en": "Glowing crystal orb mounted on an ornate pedestal. Spends 1 coin for prophecies, Soul Hearts, and pickup drops.",
        "stats_ru": "ЦЕНА: 1 МОНЕТА  ·  НАГРАДА: СЕРДЦА ДУШИ И ПРЕДСКАЗАНИЯ",
        "stats_en": "COST: 1 COIN  ·  REWARD: SOUL HEARTS & PROPHECIES",
    },
    "restock_machine": {
        "name": "Автомат Обновления",
        "name_en": "Restock Machine",
        "desc": "Механический куб с вращающимися стрелками. За 1 монету (или взрыв бомбы) мгновенно меняет товары и пьедесталы в комнате.",
        "desc_en": "Clockwork reroll cube adorned with twin rotation arrows. Rerolls room pedestals and pickups for 1 coin or a bomb blast.",
        "stats_ru": "ЦЕНА: 1 МОНЕТА / БОМБА  ·  ДЕЙСТВИЕ: ПЕРЕБРОС ТОВАРОВ",
        "stats_en": "COST: 1 COIN / BOMB  ·  ACTION: REROLLS SHOP STOCK",
    },
    "crane_game": {
        "name": "Кран-Машина",
        "name_en": "Crane Game",
        "desc": "Стеклянный куб с металлическим захватом и реликвией внутри. За 3 монеты даёт 35% шанс вытянуть артефакт на арену.",
        "desc_en": "Glass claw cabinet guarding a relic inside. Pays 3 coins for a 35% chance to pull a relic onto the floor.",
        "stats_ru": "ЦЕНА: 3 МОНЕТЫ  ·  ШАНС: 35% НА ПЬЕДЕСТАЛ (ДО 3 НАГРАД)",
        "stats_en": "COST: 3 COINS  ·  CHANCE: 35% RELIC PAYOUT (UP TO 3)",
    },
    "donation_box": {
        "name": "Копилка Пожертвований",
        "name_en": "Donation Box",
        "desc": "Деревянная казна со щелью для монет. Поглощает монеты, повышая Удачу, а каждые 5 монет порождает случайную реликвию.",
        "desc_en": "Brass-trimmed wooden strongbox. Deposits coins to boost Luck and awards a relic every 5 coins donated.",
        "stats_ru": "ЦЕНА: 1 МОНЕТА  ·  НАГРАДА: +УДАЧА + РЕЛИКВИЯ ЗА 5 МОНЕТ",
        "stats_en": "COST: 1 COIN  ·  REWARD: +LUCK + RELIC EVERY 5 COINS",
    },
    "confessional": {
        "name": "Исповедальня",
        "name_en": "Confessional",
        "desc": "Тёмная резная кабинка со светящимся крестом. За 1 монету исцеляет красные сердца, дарит Сердце души и заряд реликвии.",
        "desc_en": "Gothic carved booth beneath a pale cross. For 1 coin grants red healing, Soul Hearts, and active charge.",
        "stats_ru": "ЦЕНА: 1 МОНЕТА  ·  НАГРАДА: ЛЕЧЕНИЕ / СЕРДЦЕ ДУШИ / ЗАРЯД",
        "stats_en": "COST: 1 COIN  ·  REWARD: HEAL / SOUL HEART / CHARGE",
    },
    "computer_terminal": {
        "name": "Архивный Терминал",
        "name_en": "Archive Computer",
        "desc": "Старый ЭЛТ-компьютер с катушечным приводом и четырьмя магнитными лентами. Воспроизводит пространственную музыку с учётом расстояния и панорамы.",
        "desc_en": "Vintage CRT workstation with twin tape reels holding 4 atmospheric tracks. Plays spatial stereo audio based on listener distance.",
        "stats_ru": "БЕСПЛАТНО [G / ENTER]  ·  4 ТРЕКА  ·  ПРОСТРАНСТВЕННОЕ СТЕРЕО",
        "stats_en": "FREE [G / ENTER]  ·  4 TRACKS  ·  SPATIAL STEREO AUDIO",
    },
}

ROOM_ORDER = [
    "start",
    "normal",
    "treasure",
    "shop",
    "curse",
    "arcade",
    "sacrifice",
    "library",
    "dice",
    "miniboss",
    "boss",
    "secret",
    "devil",
]

ROOM_CUSTOM = {
    "start": {
        "ru": "Стартовый зал яруса. Освещён факелами, содержит памятку управления и не имеет врагов. Отсюда расходятся пути по всему этажу.",
        "en": "Floor starting chamber lit by warm torches with carved floor hints and no enemies. Branching corridors lead out in four directions.",
        "stats_ru": "ТИП: БЕЗОПАСНАЯ ЗОНА  ·  СВЕТ ФАКЕЛОВ  ·  СТАРТ ЭТАЖА",
        "stats_en": "TYPE: SAFE ZONE  ·  TORCHLIT  ·  FLOOR ORIGIN",
    },
    "normal": {
        "ru": "Боевой зал подземелья. Встречает комбинацией врагов, каменных глыб, колонн, жаровен, урн и шипов. Двери запираются до зачистки.",
        "en": "Combat chamber combining monsters, rocks, pillars, braziers, urns, and pits. Doors seal until every foe falls.",
        "stats_ru": "ТИП: БОЕВОЙ ЗАЛ  ·  НАГРАДА ЗА ЗАЧИСТКУ  ·  УКРЫТИЯ",
        "stats_en": "TYPE: COMBAT ROOM  ·  CLEAR DROP  ·  OBSTACLES",
    },
    "treasure": {
        "ru": "Сокровищница с ярким пьедесталом бесплатного артефакта в центре. Со 2-го яруса дверь заперта и требует 1 Золотой ключ.",
        "en": "Golden-lit vault cradling a free relic pedestal at the center. Locked from Floor 2 onward requiring 1 key.",
        "stats_ru": "ТИП: БЕСПЛАТНАЯ РЕЛИКВИЯ  ·  КЛЮЧ СО 2-ГО ЯРУСА",
        "stats_en": "TYPE: FREE RELIC PEDESTAL  ·  KEY LOCKED FLOOR 2+",
    },
    "shop": {
        "ru": "Лавка торговца под охраной Лавочника. Продаёт 2 реликвии за 15 монет, сердца, бомбы, ключи и содержит Автомат обновления.",
        "en": "Merchant sanctuary overseen by a Shopkeeper. Sells two 15-coin relics, hearts, keys, bombs, plus a Restock Machine.",
        "stats_ru": "ТИП: ТОРГОВЛЯ  ·  РЕЛИКВИИ 15 МОНЕТ  ·  СКИДКА 50% С КУПОНОМ",
        "stats_en": "TYPE: SHOP  ·  15-COIN RELICS  ·  50% OFF WITH STEAM SALE",
    },
    "curse": {
        "ru": "Мрачный зал за шипастой дверью (-0.5 сердца при проходе, если нет полёта). Хранит Чёрные сердца и проклятые дары.",
        "en": "Spiked-door chamber dealing half-heart thorn damage unless flying. Rewards Black Hearts and cursed loot.",
        "stats_ru": "ТИП: ШИПЫ НА ВХОДЕ  ·  ЧЁРНЫЕ СЕРДЦА  ·  ИГНОР ПОЛЁТОМ",
        "stats_en": "TYPE: THORN DOORWAY  ·  BLACK HEARTS  ·  FLIGHT SAFE",
    },
    "arcade": {
        "ru": "Игровая комната с игровыми автоматами, аппаратом донорства крови, гадалкой, кран-машиной и нищими.",
        "en": "Gambling hall housing Slot Machines, Blood Donation pumps, Fortune Tellers, Crane Games, and Beggars.",
        "stats_ru": "ТИП: АВТОМАТЫ И НИЩИЕ  ·  ОБМЕН МОНЕТ И КРОВИ",
        "stats_en": "TYPE: MACHINES & BEGGARS  ·  COIN & BLOOD TRADES",
    },
    "sacrifice": {
        "ru": "Алтарь с шипами в самом центре. Каждая добровольная жертва кровью приближает благословение ангелов, души и призыв Уриила.",
        "en": "Ritual room centered on blood spikes. Repeated sacrifices bestow Soul Hearts, relics, and summon Archangels.",
        "stats_ru": "ТИП: ЖЕРТВА КРОВЬЮ  ·  ДАРЫ АНГЕЛОВ И ПЬЕДЕСТАЛ",
        "stats_en": "TYPE: BLOOD ALTAR  ·  ANGEL RELICS & BOONS",
    },
    "library": {
        "ru": "Тихая библиотека древних свитков и фолиантов. Хранит сразу два пьедестала с активными книгами и артефактами.",
        "en": "Quiet archive lined with towering bookshelves. Holds two active tome pedestals waiting to be claimed.",
        "stats_ru": "ТИП: АРХИВ  ·  2 ПЬЕДЕСТАЛА С АКТИВНЫМИ КНИГАМИ",
        "stats_en": "TYPE: ARCHIVE  ·  2 ACTIVE TOME PEDESTALS",
    },
    "dice": {
        "ru": "Зал гигантской шестигранной кости. Наступив на руну в полу, путник перебрасывает артефакты комнаты или целый ярус.",
        "en": "Sanctum of Fate etched with a giant six-sided die. Stepping onto the rune rerolls relics or the entire floor.",
        "stats_ru": "ТИП: ПЛИТА КОСТИ (1-6)  ·  ПЕРЕБРОС ПЬЕДЕСТАЛОВ / ЯРУСА",
        "stats_en": "TYPE: DICE RUNE (1-6)  ·  REROLL PEDESTALS / FLOOR",
    },
    "miniboss": {
        "ru": "Арена Смертного Греха — логово одного из 7 Грехов: Похоть, Гнев, Чревоугодие, Жадность, Лень, Зависть или Гордыня.",
        "en": "Arena of Sin housing one of the Seven Deadly Sins: Lust, Wrath, Gluttony, Greed, Sloth, Envy, or Pride.",
        "stats_ru": "ТИП: ЛОГОВО 7 ГРЕХОВ  ·  ОСОБЫЙ МИНИ-БОСС И ЛУТ",
        "stats_en": "TYPE: DEADLY SIN LAIR  ·  MINIBOSS & TROPHY DROP",
    },
    "boss": {
        "ru": "Покои Стража Яруса за черепной аркой. После многофазной битвы появляется пьедестал награды, люк глубже и шанс Сделки Тьмы.",
        "en": "Chamber behind the skull archway. Victory grants a boss relic, trapdoor deeper down, and a chance for a Dark Pact door.",
        "stats_ru": "ТИП: СТРАЖ ЯРУСА  ·  ПЬЕДЕСТАЛ + ЛЮК + СДЕЛКА ТЬМЫ",
        "stats_en": "TYPE: FLOOR WARDEN  ·  RELIC + TRAPDOOR + DARK PACT",
    },
    "secret": {
        "ru": "Скрытый склеп в толще стен между соседними залами. Вскрывается с обеих сторон взрывом бомбы у середины стены.",
        "en": "Hidden crypt nestled between adjoining rooms. Open both sides by bombing the center of the connecting wall.",
        "stats_ru": "ТИП: ТАЙНИК  ·  ВЗРЫВ БОМБЫ В СТЕНУ  ·  КЛАД МОНЕТ",
        "stats_en": "TYPE: HIDDEN CRYPT  ·  BOMB WALL CENTER  ·  COIN HOARD",
    },
    "devil": {
        "ru": "Чертог Сделки Тьмы с рогатым порталом, открывающийся после босса. Редкие проклятые реликвии покупаются ценой контейнеров сердец.",
        "en": "Horned sanctuary appearing after boss fights. Offers potent dark relics bought directly with Heart Containers.",
        "stats_ru": "ТИП: СДЕЛКА ЗА СЕРДЦА  ·  ВЫХОД ОБРАТНО В ЗАЛ БОССА",
        "stats_en": "TYPE: HEART CONTAINER PACT  ·  RETURNS TO BOSS ROOM",
    },
}

BOSS_CUSTOM_LORE = {
    "monstro": {
        "ru": "Гигантская уродливая голова с заячьей губой и беззубой пастью. Прыгает по дугам, плюёт веером слёз и падает сверху с ударным кольцом.",
        "en": "Giant cleft-lipped monstrosity. Hops toward prey, spits chaotic tear bursts, and leaps high to slam down in shockwaves.",
    },
    "duke": {
        "ru": "Раздутый труп с налитыми глазами, выплёвывающий живых мух. Окружён щитом роя и бьёт 6-лучевыми волнами при смене фаз.",
        "en": "Bloated floating husk brimming with flies. Continuously spawns swarms while firing 6-way tear rings.",
    },
    "larry": {
        "ru": "Многосегментный белый земляной червь с крупной жвалой-головой и четырьмя суставчатыми кольцами. Скользит по ломаным траекториям.",
        "en": "Articulated pale crypt worm with oversized jaws and trailing body segments. Weaves rapidly across the arena.",
    },
    "gemini": {
        "ru": "Сросшийся великан с перетянутым шнуром близнецом Стивеном. Старший яростно преследует игрока, пока малый прикрывает огнём.",
        "en": "Conjoined giant tethered to his smaller twin. The hulking brother charges relentlessly while his twin peppers shots.",
    },
    "famine": {
        "ru": "Первый Всадник Апокалипсиса на тощем костяном коне. Несётся горизонтальным тараном с косой и выпускает тройные залпы.",
        "en": "First Horseman of Apocalypse riding an emaciated steed. Charges cleanly across the hall between triple-tear volleys.",
    },
    "steven": {
        "ru": "Угрюмый теневой двойник из тьмы с мертвенным белым взглядом. Осыпает арену быстрыми выстрелами и преследует вблизи.",
        "en": "Grim shadow doppelganger glowing with stark white eyes. Pursues aggressively while weaving crossfire bursts.",
    },
    "dingle": {
        "ru": "Резвый свистящий комок грязи с перекошенным смехом. Готовит рывок с красным телеграфом и стреляет веером слёз.",
        "en": "Whistling mire beast wearing a crooked grin. Telegraphs high-speed triple dashes and spits spread shots.",
    },
    "dangle": {
        "ru": "Тёмный ядовитый собрат Дингла с вытянутым языком. Оставляет токсичные кольца снарядов и разгоняется для тарана.",
        "en": "Venomous dark kin of Dingle with lolling tongue. Unleashes toxic tear rings before bursting into heavy dashes.",
    },
    "little_horn": {
        "ru": "Озорной рогатый бес с огромной улыбкой. Скрывается в разломах пола, телепортируясь на 3-й фазе к углам зала.",
        "en": "Mischievous horned fiend wearing a crescent grin. Blinks across corners in Phase 3 while tossing dark rings.",
    },
    "haunt": {
        "ru": "Плачущий белый фантом со снятой кожей нижней челюсти. Скользит вдоль стен и испускает плотные потоки слёз.",
        "en": "Weeping pale apparition with a flayed jaw trailing ghostly tendrils. Glides unpredictably and fires dense bursts.",
    },
    "gurglings": {
        "ru": "Парные зубастые личинки с выпученными глазами. Бой идёт против двоих сразу — они поочерёдно таранят арену с разных углов.",
        "en": "Frenzied twin grubs fighting side by side. Both brothers alternate high-speed charges from opposite sides.",
    },
    "turdlings": {
        "ru": "Темнокожие агрессивные близнецы с ройным шлейфом. Синхронно перекатываются через арену и разбрасывают брызги.",
        "en": "Blighted twin rollers clad in dark mire. Roll simultaneously across the chamber leaving radial bursts.",
    },
    "widow": {
        "ru": "Длинноногая паучиха с восьмью костяными лапами и бледным крестом на брюхе. Выпрыгивает высоко и давит арену весом.",
        "en": "Eight-legged pale spider queen marked with a skull cross. Leaps high through the air to crush prey on impact.",
    },
    "pin": {
        "ru": "Юркий слепой червь с загнутыми клыками и веретенообразным хвостом. Молниеносно меняет курс и осыпает комнату кольцами.",
        "en": "Slender needle worm with hooked pincers and segmented tail. Reverses direction briskly while firing rings.",
    },
    "blight_ovum": {
        "ru": "Испорченное проклятое семя с мертвенным ореолом и трещиной черепа. Порождает круговые залпы и яростно гонится вблизи.",
        "en": "Blighted twin embryo wreathed in dark aura. Relentlessly closes distance while radiating dense tear waves.",
    },
    "rag_man": {
        "ru": "Окутанный погребальными бинтами жрец с пылающим глазом. Выпускает самонаводящиеся слёзы и телепортируется в критической фазе.",
        "en": "Shroud-wrapped necromancer with a glowing cyclops eye. Fires homing bandages and teleports in Phase 3.",
    },
    "chub": {
        "ru": "Толстая бронированная гусеница с тремя массивными сегментами. Несёт вперёд железные челюсти и ломает строй путника.",
        "en": "Massive segmented grub with iron mandibles and heavy flanks. Slithers on rapid turns through every lane.",
    },
    "gurdy": {
        "ru": "Колоссальный неподвижный живой алтарь плоти с выпученными очами и широкой ухмылкой. Выбрасывает сдвоенные 8-лучевые веера.",
        "en": "Colossal flesh-altar with wide eyes and jagged grin. Anchors the chamber beneath double 8-way tear storms.",
    },
    "gurdy_jr": {
        "ru": "Стремительный отпрыск Гёрди в костяном панцире. Отскакивает по комнате словно снаряд, предупреждая о таране ореолом.",
        "en": "Furious armored offspring of Gurdy. Ricochets like a battering ram after telegraphing its charge ring.",
    },
    "mega_maw": {
        "ru": "Зубастый каменный истукан с костяной короной. Извергает веера чёрно-белых слёз из бездонной пасти-портала.",
        "en": "Crowned stone head gaping with razor fangs. Breathes alternating rings and aimed fans of dark tears.",
    },
    "mega_fatty": {
        "ru": "Массивный громила с дряблым животом и маленькой головой. Прыгает в воздух, вызывая тяжёлые ударные кольца по приземлении.",
        "en": "Hulking bruiser whose leaps shake the floor. Slams down from mid-air with 10-shot radial bursts.",
    },
    "the_gate": {
        "ru": "Костяной страж врат с оскаленным черепом-пастью и пустым взглядом. Комбинирует плотные кольца выстрелов с манёврами.",
        "en": "Skeletal portal fiend crowned by spiked horns. Weaves spiraling shots from behind bone jaws.",
    },
    "pestilence": {
        "ru": "Чумной Всадник на гниющем скакуне с ядовитой короной. Бросает личинок и разбрасывает токсичные веерные залпы.",
        "en": "Second Horseman riding a decaying steed. Spreads toxic volleys while charging across toxic mist.",
    },
    "peep": {
        "ru": "Бледный слепой великан с двумя опухшими глазами-орбитами, вылетевшими из глазниц. Прыгает по центру с дождём слёз.",
        "en": "Bloated eyeless giant shadowed by detached orbiting eyeballs. Leaps dramatically between dense spreads.",
    },
    "carrion_queen": {
        "ru": "Бесплотная падальная королева со свитой костяных позвонков и коронной пастью. Разворачивается молниеносно по арене.",
        "en": "Furious worm queen with armored vertebrae and jagged mandible crown. Carves sinuous paths across the vault.",
    },
    "wretched": {
        "ru": "Изуродованная бледная паучиха с висящими нитями коконов. Покрывает пол прыжками и шквалом арахнидных выстрелов.",
        "en": "Malformed cave spider trailing pale silk strands. Combines terrifying high leaps with sudden close slams.",
    },
    "husk": {
        "ru": "Почерневшая мумия Герцога Мух с расколотым черепом и рёбрами наружу. Непрерывно плодит мух и накрывает сферами слёз.",
        "en": "Split-skull undead vessel of the Duke. Continuously births swarming flies behind rotating tear rings.",
    },
    "polycephalus": {
        "ru": "Трёхглавый кошмар подземелий: центральная плачущая голова и два кричащих боковых лика. Выпускает густые спирали слёз.",
        "en": "Three-headed subterranean horror featuring twin screaming side visages. Floods rooms with curling spirals.",
    },
    "big_horn": {
        "ru": "Огромный демон с двумя исполинскими рогами и притягивающей пустотой. В 3-й фазе затягивает игрока гравитацией внутрь залпа.",
        "en": "Titan crowned by massive curved horns. Pulls victims toward its maw with Phase 3 gravity wells.",
    },
    "rag_mega": {
        "ru": "Верховный жрец бинтов со светящимися глазами-шарами вокруг чела. Плетёт самонаводящиеся сгустки и телепортируется по залу.",
        "en": "High Priest of Shrouds ringed by glowing orbs. Teleports cleanly in Phase 3 while weaving homing spheres.",
    },
    "sisters_vis": {
        "ru": "Близняшки сёстры-циклопы с огромными раскрытыми грудными полостями. В бою выступают дуэтом, беря путника в перекрёстный огонь.",
        "en": "Twin hollow-chested cyclops sisters attacking as a duo. Surround wanderers in overlapping crossfire.",
    },
    "dark_one": {
        "ru": "Крылатый демон Шеола в чёрной чешуе и костяных крыльях. Молниеносно меняет позицию, атакуя крестом и очередью.",
        "en": "Leather-winged fiend of Sheol with sweeping dark pinions. Darts swiftly between wide dark volleys.",
    },
    "adversary": {
        "ru": "Слепой забинтованный архидемон с мощными рогами и тёмными крыльями. Прорезает зал 4-лучевой Серой и шквалом пуль.",
        "en": "Blindfolded archfiend of wrath armed with brimstone cross-blasts and ferocious aerial sweeps.",
    },
    "frail": {
        "ru": "Хрупкий просвечивающий скелет-червь с открытыми рёбрами позвоночника и клыкастым черепом. Стремительно петляет по залу.",
        "en": "Translucent skeletal spine-worm revealing hollowed vertebrae and fang jaws. Strikes in fluid serpentine arcs.",
    },
    "brownie": {
        "ru": "Коронованный толстый бес с кривой короной. Прыгает по комнате, оставляя плотные брызги слёз во все стороны.",
        "en": "Crowned mire imp with crooked regal mask. Bounces across stones trailing dense shockwave splashes.",
    },
    "stain": {
        "ru": "Клякса живых теневых щупалец без лица, вырывающаяся из глубин чернил. Осыпает комнату широкими веерами.",
        "en": "Writhing ink blot crowned in shadow tentacles. Unfolds wide spinning bursts of dark shots.",
    },
    "forsaken": {
        "ru": "Одинокий костяной лич с рогатым черепом и призрачным шлейфом. Скользит сквозь атаки и телепортируется в 3-й фазе.",
        "en": "Skeletal bone lich with horned skull and phantom shroud. Blinks through Phase 3 behind rotating rings.",
    },
    "fistula": {
        "ru": "Угловатый сросток каменной плоти из острых граней и шипов. При поражении распадается на два меньших осколка-босса.",
        "en": "Jagged crystalline cluster of scarred stone flesh. Splits into two smaller raging chunks upon defeat.",
    },
    "blastocyst": {
        "ru": "Огромная полупрозрачная клеточная сфера с живым зародышем внутри. Как и Фистула, делится на пару дочерних пузырей.",
        "en": "Floating translucent cellular sac housing an embryonic core. Splits into twin fast-moving daughter sacs.",
    },
    "war": {
        "ru": "Третий Всадник Апокалипсиса в железной броне с пылающим черепом. Таранит на высокой скорости с градом огненных залпов.",
        "en": "Iron-armored Third Horseman wreathed in cinder flames. Charges furiously amid heavy radial barrages.",
    },
    "death": {
        "ru": "Четвёртый Всадник в бледном капюшоне с костяной косой и черепом коня. Сочетает неумолимые рывки со жнецом слёз.",
        "en": "Fourth Horseman draped in deathly shroud wielding a curved scythe. Alternates lethal charges with sweeping arcs.",
    },
    "mom": {
        "ru": "Карающая нога Матери, обрушивающаяся сверху на тень цели! Уклоняйтесь от круга-метки перед тяжёлым приземлением.",
        "en": "Stomping giant limb crashing straight down from above! Dodge her shadow telegraph before the shockwave slam.",
    },
    "moms_heart": {
        "ru": "Пульсирующее анатомическое сердце на живых сосудах в центре арены. Генерирует закрученные спиральные штормы выстрелов.",
        "en": "Beating anatomical heart suspended on thick arteries. Unleashes relentless multi-spiral bullet hell.",
    },
    "it_lives": {
        "ru": "Пробуждённое эмбриональное сердце с разверстыми венами и ярким оком жизни. Заливает весь зал пересекающимися кольцами.",
        "en": "Awakened abyssal heart glaring with radiant veins. Overwhelms arenas with accelerated 14-way rings.",
    },
    "satan": {
        "ru": "Повелитель Шеола с парой широких крыльев, изогнутыми рогами и трезубцем. Бьёт 4-направленной Серой и прицельными залпами.",
        "en": "Lord of Sheol bearing sweeping horns, wings, and trident aura. Casts brimstone crosses alongside dense spreads.",
    },
    "isaac_boss": {
        "ru": "Плачущий светлый страж Собора с сияющим нимбом и ангельскими крыльями. Чередует дуги святых слёз с волнами света.",
        "en": "Radiant weeping guardian of the Cathedral crowned with a pale halo. Fires angelic bursts and bright wave rings.",
    },
    "blue_baby": {
        "ru": "Синюшный задыхающийся дух Сундука с крестами вместо глаз и расправленными крыльями. Телепортируется в 3-й фазе со шквалом.",
        "en": "Winged suffocated spirit with cross eyes guarding the Chest. Blinks across corners in Phase 3.",
    },
    "the_lamb": {
        "ru": "Костяной Агнец Тёмной Комнаты с изогнутыми бараньими рогами и перевёрнутым крестом. Стремительно таранит и телепортируется.",
        "en": "Bone-masked Lamb bearing coiled horns and inverted cross. Teleports suddenly before blasting wide demon rings.",
    },
    "mega_satan": {
        "ru": "Колоссальный рогатый архидемон с парой гигантских когтистых дланей и ослепительной пастью. Покрывает арену штормом 14 выстрелов.",
        "en": "Colossal horned titan flanked by massive clawed fists and blazing eyes. Floods floors with 14-way bullet storms.",
    },
    "hush": {
        "ru": "Сплющенная синевато-серая маска вечного удушья. Стягивает врагов гравитацией в 3-й фазе среди непроницаемого пулевого ада.",
        "en": "Pale suffocated titan sunken into the floor. Exerts Phase 3 gravity pull amidst sweeping concentric rings.",
    },
    "delirium": {
        "ru": "Плывущий белый кошмар с десятком искажённых глаз и рваной многоугольной аурой. Хаотично телепортируется по комнате без перерыва.",
        "en": "Shapeless multi-eyed nightmare warping reality's borders. Rapidly teleports while unleashing relentless barrages.",
    },
    "uriel": {
        "ru": "Серафим суда с шестью светящимися перьями-крыльями и белым нимбом. Стреляет чередующимися прямыми и диагональными крестами света.",
        "en": "Six-winged Seraph of Judgment framed in a glowing halo. Fires alternating cardinal and diagonal radiant crosses.",
    },
    "gabriel": {
        "ru": "Архангел с золотым (белым) венцом крыльев и мечом света. Выпускает мощнейшие 8-лучевые святые кольца и прицельные очереди.",
        "en": "Crowned Archangel of Light wielding radiant blades. Unleashes synchronized 8-way holy bursts across the room.",
    },
    "fallen": {
        "ru": "Опалённый падший ангел с обломанными крыльями и огненными рогами. При ранении продолжает бой с усиленным крестом Серы.",
        "en": "Burned fallen seraph with scorched wings and jagged horns. Cuts through the vault with brimstone cross blasts.",
    },
    "headless_horseman": {
        "ru": "Всадник без головы на чёрном коне, сжимающий в руке свой оскаленный череп-фонарь. Мчит напролом сквозь преграды.",
        "en": "Headless rider astride a skeletal warhorse cradling his grinning skull. Charges wildly between aimed volleys.",
    },
    "krampus": {
        "ru": "Длиннорогий демон пепельной зимы с длинным языком. Чередует тараны с 4-направленным вращающимся крестом Серы.",
        "en": "Long-horned winter demon with a snapping tongue. Combines aggressive circling with 4-way brimstone crosses.",
    },
    "lust": {
        "ru": "Одержимый грех Похоти с треснувшей ухмылкой. Постоянно несётся на сближение и рушит позицию быстрым тараном.",
        "en": "Frenzied Sin of Lust wearing a frantic grin. Chases relentlessly with swift high-speed dashes.",
    },
    "wrath": {
        "ru": "Бомбоголовый Грех Гнева с горящим фитилём на макушке. Забрасывает комнату взрывными траекториями и плотными веерами.",
        "en": "Bomb-headed Sin of Wrath crowned with a burning fuse. Peppers targets with volatile spread volleys.",
    },
    "gluttony": {
        "ru": "Одутловатый Грех Чревоугодия с вертикально разорванной пастью-животом. Стоит в центре и стреляет во все стороны.",
        "en": "Bloated Sin of Gluttony split vertically by a torso maw. Anchors the fight with wide omnidirectional sprays.",
    },
    "greed": {
        "ru": "Скрюченный алчный грех с прорезями-копилками вместо глаз. Стреляет тройными очередями монетных слёз.",
        "en": "Coin-slit Sin of Greed clutching dark bullion. Fires precise triple spreads while circling at mid-range.",
    },
    "sloth": {
        "ru": "Гниющее измождённое тело с капающей слизью и роем мух. Призывает миньонов, прячась за плотной завесой выстрелов.",
        "en": "Rotting herald of Sloth wreathed in dark flies. Summons minions behind periodic defensive rings.",
    },
    "envy": {
        "ru": "Раздробленный череп Зависти с тремя гневными трещинами. Как Фистула и Бластоциста, при гибели раскалывается на двойников!",
        "en": "Cracked skull of Envy seething with spite. Splits into smaller screeching skulls upon destruction!",
    },
    "pride": {
        "ru": "Высокомерный грех в острой короне Гордыни с нахмуренным челом. Порождает перекрёстные штормы слёз по всей комнате.",
        "en": "Spiked-crown Sin of Pride towering in arrogance. Unleashes sweeping bullet-hell rings from afar.",
    },
    "eclipse_warden": {
        "ru": "Тёмное затмение с ослепительной лунной короной и 6 орбитальными дисками. На 3-й фазе включает гравитацию Бездны.",
        "en": "Living Black Sun crowned in 12 eclipse rays and 6 orbiting blades. Ignites Abyssal gravity in Phase 3.",
    },
    "void_architect": {
        "ru": "Кристаллическая призма с 4 парящими монолитами-колоннами и всевидящим оком. Призывает элитных теней, гравитацию и телепорт.",
        "en": "Faceted Void Prism orbited by 4 floating monolith pillars. Summons elite shadows while warping space in Phase 3.",
    },
    "pale_seraph": {
        "ru": "Высший шестикрылый Серафим глубинных ярусов с алмазом-сиянием на челе. Заполняет зал ослепительными 8-лучевыми святыми крестами.",
        "en": "Supreme six-winged Pale Seraph bearing a diamond brow-light. Floods deep abysses with 8-way radiant crosses.",
    },
}

HERO_EXTRA_EN = {
    "isaac": ("Ashen Drifter", "Balanced delver: every 4th shot fires a piercing Ash Bolt (+45% DMG). Starts with Reforge Cube."),
    "magdalene": ("Bloodwarden", "4 Red Hearts, 1 protective orbital, Chalice of Life healing, and Crimson Aegis poise."),
    "cain": ("Shadow Rogue", "High speed, innate wall-ricochet shots, 22% crit chance (1.75x DMG), and +2 Luck."),
    "judas": ("Eclipse Executioner", "Glass-cannon duelist with high base DMG, Tome of Fury, and 18% critical execution chance."),
    "azazel": ("Brimstone Herald", "Innate flight over pits, 3 Black Hearts, piercing sulfur waves, and close-range chain arcs."),
    "lost": ("Hollow Specter", "Flight, spectral-piercing twin salvo, and Shield Mantle per room—1 unshielded hit is lethal."),
    "eve": ("Raven Witch", "Blood Blade + homing shadow feathers; at 1 red heart unleashes Eclipse Form surge."),
    "samson": ("Iron Berserker", "Scarred Fury (+0.75 DMG per hit taken on the floor) and a crushing dash-strike."),
    "lazarus": ("Ashborn", "Second Wind resurrection with shockwave, piercing bolts, and massive post-revive power."),
    "eden": ("Chaos Seer", "Randomized stats, active/passive relics, and a random combat gift each run."),
    "lilith": ("Echo Summoner", "Fires homing bolts through an Echo Familiar; Echo Box doubles familiars for the room."),
    "apollyon": ("Void Devourer", "Absorbs unwanted relics into permanent stats and fires piercing gravity-vortex shots."),
    "bethany": ("Spark Weaver", "Grimoire of Sparks spawns orbital wisps that intercept bullets, plus spectral shots."),
    "forgotten": ("Bone Sentinel", "Heavy bone scythe cleave shredding foes and bullets alike; high base DMG and poise."),
    "keeper": ("Gilded Specter", "Triple salvo + Gilded Token. Damage scales with coins held; every 5 coins heals Soul HP."),
    "nocturne": ("Shadow Blinker", "Spectral bouncing tears & rapid dash unleashing 4 spectral needles + blast."),
    "chrono": ("Time Warden", "Slows enemy bullets & Pocket Watch freezes all foes in the room for 4 seconds."),
    "alchemist": ("Plague Brewer", "Splitting poison tears, explosion healing, 4 bombs & Philosopher Vial."),
    "warden": ("Iron Bastion", "4 Red Hearts, Holy Mantle, 2 orbitals & Iron Vow knockback shockwave."),
    "veil": ("Phantom Stalker", "Extended stealth [V], x2.5 ambush strikes, and piercing dash-strike."),
    "maelstrom": ("Storm Herald", "Launches gravity-vortex orbs and chain lightning arcs that pull foes together."),
    "seraph": ("Fallen Seraph", "Flight, homing radiant tears, bright lantern & Soul HP regen every 2 rooms."),
}


def _boss_floor_label(boss_key, lang):
    if boss_key in MINIBOSS_KEYS:
        return "МИНИ-БОСС (ГРЕХИ)" if lang == "ru" else "MINIBOSS (7 SINS)"
    for fl in (1, 2, 3, 4, 5):
        if boss_key in FLOOR_BOSS_POOLS.get(fl, ()):
            return (f"ЯРУС {fl}+" if fl == 5 else f"ЯРУС {fl}") if lang == "ru" else (f"FLOOR {fl}+" if fl == 5 else f"FLOOR {fl}")
    return "ОСОБЫЙ СТРАЖ" if lang == "ru" else "SPECIAL WARDEN"


def _boss_special_tags(boss_key, style, lang):
    tags = []
    if style in ("splitter",) or boss_key in ("fistula", "blastocyst", "envy"):
        tags.append("ДЕЛЕНИЕ НА ФРАГМЕНТЫ" if lang == "ru" else "SPLITS ON DEATH")
    if boss_key in _TELEPORT_BOSS_KEYS:
        tags.append("ТЕЛЕПОРТ В ФАЗЕ 3" if lang == "ru" else "PHASE 3 BLINK")
    if boss_key in _GRAVITY_PULL_KEYS:
        tags.append("ГРАВИТАЦИЯ В ФАЗЕ 3" if lang == "ru" else "PHASE 3 GRAVITY")
    if boss_key == "mom":
        tags.append("УДАР СВЕРХУ" if lang == "ru" else "OVERHEAD STOMP")
    if style == "summoner" or boss_key == "void_architect":
        tags.append("ПРИЗЫВ МИНИОНОВ" if lang == "ru" else "SUMMONS ALLIES")
    if boss_key in ("uriel", "gabriel", "pale_seraph"):
        tags.append("СВЯТЫЕ КРЕСТЫ" if lang == "ru" else "RADIANT CROSSES")
    if boss_key in ("krampus", "fallen", "satan", "adversary"):
        tags.append("ЗАЛПЫ СЕРЫ" if lang == "ru" else "BRIMSTONE CROSSES")
    if not tags:
        tags.append("3 ФАЗЫ ЯРОСТИ" if lang == "ru" else "3 RAGE PHASES")
    return "  ·  ".join(tags)


def draw_room_preview(screen, room_type, cx, cy, scale=1.0):
    w = int(136 * scale)
    h = int(92 * scale)
    scheme = ROOM_COLOR_SCHEMES.get(room_type, ROOM_COLOR_SCHEMES["normal"])
    room_rect = pygame.Rect(int(cx - w * 0.5), int(cy - h * 0.5), w, h)
    pygame.draw.rect(screen, (10, 10, 10), room_rect.inflate(10, 10), border_radius=9)
    pygame.draw.rect(screen, scheme["wall"], room_rect.inflate(4, 4), border_radius=8)
    pygame.draw.rect(screen, scheme["floor_a"], room_rect, border_radius=6)
    pygame.draw.rect(screen, scheme["floor_b"], room_rect.inflate(-18, -14), border_radius=4)
    pygame.draw.rect(screen, scheme["trim"], room_rect, 2, border_radius=6)

    dw = int(20 * scale)
    dh = int(5 * scale)
    door_col = scheme["accent"]
    pygame.draw.rect(screen, door_col, (room_rect.centerx - dw // 2, room_rect.top - dh // 2, dw, dh), border_radius=2)
    pygame.draw.rect(screen, door_col, (room_rect.centerx - dw // 2, room_rect.bottom - dh // 2, dw, dh), border_radius=2)
    pygame.draw.rect(screen, door_col, (room_rect.left - dh // 2, room_rect.centery - dw // 2, dh, dw), border_radius=2)
    pygame.draw.rect(screen, door_col, (room_rect.right - dh // 2, room_rect.centery - dw // 2, dh, dw), border_radius=2)

    if room_type == "treasure":
        draw_aa_poly(screen, (246, 246, 246), [(cx, cy - 16), (cx + 13, cy), (cx, cy + 16), (cx - 13, cy)])
        draw_aa_circle(screen, (18, 18, 18), cx, cy, 4)
    elif room_type == "shop":
        draw_aa_circle(screen, (240, 240, 240), cx, cy, 14)
        draw_aa_circle(screen, (20, 20, 20), cx, cy, 10)
        draw_aa_circle(screen, (240, 240, 240), cx, cy, 3)
    elif room_type in ("boss", "miniboss"):
        draw_aa_circle(screen, (246, 246, 246), cx, cy, 15)
        draw_aa_circle(screen, (16, 16, 16), cx - 5, cy - 3, 3)
        draw_aa_circle(screen, (16, 16, 16), cx + 5, cy - 3, 3)
        draw_aa_ellipse(screen, (16, 16, 16), cx, cy + 6, 7, 3)
    elif room_type == "devil":
        draw_aa_ring(screen, (242, 242, 242), cx, cy, 16, 2)
        draw_aa_poly(screen, (242, 242, 242), [(cx - 11, cy - 12), (cx - 18, cy - 22), (cx - 4, cy - 14)])
        draw_aa_poly(screen, (242, 242, 242), [(cx + 11, cy - 12), (cx + 18, cy - 22), (cx + 4, cy - 14)])
        draw_aa_poly(screen, (238, 238, 238), [(cx, cy + 12), (cx - 10, cy - 7), (cx + 10, cy - 7)])
    elif room_type == "curse":
        draw_aa_ring(screen, (220, 220, 220), cx, cy, 14, 2)
        pygame.draw.line(screen, (220, 220, 220), (cx - 10, cy - 10), (cx + 10, cy + 10), 3)
        pygame.draw.line(screen, (220, 220, 220), (cx + 10, cy - 10), (cx - 10, cy + 10), 3)
    elif room_type == "sacrifice":
        pygame.draw.line(screen, (240, 240, 240), (cx, cy - 14), (cx, cy + 14), 3)
        pygame.draw.line(screen, (240, 240, 240), (cx - 10, cy - 4), (cx + 10, cy - 4), 3)
    elif room_type == "library":
        pygame.draw.rect(screen, (236, 236, 236), (int(cx - 16), int(cy - 12), 14, 24), border_radius=2)
        pygame.draw.rect(screen, (214, 214, 214), (int(cx + 2), int(cy - 12), 14, 24), border_radius=2)
        pygame.draw.line(screen, (18, 18, 18), (int(cx - 9), int(cy - 7)), (int(cx - 9), int(cy + 7)), 2)
        pygame.draw.line(screen, (18, 18, 18), (int(cx + 9), int(cy - 7)), (int(cx + 9), int(cy + 7)), 2)
    elif room_type == "arcade":
        pygame.draw.rect(screen, (230, 230, 230), (int(cx - 12), int(cy - 14), 24, 28), border_radius=4)
        pygame.draw.rect(screen, (18, 18, 18), (int(cx - 8), int(cy - 10), 16, 10), border_radius=2)
        draw_aa_circle(screen, (246, 246, 246), cx - 4, cy - 5, 2)
        draw_aa_circle(screen, (246, 246, 246), cx + 4, cy - 5, 2)
    elif room_type == "secret":
        draw_aa_circle(screen, (235, 235, 235), cx, cy, 14)
        draw_aa_circle(screen, (20, 20, 20), cx, cy, 10)
        draw_aa_circle(screen, (245, 245, 245), cx, cy - 2, 3)
        draw_aa_circle(screen, (245, 245, 245), cx, cy + 5, 2)
    elif room_type == "dice":
        pygame.draw.rect(screen, (230, 230, 230), (int(cx - 14), int(cy - 14), 28, 28), border_radius=4)
        draw_aa_circle(screen, (20, 20, 20), cx - 6, cy - 6, 2.5)
        draw_aa_circle(screen, (20, 20, 20), cx + 6, cy + 6, 2.5)
        draw_aa_circle(screen, (20, 20, 20), cx, cy, 2.5)
    else:
        draw_aa_circle(screen, (186, 186, 186), cx, cy, 8)
        draw_aa_ring(screen, (112, 112, 112), cx, cy, 15, 1)


def _wrap_text(text, max_len=56):
    words = str(text or "").split()
    lines = []
    line = ""
    for w in words:
        test = f"{line} {w}".strip()
        if len(test) > max_len and line:
            lines.append(line)
            line = w
        else:
            line = test
    if line:
        lines.append(line)
    return lines


def _wrap_text_px(text, font, max_w):
    words = str(text or "").split()
    if not words:
        return []
    lines = []
    line = ""
    for w in words:
        test = f"{line} {w}".strip()
        try:
            tw = font.size(test)[0]
        except Exception:
            tw = len(test) * 9
        if tw > max_w and line:
            lines.append(line)
            line = w
        else:
            line = test
    if line:
        lines.append(line)
    return lines


class ChronicleScreen:
    def __init__(self):
        self.selected = 0
        self.hover_idx = -1
        self.hover_back = False
        self.hover_prev = False
        self.hover_next = False
        self.time_acc = 0.0
        self.transition_t = 1.0
        rng = random.Random(108)
        self.ash_motes = [
            {
                "x": rng.uniform(70.0, SCREEN_WIDTH - 70.0),
                "y": rng.uniform(55.0, SCREEN_HEIGHT - 55.0),
                "vx": rng.uniform(-0.25, 0.25),
                "vy": rng.uniform(-0.45, -0.12),
                "r": rng.choice([1, 2, 2, 3]),
                "lum": rng.randint(155, 240),
                "alpha": rng.randint(40, 118),
                "layer": rng.uniform(0.5, 1.3),
            }
            for _ in range(38)
        ]

    def _select_chapter(self, idx):
        new_idx = idx % len(CHRONICLE_CHAPTERS)
        if new_idx != self.selected:
            self.selected = new_idx
            self.transition_t = 0.0

    def _chapter_rects(self):
        ox = get_world_offset_x()
        return [pygame.Rect(ox + 102, 130 + i * 40, 344, 34) for i in range(len(CHRONICLE_CHAPTERS))]

    def _back_rect(self):
        ox = get_world_offset_x()
        return pygame.Rect(ox + 1042, 68, 132, 34)

    def _prev_rect(self):
        ox = get_world_offset_x()
        return pygame.Rect(ox + 486, 598, 128, 34)

    def _next_rect(self):
        ox = get_world_offset_x()
        return pygame.Rect(ox + 628, 598, 128, 34)

    def update(self, dt=1.0):
        vw = get_view_width()
        self.time_acc += dt
        if self.transition_t < 1.0:
            self.transition_t = min(1.0, self.transition_t + 0.055 * dt)
        for m_pt in self.ash_motes:
            m_pt["x"] += (m_pt["vx"] + math.sin(self.time_acc * 0.03 * m_pt["layer"] + m_pt["y"] * 0.02) * 0.14) * dt
            m_pt["y"] += m_pt["vy"] * m_pt["layer"] * dt
            if m_pt["y"] < 58.0:
                m_pt["y"] = SCREEN_HEIGHT - 58.0
                m_pt["x"] = 70.0 + ((m_pt["x"] * 1.37 + 190.0) % (vw - 140.0))

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                return "back"
            if event.key in (pygame.K_UP, pygame.K_w, pygame.K_LEFT, pygame.K_a):
                self._select_chapter(self.selected - 1)
            elif event.key in (pygame.K_DOWN, pygame.K_s, pygame.K_RIGHT, pygame.K_d):
                self._select_chapter(self.selected + 1)
        elif event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            self.hover_idx = -1
            for i, rc in enumerate(self._chapter_rects()):
                if rc.collidepoint(mx, my):
                    self.hover_idx = i
                    break
            self.hover_back = self._back_rect().collidepoint(mx, my)
            self.hover_prev = self._prev_rect().collidepoint(mx, my)
            self.hover_next = self._next_rect().collidepoint(mx, my)
        elif event.type == pygame.MOUSEWHEEL:
            self._select_chapter(self.selected - (1 if event.y > 0 else -1))
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4:
                self._select_chapter(self.selected - 1)
            elif event.button == 5:
                self._select_chapter(self.selected + 1)
            elif event.button == 1:
                mx, my = event.pos
                if self._back_rect().collidepoint(mx, my):
                    return "back"
                if self._prev_rect().collidepoint(mx, my):
                    self._select_chapter(self.selected - 1)
                elif self._next_rect().collidepoint(mx, my):
                    self._select_chapter(self.selected + 1)
                else:
                    for i, rc in enumerate(self._chapter_rects()):
                        if rc.collidepoint(mx, my):
                            self._select_chapter(i)
                            break
        return None

    def _draw_chapter_art(self, screen, ch_idx, box, reveal):
        pygame.draw.rect(screen, (10, 10, 10), box, border_radius=10)
        pygame.draw.rect(screen, (72, 72, 72), box, 1, border_radius=10)
        cx, cy = box.centerx, box.centery
        t = self.time_acc * 0.045
        flick = 0.5 + 0.5 * math.sin(t * 2.6 + ch_idx)

        gl = get_glow_surf(int(96 + 18 * flick), 232, int((58 + 24 * flick) * reveal))
        screen.blit(gl, (int(cx - gl.get_width() * 0.5), int(cy - gl.get_height() * 0.5)))

        clip_prev = screen.get_clip()
        screen.set_clip(box.inflate(-4, -4))

        if reveal > 0.02:
            for m_pt in self.ash_motes:
                if box.collidepoint(m_pt["x"], m_pt["y"]):
                    ps = get_particle_surf(m_pt["r"], m_pt["lum"], int(m_pt["alpha"] * reveal))
                    screen.blit(ps, (int(m_pt["x"] - ps.get_width() * 0.5), int(m_pt["y"] - ps.get_height() * 0.5)))

        if ch_idx == 0:
            for step in range(5):
                sw = 180 - step * 26
                sx = cx - sw // 2
                sy = box.top + 38 + step * 26
                shade = 190 - step * 28
                pygame.draw.rect(screen, (shade, shade, shade), (sx, sy, sw, 20), border_radius=3)
            for fx in (cx - 110, cx + 110):
                fg = get_glow_surf(int(38 + 8 * flick), 245, 92)
                screen.blit(fg, (int(fx - fg.get_width() * 0.5), int(cy - 18 - fg.get_height() * 0.5)))
                draw_aa_circle(screen, (246, 246, 246), fx, cy - 18, 5 + flick * 1.5)
                pygame.draw.line(screen, (120, 120, 120), (fx, cy - 12), (fx, cy + 36), 3)
        elif ch_idx == 1:
            hero_cnt = 7
            for i in range(hero_cnt):
                ang = t * 0.35 + i * (math.pi * 2.0 / hero_cnt)
                hx = cx + math.cos(ang) * 98
                hy = cy + 6 + math.sin(ang) * 42
                draw_hero_portrait(screen, HERO_ROSTER[(i * 2) % len(HERO_ROSTER)]["id"], hx, hy, scale=0.72)
        elif ch_idx == 2:
            for k in range(5):
                frac = k / 4.0
                px = cx - 120 + frac * 220 + math.sin(t * 2.0) * 16
                py = cy + math.sin(t * 2.4 + k * 0.7) * 12
                ps = get_particle_surf(int(10 + frac * 10), int(110 + frac * 135), int(65 + frac * 150))
                screen.blit(ps, (int(px - ps.get_width() * 0.5), int(py - ps.get_height() * 0.5)))
            draw_hero_portrait(screen, "isaac", cx + 100 + math.sin(t * 2.0) * 14, cy, scale=1.15)
        elif ch_idx == 3:
            draw_aa_ring(screen, (118, 118, 118), cx, cy, 78, 1)
            for i in range(5):
                ang = t * 0.5 + i * (math.pi * 2.0 / 5.0)
                ix = cx + math.cos(ang) * 78
                iy = cy + math.sin(ang) * 52
                draw_item_icon(screen, ITEM_POOL_65[(i * 11) % len(ITEM_POOL_65)], ix, iy, size=34)
            draw_aa_circle(screen, (240, 240, 240), cx, cy, 10 + flick * 3)
        elif ch_idx == 4:
            for px in (cx - 135, cx + 135):
                pygame.draw.rect(screen, (52, 52, 52), (px - 16, box.top + 18, 32, box.h - 36), border_radius=4)
            draw_enemy_visual(screen, "many_eyed_watcher", cx, cy, 34, age=self.time_acc * 0.08)
        elif ch_idx == 5:
            for row in range(3):
                pygame.draw.line(screen, (72, 72, 72), (cx - 180 + row * 180, box.top + 8), (cx - 180 + row * 180, cy + 28), 3)
            for ux in (cx - 110, cx, cx + 110):
                draw_aa_ellipse(screen, (152, 152, 152), ux, cy + 32, 18, 24)
                pygame.draw.rect(screen, (186, 186, 186), (ux - 10, cy + 4, 20, 6), border_radius=2)
        elif ch_idx == 6:
            draw_npc_visual(screen, "lore_monolith", cx, cy, scale=1.5, age=self.time_acc * 0.08, activated=True)
        elif ch_idx == 7:
            draw_aa_circle(screen, (226, 226, 226), cx, cy - 32, 26 + flick * 3)
            draw_aa_circle(screen, (10, 10, 10), cx + 10, cy - 34, 21)
            for idx, bkey in enumerate(("famine", "war", "death")):
                draw_boss_portrait(screen, bkey, cx + (idx - 1) * 115, cy + 34, scale=0.88, age=self.time_acc * 0.08)
        elif ch_idx == 8:
            for r_step in range(3):
                rr = 28 + ((t * 36 + r_step * 34) % 102)
                lum = int(clamp(230 - rr * 1.6, 36, 240))
                draw_aa_ring(screen, (lum, lum, lum), cx, cy, int(rr), 2)
            draw_hero_portrait(screen, "azazel", cx, cy, scale=1.1)
        elif ch_idx == 9:
            door = pygame.Rect(cx - 46, cy - 58, 92, 118)
            pygame.draw.rect(screen, (228, 228, 228), door, border_radius=8)
            pygame.draw.rect(screen, (14, 14, 14), door.inflate(-12, -12), border_radius=5)
            draw_aa_poly(screen, (238, 238, 238), [(cx - 32, cy - 56), (cx - 52, cy - 82), (cx - 18, cy - 62)])
            draw_aa_poly(screen, (238, 238, 238), [(cx + 32, cy - 56), (cx + 52, cy - 82), (cx + 18, cy - 62)])
            draw_aa_circle(screen, (246, 246, 246), cx, cy - 6, 8 + flick * 2)
        elif ch_idx == 10:
            draw_boss_portrait(screen, "eclipse_warden", cx, cy + 4, scale=1.55, age=self.time_acc * 0.08)
        else:
            pygame.draw.rect(screen, (210, 210, 210), (cx - 115, cy - 24, 52, 52), border_radius=8)
            pygame.draw.rect(screen, (10, 10, 10), (cx - 109, cy - 18, 40, 40), border_radius=6)
            for ry in range(cy - 12, cy + 18, 9):
                pygame.draw.line(screen, (150, 150, 150), (cx - 104, ry), (cx - 74, ry), 2)
            draw_aa_circle(screen, (242, 242, 242), cx + 88, cy + 2, 26 + flick * 3)
            draw_aa_circle(screen, (18, 18, 18), cx + 88, cy + 2, 16)
            draw_aa_circle(screen, (250, 250, 250), cx + 88, cy + 2, 9 + flick * 3)

        screen.set_clip(clip_prev)

    def draw(self, screen, ui):
        lang = get_lang()
        ox = get_world_offset_x()
        screen.fill((8, 8, 8))
        panel = get_panel_surf(1140, 624, 14, 240, 108, 12)
        screen.blit(panel, (ox + 70, 48))
        title = render_text_cached(ui.font_huge, tr("chronicle_title"), PALETTE["text_main"])
        screen.blit(title, (ox + 104, 68))
        alpha_s = render_text_cached(ui.font_tiny, tr("alpha_badge"), (152, 152, 152))
        screen.blit(alpha_s, (ox + 954 - alpha_s.get_width(), 80))

        back_r = self._back_rect()
        pygame.draw.rect(screen, (236, 236, 236) if self.hover_back else (28, 28, 28), back_r, border_radius=6)
        pygame.draw.rect(screen, (250, 250, 250) if self.hover_back else (96, 96, 96), back_r, 1, border_radius=6)
        blit_text_fitted(screen, back_r, ui.font_small, tr("tutorial_back"), (14, 14, 14) if self.hover_back else PALETTE["text_main"], pad_x=8)

        ch_rects = self._chapter_rects()
        for idx, ch in enumerate(CHRONICLE_CHAPTERS):
            rc = ch_rects[idx]
            sel = idx == self.selected
            hov = idx == self.hover_idx
            fill = (238, 238, 238) if sel else ((48, 48, 48) if hov else (24, 24, 24))
            border = (255, 255, 255) if sel else ((140, 140, 140) if hov else (56, 56, 56))
            pygame.draw.rect(screen, fill, rc, border_radius=6)
            pygame.draw.rect(screen, border, rc, 1, border_radius=6)
            ch_title = ch["title_en"] if lang == "en" else ch["title"]
            blit_text_fitted(screen, rc, ui.font_small, ch_title, (14, 14, 14) if sel else PALETTE["text_main"], align="left", pad_x=12)

        reveal = ease_out_cubic(self.transition_t)
        slide_y = int((1.0 - reveal) * 16.0)
        cur = CHRONICLE_CHAPTERS[self.selected]
        cur_title = cur["title_en"] if lang == "en" else cur["title"]
        cur_body = cur["body_en"] if lang == "en" else cur["body"]
        art_box = pygame.Rect(ox + 486, 130 + slide_y, 684, 214)
        self._draw_chapter_art(screen, self.selected, art_box, reveal)

        h_lbl = fit_text_surf(ui.font_big, cur_title, PALETTE["text_main"], 684)
        screen.blit(h_lbl, (ox + 486, 360 + slide_y))
        txt_lum = int(40 + 162 * reveal)
        body_clip = screen.get_clip()
        screen.set_clip(pygame.Rect(ox + 482, 398, 692, 192))
        lines = _wrap_text_px(cur_body, ui.font_small, 680)
        line_step = 24 if len(lines) <= 7 else 21
        for li, ln in enumerate(lines[:8]):
            ts = render_text_cached(ui.font_small, ln, (txt_lum, txt_lum, txt_lum))
            screen.blit(ts, (ox + 486, 404 + slide_y + li * line_step))
        screen.set_clip(body_clip)

        prev_r = self._prev_rect()
        next_r = self._next_rect()
        p_txt = "< CHAPTER" if lang == "en" else "< ГЛАВА"
        n_txt = "CHAPTER >" if lang == "en" else "ГЛАВА >"
        for rc, hov, txt_s in ((prev_r, self.hover_prev, p_txt), (next_r, self.hover_next, n_txt)):
            pygame.draw.rect(screen, (236, 236, 236) if hov else (26, 26, 26), rc, border_radius=6)
            pygame.draw.rect(screen, (250, 250, 250) if hov else (88, 88, 88), rc, 1, border_radius=6)
            blit_text_fitted(screen, rc, ui.font_small, txt_s, (14, 14, 14) if hov else PALETTE["text_main"], pad_x=8)

        hint_txt = "Wheel / W/S / Click — Chapter   |   ESC — Back" if lang == "en" else "Колёсико / W/S / Клик — Глава   |   ESC — Назад"
        hint = fit_text_surf(ui.font_small, hint_txt, PALETTE["text_dim"], 410)
        screen.blit(hint, (ox + 776, 606))


class CodexScreen:
    def __init__(self):
        self.tab = 0
        self.selected = 0
        self.scroll_idx = 0
        self.hover_tab = -1
        self.hover_row = -1
        self.hover_back = False
        self.hover_scroll = 0
        self._drag_y = None
        self.anim_age = 0.0

    def update(self, dt=1.0):
        self.anim_age += 0.09 * dt

    def _tabs(self):
        if get_lang() == "en":
            return [
                f"HEROES ({len(HERO_ROSTER)})",
                f"ENEMIES ({len(REGULAR_ENEMY_TYPES)})",
                f"NPCS ({len(NPC_KEYS)})",
                f"BOSSES ({len(PLAYABLE_BOSS_KEYS)})",
                f"ROOMS ({len(ROOM_ORDER)})",
                f"RELICS ({len(ITEM_POOL_65)})",
                f"CONSOLE ({len(CONSOLE_DOC_ENTRIES)})",
            ]
        return [
            f"ГЕРОИ ({len(HERO_ROSTER)})",
            f"ВРАГИ ({len(REGULAR_ENEMY_TYPES)})",
            f"НПС ({len(NPC_KEYS)})",
            f"БОССЫ ({len(PLAYABLE_BOSS_KEYS)})",
            f"ЗАЛЫ ({len(ROOM_ORDER)})",
            f"АРТЕФАКТЫ ({len(ITEM_POOL_65)})",
            f"КОНСОЛЬ ({len(CONSOLE_DOC_ENTRIES)})",
        ]

    def _current_list(self):
        if self.tab == 0:
            return HERO_ROSTER
        if self.tab == 1:
            return REGULAR_ENEMY_TYPES
        if self.tab == 2:
            return NPC_KEYS
        if self.tab == 3:
            return PLAYABLE_BOSS_KEYS
        if self.tab == 4:
            return ROOM_ORDER
        if self.tab == 5:
            return ITEM_POOL_65
        return CONSOLE_DOC_ENTRIES

    def _tab_rects(self):
        ox = get_world_offset_x()
        return [pygame.Rect(ox + 90 + i * 158, 102, 150, 30) for i in range(7)]

    def _back_rect(self):
        ox = get_world_offset_x()
        return pygame.Rect(ox + 1056, 56, 134, 34)

    def _row_rects(self, visible_count):
        ox = get_world_offset_x()
        return [pygame.Rect(ox + 90, 152 + vi * 38, 354, 32) for vi in range(visible_count)]

    def _scroll_btn_rects(self):
        ox = get_world_offset_x()
        return (
            pygame.Rect(ox + 448, 152, 26, 26),
            pygame.Rect(ox + 448, 576, 26, 26),
        )

    def _sync_scroll(self, total_len):
        if total_len <= 12:
            self.scroll_idx = 0
            return
        max_start = total_len - 12
        if self.selected < self.scroll_idx:
            self.scroll_idx = self.selected
        elif self.selected >= self.scroll_idx + 12:
            self.scroll_idx = self.selected - 11
        self.scroll_idx = int(clamp(self.scroll_idx, 0, max_start))

    def _scroll_list(self, delta):
        items = self._current_list()
        if not items:
            return
        max_start = max(0, len(items) - 12)
        self.scroll_idx = int(clamp(self.scroll_idx + delta, 0, max_start))
        if self.selected < self.scroll_idx:
            self.selected = self.scroll_idx
        elif self.selected >= self.scroll_idx + 12:
            self.selected = self.scroll_idx + 11

    def handle_event(self, event):
        items = self._current_list()
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                return "back"
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.tab = (self.tab - 1) % 7
                self.selected = 0
                self.scroll_idx = 0
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.tab = (self.tab + 1) % 7
                self.selected = 0
                self.scroll_idx = 0
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % max(1, len(items))
                self._sync_scroll(len(items))
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % max(1, len(items))
                self._sync_scroll(len(items))
        elif event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            self.hover_back = self._back_rect().collidepoint(mx, my)
            up_rc, dn_rc = self._scroll_btn_rects()
            self.hover_scroll = -1 if (len(items) > 12 and up_rc.collidepoint(mx, my)) else (1 if (len(items) > 12 and dn_rc.collidepoint(mx, my)) else 0)
            self.hover_tab = -1
            for i, rc in enumerate(self._tab_rects()):
                if rc.collidepoint(mx, my):
                    self.hover_tab = i
                    break
            vis_len = min(12, max(0, len(items) - self.scroll_idx))
            self.hover_row = -1
            for vi, rc in enumerate(self._row_rects(vis_len)):
                if rc.collidepoint(mx, my):
                    self.hover_row = self.scroll_idx + vi
                    break
            buttons = getattr(event, "buttons", (0, 0, 0))
            if self._drag_y is not None and buttons and buttons[0] and len(items) > 12:
                dy = my - self._drag_y
                if abs(dy) >= 24:
                    step = -1 if dy > 0 else 1
                    self._scroll_list(step * max(1, abs(dy) // 24))
                    self._drag_y = my
        elif event.type == pygame.MOUSEWHEEL:
            self._scroll_list(-2 if event.y > 0 else 2)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._drag_y = None
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 4:
                self._scroll_list(-2)
            elif event.button == 5:
                self._scroll_list(2)
            elif event.button == 1:
                mx, my = event.pos
                if self._back_rect().collidepoint(mx, my):
                    return "back"
                if len(items) > 12:
                    up_rc, dn_rc = self._scroll_btn_rects()
                    if up_rc.collidepoint(mx, my):
                        self._scroll_list(-4)
                        return None
                    if dn_rc.collidepoint(mx, my):
                        self._scroll_list(4)
                        return None
                for i, rc in enumerate(self._tab_rects()):
                    if rc.collidepoint(mx, my):
                        self.tab = i
                        self.selected = 0
                        self.scroll_idx = 0
                        self._drag_y = None
                        return None
                vis_len = min(12, max(0, len(items) - self.scroll_idx))
                for vi, rc in enumerate(self._row_rects(vis_len)):
                    if rc.collidepoint(mx, my):
                        self.selected = self.scroll_idx + vi
                        self._drag_y = my
                        return None
                if pygame.Rect(get_world_offset_x() + 90, 152, 354, 456).collidepoint(mx, my):
                    self._drag_y = my
        return None

    def _entry_label(self, entry, lang):
        if self.tab == 0:
            return entry.get("name_en", entry["name"]) if lang == "en" else entry["name"]
        if self.tab == 1:
            return entry.replace("_", " ").upper()
        if self.tab == 2:
            info = NPC_CUSTOM.get(entry, {})
            return info.get("name_en", entry.upper()) if lang == "en" else info.get("name", entry.upper())
        if self.tab == 3:
            return tr_boss(entry)
        if self.tab == 4:
            return tr_room(entry)
        if self.tab == 5:
            return tr_item_name(entry)
        return entry.get("name_en", entry["name"]) if lang == "en" else entry["name"]

    def _draw_showcase_visual(self, screen, cur, box):
        cx, cy = box.centerx, box.centery
        pygame.draw.rect(screen, (11, 11, 11), box, border_radius=10)
        pygame.draw.rect(screen, (72, 72, 72), box, 1, border_radius=10)
        gl = get_glow_surf(84, 224, 52)
        screen.blit(gl, (int(cx - gl.get_width() * 0.5), int(cy - gl.get_height() * 0.5)))

        prev_clip = screen.get_clip()
        screen.set_clip(box.inflate(-6, -6))

        if self.tab == 0:
            bob = math.sin(self.anim_age * 0.9) * 2.5
            draw_hero_portrait(screen, cur["id"], cx, cy + bob, scale=1.75)
        elif self.tab == 1:
            trail = None
            if cur in ("whispering_phantom", "thread_serpent", "ash_stalker"):
                trail = [(cx - i * 11, cy + math.sin(self.anim_age + i * 0.8) * 7) for i in range(1, 7)]
            draw_enemy_visual(
                screen,
                cur,
                cx,
                cy + 2,
                34,
                age=self.anim_age,
                flash=False,
                trail=trail,
                slam_ring=(10.0 if cur == "hollow_bell" and math.sin(self.anim_age * 1.1) > 0.6 else 0.0),
                air_z=(max(0.0, math.sin(self.anim_age * 1.4)) * 12.0 if cur == "hopper" else 0.0),
            )
        elif self.tab == 2:
            draw_npc_visual(screen, cur, cx, cy + 4, scale=1.5, age=self.anim_age, activated=(cur == "lore_monolith"))
        elif self.tab == 3:
            draw_boss_portrait(screen, cur, cx, cy + 4, scale=1.65, age=self.anim_age)
        elif self.tab == 4:
            draw_room_preview(screen, cur, cx, cy, scale=1.25)
        elif self.tab == 5:
            bob = math.sin(self.anim_age * 1.2) * 3.0
            draw_item_icon(screen, cur, cx, cy + bob, size=76)
        elif self.tab == 6:
            ik = cur.get("icon_kind", "terminal")
            pygame.draw.rect(screen, (22, 22, 22), (cx - 58, cy - 42, 116, 84), border_radius=8)
            pygame.draw.rect(screen, (196, 196, 196), (cx - 58, cy - 42, 116, 84), 2, border_radius=8)
            if ik == "terminal":
                pygame.draw.line(screen, (240, 240, 240), (cx - 42, cy - 22), (cx - 26, cy - 10), 3)
                pygame.draw.line(screen, (240, 240, 240), (cx - 42, cy + 2), (cx - 26, cy - 10), 3)
                pygame.draw.line(screen, (220, 220, 220), (cx - 18, cy + 2), (cx + 28, cy + 2), 3)
                if int(self.anim_age * 2.0) % 2 == 0:
                    pygame.draw.rect(screen, (245, 245, 245), (cx + 32, cy - 8, 8, 12))
            elif ik == "editor":
                for gx in (-28, 0, 28):
                    pygame.draw.line(screen, (76, 76, 76), (cx + gx, cy - 32), (cx + gx, cy + 32), 1)
                for gy in (-18, 0, 18):
                    pygame.draw.line(screen, (76, 76, 76), (cx - 44, cy + gy), (cx + 44, cy + gy), 1)
                pygame.draw.rect(screen, (238, 238, 238), (cx - 22, cy - 14, 22, 22), 2, border_radius=3)
                draw_aa_circle(screen, (245, 245, 245), cx + 18, cy + 12, 8)
            elif ik == "effect":
                draw_aa_ring(screen, (242, 242, 242), cx, cy, 28, 2)
                draw_aa_ring(screen, (150, 150, 150), cx, cy, 18, 2)
                for p_i in range(4):
                    ang = self.anim_age * 0.8 + p_i * math.pi * 0.5
                    draw_aa_circle(screen, (248, 248, 248), cx + math.cos(ang) * 28, cy + math.sin(ang) * 28, 4.5)
            elif ik == "relic":
                draw_aa_poly(screen, (242, 242, 242), [(cx, cy - 26), (cx + 22, cy), (cx, cy + 26), (cx - 22, cy)])
                draw_aa_circle(screen, (18, 18, 18), cx, cy, 8)
            else:
                draw_aa_ring(screen, (220, 220, 220), cx, cy, 28, 2)
                pygame.draw.line(screen, (220, 220, 220), (cx - 28, cy), (cx + 28, cy), 1)
                pygame.draw.line(screen, (220, 220, 220), (cx, cy - 28), (cx, cy + 28), 1)
                draw_aa_circle(screen, (246, 246, 246), cx, cy, 6)

        screen.set_clip(prev_clip)

    def _build_entry_details(self, cur, lang):
        if self.tab == 0:
            ex = HERO_EXTRA_EN.get(cur["id"], (cur["title"], cur["desc"]))
            title = f"{cur.get('name_en', cur['name'])} — {ex[0]}" if lang == "en" else f"{cur['name']} — {cur['title']}"
            subtitle = "ГЕРОЙ ПОДЗЕМЕЛЬЯ ТЬМЫ" if lang == "ru" else "DARKVAULT HERO"
            lore = ex[1] if lang == "en" else cur["desc"]

            active_id = cur.get("starting_active")
            active_it = ITEM_REGISTRY.get(active_id) if active_id else None
            passives = [tr_item_name(ITEM_REGISTRY[pid]) for pid in cur.get("starting_passive", []) if pid in ITEM_REGISTRY]
            act_str = tr_item_name(active_it) if active_it else ("Нет" if lang == "ru" else "None")
            pas_str = ", ".join(passives) if passives else ("Нет" if lang == "ru" else "None")
            traits = []
            if cur.get("has_flight"):
                traits.append("Полёт" if lang == "ru" else "Flight")
            if cur.get("has_piercing"):
                traits.append("Пронзание" if lang == "ru" else "Piercing")
            if cur["id"] == "eden":
                traits.append("Случайный старт" if lang == "ru" else "Randomized")
            if cur["id"] == "lost":
                traits.append("Смерть от 1 удара" if lang == "ru" else "1-Hit Fragile")
            trait_str = " · ".join(traits) if traits else ("Стандартные слёзы" if lang == "ru" else "Standard Tears")

            ability = (
                f"АКТИВНАЯ РЕЛИКВИЯ: {act_str}  |  ПАССИВНАЯ: {pas_str}  |  ОСОБЕННОСТЬ: {trait_str}"
                if lang == "ru"
                else f"ACTIVE RELIC: {act_str}  |  PASSIVE: {pas_str}  |  TRAITS: {trait_str}"
            )
            stats_rows = [
                ("ОЗ / ЩИТЫ" if lang == "ru" else "HP / HEARTS", f"{cur['hp']} / {cur['soul_hp']}S / {cur['black_hp']}B"),
                ("УРОН / ТЕМП" if lang == "ru" else "DMG / DELAY", f"{cur['damage']}  ·  {cur['fire_delay']}"),
                ("СКОР. / ДАЛЬН." if lang == "ru" else "SPD / RANGE", f"{cur['speed']}  ·  {cur['tear_range']}"),
                ("ПРИПАСЫ" if lang == "ru" else "RESOURCES", f"{cur['coins']}C · {cur['bombs']}B · {cur['keys']}K · LCK {cur['luck']}"),
            ]
            footer = f"ТЕГ: {cur['id'].upper()}  ·  TEAR SPD {cur['tear_speed']}"
            return title, subtitle, lore, ability, stats_rows, footer

        if self.tab == 1:
            st = ENEMY_BASE_STATS.get(cur, {"hp": 20, "speed": 2.0, "radius": 16})
            info = ENEMY_LORE_CUSTOM.get(cur, {})
            title = cur.replace("_", " ").upper()
            flying = cur in ("fly", "pooter", "boil", "whispering_phantom", "many_eyed_watcher", "hollow_bell")
            subtitle = (
                ("ЛЕТАЮЩАЯ СУЩНОСТЬ" if flying else "НАЗЕМНАЯ СУЩНОСТЬ")
                if lang == "ru"
                else ("FLYING ENTITY" if flying else "GROUND ENTITY")
            )
            lore = info.get(lang, info.get("ru", ""))
            ability = info.get(f"ability_{lang}", info.get("ability_ru", ""))
            stats_rows = [
                ("БАЗОВОЕ ОЗ" if lang == "ru" else "BASE HP", f"{st['hp']}"),
                ("СКОРОСТЬ" if lang == "ru" else "SPEED", f"{st['speed']}"),
                ("РАДИУС ХИТБОКСА" if lang == "ru" else "HITBOX RAD", f"{st['radius']} px"),
                ("ПЕРЕМЕЩЕНИЕ" if lang == "ru" else "MOVEMENT", ("Полёт" if flying else "Наземный") if lang == "ru" else ("Airborne" if flying else "Grounded")),
            ]
            footer = f"ID: {cur.upper()}  ·  МАСШТАБИРУЕТСЯ ПО ЯРУСАМ" if lang == "ru" else f"ID: {cur.upper()}  ·  SCALES WITH FLOOR DEPTH"
            return title, subtitle, lore, ability, stats_rows, footer

        if self.tab == 2:
            info = NPC_CUSTOM.get(cur, {})
            title = info.get("name_en", cur) if lang == "en" else info.get("name", cur)
            subtitle = "ОБИТАТЕЛЬ ИЛИ МЕХАНИЗМ" if lang == "ru" else "CRYPT NPC OR MACHINE"
            lore = info.get("desc_en", info.get("desc", "")) if lang == "en" else info.get("desc", "")
            stats_line = info.get("stats_en", "") if lang == "en" else info.get("stats_ru", "")
            ability = stats_line
            bomb_note = "Монеты / Припасы" if lang == "ru" else "Coins / Pickups"
            if cur == "shopkeeper":
                bomb_note = "Монеты или Пауки" if lang == "ru" else "Coins or Spiders"
            elif cur == "lore_monolith":
                bomb_note = "Неразрушим" if lang == "ru" else "Indestructible"
            stats_rows = [
                ("КЛЮЧ" if lang == "ru" else "KEY", cur.upper()),
                ("РЕАКЦИЯ НА БОМБУ" if lang == "ru" else "ON BOMB", bomb_note),
                ("ТИП ВСТРЕЧИ" if lang == "ru" else "ENCOUNTER", "Магазин / Зал / Склеп" if lang == "ru" else "Shop / Arcade / Vault"),
                ("ВЗАИМОДЕЙСТВИЕ" if lang == "ru" else "INTERACTION", "Касание" if lang == "ru" else "Touch Trigger"),
            ]
            return title, subtitle, lore, ability, stats_rows, stats_line

        if self.tab == 3:
            cfg = BOSS_BASE_CONFIG.get(cur, {"hp": 220, "radius": 34, "speed": 2.2, "style": "jumper"})
            info = BOSS_CUSTOM_LORE.get(cur, {})
            title = tr_boss(cur)
            subtitle = tr_boss_subtitle(cur)
            lore = info.get(lang, info.get("ru", ""))
            tier_txt = _boss_floor_label(cur, lang)
            tags_txt = _boss_special_tags(cur, cfg["style"], lang)
            ability = (f"МЕХАНИКА: {tags_txt}" if lang == "ru" else f"MECHANICS: {tags_txt}")
            stats_rows = [
                ("БАЗОВОЕ ОЗ" if lang == "ru" else "BASE HP", f"{cfg['hp']} (xFloor)"),
                ("СКОРОСТЬ / РАД." if lang == "ru" else "SPD / RADIUS", f"{cfg['speed']}  ·  {cfg['radius']}px"),
                ("АРХЕТИП" if lang == "ru" else "ARCHETYPE", cfg["style"].upper()),
                ("ЯРУС ПОЯВЛЕНИЯ" if lang == "ru" else "FLOOR TIER", tier_txt),
            ]
            footer = f"BOSS ID: {cur.upper()}  ·  3 ФАЗЫ БОЯ" if lang == "ru" else f"BOSS ID: {cur.upper()}  ·  3 COMBAT PHASES"
            return title, subtitle, lore, ability, stats_rows, footer

        if self.tab == 4:
            info = ROOM_CUSTOM.get(cur, {})
            title = tr_room(cur)
            subtitle = "АРХИТЕКТУРА ПОДЗЕМЕЛИЙ" if lang == "ru" else "DUNGEON ARCHITECTURE"
            lore = info.get(lang, info.get("ru", ""))
            ability = info.get("stats_en", "") if lang == "en" else info.get("stats_ru", "")
            scheme = ROOM_COLOR_SCHEMES.get(cur, ROOM_COLOR_SCHEMES["normal"])
            stats_rows = [
                ("ТИП ЗАЛА" if lang == "ru" else "ROOM KEY", cur.upper()),
                ("ТОН ПОЛА" if lang == "ru" else "FLOOR TONE", f"{scheme['floor_a'][0]} / 255"),
                ("ТОН СТЕН" if lang == "ru" else "WALL TONE", f"{scheme['wall'][0]} / 255"),
                ("ДОСТУП" if lang == "ru" else "ACCESS", "Бомба" if cur == "secret" else ("Ключ" if cur == "treasure" else ("Свободный" if lang == "ru" else "Open"))),
            ]
            return title, subtitle, lore, ability, stats_rows, ability

        if self.tab == 5:
            it_type = cur.get("type", "passive")
            is_act = it_type == "active"
            title = tr_item_name(cur)
            subtitle = (
                (f"АКТИВНАЯ РЕЛИКВИЯ · ЗАРЯД {cur.get('max_charge', 0)}" if is_act else "ПАССИВНЫЙ АРТЕФАКТ")
                if lang == "ru"
                else (f"ACTIVE RELIC · CHARGE {cur.get('max_charge', 0)}" if is_act else "PASSIVE RELIC")
            )
            lore = tr_item_desc(cur)
            ability = (
                "Нажимайте ПРОБЕЛ для активации (1–9 — выбор реликвии); перезарядка за комнаты и монолиты."
                if is_act and lang == "ru"
                else (
                    "Press SPACE to unleash (1–9 selects relics); recharges from room clears, batteries, and monoliths."
                    if is_act
                    else (
                        "Синергирует с другими пассивными артефактами, спутниками и модификаторами слёз."
                        if lang == "ru"
                        else "Stacks cumulatively with all passive relics, orbitals, and tear modifiers."
                    )
                )
            )
            stats_rows = [
                ("ТИП" if lang == "ru" else "TYPE", "ACTIVE" if is_act else "PASSIVE"),
                ("МАКС. ЗАРЯД" if lang == "ru" else "MAX CHARGE", f"{cur.get('max_charge', 0)}" if is_act else "—"),
                ("ИКОНКА" if lang == "ru" else "GLYPH", cur.get("icon", "orb").upper()),
                ("ID ПУЛА" if lang == "ru" else "ITEM ID", cur["id"].upper()[:18]),
            ]
            footer = f"КОЛЛЕКЦИЯ: #{self.selected + 1} ИЗ {len(ITEM_POOL_65)}" if lang == "ru" else f"COLLECTION: #{self.selected + 1} OF {len(ITEM_POOL_65)}"
            return title, subtitle, lore, ability, stats_rows, footer

        title = cur.get("name_en", cur["name"]) if lang == "en" else cur["name"]
        subtitle = cur.get("sub_en", cur["sub"]) if lang == "en" else cur["sub"]
        lore = cur.get("lore_en", cur["lore"]) if lang == "en" else cur["lore"]
        ability = cur.get("ability_en", cur["ability_ru"]) if lang == "en" else cur["ability_ru"]
        stats_rows = cur.get("stats_rows_en", cur["stats_rows_ru"]) if lang == "en" else cur["stats_rows_ru"]
        footer = cur.get("footer_en", cur["footer_ru"]) if lang == "en" else cur["footer_ru"]
        return title, subtitle, lore, ability, stats_rows, footer

    def draw(self, screen, ui):
        lang = get_lang()
        ox = get_world_offset_x()
        tabs = self._tabs()
        screen.fill((8, 8, 8))
        panel = get_panel_surf(1160, 640, 14, 240, 108, 12)
        screen.blit(panel, (ox + 60, 40))

        title = render_text_cached(ui.font_big, tr("codex_title"), PALETTE["text_main"])
        screen.blit(title, (ox + 90, 58))

        back_r = self._back_rect()
        pygame.draw.rect(screen, (236, 236, 236) if self.hover_back else (28, 28, 28), back_r, border_radius=6)
        pygame.draw.rect(screen, (250, 250, 250) if self.hover_back else (96, 96, 96), back_r, 1, border_radius=6)
        blit_text_fitted(screen, back_r, ui.font_small, tr("tutorial_back"), (14, 14, 14) if self.hover_back else PALETTE["text_main"], pad_x=8)

        for i, (tb, rc) in enumerate(zip(tabs, self._tab_rects())):
            sel = i == self.tab
            hov = i == self.hover_tab
            fill = (238, 238, 238) if sel else ((54, 54, 54) if hov else (28, 28, 28))
            pygame.draw.rect(screen, fill, rc, border_radius=6)
            pygame.draw.rect(screen, (252, 252, 252) if sel else ((140, 140, 140) if hov else (68, 68, 68)), rc, 1, border_radius=6)
            blit_text_fitted(screen, rc, ui.font_tiny, tb, (14, 14, 14) if sel else PALETTE["text_main"], pad_x=6)

        items = self._current_list()
        if items:
            self.selected = int(clamp(self.selected, 0, len(items) - 1))
        self._sync_scroll(len(items))
        start_idx = self.scroll_idx
        visible = items[start_idx:start_idx + 12]
        row_rects = self._row_rects(len(visible))
        for vi, entry in enumerate(visible):
            real_idx = start_idx + vi
            rc = row_rects[vi]
            sel = real_idx == self.selected
            hov = real_idx == self.hover_row
            fill = (234, 234, 234) if sel else ((48, 48, 48) if hov else (24, 24, 24))
            pygame.draw.rect(screen, fill, rc, border_radius=6)
            if hov and not sel:
                pygame.draw.rect(screen, (118, 118, 118), rc, 1, border_radius=6)
            name = self._entry_label(entry, lang)
            blit_text_fitted(screen, rc, ui.font_small, name, (14, 14, 14) if sel else PALETTE["text_main"], align="left", pad_x=10)

        if len(items) > 12:
            up_rc, dn_rc = self._scroll_btn_rects()
            for dir_s, b_rc, b_lbl in ((-1, up_rc, "▲"), (1, dn_rc, "▼")):
                hov_s = self.hover_scroll == dir_s
                pygame.draw.rect(screen, (236, 236, 236) if hov_s else (28, 28, 28), b_rc, border_radius=5)
                pygame.draw.rect(screen, (250, 250, 250) if hov_s else (88, 88, 88), b_rc, 1, border_radius=5)
                t_s = render_text_cached(ui.font_tiny, b_lbl, (14, 14, 14) if hov_s else PALETTE["text_main"])
                screen.blit(t_s, (b_rc.centerx - t_s.get_width() // 2, b_rc.centery - t_s.get_height() // 2))
            sb_x = ox + 458
            sb_y = 184
            sb_h = 386
            pygame.draw.rect(screen, (26, 26, 26), (sb_x, sb_y, 6, sb_h), border_radius=3)
            knob_h = max(28, int(sb_h * (12.0 / len(items))))
            knob_y = sb_y + int((sb_h - knob_h) * (start_idx / max(1, len(items) - 12)))
            pygame.draw.rect(screen, (164, 164, 164), (sb_x, knob_y, 6, knob_h), border_radius=3)

        if items:
            cur = items[self.selected]
            showcase_box = pygame.Rect(ox + 486, 152, 230, 184)
            self._draw_showcase_visual(screen, cur, showcase_box)

            e_title, e_sub, e_lore, e_ability, stats_rows, e_footer = self._build_entry_details(cur, lang)

            meta_x = ox + 736
            meta_w = 452
            title_lines = _wrap_text_px(e_title, ui.font_big, meta_w)[:2]
            ty = 152
            for tl in title_lines:
                ts = fit_text_surf(ui.font_big, tl, PALETTE["text_main"], meta_w)
                screen.blit(ts, (meta_x, ty))
                ty += 28

            sub_surf = fit_text_surf(ui.font_tiny, e_sub, (214, 214, 214), meta_w)
            screen.blit(sub_surf, (meta_x, ty + 2))

            stat_y = 224
            col_w = 220
            for idx, (s_k, s_v) in enumerate(stats_rows[:4]):
                cx_box = meta_x + (idx % 2) * (col_w + 10)
                cy_box = stat_y + (idx // 2) * 56
                s_rc = pygame.Rect(cx_box, cy_box, col_w, 48)
                pygame.draw.rect(screen, (20, 20, 20), s_rc, border_radius=6)
                pygame.draw.rect(screen, (60, 60, 60), s_rc, 1, border_radius=6)
                kl = fit_text_surf(ui.font_tiny, s_k, PALETTE["text_dim"], col_w - 20)
                vl = fit_text_surf(ui.font_small, str(s_v), PALETTE["text_main"], col_w - 20)
                screen.blit(kl, (cx_box + 10, cy_box + 6))
                screen.blit(vl, (cx_box + 10, cy_box + 23))

            body_rc = pygame.Rect(ox + 486, 352, 702, 266)
            pygame.draw.rect(screen, (18, 18, 18), body_rc, border_radius=8)
            pygame.draw.rect(screen, (58, 58, 58), body_rc, 1, border_radius=8)

            hdr_txt = "ОБЛИК, ЛОР И ПОВЕДЕНИЕ" if lang == "ru" else "FORM, LORE & BEHAVIOR"
            screen.blit(render_text_cached(ui.font_tiny, hdr_txt, PALETTE["text_dim"]), (ox + 504, 366))

            cur_y = 388
            for ln in _wrap_text_px(e_lore, ui.font_med, 666)[:4]:
                screen.blit(fit_text_surf(ui.font_med, ln, (226, 226, 226), 666), (ox + 504, cur_y))
                cur_y += 22

            ab_box_y = max(cur_y + 8, 494)
            ab_h = 56
            ab_rc = pygame.Rect(ox + 504, ab_box_y, 666, ab_h)
            pygame.draw.rect(screen, (26, 26, 26), ab_rc, border_radius=6)
            pygame.draw.rect(screen, (88, 88, 88), ab_rc, 1, border_radius=6)
            for ai, aln in enumerate(_wrap_text_px(e_ability, ui.font_small, 642)[:2]):
                screen.blit(fit_text_surf(ui.font_small, aln, (242, 242, 242), 642), (ox + 516, ab_box_y + 8 + ai * 19))

            foot_surf = fit_text_surf(ui.font_tiny, e_footer, PALETTE["accent_soft"], 666)
            screen.blit(foot_surf, (ox + 504, 594))

        hint_txt = (
            "Wheel / W/S — Entry   |   A/D / Click — Category   |   ESC — Back"
            if lang == "en"
            else "Колёсико / W/S — Запись   |   A/D / Клик — Раздел   |   ESC — Назад"
        )
        hint = fit_text_surf(ui.font_small, hint_txt, PALETTE["text_dim"], 700)
        screen.blit(hint, (ox + 486, 636))
