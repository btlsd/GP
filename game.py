import json
import random
import string
import time
from pathlib import Path

try:
    import js
    from browser import write
except Exception:  # Fallback when running outside Pyodide
    js = None
    write = None


def print(*args, sep=" ", end="\n", **kwargs):
    """Custom print that works with or without the browser module."""
    text = sep.join(map(str, args)) + end
    if write:
        write(text)
    else:  # pragma: no cover - fallback for local execution
        __builtins__.print(text, end="")


def input(prompt: str = "") -> str:
    """Prompt the user, falling back to standard input if needed."""
    if js and hasattr(js, "prompt"):
        return js.prompt(prompt) or ""
    return __builtins__.input(prompt)

BASE_PATH = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()


def _load_json(filename: str):
    path = BASE_PATH / filename
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:  # pragma: no cover - runtime safety
        raise FileNotFoundError(f"Required file not found: {path}") from exc


def _save_json(filename: str, data):
    path = BASE_PATH / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# Load configurable text and lists
CONFIG = _load_json("config.json")

# Load combat actions
ACTIONS = _load_json("actions.json")

# Load tutorial script
TUTORIAL = _load_json("tutorial.json")

# Load starting player template
PLAYER_TEMPLATE = _load_json("player.json")

def generate_code_name():
    letters = random.choice(string.ascii_uppercase) + random.choice(string.ascii_uppercase)
    numbers = f"{random.randint(0,99):02d}"
    return f"{letters}-{numbers}"

class Item:
    def __init__(self, name, attack_bonus=0, defense_bonus=0):
        self.name = name
        self.attack_bonus = attack_bonus
        self.defense_bonus = defense_bonus

class Player:
    def __init__(self, state):
        self.name = state.get("name") or generate_code_name()
        stats = state.get("stats", {})
        self.hp = stats.get("hp", 100)
        self.base_attack = stats.get("base_attack", 10)
        self.defense = stats.get("defense", 5)
        self.inventory = [
            Item(i["name"], i.get("attack_bonus", 0), i.get("defense_bonus", 0))
            for i in state.get("inventory", [])
        ]
        weapon_name = state.get("equipment", {}).get("weapon")
        self.weapon = next(
            (item for item in self.inventory if item.name == weapon_name), None
        )
        self.missions = state.get("missions", {})

    @property
    def attack(self):
        bonus = self.weapon.attack_bonus if self.weapon else 0
        return self.base_attack + bonus

    def to_dict(self):
        return {
            "name": self.name,
            "stats": {
                "hp": self.hp,
                "base_attack": self.base_attack,
                "defense": self.defense,
            },
            "inventory": [
                {
                    "name": i.name,
                    "attack_bonus": i.attack_bonus,
                    "defense_bonus": i.defense_bonus,
                }
                for i in self.inventory
            ],
            "equipment": {"weapon": self.weapon.name if self.weapon else None},
            "missions": self.missions,
        }

class Enemy:
    def __init__(self, name, hp, attack, defense, description=""):
        self.name = name
        self.hp = hp
        self.attack = attack
        self.defense = defense
        self.description = description


def save_game(player, filename: str = "save.json"):
    _save_json(filename, player.to_dict())


def check_conditions(player, conditions):
    for key, value in conditions.items():
        if key == "weapon":
            if value is True and not player.weapon:
                return False
            if isinstance(value, str):
                if not player.weapon or player.weapon.name != value:
                    return False
        elif key == "has_item":
            if not any(item.name == value for item in player.inventory):
                return False
        elif key == "mission":
            if player.missions.get("current") != value:
                return False
        else:
            return False
    return True


def get_available_actions(player):
    available = []
    for cat in ACTIONS:
        if not check_conditions(player, cat.get("conditions", {})):
            continue
        opts = []
        for opt in cat.get("options", []):
            if check_conditions(player, opt.get("conditions", {})):
                opts.append(opt)
        if opts or not cat.get("options"):
            new_cat = dict(cat)
            new_cat["options"] = opts
            available.append(new_cat)
    return available


def show_location(key: str, npcs_override=None, actions_override=None):
    loc = CONFIG["locations"][key]
    print(f"\n{loc['description']}")
    npcs = npcs_override if npcs_override is not None else loc.get("npcs", [])
    if npcs:
        print("NPC 목록:")
        for npc in npcs:
            print(f" - {npc}")
    else:
        print("NPC 없음")
    actions = actions_override if actions_override is not None else loc.get("actions", [])
    print("가능한 행동:")
    for idx, action in enumerate(actions, 1):
        print(f"{idx}. {action}")

def equip_menu(player):
    menu = CONFIG["equipment_menu"]
    print(f"\n{menu['title']}")
    for idx, item in enumerate(player.inventory, 1):
        msg = (
            f"{idx}. {item.name} "
            f"(공격 +{item.attack_bonus}, 방어 +{item.defense_bonus})"
        )
        print(msg)
    choice = input(menu["prompt"]).strip()
    if choice.isdigit() and 1 <= int(choice) <= len(player.inventory):
        item = player.inventory[int(choice) - 1]
        player.weapon = item
        print(menu["success"].format(item=item.name))
        save_game(player)
    else:
        print(menu["cancel"])

def turn_based_combat(player, enemy):
    cfg = CONFIG["combat"]
    enemy_name = enemy.name or cfg["unknown"]
    print(f"\n{cfg['start_text'].format(enemy=enemy_name)}")
    if enemy.description:
        print(cfg["appearance_text"].format(desc=enemy.description))
    while player.hp > 0 and enemy.hp > 0:
        print(f"\n{player.name} HP: {player.hp}, {enemy_name} HP: {enemy.hp}")
        available = get_available_actions(player)
        print("가능한 행동:")
        for i, act in enumerate(available, 1):
            print(f"{i}. {act['name']}")
        action_choice = input(cfg["prompt_main"]).strip()
        if not action_choice.isdigit() or not (1 <= int(action_choice) <= len(available)):
            print(cfg["player_invalid"])
            continue
        category = available[int(action_choice) - 1]
        subactions = category.get("options", [])
        move_name = category["name"]
        if subactions:
            for i, move in enumerate(subactions, 1):
                print(f"{i}. {move['name']}")
            move_choice = input(cfg["prompt_sub"]).strip()
            if not move_choice.isdigit() or not (1 <= int(move_choice) <= len(subactions)):
                print(cfg["player_invalid"])
                continue
            move = subactions[int(move_choice) - 1]
            move_name = move["name"]

        key = category["key"]
        if key == "attack":
            damage = max(player.attack - enemy.defense, 0)
            enemy.hp -= damage
            print(
                cfg["player_attack"].format(
                    player=player.name, enemy=enemy_name, dmg=damage, move=move_name
                )
            )
        elif key == "defend":
            print(cfg["player_defend"].format(player=player.name, move=move_name))
            player.defense += 5
        elif key == "skill":
            print(cfg["player_skill"].format(player=player.name, move=move_name))
        elif key == "item":
            print(cfg["player_item"].format(player=player.name, move=move_name))
        elif key == "escape":
            print(cfg["player_escape"].format(player=player.name))
            break
        else:
            print(cfg["player_invalid"])
            continue

        if enemy.hp <= 0:
            print(cfg["enemy_defeated"].format(enemy=enemy_name))
            break

        print(cfg["enemy_turn"].format(enemy=enemy_name))
        enemy_action = random.choice(["attack", "attack", "attack", "defense"])
        if enemy_action == "attack":
            damage = max(enemy.attack - player.defense, 0)
            player.hp -= damage
            print(
                cfg["enemy_attack"].format(
                    enemy=enemy_name, player=player.name, dmg=damage
                )
            )
        else:
            print(cfg["enemy_defend"].format(enemy=enemy_name))
            enemy.defense += 3

        if player.hp <= 0:
            print(cfg["player_defeated"].format(player=player.name))
            break

    player.defense = 5
    save_game(player)

def mission_office(demo: bool = False):
    loc = CONFIG["locations"]["mission_office"]
    show_location("mission_office")
    time.sleep(0.5)
    for note in loc.get("notifications", []):
        print(note)
        time.sleep(0.5)
    if demo:
        print(loc["demo_hint"])
    action = input(loc["prompt"]).strip().lower()
    if demo:
        print(CONFIG["misc"]["demo_complete"])
        return False
    return action == "y"


def start_menu():
    while True:
        print("1. 새 게임")
        print("2. 불러오기")
        choice = input("메뉴를 선택하세요: ").strip()
        if choice == "1":
            player = Player(PLAYER_TEMPLATE)
            save_game(player)
            return player, True
        if choice == "2":
            try:
                state = _load_json("save.json")
            except FileNotFoundError:
                print("세이브 파일이 없습니다.")
                continue
            player = Player(state)
            return player, False
        print(CONFIG["combat"]["player_invalid"])

def training_session(player):
    tut = TUTORIAL
    stick_cfg = tut.get("stick_item", {})
    stick = Item(
        stick_cfg.get("name", "막대기"),
        attack_bonus=stick_cfg.get("attack_bonus", 0),
        defense_bonus=stick_cfg.get("defense_bonus", 0),
    )

    steps = tut.get("steps", [])

    # Step 0: stick pickup
    step = steps[0]
    while True:
        show_location("training_ground", actions_override=step.get("actions", []))
        if step.get("line"):
            print(step["line"])
        action = input("행동을 선택하세요: ").strip()
        if action in step.get("actions", []):
            player.inventory.append(stick)
            player.weapon = stick
            print(step.get("success", "장비를 주웠습니다."))
            save_game(player)
            break
        else:
            print(CONFIG["combat"]["player_invalid"])

    # Step 1: choose instructor or menu
    step = steps[1]
    while True:
        show_location("training_ground", actions_override=step.get("actions", []))
        if step.get("info"):
            print(step["info"])
        if step.get("line"):
            print(step["line"])
        choice = input("행동을 선택하세요: ").strip()
        if choice == "교관":
            break
        elif choice == "메뉴":
            equip_menu(player)
        else:
            print(CONFIG["combat"]["player_invalid"])

    # Step 2: interaction (combat or menu)
    step = steps[2]
    while True:
        show_location("training_ground", actions_override=step.get("actions", []))
        interaction = input("상호작용을 선택하세요: ").strip()
        if interaction == "전투":
            enemy = Enemy("교관", 30, 5, 2, "훈련 교관")
            turn_based_combat(player, enemy)
            break
        elif interaction == "메뉴":
            equip_menu(player)
        else:
            print(CONFIG["combat"]["player_invalid"])

    # Step 3: conclude tutorial
    if player.hp > 0 and len(steps) > 3:
        step = steps[3]
        if step.get("line"):
            print(step["line"])
        if step.get("demo"):
            mission_office(demo=True)
    save_game(player)

def main():
    player, is_new = start_menu()
    misc = CONFIG["misc"]
    print(misc["code_name"].format(name=player.name))
    if is_new:
        print(misc["awakening"].format(name=player.name))
        training_session(player)
        if player.hp <= 0:
            print(misc["game_over"])
            return
    print(misc["waiting"])

    loc = CONFIG["locations"]["mission_office"]
    while player.hp > 0:
        if mission_office():
            print(loc["accept_text"])
            enemy = Enemy(
                misc["mission_enemy_name"],
                50,
                10,
                3,
                misc["mission_enemy_desc"],
            )
            turn_based_combat(player, enemy)
            if player.hp <= 0:
                print(misc["game_over"])
            else:
                print(misc["mission_complete"])
                player.missions["completed"] = player.missions.get("completed", 0) + 1
                save_game(player)
        else:
            print(loc["decline_text"])
            time.sleep(1)
        save_game(player)

if __name__ == "__main__":
    main()
