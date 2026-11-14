"""Monstro e humano: paridade com as respostas douradas do Godot."""

import json
from pathlib import Path

import pytest

from monstervale_ia.dados_jogo import carregar_catalogo
from monstervale_ia.godot import roundi
from monstervale_ia.humano import Humano
from monstervale_ia.monstro import Monstro
from monstervale_ia.rota import Rota
from monstervale_ia.vetor import vetor

REF = json.loads((Path(__file__).parent / "referencias" / "entidades.json").read_text())
CATALOGO = carregar_catalogo()
PASSO = 1.0 / 60.0


# --- Arredondamento ---------------------------------------------------------------

@pytest.mark.parametrize(
    "x, esperado",
    [(2.5, 3), (3.5, 4), (-2.5, -3), (4.5, 5), (0.49999999999999994, 0), (7.4999, 7), (0.0, 0)],
)
def test_roundi_arredonda_meio_para_longe_do_zero(x, esperado):
    assert roundi(x) == esperado


def test_round_do_python_seria_diferente():
    # A armadilha que roundi evita: round() do Python vai para o par.
    assert round(2.5) == 2 and roundi(2.5) == 3


# --- Monstro ------------------------------------------------------------------------

@pytest.mark.parametrize("tipo", list(REF["damage"]))
def test_dano_com_resistencia_igual_ao_godot(tipo):
    monstro = Monstro(tipo, CATALOGO["monsters"][tipo], Rota([(0, 0), (100, 0)]))
    for tipo_dano, esperado in REF["damage"][tipo].items():
        obtido = [monstro.dano_recebido(q, tipo_dano) for q in range(1, 81)]
        assert obtido == esperado, tipo_dano


def test_lentidao_mais_fraca_nao_substitui_mais_forte():
    monstro = Monstro("goblin", CATALOGO["monsters"]["goblin"], Rota([(0, 0), (100, 0)]))
    monstro.aplicar_lentidao(0.4, 2.0)
    monstro.aplicar_lentidao(0.7, 5.0)
    assert (monstro.fator_lentidao, monstro.tempo_lentidao) == (0.4, 2.0)
    assert monstro.velocidade_atual() == 24 * 0.4


def test_rei_slime_e_imune_a_raiz_atordoamento_e_bloqueio():
    rei = Monstro("slime_king", CATALOGO["monsters"]["slime_king"], Rota([(0, 0), (100, 0)]))
    rei.aplicar_raiz(2.0)
    rei.aplicar_atordoamento(2.0)
    assert not rei.esta_preso() and not rei.esta_atordoado()
    assert not rei.pode_ser_bloqueado()


def test_efeitos_acabam_com_o_tempo():
    monstro = Monstro("goblin", CATALOGO["monsters"]["goblin"], Rota([(0, 0), (100, 0)]))
    monstro.aplicar_atordoamento(0.5)
    assert monstro.velocidade_atual() == 0.0
    for _ in range(31):
        monstro.atualizar_efeitos(PASSO)
    assert monstro.velocidade_atual() == 24.0


# --- Humano -------------------------------------------------------------------------

@pytest.mark.parametrize("tipo", list(REF["units"]))
def test_niveis_custos_e_reembolso_iguais_ao_godot(tipo):
    humano = Humano(tipo, CATALOGO["units"][tipo], (3, 4), vetor(112, 144))
    for esperado in REF["units"][tipo]:
        obtido = {
            "level": humano.nivel, "spent": humano.gasto, "refund": humano.reembolso(),
            "hp": humano.vida, "upgrade_cost": humano.custo_melhoria(),
            "block_room": humano.tem_espaco_para_bloquear(),
        }
        assert obtido == esperado
        if not humano.pode_melhorar():
            break
        humano.vida -= 7
        humano.subir_nivel()


@pytest.mark.parametrize("chave", list(REF["regen"]))
def test_recuperacao_quadro_a_quadro_igual_ao_godot(chave):
    tipo, nivel = chave.rsplit("_", 1)
    humano = Humano(tipo, CATALOGO["units"][tipo], (0, 0), vetor(0, 0))
    while humano.nivel < int(nivel):
        humano.subir_nivel()
    humano.vida = 10
    obtido = []
    for _ in range(900):
        humano.recuperar(PASSO)
        obtido.append(humano.vida)
    assert obtido == REF["regen"][chave]


def test_prioridade_da_a_volta():
    humano = Humano("archer", CATALOGO["units"]["archer"], (0, 0), vetor(0, 0))
    vistas = []
    for _ in range(5):
        vistas.append(humano.prioridade)
        humano.trocar_prioridade()
    assert vistas == ["first", "last", "strongest", "closest", "first"]
