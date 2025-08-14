"""
Python implementation of the mini text adventure / combat game.

The script is designed to run both in a normal Python interpreter and inside a
web page through Pyodide.  To help future contributors understand the flow,
the main sections below are heavily commented.
"""

import json        # JSON 파일을 읽고 쓰기 위한 표준 라이브러리
import random      # 난수 생성을 위해 사용
import string      # 문자열 관련 편의 기능 제공
import time        # 지연 효과 등을 주기 위한 타이머
from pathlib import Path  # 경로 처리를 객체지향적으로 다룸

# Pyodide 환경에서는 브라우저와 상호작용하기 위한 모듈을 불러온다.
# 일반 파이썬 환경에서는 import가 실패하므로 예외 처리 후 None으로 둔다.
try:
    import js  # 브라우저의 window 객체에 접근
    from browser import write  # HTML에 직접 출력하는 함수
except Exception:  # Fallback when running outside Pyodide
    js = None
    write = None


def print(*args, sep=" ", end="\n", **kwargs):
    """브라우저 환경 여부에 따라 적절한 출력 방식을 선택하는 print 함수."""
    text = sep.join(map(str, args)) + end
    if write:
        write(text)
    else:  # pragma: no cover - fallback for local execution
        __builtins__.print(text, end="")


def input(prompt: str = "") -> str:
    """브라우저에서 입력을 받거나, 일반 환경에서는 표준 입력을 사용한다."""
    if js and hasattr(js, "prompt"):
        return js.prompt(prompt) or ""
    return __builtins__.input(prompt)

# 현재 스크립트가 위치한 경로. Pyodide와 로컬 환경 모두에서 안전하게 계산된다.
BASE_PATH = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()


def _load_json(filename: str):
    """지정된 JSON 파일을 읽어 파이썬 객체로 반환한다."""
    path = BASE_PATH / filename
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:  # pragma: no cover - runtime safety
        raise FileNotFoundError(f"Required file not found: {path}") from exc


def _save_json(filename: str, data):
    """파이썬 객체를 JSON 파일로 저장한다."""
    path = BASE_PATH / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# 아래의 JSON 파일들은 게임에서 사용되는 기본 데이터와 문구를 정의한다.
CONFIG = _load_json("config.json")        # 각종 위치/전투 메시지 등 설정
ACTIONS = _load_json("actions.json")      # 플레이어 행동 목록
TUTORIAL = _load_json("tutorial.json")    # 튜토리얼 진행 스크립트
PLAYER_TEMPLATE = _load_json("player.json")  # 새 플레이어의 기본 상태

def generate_code_name():
    """랜덤한 코드네임을 생성한다. 예: AB-12"""
    letters = random.choice(string.ascii_uppercase) + random.choice(string.ascii_uppercase)
    numbers = f"{random.randint(0,99):02d}"
    return f"{letters}-{numbers}"

class Item:
    """플레이어가 소지할 수 있는 장비/아이템을 표현한다."""

    def __init__(self, name, attack_bonus=0, defense_bonus=0):
        self.name = name
        self.attack_bonus = attack_bonus
        self.defense_bonus = defense_bonus

class Player:
    """게임의 주인공을 나타내는 클래스."""

    def __init__(self, state):
        # 저장된 상태에서 캐릭터를 불러오거나 새로 생성한다.
        self.name = state.get("name") or generate_code_name()
        stats = state.get("stats", {})
        self.hp = stats.get("hp", 100)
        self.base_attack = stats.get("base_attack", 10)
        self.defense = stats.get("defense", 5)
        # 인벤토리의 각 아이템을 Item 객체로 변환
        self.inventory = [
            Item(i["name"], i.get("attack_bonus", 0), i.get("defense_bonus", 0))
            for i in state.get("inventory", [])
        ]
        # 장착 중인 무기 정보
        weapon_name = state.get("equipment", {}).get("weapon")
        self.weapon = next(
            (item for item in self.inventory if item.name == weapon_name), None
        )
        # 진행 중/완료한 미션 정보
        self.missions = state.get("missions", {})

    @property
    def attack(self):
        """장착 무기의 공격력을 합산한 실제 공격력."""
        bonus = self.weapon.attack_bonus if self.weapon else 0
        return self.base_attack + bonus

    def to_dict(self):
        """현재 플레이어 상태를 저장 가능한 dict로 변환한다."""
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
    """전투에서 상대할 적 캐릭터."""

    def __init__(self, name, hp, attack, defense, description=""):
        self.name = name
        self.hp = hp
        self.attack = attack
        self.defense = defense
        self.description = description


def save_game(player, filename: str = "save.json"):
    """플레이어 상태를 JSON 파일로 저장."""
    _save_json(filename, player.to_dict())


def check_conditions(player, conditions):
    """행동/카테고리 표시 조건을 검사한다."""
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
    """플레이어 상태에 맞는 행동 목록을 만들어 반환한다."""
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
    """위치 설명과 NPC/행동 목록을 화면에 출력한다."""
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
    """무기를 장착하거나 변경하는 메뉴."""
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
    """플레이어와 적 사이의 턴제 전투 루프."""
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
    """임무 수행 여부를 묻는 로비 화면."""
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
    """게임 시작 시 표시되는 메인 메뉴."""
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
    """튜토리얼 전투 및 장비 사용을 안내하는 섹션."""
    tut = TUTORIAL
    stick_cfg = tut.get("stick_item", {})
    stick = Item(
        stick_cfg.get("name", "막대"),
        attack_bonus=stick_cfg.get("attack_bonus", 0),
        defense_bonus=stick_cfg.get("defense_bonus", 0),
    )

    steps = tut.get("steps", [])

    # Step 0: 막대를 줍게 하는 단계
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

    # Step 1: 교관과 대화하거나 장비 메뉴로 이동
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

    # Step 2: 전투를 진행하거나 다시 메뉴로 이동
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

    # Step 3: 튜토리얼 종료
    if player.hp > 0 and len(steps) > 3:
        step = steps[3]
        if step.get("line"):
            print(step["line"])
        if step.get("demo"):
            mission_office(demo=True)
    save_game(player)

def main():
    """게임의 진입점. 전체 흐름을 제어한다."""
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
