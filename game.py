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


# Load configurable text and lists
CONFIG = _load_json("config.json")

# Load combat actions
ACTIONS = _load_json("actions.json")

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
    def __init__(self, name):
        self.name = name
        self.hp = 100
        self.base_attack = 10
        self.defense = 5
        self.inventory = [Item("훈련용 블레이드", attack_bonus=5)]
        self.weapon = None

    @property
    def attack(self):
        bonus = self.weapon.attack_bonus if self.weapon else 0
        return self.base_attack + bonus

class Enemy:
    def __init__(self, name, hp, attack, defense, description=""):
        self.name = name
        self.hp = hp
        self.attack = attack
        self.defense = defense
        self.description = description


def show_location(key: str):
    loc = CONFIG["locations"][key]
    print(f"\n{loc['description']}")
    npcs = loc.get("npcs", [])
    if npcs:
        print("NPC 목록:")
        for npc in npcs:
            print(f" - {npc}")
    else:
        print("NPC 없음")
    print("가능한 행동:")
    for idx, action in enumerate(loc.get("actions", []), 1):
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
        print("가능한 행동:")
        for i, act in enumerate(ACTIONS, 1):
            print(f"{i}. {act['name']}")
        action_choice = input(cfg["prompt_main"]).strip()
        if not action_choice.isdigit() or not (1 <= int(action_choice) <= len(ACTIONS)):
            print(cfg["player_invalid"])
            continue
        category = ACTIONS[int(action_choice) - 1]
        subactions = category.get("options", [])
        move_name = category["name"]
        if subactions:
            for i, move in enumerate(subactions, 1):
                print(f"{i}. {move}")
            move_choice = input(cfg["prompt_sub"]).strip()
            if not move_choice.isdigit() or not (1 <= int(move_choice) <= len(subactions)):
                print(cfg["player_invalid"])
                continue
            move_name = subactions[int(move_choice) - 1]

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

def training_session(player):
    loc = CONFIG["locations"]["training_ground"]
    show_location("training_ground")
    print(loc["lines"][0])
    equip_menu(player)
    print(loc["lines"][1])
    dummy = Enemy(
        CONFIG["misc"]["training_dummy_name"],
        30,
        5,
        2,
        CONFIG["misc"]["training_dummy_desc"],
    )
    turn_based_combat(player, dummy)
    if player.hp > 0:
        print(loc["lines"][2])
        mission_office(demo=True)

def main():
    player_name = generate_code_name()
    player = Player(player_name)
    misc = CONFIG["misc"]
    print(misc["code_name"].format(name=player.name))
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
        else:
            print(loc["decline_text"])
            time.sleep(1)

if __name__ == "__main__":
    main()
