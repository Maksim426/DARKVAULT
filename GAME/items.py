import hashlib
import math
import random
import pygame
from settings import (
    GAME_SETTINGS,
    _prune_cache,
    draw_aa_circle,
    draw_aa_ellipse,
    draw_aa_poly,
    draw_aa_ring,
    ease_in_out,
    get_glow_surf,
    get_particle_surf,
    get_shadow_surf,
    gray,
    render_4x_smooth,
    render_text_cached,
)

ITEM_POOL_65 = [
    {"id": "eclipse_shard", "name": "Осколок затмения", "desc": "+2.0 Урон и ореол тёмной орбитали", "type": "passive", "color": (236, 236, 236), "icon": "eclipse"},
    {"id": "bone_compass", "name": "Костяной компас", "desc": "+0.8 Скорость, самонаведение и обзор карты", "type": "passive", "color": (244, 244, 244), "icon": "compass"},
    {"id": "frozen_hourglass", "name": "Застывшие песочные часы", "desc": "+Темп огня и замедление вражеских пуль", "type": "passive", "color": (228, 228, 228), "icon": "hourglass"},
    {"id": "crown_of_ash", "name": "Корона пепла", "desc": "+2.2 Урон, +2 Чёрных сердца и пепельный щит", "type": "passive", "color": (212, 212, 212), "icon": "crown"},
    {"id": "mask_of_void", "name": "Маска пустоты", "desc": "Шанс уклонения от удара и +1.2 Урон", "type": "passive", "color": (248, 248, 248), "icon": "mask"},
    {"id": "monolith_tear", "name": "Слеза монолита", "desc": "Пронзание, сквозь камни и +90 Дальность", "type": "passive", "color": (250, 250, 250), "icon": "monolith_tear"},
    {"id": "seers_skull", "name": "Череп провидца", "desc": "+2 Удача, +1.5 Урон и яркий фонарь", "type": "passive", "color": (238, 238, 238), "icon": "seers_skull"},
    {"id": "key_of_abyss", "name": "Ключ от бездны", "desc": "+5 Ключей, +0.9 Урон и отпирание замков", "type": "passive", "color": (242, 242, 242), "icon": "abyss_key"},
    {"id": "spoon_bender", "name": "Ложка-маг", "desc": "+Самонаведение слёз", "type": "passive", "color": (210, 210, 210), "icon": "spoon"},
    {"id": "sad_onion", "name": "Грустный лук", "desc": "+Скорострельность", "type": "passive", "color": (236, 236, 236), "icon": "onion"},
    {"id": "crickets_head", "name": "Голова Крикета", "desc": "+2.2 Урон и x1.35 мощь", "type": "passive", "color": (196, 196, 196), "icon": "skull"},
    {"id": "cricket_body", "name": "Тело Крикета", "desc": "Слёзы расщепляются", "type": "passive", "color": (214, 214, 214), "icon": "orb"},
    {"id": "the_belt", "name": "Старый ремень", "desc": "+0.9 Скорость", "type": "passive", "color": (132, 132, 132), "icon": "belt"},
    {"id": "mutant_spider", "name": "Паук-мутант", "desc": "4 слезы за выстрел", "type": "passive", "color": (148, 148, 148), "icon": "spider"},
    {"id": "inner_eye", "name": "Третий глаз", "desc": "Тройной выстрел", "type": "passive", "color": (232, 232, 232), "icon": "eye"},
    {"id": "twin_lens", "name": "Двойная линза", "desc": "Двойной залп", "type": "passive", "color": (222, 222, 222), "icon": "lens"},
    {"id": "my_reflection", "name": "Отражение", "desc": "Слёзы возвращаются", "type": "passive", "color": (190, 190, 190), "icon": "mirror"},
    {"id": "number_one", "name": "Номер Один", "desc": "Ураганный темп огня", "type": "passive", "color": (244, 244, 244), "icon": "drop"},
    {"id": "phantom_blade", "name": "Призрачный клинок", "desc": "Пронзание и сквозь камни", "type": "passive", "color": (208, 208, 208), "icon": "blade"},
    {"id": "twilight_prism", "name": "Призма сумерек", "desc": "+Урон, +Дальность, +Темп", "type": "passive", "color": (248, 248, 248), "icon": "prism"},
    {"id": "guardian_shard", "name": "Осколок стража", "desc": "Орбитальный щит от пуль", "type": "passive", "color": (226, 226, 226), "icon": "shield"},
    {"id": "twin_orbitals", "name": "Двойные спутники", "desc": "+2 боевых орбиталя", "type": "passive", "color": (218, 218, 218), "icon": "orbit"},
    {"id": "blood_ruby", "name": "Тёмный рубин", "desc": "+1 Сердце и +1.2 Урон", "type": "passive", "color": (166, 166, 166), "icon": "gem"},
    {"id": "shadow_cloak", "name": "Плащ теней", "desc": "Быстрый откат рывка и +Скорость", "type": "passive", "color": (88, 88, 88), "icon": "cloak"},
    {"id": "rubber_cement", "name": "Резиновый клей", "desc": "Слёзы отскакивают от стен", "type": "passive", "color": (228, 228, 228), "icon": "orb"},
    {"id": "dinner", "name": "Ужин", "desc": "+1 Макс. сердце и лечение", "type": "passive", "color": (210, 210, 210), "icon": "heart"},
    {"id": "magic_mushroom", "name": "Магический гриб", "desc": "Мощный рост всех статов", "type": "passive", "color": (238, 238, 238), "icon": "mushroom"},
    {"id": "brimstone", "name": "Сера Бездны", "desc": "+3.2 Урон и пронзающие заряды", "type": "passive", "color": (124, 124, 124), "icon": "brimstone"},
    {"id": "brimstone_pact", "name": "Пакт Серы", "desc": "+2.4 Урон, +Чёрные сердца", "type": "passive", "color": (96, 96, 96), "icon": "brimstone"},
    {"id": "polyphemus", "name": "Полифем", "desc": "Огромный урон и крупные слёзы", "type": "passive", "color": (246, 246, 246), "icon": "eye"},
    {"id": "holy_mantle", "name": "Святая мантия", "desc": "Щит от 1 удара в каждой комнате", "type": "passive", "color": (250, 250, 250), "icon": "shield"},
    {"id": "holy_mantle_shield", "name": "Покров Духа", "desc": "Стартовый щит комнаты", "type": "passive", "color": (244, 244, 244), "icon": "shield"},
    {"id": "pentagram", "name": "Пентаграмма", "desc": "+1.6 Урон", "type": "passive", "color": (146, 146, 146), "icon": "star"},
    {"id": "halo", "name": "Нимб", "desc": "+Все характеристики и +1 сердце", "type": "passive", "color": (248, 248, 248), "icon": "halo"},
    {"id": "meat", "name": "Кусок плоти", "desc": "+1 Сердце и +0.6 Урон", "type": "passive", "color": (182, 182, 182), "icon": "heart"},
    {"id": "breakfast", "name": "Завтрак", "desc": "+1 Контейнер сердца", "type": "passive", "color": (228, 228, 228), "icon": "heart"},
    {"id": "the_pact", "name": "Договор", "desc": "+1.2 Урон, +Темп, +2 Чёрных сердца", "type": "passive", "color": (106, 106, 106), "icon": "scroll"},
    {"id": "the_mark", "name": "Знак Зверя", "desc": "+1.4 Урон, +0.6 Скорость, +1 Чёрное сердце", "type": "passive", "color": (122, 122, 122), "icon": "star"},
    {"id": "lord_of_the_pit", "name": "Владыка Ямы", "desc": "Полёт и +0.7 Скорость", "type": "passive", "color": (72, 72, 72), "icon": "wing"},
    {"id": "tooth_picks", "name": "Зубочистки", "desc": "+Скорострельность и скорость слёз", "type": "passive", "color": (232, 232, 232), "icon": "blade"},
    {"id": "steven", "name": "Стивен", "desc": "+1.5 Урон", "type": "passive", "color": (174, 174, 174), "icon": "skull"},
    {"id": "sacred_heart", "name": "Святое Сердце", "desc": "Урон x1.4, +Самонаведение и +Сердце", "type": "passive", "color": (252, 252, 252), "icon": "heart"},
    {"id": "godhead", "name": "Лик Божества", "desc": "+Самонаведение, +Аура и +Урон", "type": "passive", "color": (246, 246, 246), "icon": "prism"},
    {"id": "cancer", "name": "Талисман Рака", "desc": "Максимальное ускорение темпа", "type": "passive", "color": (212, 212, 212), "icon": "orb"},
    {"id": "mini_mush", "name": "Мини-гриб", "desc": "Меньше размер и +0.8 Скорость", "type": "passive", "color": (196, 196, 196), "icon": "mushroom"},
    {"id": "cat_o_nine_tails", "name": "Хлыст", "desc": "+Скорость слёз и +0.9 Урон", "type": "passive", "color": (162, 162, 162), "icon": "blade"},
    {"id": "iron_bar", "name": "Железный прут", "desc": "+0.9 Урон и тяжёлый удар", "type": "passive", "color": (154, 154, 154), "icon": "blade"},
    {"id": "moms_heels", "name": "Туфли матери", "desc": "+50 Дальность и +Скорость", "type": "passive", "color": (192, 192, 192), "icon": "boot"},
    {"id": "wooden_spoon", "name": "Деревянная ложка", "desc": "+0.65 Скорость", "type": "passive", "color": (176, 176, 176), "icon": "spoon"},
    {"id": "speed_ball", "name": "Ускоритель", "desc": "+0.65 Скорость и +Дальность", "type": "passive", "color": (236, 236, 236), "icon": "drop"},
    {"id": "wire_coat_hanger", "name": "Вешалка", "desc": "+Быстрая перезарядка слёз", "type": "passive", "color": (204, 204, 204), "icon": "orbit"},
    {"id": "skeleton_key", "name": "Отмычка", "desc": "+12 Ключей", "type": "passive", "color": (228, 228, 228), "icon": "key"},
    {"id": "pyro", "name": "Пиротехник", "desc": "+12 Бомб", "type": "passive", "color": (168, 168, 168), "icon": "bomb"},
    {"id": "pyromaniac", "name": "Пироман", "desc": "Взрывы лечат, +5 Бомб", "type": "passive", "color": (218, 218, 218), "icon": "bomb"},
    {"id": "a_dollar", "name": "Доллар", "desc": "+30 Монет", "type": "passive", "color": (236, 236, 236), "icon": "coin"},
    {"id": "blood_martyr", "name": "Кровь мученика", "desc": "+1.4 Урон", "type": "passive", "color": (172, 172, 172), "icon": "drop"},
    {"id": "tough_love", "name": "Зубной кастет", "desc": "+1.4 Урон и мощные выстрелы", "type": "passive", "color": (240, 240, 240), "icon": "skull"},
    {"id": "roid_rage", "name": "Стимулятор", "desc": "+0.65 Скорость и +50 Дальность", "type": "passive", "color": (206, 206, 206), "icon": "drop"},
    {"id": "synthoil", "name": "Синтол", "desc": "+0.9 Урон и +35 Дальность", "type": "passive", "color": (188, 188, 188), "icon": "drop"},
    {"id": "magic_8_ball", "name": "Шар 8", "desc": "+Скорость слёз и +1 Удача", "type": "passive", "color": (94, 94, 94), "icon": "orb"},
    {"id": "rosary", "name": "Чётки", "desc": "+2 Сердца души и +Темп", "type": "passive", "color": (224, 224, 224), "icon": "halo"},
    {"id": "jesus_juice", "name": "Причастие", "desc": "+0.9 Урон и +35 Дальность", "type": "passive", "color": (200, 200, 200), "icon": "drop"},
    {"id": "growth_hormones", "name": "Гормон роста", "desc": "+0.9 Урон и +Скорость слёз", "type": "passive", "color": (216, 216, 216), "icon": "orb"},
    {"id": "capricorn", "name": "Козерог", "desc": "+Все статы и +1 ключ, бомба, монета", "type": "passive", "color": (226, 226, 226), "icon": "star"},
    {"id": "scorpio", "name": "Скорпион", "desc": "Ядовитые слёзы разъедают врагов", "type": "passive", "color": (152, 152, 152), "icon": "spider"},
    {"id": "rotten_meat", "name": "Гнилое мясо", "desc": "+1 Контейнер сердца", "type": "passive", "color": (144, 144, 144), "icon": "heart"},
    {"id": "super_bandage", "name": "Супер-бинт", "desc": "+1 Сердце и +2 Сердца души", "type": "passive", "color": (244, 244, 244), "icon": "heart"},
    {"id": "infamy", "name": "Маска позора", "desc": "Шанс 35% заблокировать удар", "type": "passive", "color": (196, 196, 196), "icon": "mask"},
    {"id": "mitre", "name": "Митра", "desc": "+2 Сердца души и благословение", "type": "passive", "color": (236, 236, 236), "icon": "halo"},
    {"id": "the_relic", "name": "Реликвия", "desc": "Даёт сердца души при зачистке", "type": "passive", "color": (214, 214, 214), "icon": "shield"},
    {"id": "the_wafer", "name": "Облатка", "desc": "Снижает весь урон до половины сердца", "type": "passive", "color": (242, 242, 242), "icon": "orb"},
    {"id": "whore_of_babylon", "name": "Тень Вавилона", "desc": "+Урон и скорость при 1 красном сердце", "type": "passive", "color": (84, 84, 84), "icon": "star"},
    {"id": "dark_bum", "name": "Тёмный бродяга", "desc": "Собирает сердца и даёт души", "type": "passive", "color": (98, 98, 98), "icon": "cloak"},
    {"id": "lunch", "name": "Обед", "desc": "+1 Контейнер сердца", "type": "passive", "color": (222, 222, 222), "icon": "heart"},
    {"id": "dessert", "name": "Десерт", "desc": "+1 Контейнер сердца", "type": "passive", "color": (234, 234, 234), "icon": "heart"},
    {"id": "snack", "name": "Перекус", "desc": "+1 Контейнер сердца и +Скорость", "type": "passive", "color": (216, 216, 216), "icon": "heart"},
    {"id": "stem_cells", "name": "Стволовые клетки", "desc": "+1 Сердце и +Скорость слёз", "type": "passive", "color": (204, 204, 204), "icon": "orb"},
    {"id": "stigmata", "name": "Стигматы", "desc": "+0.9 Урон и +Дальность", "type": "passive", "color": (164, 164, 164), "icon": "heart"},
    {"id": "black_lotus", "name": "Чёрный лотос", "desc": "+1 Красное, +1 Души, +1 Чёрное сердце", "type": "passive", "color": (110, 110, 110), "icon": "star"},
    {"id": "iron_maiden", "name": "Железная дева", "desc": "+1.4 Урон, защита, -0.2 Скорость", "type": "passive", "color": (136, 136, 136), "icon": "shield"},
    {"id": "cat_head", "name": "Голова кота", "desc": "+1.4 Урон и когтистые слёзы", "type": "passive", "color": (180, 180, 180), "icon": "skull"},
    {"id": "torn_photo", "name": "Рваное фото", "desc": "+Скорость выстрела и +Темп", "type": "passive", "color": (226, 226, 226), "icon": "scroll"},
    {"id": "blood_bag", "name": "Пакет крови", "desc": "+1 Сердце, лечение и +0.5 Скорость", "type": "passive", "color": (190, 190, 190), "icon": "heart"},
    {"id": "lucky_foot", "name": "Счастливая лапка", "desc": "+2 Удача и лучшие находки", "type": "passive", "color": (232, 232, 232), "icon": "boot"},
    {"id": "skatole", "name": "Скатол", "desc": "Мухи боятся и реже атакуют", "type": "passive", "color": (150, 150, 150), "icon": "spider"},
    {"id": "abaddon", "name": "Абаддон", "desc": "+2.5 Урон, +4 Чёрных сердца, +Скорость", "type": "passive", "color": (68, 68, 68), "icon": "brimstone"},
    {"id": "spirit_night", "name": "Дух ночи", "desc": "Полёт и призрачные слёзы", "type": "passive", "color": (140, 140, 140), "icon": "wing"},
    {"id": "raw_liver", "name": "Сырая печень", "desc": "+2 Сердца и полное исцеление", "type": "passive", "color": (168, 168, 168), "icon": "heart"},
    {"id": "placenta", "name": "Плацента", "desc": "+1 Сердце и медленная регенерация", "type": "passive", "color": (200, 200, 200), "icon": "heart"},
    {"id": "steam_sale", "name": "Скидка 50%", "desc": "Все товары в лавке вдвое дешевле", "type": "passive", "color": (244, 244, 244), "icon": "coin"},
    {"id": "moms_key", "name": "Ключ матери", "desc": "+2 Ключа и щедрые сундуки", "type": "passive", "color": (228, 228, 228), "icon": "key"},
    {"id": "sad_bombs", "name": "Грустные бомбы", "desc": "Взрыв бомбы разбрасывает слёзы", "type": "passive", "color": (184, 184, 184), "icon": "bomb"},
    {"id": "bloody_lust", "name": "Жажда битвы", "desc": "Ранения усиливают урон на ярусе", "type": "passive", "color": (160, 160, 160), "icon": "blade"},
    {"id": "lazarus_rags", "name": "Лохмотья Лазаря", "desc": "Одно воскрешение с ростом урона", "type": "passive", "color": (212, 212, 212), "icon": "scroll"},
    {"id": "incubus", "name": "Инкуб", "desc": "Тёмный спутник дублирует выстрелы", "type": "passive", "color": (92, 92, 92), "icon": "wing"},
    {"id": "bone_club", "name": "Костяная дубина", "desc": "+1.4 Урон и костяные слёзы", "type": "passive", "color": (242, 242, 242), "icon": "blade"},
    {"id": "lump_of_coal", "name": "Кусок угля", "desc": "Слёзы растут в уроне по мере полёта", "type": "passive", "color": (78, 78, 78), "icon": "orb"},
    {"id": "krampus_head", "name": "Голова Крампуса", "desc": "Мощный залп из 4 серных лучей", "type": "active", "max_charge": 4, "color": (118, 118, 118), "icon": "brimstone"},
    {"id": "the_poop", "name": "Кучка", "desc": "Ставит барьер перед игроком", "type": "active", "max_charge": 1, "color": (136, 136, 136), "icon": "orb"},
    {"id": "yum_heart", "name": "Вкусное Сердце", "desc": "Восстанавливает 1 полное сердце", "type": "active", "max_charge": 4, "color": (236, 236, 236), "icon": "heart"},
    {"id": "guppys_head", "name": "Голова Гаппи", "desc": "Призывает 3 боевых синих мух", "type": "active", "max_charge": 1, "color": (176, 176, 176), "icon": "spider"},
    {"id": "the_d6", "name": "Игральная кость D6", "desc": "Перебрасывает артефакты в комнате", "type": "active", "max_charge": 6, "color": (244, 244, 244), "icon": "dice"},
    {"id": "book_of_belial", "name": "Книга Велиала", "desc": "+2.5 Урон на текущую комнату", "type": "active", "max_charge": 3, "color": (128, 128, 128), "icon": "book"},
    {"id": "book_of_shadows", "name": "Книга Теней", "desc": "Неуязвимость на 8 секунд", "type": "active", "max_charge": 3, "color": (214, 214, 214), "icon": "book"},
    {"id": "razor_blade", "name": "Лезвие бритвы", "desc": "Тратит 0.5 сердца ради +1.6 Урона", "type": "active", "max_charge": 0, "color": (222, 222, 222), "icon": "blade"},
    {"id": "box_of_friends", "name": "Коробка друзей", "desc": "Удваивает спутников в комнате", "type": "active", "max_charge": 3, "color": (198, 198, 198), "icon": "orbit"},
    {"id": "void", "name": "Пустота", "desc": "Поглощает реликвии для роста статов", "type": "active", "max_charge": 6, "color": (92, 92, 92), "icon": "prism"},
    {"id": "book_of_virtues", "name": "Книга Добродетелей", "desc": "Призывает защитные белые огоньки", "type": "active", "max_charge": 4, "color": (248, 248, 248), "icon": "book"},
    {"id": "wooden_nickel", "name": "Деревянный пятак", "desc": "Монеты или +1 Сердце души при активации", "type": "active", "max_charge": 1, "color": (228, 228, 228), "icon": "coin"},
    {"id": "chrono_pocket", "name": "Карманные часы", "desc": "Замораживает врагов и ускоряет темп слёз", "type": "active", "max_charge": 3, "color": (236, 236, 236), "icon": "hourglass"},
    {"id": "philosopher_vial", "name": "Философский сосуд", "desc": "Залп из 8 ядовитых слёз и припас", "type": "active", "max_charge": 2, "color": (192, 192, 192), "icon": "drop"},
    {"id": "iron_bastion", "name": "Железный обет", "desc": "+2 Орбиталя в комнате и ударная волна", "type": "active", "max_charge": 3, "color": (212, 212, 212), "icon": "shield"},
    {"id": "seraph_bell", "name": "Колокол Серафима", "desc": "Обновляет щит и бьёт 8 святыми лучами", "type": "active", "max_charge": 4, "color": (248, 248, 248), "icon": "halo"},
    {"id": "blast_tear", "name": "Взрывная слеза", "desc": "Слёзы взрываются по площади и рушат камни", "type": "passive", "color": (240, 240, 240), "icon": "cluster"},
    {"id": "mortar_eye", "name": "Глаз-мортира", "desc": "Навесные слёзы летят дугой над преградами и взрываются", "type": "passive", "color": (222, 222, 222), "icon": "mortar"},
    {"id": "seismic_boots", "name": "Сейсмические сапоги", "desc": "+Скорость, быстрый прыжок и взрывной удар приземления", "type": "passive", "color": (208, 208, 208), "icon": "boot"},
    {"id": "shock_core", "name": "Импульсное ядро", "desc": "Ударные волны от попаданий и усиленный прыжок-удар", "type": "passive", "color": (246, 246, 246), "icon": "shockwave"},
    {"id": "cluster_detonator", "name": "Кластерный детонатор", "desc": "Запускает 6 разрывных мортирных снарядов вокруг", "type": "active", "max_charge": 3, "color": (232, 232, 232), "icon": "cluster"},
    {"id": "comet_leap", "name": "Кометный прыжок", "desc": "Мощный прыжок-удар с метеоритным взрывом и волной", "type": "active", "max_charge": 2, "color": (250, 250, 250), "icon": "comet"},
    {"id": "phantom_cloak", "name": "Покров Фантома", "desc": "Сокращает откат невидимости [V] и усиливает засаду (x2.5)", "type": "passive", "color": (166, 166, 166), "icon": "cloak"},
    {"id": "singularity_orb", "name": "Сфера Сингулярности", "desc": "Гравитационные слёзы стягивают врагов и снаряды в вихрь", "type": "passive", "color": (214, 214, 214), "icon": "vortex"},
    {"id": "chain_coil", "name": "Катушка Разряда", "desc": "Цепная молния при попадании бьёт до 2 ближайших врагов", "type": "passive", "color": (244, 244, 244), "icon": "chain"},
    {"id": "storm_greaves", "name": "Грозовые поножи", "desc": "Рывок [Shift] становится атакующим ударом по врагам", "type": "passive", "color": (228, 228, 228), "icon": "boot"},
]

ITEM_TEXTS_EN = {
    "eclipse_shard": ("Eclipse Shard", "+2.0 DMG and dark orbital shield"),
    "bone_compass": ("Bone Compass", "+0.8 SPD, homing tears, full map reveal"),
    "frozen_hourglass": ("Frozen Hourglass", "+Fire rate & slows enemy projectiles"),
    "crown_of_ash": ("Crown of Ash", "+2.2 DMG, +2 Black Hearts, room shield"),
    "mask_of_void": ("Mask of Void", "Dodge chance and +1.2 DMG"),
    "monolith_tear": ("Monolith Tear", "Piercing, spectral tears & +90 Range"),
    "seers_skull": ("Seer's Skull", "+2 Luck, +1.5 DMG, brighter lantern"),
    "key_of_abyss": ("Key of the Abyss", "+5 Keys, +0.9 DMG, unlocks all doors"),
    "spoon_bender": ("Spoon Bender", "Homing tears bend toward foes"),
    "sad_onion": ("The Sad Onion", "Substantial fire rate up"),
    "crickets_head": ("Cricket's Head", "+2.2 DMG and x1.25 power multiplier"),
    "cricket_body": ("Cricket's Body", "Tears split into 4 mini-tears on impact"),
    "the_belt": ("The Belt", "+0.9 Move speed"),
    "mutant_spider": ("Mutant Spider", "Fires 4 tears per salvo"),
    "inner_eye": ("The Inner Eye", "Triple tear salvo"),
    "twin_lens": ("Twin Lens", "Double tear salvo"),
    "my_reflection": ("My Reflection", "Boomerang tears curve back toward you"),
    "number_one": ("Number One", "Massive tears-up at shorter range"),
    "phantom_blade": ("Phantom Blade", "Piercing & spectral tears through rocks"),
    "twilight_prism": ("Twilight Prism", "+DMG, +Range, +Fire rate"),
    "guardian_shard": ("Guardian Shard", "Orbiting shard blocks shots & hits foes"),
    "twin_orbitals": ("Twin Orbitals", "+2 protective combat orbitals"),
    "blood_ruby": ("Dark Ruby", "+1 Heart container and +1.2 DMG"),
    "shadow_cloak": ("Shadow Cloak", "Faster dash cooldown and +Speed"),
    "rubber_cement": ("Rubber Cement", "Tears ricochet off walls and rocks"),
    "dinner": ("Dinner", "+1 Max Heart container and heal"),
    "magic_mushroom": ("Magic Mushroom", "Major all-stats surge and full heal"),
    "brimstone": ("Brimstone", "+3.2 DMG and piercing sulfur blasts"),
    "brimstone_pact": ("Brimstone Pact", "+2.4 DMG and +2 Black Hearts"),
    "polyphemus": ("Polyphemus", "Huge DMG multiplier & massive tears"),
    "holy_mantle": ("Holy Mantle", "Negates the first hit in every room"),
    "holy_mantle_shield": ("Spirit Shroud", "Protective first-hit mantle every room"),
    "pentagram": ("Pentagram", "+1.6 DMG up"),
    "halo": ("The Halo", "All stats up + 1 Heart container"),
    "meat": ("Meat!", "+1 Heart container and +0.6 DMG"),
    "breakfast": ("Breakfast", "+1 Heart container"),
    "the_pact": ("The Pact", "+1.2 DMG, +Fire rate, +2 Black Hearts"),
    "the_mark": ("The Mark", "+1.4 DMG, +0.6 SPD, +1 Black Heart"),
    "lord_of_the_pit": ("Lord of the Pit", "Grants flight over pits and +0.7 SPD"),
    "tooth_picks": ("Tooth Picks", "+Fire rate and +Tear velocity"),
    "steven": ("Steven", "+1.4 DMG up"),
    "sacred_heart": ("Sacred Heart", "Huge DMG multiplier, homing & full heal"),
    "godhead": ("Godhead", "Homing, damaging holy aura & +DMG"),
    "cancer": ("Cancer Trinket", "Drastically lowers fire delay"),
    "mini_mush": ("Mini Mush", "Smaller hitbox and +0.8 SPD"),
    "cat_o_nine_tails": ("Cat-O-Nine-Tails", "+Tear speed and +0.9 DMG"),
    "iron_bar": ("Iron Bar", "+0.9 DMG and heavy knockback shots"),
    "moms_heels": ("Mom's Heels", "+50 Tear range and +Speed"),
    "wooden_spoon": ("Wooden Spoon", "+0.65 Move speed"),
    "speed_ball": ("Speed Ball", "+0.65 Speed and +Range"),
    "wire_coat_hanger": ("Wire Coat Hanger", "Greatly faster tear fire rate"),
    "skeleton_key": ("Skeleton Key", "+12 Keys"),
    "pyro": ("Pyro", "+12 Bombs"),
    "pyromaniac": ("Pyromaniac", "Explosions heal you; +5 Bombs"),
    "a_dollar": ("A Dollar", "+30 Coins"),
    "blood_martyr": ("Blood of the Martyr", "+1.4 DMG up"),
    "tough_love": ("Tough Love", "+1.4 DMG and crushing impacts"),
    "roid_rage": ("Roid Rage", "+0.65 Speed and +50 Range"),
    "synthoil": ("Synthoil", "+0.9 DMG and +35 Range"),
    "magic_8_ball": ("Magic 8 Ball", "+Tear speed and +1 Luck"),
    "rosary": ("Rosary", "+2 Soul Hearts and +Fire rate"),
    "jesus_juice": ("Jesus Juice", "+0.9 DMG and +35 Range"),
    "growth_hormones": ("Growth Hormones", "+0.9 DMG and +Tear velocity"),
    "capricorn": ("Capricorn", "All stats up +1 key, bomb, coin"),
    "scorpio": ("Scorpio", "Poisonous tears corrode enemies over time"),
    "rotten_meat": ("Rotten Meat", "+1 Heart container"),
    "super_bandage": ("Super Bandage", "+1 Heart and +2 Soul Hearts"),
    "infamy": ("Infamy", "35% chance to deflect incoming hits"),
    "mitre": ("The Mitre", "+2 Soul Hearts and blessing"),
    "the_relic": ("The Relic", "Drops bonus Soul Hearts on room clear"),
    "the_wafer": ("The Wafer", "Reduces all damage taken to half a heart"),
    "whore_of_babylon": ("Whore of Babylon", "Surges DMG & SPD at <= 1 red heart"),
    "dark_bum": ("Dark Bum", "Converts excess hearts into Soul/Black Hearts"),
    "lunch": ("Lunch", "+1 Heart container"),
    "dessert": ("Dessert", "+1 Heart container"),
    "snack": ("A Snack", "+1 Heart container and +Speed"),
    "stem_cells": ("Stem Cells", "+1 Heart container and +Tear speed"),
    "stigmata": ("Stigmata", "+0.9 DMG and +Range"),
    "black_lotus": ("Black Lotus", "+1 Red, +1 Soul, +1 Black Heart"),
    "iron_maiden": ("Iron Maiden", "+1.4 DMG, +Soul Heart, -0.2 SPD"),
    "cat_head": ("Tammy's / Cat Head", "+1.4 DMG claws"),
    "torn_photo": ("Torn Photo", "+Tear velocity and +Fire rate"),
    "blood_bag": ("Blood Bag", "+1 Heart container, heal 2, +0.5 SPD"),
    "lucky_foot": ("Lucky Foot", "+2 Luck and better drops"),
    "skatole": ("Skatole", "Flies become pacified and timid"),
    "abaddon": ("Abaddon", "+2.5 DMG, +4 Black Hearts, +Speed"),
    "spirit_night": ("Spirit of the Night", "Flight & spectral tears through cover"),
    "raw_liver": ("Raw Liver", "+2 Heart containers and full red heal"),
    "placenta": ("Placenta", "+1 Heart container and slow regeneration"),
    "steam_sale": ("Steam Sale", "50% discount on all shop goods"),
    "moms_key": ("Mom's Key", "+2 Keys and richer urn/chest drops"),
    "sad_bombs": ("Sad Bombs", "Bomb blasts burst 8 modified tears"),
    "bloody_lust": ("Bloody Lust", "Taking hits boosts floor DMG"),
    "lazarus_rags": ("Lazarus' Rags", "Grants 1 revival with huge DMG boost"),
    "incubus": ("Incubus", "Shadow familiar echoes your tear salvos"),
    "bone_club": ("Bone Club", "+1.4 DMG and spinning piercing bones"),
    "lump_of_coal": ("A Lump of Coal", "Tears gain massive DMG as they travel"),
    "krampus_head": ("Head of Krampus", "Blasts 4 piercing brimstone beams"),
    "the_poop": ("The Poop", "Drops a destructible barrier behind you"),
    "yum_heart": ("Yum Heart", "Restores 1 full Red Heart"),
    "guppys_head": ("Guppy's Head", "Summons 3 attacking Blue Flies"),
    "the_d6": ("The D6", "Rerolls pedestals in the current room"),
    "book_of_belial": ("Book of Belial", "+2.5 DMG for the current room"),
    "book_of_shadows": ("Book of Shadows", "8 seconds of complete invulnerability"),
    "razor_blade": ("Razor Blade", "Sacrifice 0.5 heart for +1.6 room DMG"),
    "box_of_friends": ("Box of Friends", "Doubles active familiars, orbitals & wisps"),
    "void": ("Void", "Absorbs room pedestals into permanent stats"),
    "book_of_virtues": ("Book of Virtues", "Summons protective shooting wisps"),
    "wooden_nickel": ("Wooden Nickel", "70% chance to spawn coins or restore 1 Soul HP"),
    "chrono_pocket": ("Chrono Pocket", "Freezes all room enemies for 4s & grants Haste"),
    "philosopher_vial": ("Philosopher's Vial", "Bursts 8 spectral venom tears & spawns loot"),
    "iron_bastion": ("Iron Vow", "Summons +2 room orbitals & knockback shockwave"),
    "seraph_bell": ("Seraph's Bell", "Refreshes Shield Mantle & fires 8 homing holy rays"),
    "blast_tear": ("Blast Tear", "+1.0 DMG & tears detonate in AoE blasts that shatter stone"),
    "mortar_eye": ("Mortar Eye", "Lobbed parabolic shots arc over cover & explode on impact"),
    "seismic_boots": ("Seismic Greaves", "+SPD, faster Jump cooldown & explosive ground-slams"),
    "shock_core": ("Shockwave Core", "+1.1 DMG & impact shockwaves + stronger Jump-Slams"),
    "cluster_detonator": ("Cluster Detonator", "Launches 6 lobbed explosive mortars in a radial volley"),
    "comet_leap": ("Comet Leap", "Instant high leap forward with meteor blast & shockwave"),
    "phantom_cloak": ("Phantom Cloak", "Faster Invisibility [V] recharge & lethal x2.5 Ambush crits"),
    "singularity_orb": ("Singularity Orb", "Gravity-well tears pull surrounding foes inward"),
    "chain_coil": ("Arc Coil", "Tears discharge chain-lightning bolts between nearby foes"),
    "storm_greaves": ("Storm Greaves", "Turns Shadow Dash [Shift] into a damaging lunge strike"),
}

for _it in ITEM_POOL_65:
    _en = ITEM_TEXTS_EN.get(_it["id"])
    if _en is not None:
        _it["name_en"] = _en[0]
        _it["desc_en"] = _en[1]
    else:
        _it["name_en"] = _it["name"]
        _it["desc_en"] = _it["desc"]


def tr_item_name(item):
    if not item:
        return ""
    if GAME_SETTINGS.get("language", "ru") == "en":
        return item.get("name_en", item.get("name", ""))
    return item.get("name", "")


def tr_item_desc(item):
    if not item:
        return ""
    if GAME_SETTINGS.get("language", "ru") == "en":
        return item.get("desc_en", item.get("desc", ""))
    return item.get("desc", "")

ITEM_REGISTRY = {item["id"]: item for item in ITEM_POOL_65}
ICON_CACHE = {}
_PICKUP_SPRITE_CACHE = {}


def _get_pickup_sprite(kind):
    spr = _PICKUP_SPRITE_CACHE.get(kind)
    if spr is not None:
        return spr
    _prune_cache(_PICKUP_SPRITE_CACHE, 32)
    size = 30

    def _draw(hi, hw, hh):
        cx = hw * 0.5
        cy = hh * 0.5
        s = 4.0
        if kind in ("heart", "half_heart", "soul_heart", "black_heart"):
            lum = 242 if kind in ("heart", "half_heart") else (198 if kind == "soul_heart" else 44)
            rim = 14 if lum > 80 else 222
            shade = max(18, lum - 46)
            draw_aa_circle(hi, (rim, rim, rim, 255), cx - 4 * s, cy - 2 * s, 6.2 * s)
            draw_aa_circle(hi, (rim, rim, rim, 255), cx + 4 * s, cy - 2 * s, 6.2 * s)
            draw_aa_poly(hi, (rim, rim, rim, 255), [(cx - 10.2 * s, cy), (cx + 10.2 * s, cy), (cx, cy + 10.2 * s)])
            draw_aa_circle(hi, (lum, lum, lum, 255), cx - 4 * s, cy - 2 * s, 4.6 * s)
            if kind != "half_heart":
                draw_aa_circle(hi, (lum, lum, lum, 255), cx + 4 * s, cy - 2 * s, 4.6 * s)
                draw_aa_poly(hi, (lum, lum, lum, 255), [(cx - 8 * s, cy), (cx + 8 * s, cy), (cx, cy + 8 * s)])
                draw_aa_poly(hi, (shade, shade, shade, 140), [(cx + 0.5 * s, cy + 0.5 * s), (cx + 7.5 * s, cy), (cx, cy + 7.5 * s)])
            else:
                draw_aa_poly(hi, (lum, lum, lum, 255), [(cx - 8 * s, cy), (cx, cy), (cx, cy + 8 * s)])
                pygame.draw.line(hi, (rim, rim, rim, 255), (int(cx), int(cy - 5 * s)), (int(cx), int(cy + 8 * s)), int(1.6 * s))
            draw_aa_circle(hi, (254, 254, 254, 235), cx - 5.2 * s, cy - 3.4 * s, 1.6 * s)
        elif kind in ("coin", "nickel", "dime"):
            lum = 228 if kind == "coin" else (168 if kind == "nickel" else 248)
            r = 8 if kind == "coin" else (9 if kind == "nickel" else 7)
            draw_aa_ellipse(hi, (14, 14, 14, 255), cx, cy, (r + 2.2) * s, (r + 3.2) * s)
            draw_aa_ellipse(hi, (max(40, lum - 48), max(40, lum - 48), max(40, lum - 48), 255), cx + 0.6 * s, cy + 0.8 * s, r * s, (r + 1) * s)
            draw_aa_ellipse(hi, (lum, lum, lum, 255), cx, cy, (r - 0.6) * s, (r + 0.4) * s)
            draw_aa_ellipse(hi, (max(24, lum - 72), max(24, lum - 72), max(24, lum - 72), 180), cx, cy, (r - 2.6) * s, (r - 1.4) * s)
            draw_aa_ellipse(hi, (lum, lum, lum, 255), cx - 0.5 * s, cy - 0.5 * s, (r - 3.2) * s, (r - 2.0) * s)
            pygame.draw.line(hi, (36, 36, 36, 255), (int(cx), int(cy - 4 * s)), (int(cx), int(cy + 4 * s)), int(2 * s))
            draw_aa_circle(hi, (254, 254, 254, 220), cx - 3 * s, cy - 4 * s, 1.4 * s)
        elif kind == "bomb":
            draw_aa_circle(hi, (14, 14, 14, 255), cx, cy + 1 * s, 9.2 * s)
            draw_aa_circle(hi, (88, 88, 88, 255), cx, cy + 1 * s, 7.2 * s)
            draw_aa_circle(hi, (132, 132, 132, 255), cx - 1.2 * s, cy - 0.2 * s, 5.2 * s)
            draw_aa_circle(hi, (232, 232, 232, 255), cx - 2.6 * s, cy - 1.6 * s, 2.2 * s)
            pygame.draw.rect(hi, (38, 38, 38, 255), (int(cx - 2.2 * s), int(cy - 7.5 * s), int(4.4 * s), int(2.6 * s)), border_radius=int(s))
            pygame.draw.line(hi, (240, 240, 240, 255), (int(cx), int(cy - 6.5 * s)), (int(cx + 5 * s), int(cy - 11 * s)), int(2 * s))
            draw_aa_circle(hi, (254, 254, 254, 140), cx + 6 * s, cy - 11 * s, 3.2 * s)
            draw_aa_circle(hi, (254, 254, 254, 255), cx + 6 * s, cy - 11 * s, 1.8 * s)
        elif kind == "key":
            draw_aa_circle(hi, (14, 14, 14, 255), cx - 4 * s, cy, 5.8 * s)
            draw_aa_circle(hi, (232, 232, 232, 255), cx - 4 * s, cy, 4.2 * s)
            draw_aa_circle(hi, (14, 14, 14, 255), cx - 4 * s, cy, 1.9 * s)
            pygame.draw.line(hi, (14, 14, 14, 255), (int(cx), int(cy)), (int(cx + 10.6 * s), int(cy)), int(4.2 * s))
            pygame.draw.line(hi, (232, 232, 232, 255), (int(cx), int(cy)), (int(cx + 10 * s), int(cy)), int(2.8 * s))
            pygame.draw.line(hi, (232, 232, 232, 255), (int(cx + 6.5 * s), int(cy)), (int(cx + 6.5 * s), int(cy + 4.2 * s)), int(2.2 * s))
            pygame.draw.line(hi, (232, 232, 232, 255), (int(cx + 9.2 * s), int(cy)), (int(cx + 9.2 * s), int(cy + 3.0 * s)), int(1.8 * s))
            draw_aa_circle(hi, (254, 254, 254, 220), cx - 5.5 * s, cy - 2.2 * s, 1.1 * s)
        elif kind == "card":
            rect = pygame.Rect(int(cx - 7 * s), int(cy - 9 * s), int(14 * s), int(18 * s))
            pygame.draw.rect(hi, (14, 14, 14, 255), rect.inflate(int(2.2 * s), int(2.2 * s)), border_radius=int(2.4 * s))
            pygame.draw.rect(hi, (242, 242, 242, 255), rect, border_radius=int(2 * s))
            pygame.draw.rect(hi, (32, 32, 32, 255), rect.inflate(-int(3 * s), -int(3 * s)), int(s), border_radius=int(1 * s))
            draw_aa_poly(hi, (20, 20, 20, 255), [(cx, cy - 4.2 * s), (cx + 3.4 * s, cy), (cx, cy + 4.2 * s), (cx - 3.4 * s, cy)])
            draw_aa_circle(hi, (246, 246, 246, 220), cx, cy, 1.0 * s)
        else:
            rect = pygame.Rect(int(cx - 6 * s), int(cy - 8 * s), int(12 * s), int(16 * s))
            pygame.draw.rect(hi, (14, 14, 14, 255), rect.inflate(int(2 * s), int(2 * s)), border_radius=int(3.2 * s))
            pygame.draw.rect(hi, (228, 228, 228, 255), rect, border_radius=int(2.8 * s))
            pygame.draw.rect(hi, (160, 160, 160, 255), (rect.x + int(2 * s), rect.y + int(7 * s), rect.w - int(4 * s), int(6 * s)), border_radius=int(1.2 * s))
            pygame.draw.rect(hi, (18, 18, 18, 255), rect, int(s), border_radius=int(2.8 * s))
            pygame.draw.rect(hi, (248, 248, 248, 255), (rect.x + int(3 * s), rect.y - int(2 * s), int(6 * s), int(3 * s)), border_radius=int(1 * s))

    spr = render_4x_smooth(size, size, _draw, blur_radius=0.14)
    _PICKUP_SPRITE_CACHE[kind] = spr
    return spr


def get_item_by_id(item_id):
    return ITEM_REGISTRY.get(item_id)


def get_random_item(exclude_ids=None, item_type=None):
    ex = set(exclude_ids or ())
    candidates = [
        it for it in ITEM_POOL_65
        if it["id"] not in ex and (item_type is None or it["type"] == item_type)
    ]
    if not candidates:
        candidates = [it for it in ITEM_POOL_65 if item_type is None or it["type"] == item_type]
    return random.choice(candidates)


def _draw_icon_vector(surf, item, size):
    cx = size // 2
    cy = size // 2
    r = max(8, int(size * 0.34))
    col = gray(item.get("color", (220, 220, 220)))
    lum = col[0]
    dark = (max(12, lum - 110), max(12, lum - 110), max(12, lum - 110))
    bright = (min(255, lum + 35), min(255, lum + 35), min(255, lum + 35))
    icon = item.get("icon", "orb")

    if icon == "eclipse":
        draw_aa_circle(surf, (242, 242, 242), cx, cy, r * 1.02)
        draw_aa_circle(surf, (14, 14, 14), cx + r * 0.14, cy, r * 0.84)
        for i in range(8):
            a = i * (math.pi / 4.0)
            p1 = (cx + math.cos(a) * r * 0.88, cy + math.sin(a) * r * 0.88)
            p2 = (cx + math.cos(a) * r * 1.18, cy + math.sin(a) * r * 1.18)
            pygame.draw.line(surf, (238, 238, 238), (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), max(2, r // 10))
    elif icon == "compass":
        draw_aa_circle(surf, (16, 16, 16), cx, cy, r * 1.04)
        draw_aa_circle(surf, (218, 218, 218), cx, cy, r * 0.90)
        draw_aa_circle(surf, (24, 24, 24), cx, cy, r * 0.70)
        n_pts = [(cx, cy - r * 0.88), (cx + r * 0.22, cy), (cx, cy + r * 0.88), (cx - r * 0.22, cy)]
        draw_aa_poly(surf, (248, 248, 248), n_pts)
        e_pts = [(cx - r * 0.68, cy), (cx, cy - r * 0.18), (cx + r * 0.68, cy), (cx, cy + r * 0.18)]
        draw_aa_poly(surf, (164, 164, 164), e_pts)
        draw_aa_circle(surf, (18, 18, 18), cx, cy, r * 0.14)
    elif icon == "hourglass":
        top_p = [(cx - r * 0.72, cy - r * 0.88), (cx + r * 0.72, cy - r * 0.88), (cx + r * 0.12, cy), (cx - r * 0.12, cy)]
        bot_p = [(cx - r * 0.12, cy), (cx + r * 0.12, cy), (cx + r * 0.72, cy + r * 0.88), (cx - r * 0.72, cy + r * 0.88)]
        draw_aa_poly(surf, (16, 16, 16), [(cx - r * 0.84, cy - r * 0.96), (cx + r * 0.84, cy - r * 0.96), (cx + r * 0.20, cy), (cx - r * 0.20, cy)])
        draw_aa_poly(surf, (16, 16, 16), [(cx - r * 0.20, cy), (cx + r * 0.20, cy), (cx + r * 0.84, cy + r * 0.96), (cx - r * 0.84, cy + r * 0.96)])
        draw_aa_poly(surf, (226, 226, 226), top_p)
        draw_aa_poly(surf, (148, 148, 148), bot_p)
        draw_aa_poly(surf, (248, 248, 248), [(cx - r * 0.42, cy + r * 0.80), (cx + r * 0.42, cy + r * 0.80), (cx, cy + r * 0.36)])
        pygame.draw.rect(surf, (244, 244, 244), (int(cx - r * 0.82), int(cy - r * 0.98), int(r * 1.64), max(3, r // 6)), border_radius=2)
        pygame.draw.rect(surf, (244, 244, 244), (int(cx - r * 0.82), int(cy + r * 0.84), int(r * 1.64), max(3, r // 6)), border_radius=2)
    elif icon == "crown":
        pts = [
            (cx - r * 0.92, cy + r * 0.62),
            (cx - r * 0.96, cy - r * 0.45),
            (cx - r * 0.48, cy + r * 0.04),
            (cx, cy - r * 0.82),
            (cx + r * 0.48, cy + r * 0.04),
            (cx + r * 0.96, cy - r * 0.45),
            (cx + r * 0.92, cy + r * 0.62),
        ]
        draw_aa_poly(surf, (16, 16, 16), pts)
        pts_in = [(cx + (px - cx) * 0.82, cy + (py - cy) * 0.82) for px, py in pts]
        draw_aa_poly(surf, (224, 224, 224), pts_in)
        for tx, ty in ((cx - r * 0.96, cy - r * 0.45), (cx, cy - r * 0.82), (cx + r * 0.96, cy - r * 0.45)):
            draw_aa_circle(surf, (250, 250, 250), tx, ty, r * 0.14)
    elif icon == "mask":
        draw_aa_ellipse(surf, (16, 16, 16), cx, cy, r * 0.88, r * 1.05)
        draw_aa_ellipse(surf, (240, 240, 240), cx, cy, r * 0.74, r * 0.90)
        pygame.draw.rect(surf, (58, 58, 58), (cx, int(cy - r * 0.88), int(r * 0.74), int(r * 1.76)))
        draw_aa_circle(surf, (16, 16, 16), cx - r * 0.30, cy - r * 0.18, r * 0.20)
        draw_aa_circle(surf, (246, 246, 246), cx + r * 0.30, cy - r * 0.18, r * 0.20)
        draw_aa_ellipse(surf, (18, 18, 18), cx, cy + r * 0.38, r * 0.26, r * 0.14)
    elif icon == "monolith_tear":
        pts = [(cx, cy - r * 1.04), (cx + r * 0.76, cy + r * 0.22), (cx + r * 0.50, cy + r * 0.88), (cx, cy + r * 1.02), (cx - r * 0.50, cy + r * 0.88), (cx - r * 0.76, cy + r * 0.22)]
        draw_aa_poly(surf, (16, 16, 16), pts)
        pts_in = [(cx + (px - cx) * 0.82, cy + (py - cy) * 0.82) for px, py in pts]
        draw_aa_poly(surf, (238, 238, 238), pts_in)
        pygame.draw.line(surf, (28, 28, 28), (cx, int(cy - r * 0.44)), (cx, int(cy + r * 0.56)), max(2, r // 8))
        pygame.draw.line(surf, (28, 28, 28), (int(cx - r * 0.28), int(cy + r * 0.08)), (int(cx + r * 0.28), int(cy + r * 0.08)), max(2, r // 8))
    elif icon == "seers_skull":
        draw_aa_circle(surf, (16, 16, 16), cx, cy - r * 0.12, r * 0.96)
        draw_aa_circle(surf, (236, 236, 236), cx, cy - r * 0.12, r * 0.82)
        pygame.draw.rect(surf, (236, 236, 236), (int(cx - r * 0.46), int(cy + r * 0.24), int(r * 0.92), int(r * 0.62)), border_radius=6)
        draw_aa_circle(surf, (16, 16, 16), cx - r * 0.28, cy - r * 0.02, r * 0.20)
        draw_aa_circle(surf, (16, 16, 16), cx + r * 0.28, cy - r * 0.02, r * 0.20)
        draw_aa_circle(surf, (16, 16, 16), cx, cy - r * 0.42, r * 0.22)
        draw_aa_circle(surf, (252, 252, 252), cx, cy - r * 0.42, r * 0.11)
    elif icon == "abyss_key":
        draw_aa_circle(surf, (16, 16, 16), cx - r * 0.44, cy, r * 0.52)
        draw_aa_circle(surf, (242, 242, 242), cx - r * 0.44, cy, r * 0.38)
        draw_aa_circle(surf, (18, 18, 18), cx - r * 0.44, cy, r * 0.18)
        pygame.draw.line(surf, (242, 242, 242), (int(cx - r * 0.12), cy), (int(cx + r * 0.92), cy), max(4, r // 4))
        pygame.draw.line(surf, (242, 242, 242), (int(cx + r * 0.48), cy), (int(cx + r * 0.48), int(cy + r * 0.44)), max(3, r // 5))
        pygame.draw.line(surf, (242, 242, 242), (int(cx + r * 0.82), cy), (int(cx + r * 0.82), int(cy + r * 0.36)), max(3, r // 5))
        draw_aa_poly(surf, (206, 206, 206), [(cx - r * 0.44, cy - r * 0.40), (cx - r * 0.86, cy - r * 0.88), (cx - r * 0.14, cy - r * 0.54)])
    elif icon == "heart":
        draw_aa_circle(surf, (18, 18, 18), cx - r * 0.42, cy - r * 0.22, r * 0.56)
        draw_aa_circle(surf, (18, 18, 18), cx + r * 0.42, cy - r * 0.22, r * 0.56)
        draw_aa_poly(surf, (18, 18, 18), [(cx - r * 0.96, cy - r * 0.05), (cx + r * 0.96, cy - r * 0.05), (cx, cy + r * 0.98)])
        draw_aa_circle(surf, col, cx - r * 0.40, cy - r * 0.22, r * 0.44)
        draw_aa_circle(surf, col, cx + r * 0.40, cy - r * 0.22, r * 0.44)
        draw_aa_poly(surf, col, [(cx - r * 0.80, cy - r * 0.06), (cx + r * 0.80, cy - r * 0.06), (cx, cy + r * 0.82)])
        draw_aa_circle(surf, bright, cx - r * 0.45, cy - r * 0.34, max(2, r * 0.16))
    elif icon == "eye":
        draw_aa_ellipse(surf, (18, 18, 18), cx, cy, r * 1.15, r * 0.78)
        draw_aa_ellipse(surf, (244, 244, 244), cx, cy, r * 0.98, r * 0.64)
        draw_aa_circle(surf, col, cx, cy, r * 0.42)
        draw_aa_circle(surf, (16, 16, 16), cx, cy, r * 0.22)
        draw_aa_circle(surf, (255, 255, 255), cx - r * 0.15, cy - r * 0.15, max(2, r * 0.1))
    elif icon == "skull":
        draw_aa_circle(surf, (16, 16, 16), cx, cy - r * 0.12, r * 0.95)
        draw_aa_circle(surf, col, cx, cy - r * 0.12, r * 0.80)
        pygame.draw.rect(surf, col, (int(cx - r * 0.44), int(cy + r * 0.25), int(r * 0.88), int(r * 0.56)), border_radius=4)
        draw_aa_circle(surf, (14, 14, 14), cx - r * 0.28, cy - r * 0.06, r * 0.22)
        draw_aa_circle(surf, (14, 14, 14), cx + r * 0.28, cy - r * 0.06, r * 0.22)
    elif icon == "book":
        rect = pygame.Rect(int(cx - r * 0.78), int(cy - r * 0.92), int(r * 1.56), int(r * 1.84))
        pygame.draw.rect(surf, (16, 16, 16), rect.inflate(8, 8), border_radius=8)
        pygame.draw.rect(surf, col, rect, border_radius=6)
        pygame.draw.rect(surf, dark, (rect.x, rect.y, int(r * 0.34), rect.h), border_radius=4)
        pygame.draw.line(surf, bright, (rect.centerx + 3, rect.y + int(r * 0.35)), (rect.centerx + 3, rect.bottom - int(r * 0.35)), max(3, r // 6))
        pygame.draw.line(surf, bright, (rect.centerx - int(r * 0.32), rect.centery), (rect.centerx + int(r * 0.42), rect.centery), max(3, r // 6))
    elif icon == "dice":
        rect = pygame.Rect(int(cx - r * 0.84), int(cy - r * 0.84), int(r * 1.68), int(r * 1.68))
        pygame.draw.rect(surf, (14, 14, 14), rect.inflate(8, 8), border_radius=12)
        pygame.draw.rect(surf, (242, 242, 242), rect, border_radius=10)
        for ox, oy in ((-0.4, -0.4), (0.4, -0.4), (-0.4, 0.0), (0.4, 0.0), (-0.4, 0.4), (0.4, 0.4)):
            draw_aa_circle(surf, (18, 18, 18), cx + r * ox, cy + r * oy, max(3, r * 0.14))
    elif icon == "blade":
        pts_outer = [(cx - r * 0.85, cy + r * 0.72), (cx + r * 0.75, cy - r * 0.88), (cx + r * 0.92, cy - r * 0.55), (cx - r * 0.50, cy + r * 0.88)]
        draw_aa_poly(surf, (16, 16, 16), pts_outer)
        pts_in = [(cx - r * 0.65, cy + r * 0.55), (cx + r * 0.65, cy - r * 0.74), (cx + r * 0.76, cy - r * 0.55), (cx - r * 0.45, cy + r * 0.70)]
        draw_aa_poly(surf, bright, pts_in)
        pygame.draw.line(surf, (42, 42, 42), (int(cx - r * 0.75), int(cy + r * 0.42)), (int(cx - r * 0.36), int(cy + r * 0.80)), max(5, r // 4))
    elif icon == "shield":
        pts = [(cx - r * 0.85, cy - r * 0.75), (cx + r * 0.85, cy - r * 0.75), (cx + r * 0.75, cy + r * 0.25), (cx, cy + r * 0.98), (cx - r * 0.75, cy + r * 0.25)]
        draw_aa_poly(surf, (16, 16, 16), pts)
        pts2 = [(cx - r * 0.68, cy - r * 0.58), (cx + r * 0.68, cy - r * 0.58), (cx + r * 0.58, cy + r * 0.18), (cx, cy + r * 0.78), (cx - r * 0.58, cy + r * 0.18)]
        draw_aa_poly(surf, col, pts2)
        pygame.draw.line(surf, bright, (cx, int(cy - r * 0.42)), (cx, int(cy + r * 0.52)), max(3, r // 6))
    elif icon == "brimstone":
        draw_aa_circle(surf, (18, 18, 18), cx, cy + r * 0.28, r * 0.55)
        draw_aa_ring(surf, bright, cx, cy + r * 0.30, r * 0.44, max(3, r // 6))
        pygame.draw.line(surf, bright, (cx, int(cy - r * 0.88)), (cx, int(cy + r * 0.08)), max(4, r // 5))
        pygame.draw.line(surf, bright, (int(cx - r * 0.52), int(cy - r * 0.45)), (int(cx + r * 0.52), int(cy - r * 0.45)), max(3, r // 6))
        pygame.draw.line(surf, bright, (int(cx - r * 0.42), int(cy - r * 0.14)), (int(cx + r * 0.42), int(cy - r * 0.14)), max(3, r // 6))
    elif icon == "star":
        pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * (math.pi / 5)
            rad = r * (0.98 if i % 2 == 0 else 0.44)
            pts.append((cx + math.cos(ang) * rad, cy + math.sin(ang) * rad))
        draw_aa_poly(surf, (16, 16, 16), pts)
        draw_aa_poly(surf, col, [(cx + (px - cx) * 0.82, cy + (py - cy) * 0.82) for px, py in pts])
    elif icon == "bomb":
        draw_aa_circle(surf, (18, 18, 18), cx, cy + r * 0.14, r * 0.82)
        draw_aa_circle(surf, col, cx, cy + r * 0.14, r * 0.68)
        draw_aa_circle(surf, bright, cx - r * 0.22, cy - r * 0.06, r * 0.22)
        pygame.draw.line(surf, (236, 236, 236), (cx, int(cy - r * 0.54)), (int(cx + r * 0.42), int(cy - r * 0.92)), max(3, r // 6))
        draw_aa_circle(surf, (252, 252, 252), cx + r * 0.45, cy - r * 0.94, max(2, r * 0.16))
    elif icon == "key":
        draw_aa_circle(surf, (18, 18, 18), cx - r * 0.42, cy, r * 0.46)
        draw_aa_circle(surf, col, cx - r * 0.42, cy, r * 0.34)
        draw_aa_circle(surf, (18, 18, 18), cx - r * 0.42, cy, r * 0.14)
        pygame.draw.line(surf, col, (int(cx - r * 0.12), cy), (int(cx + r * 0.82), cy), max(4, r // 5))
        pygame.draw.line(surf, col, (int(cx + r * 0.52), cy), (int(cx + r * 0.52), int(cy + r * 0.36)), max(3, r // 6))
        pygame.draw.line(surf, col, (int(cx + r * 0.80), cy), (int(cx + r * 0.80), int(cy + r * 0.30)), max(3, r // 6))
    elif icon == "prism":
        pts = [(cx, cy - r * 0.95), (cx + r * 0.92, cy + r * 0.72), (cx - r * 0.92, cy + r * 0.72)]
        draw_aa_poly(surf, (16, 16, 16), pts)
        pts2 = [(cx, cy - r * 0.74), (cx + r * 0.72, cy + r * 0.56), (cx - r * 0.72, cy + r * 0.56)]
        draw_aa_poly(surf, col, pts2)
        draw_aa_circle(surf, bright, cx, cy + r * 0.08, r * 0.24)
    elif icon == "halo":
        draw_aa_ellipse(surf, (18, 18, 18), cx, cy, r * 1.0, r * 0.55)
        draw_aa_ellipse(surf, bright, cx, cy, r * 0.86, r * 0.42)
        draw_aa_ellipse(surf, (24, 24, 24), cx, cy, r * 0.52, r * 0.20)
    elif icon == "mushroom":
        draw_aa_circle(surf, (18, 18, 18), cx, cy - r * 0.12, r * 0.85)
        draw_aa_circle(surf, col, cx, cy - r * 0.12, r * 0.72)
        pygame.draw.rect(surf, (236, 236, 236), (int(cx - r * 0.34), int(cy + r * 0.04), int(r * 0.68), int(r * 0.78)), border_radius=6)
        draw_aa_circle(surf, (250, 250, 250), cx - r * 0.32, cy - r * 0.32, r * 0.16)
        draw_aa_circle(surf, (250, 250, 250), cx + r * 0.28, cy - r * 0.26, r * 0.14)
    elif icon == "coin":
        draw_aa_circle(surf, (16, 16, 16), cx, cy, r * 0.96)
        draw_aa_circle(surf, col, cx, cy, r * 0.82)
        draw_aa_ring(surf, dark, cx, cy, r * 0.64, max(2, r // 9))
        pygame.draw.line(surf, (18, 18, 18), (cx, int(cy - r * 0.44)), (cx, int(cy + r * 0.44)), max(3, r // 6))
    elif icon == "drop":
        pts = [(cx, cy - r * 0.98), (cx + r * 0.66, cy + r * 0.18), (cx, cy + r * 0.92), (cx - r * 0.66, cy + r * 0.18)]
        draw_aa_poly(surf, (16, 16, 16), pts)
        draw_aa_circle(surf, (16, 16, 16), cx, cy + r * 0.28, r * 0.68)
        draw_aa_poly(surf, col, [(cx, cy - r * 0.78), (cx + r * 0.50, cy + r * 0.16), (cx, cy + r * 0.74), (cx - r * 0.50, cy + r * 0.16)])
        draw_aa_circle(surf, col, cx, cy + r * 0.26, r * 0.52)
        draw_aa_circle(surf, bright, cx - r * 0.18, cy + r * 0.12, max(2, r * 0.15))
    elif icon == "boot":
        pts = [(cx - r * 0.56, cy - r * 0.84), (cx + r * 0.08, cy - r * 0.84), (cx + r * 0.14, cy + r * 0.16), (cx + r * 0.82, cy + r * 0.28), (cx + r * 0.82, cy + r * 0.78), (cx - r * 0.62, cy + r * 0.78)]
        draw_aa_poly(surf, (16, 16, 16), pts)
        draw_aa_poly(surf, col, [(cx + (px - cx) * 0.84, cy + (py - cy) * 0.84) for px, py in pts])
        pygame.draw.line(surf, bright, (int(cx - r * 0.45), int(cy + r * 0.52)), (int(cx + r * 0.64), int(cy + r * 0.52)), max(3, r // 6))
    elif icon == "mortar":
        draw_aa_poly(surf, (16, 16, 16), [(cx - r * 0.66, cy + r * 0.76), (cx + r * 0.66, cy + r * 0.76), (cx + r * 0.42, cy - r * 0.72), (cx - r * 0.42, cy - r * 0.72)])
        draw_aa_poly(surf, col, [(cx - r * 0.52, cy + r * 0.62), (cx + r * 0.52, cy + r * 0.62), (cx + r * 0.30, cy - r * 0.56), (cx - r * 0.30, cy - r * 0.56)])
        draw_aa_circle(surf, bright, cx, cy - r * 0.78, r * 0.24)
        draw_aa_ring(surf, (18, 18, 18), cx, cy - r * 0.78, r * 0.34, max(2, r // 8))
    elif icon == "shockwave":
        draw_aa_ring(surf, (16, 16, 16), cx, cy, r * 0.98, max(3, r // 5))
        draw_aa_ring(surf, bright, cx, cy, r * 0.90, max(2, r // 6))
        draw_aa_ring(surf, col, cx, cy, r * 0.56, max(2, r // 6))
        draw_aa_circle(surf, bright, cx, cy, r * 0.24)
    elif icon == "cluster":
        for ox, oy, cr in ((-0.38, 0.24, 0.42), (0.38, 0.24, 0.42), (0.0, -0.32, 0.46)):
            draw_aa_circle(surf, (16, 16, 16), cx + r * ox, cy + r * oy, r * (cr + 0.12))
            draw_aa_circle(surf, col, cx + r * ox, cy + r * oy, r * cr)
            draw_aa_circle(surf, bright, cx + r * (ox - 0.1), cy + r * (oy - 0.1), r * cr * 0.35)
    elif icon == "comet":
        draw_aa_poly(surf, (16, 16, 16), [(cx - r * 0.88, cy - r * 0.84), (cx + r * 0.55, cy + r * 0.08), (cx + r * 0.08, cy + r * 0.55)])
        draw_aa_poly(surf, (164, 164, 164), [(cx - r * 0.72, cy - r * 0.68), (cx + r * 0.42, cy + r * 0.06), (cx + r * 0.06, cy + r * 0.42)])
        draw_aa_circle(surf, (16, 16, 16), cx + r * 0.36, cy + r * 0.36, r * 0.48)
        draw_aa_circle(surf, bright, cx + r * 0.36, cy + r * 0.36, r * 0.34)
    elif icon == "vortex":
        draw_aa_ring(surf, (16, 16, 16), cx, cy, r * 0.94, max(4, r // 5))
        draw_aa_ring(surf, col, cx, cy, r * 0.82, max(2, r // 7))
        draw_aa_ring(surf, bright, cx, cy, r * 0.50, max(2, r // 7))
        draw_aa_circle(surf, (18, 18, 18), cx, cy, r * 0.28)
        draw_aa_circle(surf, bright, cx, cy, r * 0.14)
    elif icon == "chain":
        draw_aa_poly(
            surf,
            (18, 18, 18),
            [(cx + r * 0.16, cy - r * 0.95), (cx - r * 0.48, cy + r * 0.06), (cx - r * 0.02, cy + r * 0.06), (cx - r * 0.24, cy + r * 0.95), (cx + r * 0.52, cy - r * 0.08), (cx + r * 0.04, cy - r * 0.08)],
        )
        draw_aa_poly(
            surf,
            bright,
            [(cx + r * 0.10, cy - r * 0.78), (cx - r * 0.34, cy - r * 0.02), (cx + r * 0.08, cy - r * 0.02), (cx - r * 0.12, cy + r * 0.76), (cx + r * 0.36, cy - r * 0.06), (cx - r * 0.04, cy - r * 0.06)],
        )
    elif icon == "spoon":
        draw_aa_ellipse(surf, (16, 16, 16), cx - r * 0.28, cy - r * 0.28, r * 0.56, r * 0.42)
        draw_aa_ellipse(surf, bright, cx - r * 0.28, cy - r * 0.28, r * 0.42, r * 0.29)
        draw_aa_ellipse(surf, dark, cx - r * 0.30, cy - r * 0.30, r * 0.22, r * 0.14)
        pygame.draw.line(surf, (16, 16, 16), (int(cx), int(cy)), (int(cx + r * 0.86), int(cy + r * 0.86)), max(5, r // 4))
        pygame.draw.line(surf, col, (int(cx), int(cy)), (int(cx + r * 0.82), int(cy + r * 0.82)), max(3, r // 6))
    elif icon == "onion":
        draw_aa_circle(surf, (16, 16, 16), cx, cy + r * 0.12, r * 0.88)
        draw_aa_circle(surf, col, cx, cy + r * 0.12, r * 0.74)
        for ox in (-0.34, 0.0, 0.34):
            draw_aa_ellipse(surf, dark, cx + r * ox, cy + r * 0.12, r * 0.14, r * 0.62)
        draw_aa_poly(surf, bright, [(cx - r * 0.16, cy - r * 0.52), (cx, cy - r * 0.96), (cx + r * 0.16, cy - r * 0.52)])
    elif icon == "belt":
        rect = pygame.Rect(int(cx - r * 0.96), int(cy - r * 0.36), int(r * 1.92), int(r * 0.72))
        pygame.draw.rect(surf, (16, 16, 16), rect.inflate(6, 6), border_radius=6)
        pygame.draw.rect(surf, col, rect, border_radius=5)
        buckle = pygame.Rect(int(cx - r * 0.38), int(cy - r * 0.46), int(r * 0.76), int(r * 0.92))
        pygame.draw.rect(surf, bright, buckle, max(3, r // 7), border_radius=4)
        pygame.draw.line(surf, bright, (int(cx - r * 0.18), cy), (int(cx + r * 0.18), cy), max(2, r // 8))
    elif icon == "spider":
        for side in (-1, 1):
            for li in (-1, 0, 1):
                pygame.draw.line(surf, (16, 16, 16), (cx, cy), (int(cx + side * r * 0.96), int(cy + li * r * 0.46 - r * 0.18)), max(3, r // 6))
                pygame.draw.line(surf, bright, (cx, cy), (int(cx + side * r * 0.88), int(cy + li * r * 0.42 - r * 0.16)), max(2, r // 9))
        draw_aa_circle(surf, (16, 16, 16), cx, cy - r * 0.14, r * 0.52)
        draw_aa_circle(surf, col, cx, cy - r * 0.14, r * 0.40)
        draw_aa_circle(surf, bright, cx - r * 0.18, cy + r * 0.18, r * 0.12)
        draw_aa_circle(surf, bright, cx + r * 0.18, cy + r * 0.18, r * 0.12)
    elif icon == "lens":
        draw_aa_circle(surf, (16, 16, 16), cx - r * 0.34, cy, r * 0.54)
        draw_aa_circle(surf, (16, 16, 16), cx + r * 0.34, cy, r * 0.54)
        draw_aa_circle(surf, col, cx - r * 0.34, cy, r * 0.42)
        draw_aa_circle(surf, col, cx + r * 0.34, cy, r * 0.42)
        draw_aa_ring(surf, bright, cx - r * 0.34, cy, r * 0.44, max(2, r // 8))
        draw_aa_ring(surf, bright, cx + r * 0.34, cy, r * 0.44, max(2, r // 8))
        pygame.draw.line(surf, bright, (int(cx - r * 0.12), cy), (int(cx + r * 0.12), cy), max(2, r // 8))
    elif icon == "mirror":
        draw_aa_ellipse(surf, (16, 16, 16), cx, cy - r * 0.12, r * 0.72, r * 0.90)
        draw_aa_ellipse(surf, bright, cx, cy - r * 0.12, r * 0.58, r * 0.76)
        draw_aa_ellipse(surf, (44, 44, 44), cx, cy - r * 0.12, r * 0.46, r * 0.62)
        pygame.draw.line(surf, bright, (int(cx - r * 0.24), int(cy - r * 0.42)), (int(cx + r * 0.18), int(cy + r * 0.10)), max(2, r // 8))
        pygame.draw.line(surf, col, (cx, int(cy + r * 0.62)), (cx, int(cy + r * 0.98)), max(4, r // 5))
    elif icon == "cloak":
        pts = [(cx, cy - r * 0.92), (cx + r * 0.86, cy + r * 0.78), (cx + r * 0.28, cy + r * 0.56), (cx, cy + r * 0.88), (cx - r * 0.28, cy + r * 0.56), (cx - r * 0.86, cy + r * 0.78)]
        draw_aa_poly(surf, (16, 16, 16), pts)
        draw_aa_poly(surf, col, [(cx + (px - cx) * 0.82, cy + (py - cy) * 0.82) for px, py in pts])
        draw_aa_circle(surf, bright, cx, cy - r * 0.54, r * 0.22)
    elif icon == "scroll":
        rect = pygame.Rect(int(cx - r * 0.72), int(cy - r * 0.84), int(r * 1.44), int(r * 1.68))
        pygame.draw.rect(surf, (16, 16, 16), rect.inflate(6, 6), border_radius=6)
        pygame.draw.rect(surf, col, rect, border_radius=5)
        pygame.draw.rect(surf, bright, (int(cx - r * 0.86), int(cy - r * 0.92), int(r * 1.72), int(r * 0.30)), border_radius=4)
        pygame.draw.rect(surf, bright, (int(cx - r * 0.86), int(cy + r * 0.62), int(r * 1.72), int(r * 0.30)), border_radius=4)
        for ly in (-0.28, 0.0, 0.28):
            pygame.draw.line(surf, dark, (int(cx - r * 0.42), int(cy + r * ly)), (int(cx + r * 0.42), int(cy + r * ly)), max(2, r // 9))
    elif icon == "orbit":
        draw_aa_ring(surf, (16, 16, 16), cx, cy, r * 0.88, max(3, r // 6))
        draw_aa_ring(surf, col, cx, cy, r * 0.84, max(2, r // 8))
        draw_aa_circle(surf, bright, cx, cy, r * 0.34)
        draw_aa_circle(surf, bright, cx + r * 0.78, cy - r * 0.24, r * 0.22)
        draw_aa_circle(surf, col, cx - r * 0.74, cy + r * 0.32, r * 0.20)
    elif icon == "wing":
        for side in (-1, 1):
            pts = [(cx, cy + r * 0.16), (cx + side * r * 0.98, cy - r * 0.76), (cx + side * r * 0.84, cy + r * 0.16), (cx + side * r * 0.34, cy + r * 0.66)]
            draw_aa_poly(surf, (16, 16, 16), pts)
            draw_aa_poly(surf, col, [(cx + (px - cx) * 0.82, cy + (py - cy) * 0.82) for px, py in pts])
    elif icon == "gem":
        pts = [(cx, cy - r * 0.96), (cx + r * 0.80, cy - r * 0.18), (cx, cy + r * 0.96), (cx - r * 0.80, cy - r * 0.18)]
        draw_aa_poly(surf, (16, 16, 16), pts)
        draw_aa_poly(surf, col, [(cx + (px - cx) * 0.84, cy + (py - cy) * 0.84) for px, py in pts])
        draw_aa_poly(surf, bright, [(cx, cy - r * 0.68), (cx + r * 0.38, cy - r * 0.16), (cx, cy + r * 0.44), (cx - r * 0.38, cy - r * 0.16)])
    else:
        draw_aa_circle(surf, (18, 18, 18), cx, cy, r * 0.92)
        draw_aa_circle(surf, col, cx, cy, r * 0.76)
        draw_aa_circle(surf, bright, cx - r * 0.24, cy - r * 0.24, r * 0.24)

    # Unique deterministic monochrome signature per item ID so every artifact has a distinct icon
    iid = str(item.get("id", icon))
    digest = hashlib.md5(iid.encode("utf-8")).digest()
    sig_style = digest[0] % 6
    rot_base = (digest[1] / 255.0) * math.pi * 2.0
    pip_count = 1 + (digest[2] % 4)
    accent_lum = 248 if lum < 165 else 24
    accent_col = (accent_lum, accent_lum, accent_lum)
    edge_col = (242, 242, 242) if accent_lum < 100 else (24, 24, 24)
    tick_w = max(2, r // 11)
    if sig_style == 0:
        for pi in range(pip_count):
            ang = rot_base + pi * (math.pi * 2.0 / pip_count)
            px = cx + math.cos(ang) * (r * 0.98)
            py = cy + math.sin(ang) * (r * 0.98)
            draw_aa_circle(surf, edge_col, px, py, max(2, r * 0.13))
            draw_aa_circle(surf, accent_col, px, py, max(1.5, r * 0.08))
    elif sig_style == 1:
        for pi in range(pip_count + 1):
            ang = rot_base + pi * (math.pi * 2.0 / (pip_count + 1))
            p1 = (cx + math.cos(ang) * (r * 0.84), cy + math.sin(ang) * (r * 0.84))
            p2 = (cx + math.cos(ang) * (r * 1.14), cy + math.sin(ang) * (r * 1.14))
            pygame.draw.line(surf, accent_col, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), tick_w)
    elif sig_style == 2:
        rx = cx + math.cos(rot_base) * (r * 0.72)
        ry = cy + math.sin(rot_base) * (r * 0.72)
        ds = max(3.0, r * 0.22)
        draw_aa_poly(surf, edge_col, [(rx, ry - ds), (rx + ds, ry), (rx, ry + ds), (rx - ds, ry)])
        draw_aa_poly(surf, accent_col, [(rx, ry - ds * 0.62), (rx + ds * 0.62, ry), (rx, ry + ds * 0.62), (rx - ds * 0.62, ry)])
    elif sig_style == 3:
        draw_aa_ring(surf, accent_col, cx, cy, r * (0.94 + (digest[3] % 3) * 0.07), tick_w)
        px = cx + math.cos(rot_base) * (r * 0.98)
        py = cy + math.sin(rot_base) * (r * 0.98)
        draw_aa_circle(surf, edge_col, px, py, max(2, r * 0.14))
    elif sig_style == 4:
        ang = rot_base
        dx = math.cos(ang) * (r * 0.56)
        dy = math.sin(ang) * (r * 0.56)
        pygame.draw.line(surf, edge_col, (int(cx - dx), int(cy - dy)), (int(cx + dx), int(cy + dy)), tick_w + 1)
        pygame.draw.line(surf, accent_col, (int(cx - dx * 0.78), int(cy - dy * 0.78)), (int(cx + dx * 0.78), int(cy + dy * 0.78)), max(1, tick_w - 1))
    else:
        for pi in range(pip_count):
            ang = rot_base + pi * 0.55
            px = cx + math.cos(ang) * (r * 0.92)
            py = cy + math.sin(ang) * (r * 0.92)
            draw_aa_circle(surf, accent_col, px, py, max(2, r * 0.10))


def draw_item_icon(screen, item, x, y, size=24):
    key = (item["id"], int(size))
    surf = ICON_CACHE.get(key)
    if surf is None:
        _prune_cache(ICON_CACHE, 512)
        surf = render_4x_smooth(
            int(size),
            int(size),
            lambda hi, hw, hh: _draw_icon_vector(hi, item, hw),
            blur_radius=0.25,
        )
        ICON_CACHE[key] = surf
    screen.blit(surf, (int(round(x - size * 0.5)), int(round(y - size * 0.5))))


class ItemPedestal:
    def __init__(self, x, y, item_data, price=0, devil_cost=0):
        self.x = float(x)
        self.y = float(y)
        self.item = item_data
        self.price = int(price)
        self.devil_cost = int(devil_cost)
        self.alive = True
        self.bob = random.uniform(0.0, 6.28)
        self.motes = [
            {
                "ang": random.uniform(0.0, 6.28),
                "h": random.uniform(0.0, 24.0),
                "spd": random.uniform(0.22, 0.45),
                "r": random.choice([1, 2]),
            }
            for _ in range(5)
        ]

    def update(self, dt=1.0):
        self.bob += 0.055 * dt
        for mt in self.motes:
            mt["h"] += mt["spd"] * dt
            mt["ang"] += 0.04 * dt
            if mt["h"] > 28.0:
                mt["h"] = 0.0

    def draw(self, screen, font=None, discount=False, highlighted=False):
        if not self.alive:
            return
        sh = get_shadow_surf(46, 16, 134)
        screen.blit(sh, (int(round(self.x - sh.get_width() * 0.5)), int(round(self.y + 13 - sh.get_height() * 0.5))))

        wave = ease_in_out(0.5 + 0.5 * math.sin(self.bob))
        q_wave = round(wave * 4.0) / 4.0
        lift = -10.0 - wave * 4.5
        q_pulse = 0.72 + 0.28 * q_wave

        gl = get_glow_surf(int(34 + 9 * q_pulse), 244, int(62 + 26 * q_pulse))
        screen.blit(gl, (int(round(self.x - gl.get_width() * 0.5)), int(round(self.y + lift - gl.get_height() * 0.5))))

        # Sculpted round/octagonal beveled stone pedestal (zero square corners)
        draw_aa_ellipse(screen, (16, 16, 16), self.x, self.y + 11, 21, 9.2)
        draw_aa_ellipse(screen, (56, 56, 56), self.x, self.y + 10, 19.5, 8.0)
        pygame.draw.rect(screen, (42, 42, 42), (int(self.x - 16), int(self.y + 3), 32, 8))
        pygame.draw.line(screen, (72, 72, 72), (int(self.x - 8), int(self.y + 4)), (int(self.x - 8), int(self.y + 10)), 2)
        pygame.draw.line(screen, (28, 28, 28), (int(self.x + 8), int(self.y + 4)), (int(self.x + 8), int(self.y + 10)), 2)
        pygame.draw.line(screen, (18, 18, 18), (int(self.x - 16), int(self.y + 3)), (int(self.x - 16), int(self.y + 10)), 1)
        pygame.draw.line(screen, (18, 18, 18), (int(self.x + 16), int(self.y + 3)), (int(self.x + 16), int(self.y + 10)), 1)
        draw_aa_ellipse(screen, (18, 18, 18), self.x, self.y + 3, 18.5, 7.6)
        draw_aa_ellipse(screen, (104, 104, 104), self.x, self.y + 3, 17, 6.4)
        draw_aa_ellipse(screen, (156, 156, 156), self.x, self.y + 2, 12.8, 4.4)
        if highlighted:
            draw_aa_ring(screen, (242, 242, 242), self.x, self.y + 8, 25, 1)

        item_sh = get_shadow_surf(int(22 - q_wave * 3), int(8 - q_wave * 1.5), int(116 - q_wave * 20))
        screen.blit(item_sh, (int(round(self.x - item_sh.get_width() * 0.5)), int(round(self.y + 2 - item_sh.get_height() * 0.5))))

        for mt in self.motes:
            mx = self.x + math.cos(mt["ang"]) * 16.0
            my = self.y - mt["h"] - 2.0
            ma = int(200 * (1.0 - mt["h"] / 28.0))
            ps = get_particle_surf(mt["r"], 248, ma)
            screen.blit(ps, (int(round(mx - ps.get_width() * 0.5)), int(round(my - ps.get_height() * 0.5))))

        draw_item_icon(screen, self.item, self.x, self.y + lift, size=34)

        if font is not None:
            if self.devil_cost > 0:
                txt = render_text_cached(font, f"-{self.devil_cost}♥", (236, 236, 236))
                screen.blit(txt, (int(self.x - txt.get_width() // 2), int(self.y + 24)))
            elif self.price > 0:
                cost = max(1, self.price // 2) if discount else self.price
                txt = render_text_cached(font, f"{cost}¢", (238, 238, 238))
                screen.blit(txt, (int(self.x - txt.get_width() // 2), int(self.y + 24)))


class Pickup:
    def __init__(self, x, y, kind="coin", price=0):
        self.x = float(x)
        self.y = float(y)
        self.kind = kind
        self.price = int(price)
        self.radius = 12.0
        self.alive = True
        self.age = random.uniform(0.0, 6.28)
        self.vx = 0.0
        self.vy = 0.0

    def update(self, dt=1.0):
        self.age += 0.075 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= 0.85 ** dt
        self.vy *= 0.85 ** dt

    def draw(self, screen, font=None, discount=False):
        if not self.alive:
            return
        wave = ease_in_out(0.5 + 0.5 * math.sin(self.age))
        bob = (wave - 0.5) * 3.0
        sh_alpha = int(118 - wave * 20)
        sh = get_shadow_surf(int(22 - wave * 2), int(8 - wave), sh_alpha)
        screen.blit(sh, (int(round(self.x - sh.get_width() * 0.5)), int(round(self.y + 8 - sh.get_height() * 0.5))))
        py = self.y + bob

        if self.kind not in ("heart", "half_heart", "soul_heart", "black_heart", "coin", "nickel", "dime", "bomb", "key"):
            gl = get_glow_surf(17, 242, 58)
            screen.blit(gl, (int(round(self.x - gl.get_width() * 0.5)), int(round(py - gl.get_height() * 0.5))))
        spr = _get_pickup_sprite(self.kind)
        screen.blit(spr, (int(round(self.x - spr.get_width() * 0.5)), int(round(py - spr.get_height() * 0.5))))

        if font is not None and self.price > 0:
            cost = max(1, self.price // 2) if discount else self.price
            txt = render_text_cached(font, f"{cost}¢", (238, 238, 238))
            screen.blit(txt, (int(self.x - txt.get_width() // 2), int(self.y + 14)))
