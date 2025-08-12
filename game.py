import random, time, js, string
from browser import write

def print(*args, **kwargs):
    write(" ".join(map(str, args)) + "\\n")

def input(prompt=""):
    return js.prompt(prompt) or ""

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
    def __init__(self, name, hp, attack, defense):
        self.name = name
        self.hp = hp
        self.attack = attack
        self.defense = defense

def equip_menu(player):
    print("\n[아이템 장착] 인벤토리:")
    for idx, item in enumerate(player.inventory, 1):
        print(f"{idx}. {item.name} (공격 +{item.attack_bonus}, 방어 +{item.defense_bonus})")
    choice = input("장착할 아이템 번호를 선택하세요: ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(player.inventory):
        item = player.inventory[int(choice) - 1]
        player.weapon = item
        print(f"{item.name}을(를) 장착했습니다.")
    else:
        print("장착을 취소했습니다.")

def turn_based_combat(player, enemy):
    print(f"\n[전투 개시] {player.name} vs {enemy.name}")
    while player.hp > 0 and enemy.hp > 0:
        print(f"\n{player.name} HP: {player.hp}, {enemy.name} HP: {enemy.hp}")
        action = input("행동을 선택하세요 (1: 공격, 2: 방어): ").strip()
        if action == "1":
            damage = max(player.attack - enemy.defense, 0)
            enemy.hp -= damage
            print(f"{player.name}의 공격! {enemy.name}에게 {damage}만큼의 피해를 입혔습니다.")
        elif action == "2":
            print(f"{player.name}는 방어 태세를 취했습니다.")
            player.defense += 5
        else:
            print("잘못된 입력입니다.")

        if enemy.hp <= 0:
            print(f"{enemy.name}를 처치했습니다!")
            break

        print(f"{enemy.name}의 차례!")
        enemy_action = random.choice(["attack", "attack", "attack", "defense"])
        if enemy_action == "attack":
            damage = max(enemy.attack - player.defense, 0)
            player.hp -= damage
            print(f"{enemy.name}의 공격! {player.name}이 {damage}만큼의 피해를 입었습니다.")
        else:
            print(f"{enemy.name}는 방어 태세를 취했습니다.")
            enemy.defense += 3

        if player.hp <= 0:
            print(f"{player.name}는 쓰러졌습니다...")
            break

    player.defense = 5

def mission_office(demo=False):
    print("\n[의뢰 사무소] 의뢰가 등록되어 있습니다.")
    time.sleep(0.5)
    print("[단말기 알림] 새 임무가 도착했습니다.")
    time.sleep(0.5)
    print("내용: 거대 기업의 비밀 연구소 침입.")
    if demo:
        print("(연습) 임무 수락 절차를 연습합니다.")
    action = input("임무를 수락하시겠습니까? (y/n): ").strip().lower()
    if demo:
        print("연습 완료.")
        return False
    return action == "y"

def training_session(player):
    print("\n[훈련장] 교관이 다가옵니다.")
    print("NPC: '기본 장비 교육을 시작한다.'")
    equip_menu(player)
    print("NPC: '이제 공격 훈련이다.'")
    dummy = Enemy("훈련용 드론", 30, 5, 2)
    turn_based_combat(player, dummy)
    if player.hp > 0:
        print("NPC: '마지막으로 의뢰를 받는 방법을 익혀라.'")
        mission_office(demo=True)

def main():
    player_name = generate_code_name()
    player = Player(player_name)
    print(f"\n지정된 코드명: {player.name}")
    print(f"{player.name}가(이) 소모형 인공 용병으로서 깨어났습니다.")
    training_session(player)
    if player.hp <= 0:
        print("\n[게임 종료] 당신은 더 이상 임무를 수행할 수 없습니다.")
        return
    print("회사로부터 의뢰를 기다립니다...")

    while player.hp > 0:
        if mission_office():
            print("\n임무를 수락했습니다. 현장으로 이동합니다...")
            enemy = Enemy("경비 드론", 50, 10, 3)
            turn_based_combat(player, enemy)
            if player.hp <= 0:
                print("\n[게임 종료] 당신은 더 이상 임무를 수행할 수 없습니다.")
            else:
                print("\n임무 완료! 보상을 받았습니다.")
                print("의뢰 사무소로 돌아갑니다.\n")
        else:
            print("\n임무를 거부했습니다. 다른 의뢰를 기다립니다.")
            time.sleep(1)

if __name__ == "__main__":
    main()