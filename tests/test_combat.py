from services.combat import Combatant, simulate


def _mk(name, hp=1000, atk=100, df=50, spd=30, crit=10, mp=100, skills=None, **mods):
    return Combatant(name=name, hp=hp, mp=mp, atk=atk, df=df, spd=spd,
                     crit=crit, skills=skills or ["普攻"], **mods)


def test_deterministic_same_seed():
    r1 = simulate(_mk("甲"), _mk("乙", spd=20), seed=42)
    r2 = simulate(_mk("甲"), _mk("乙", spd=20), seed=42)
    assert r1["log"] == r2["log"]
    assert r1["winner"].name == r2["winner"].name
    assert r1["rounds"] == r2["rounds"]


def test_stronger_wins():
    strong = _mk("强", hp=3000, atk=300, df=120)
    weak = _mk("弱", hp=500, atk=40, df=20)
    assert simulate(strong, weak, seed=1)["winner"].name == "强"


def test_winner_is_input_object():
    a, b = _mk("甲"), _mk("乙")
    assert simulate(a, b, seed=7)["winner"] in (a, b)


def test_rounds_capped_and_resolved():
    a = _mk("甲", hp=100000, atk=1, df=10000)
    b = _mk("乙", hp=100000, atk=1, df=10000, spd=10)
    r = simulate(a, b, seed=3)
    assert r["rounds"] <= 30
    assert r["winner"] in (a, b)


def test_skill_used_when_affordable():
    # 快剑斩 系数高，强者带技能应能赢且日志含技能名
    a = _mk("剑修", atk=200, skills=["快剑斩"])
    b = _mk("木桩", hp=400, atk=10, df=10)
    r = simulate(a, b, seed=5)
    assert any("快剑斩" in line for line in r["log"])


def test_combat_affixes_lifesteal_reflect_and_initiative():
    slow = _mk("慢剑", hp=1000, atk=240, spd=1, lifesteal_pct=0.5, initiative=100)
    thorn = _mk("反甲", hp=1000, atk=10, spd=80, reflect_pct=0.2)

    r = simulate(slow, thorn, seed=11)

    assert "慢剑" in r["log"][1]
    assert any("汲取气血" in line for line in r["log"])
    assert any("反震" in line for line in r["log"])
