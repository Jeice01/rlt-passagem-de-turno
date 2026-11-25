"""Gera as telas do app de tela "RLT Passagem de Turno" em Power Apps YAML (*.pa.yaml).

As telas seguem o protótipo validado com Valério Melo (prototipo/index.html, PRD 1.3).
Fluxo de build (ver app/LEIA-ME.md):
    1. pac canvas unpack  --layout SourceCode   (casca exportada do ambiente: dados e conexões)
    2. python -E -P app/gerar_app.py <pasta Src da casca>
    3. pac canvas pack    --layout SourceCode   -> .msapp
    4. troca o .msapp na solução, pac solution pack + import
    5. abrir uma vez no Power Apps Studio, salvar e publicar (validação exigida pelo pac)

Colunas são referenciadas pelo nome técnico (rlt_...), que não muda se o rótulo mudar.
"""
import os
import sys

# ------------------------------------------------------------------ utilidades YAML
def bloco(f):
    """Toda fórmula vai como bloco literal: evita problemas de aspas e dois-pontos no YAML."""
    f = f.strip("\n")
    if not f.startswith("="):
        f = "=" + f
    linhas = f.split("\n")
    return "|-\n" + "\n".join(linhas)


FONTE, FONTE_TIT = "Font.Arial", "Font.'Open Sans Condensed'"  # PRD: Helvetica Neue/Arial no texto; Borba (condensada) nos títulos


def emitir(nome, controle, props, filhos=None, variante=None, nivel=0, chaves=None):
    if controle in COM_FONTE and "Font" not in props:
        props = {**props, "Font": FONTE}
    ind = "  " * nivel
    out = [f"{ind}- {nome}:", f"{ind}    Control: {controle}"]
    if variante:
        out.append(f"{ind}    Variant: {variante}")
    for k, v in (chaves or {}).items():  # Layout, IsLocked, MetadataKey (formulários e cartões)
        out.append(f"{ind}    {k}: {v}")
    if props:
        out.append(f"{ind}    Properties:")
        for k, v in props.items():
            b = bloco(str(v)).split("\n")
            out.append(f"{ind}      {k}: {b[0]}")
            out += [f"{ind}        {l}" for l in b[1:]]
    if filhos:
        out.append(f"{ind}    Children:")
        for f in filhos:
            out.append(f(nivel + 3) if callable(f) else f)
    return "\n".join(out)


def C(nome, controle, variante=None, filhos=None, chaves=None, **props):
    return lambda nivel: emitir(nome, controle, props, filhos, variante, nivel, chaves)


def tela(nome, props, filhos):
    out = ["Screens:", f"  {nome}:", "    Properties:"]
    for k, v in props.items():
        b = bloco(v).split("\n")
        out.append(f"      {k}: {b[0]}")
        out += [f"        {l}" for l in b[1:]]
    out.append("    Children:")
    for f in filhos:
        out.append(f(2))
    return "\n".join(out) + "\n"


LBL, BTN, RET = "Label@2.5.1", "Classic/Button@2.2.0", "Rectangle@2.3.0"
TXT, DDL, CBX = "Classic/TextInput@2.3.2", "Classic/DropDown@2.3.1", "Classic/ComboBox@2.4.0"
DTP, CHK, GAL = "Classic/DatePicker@2.6.0", "Classic/CheckBox@2.1.0", "Gallery@2.15.0"
COM_FONTE = {LBL, BTN, TXT, DDL, CBX, DTP, CHK}

# ------------------------------------------------------------------ trechos de fórmula
SEC = "[@'Seção']"
ST = "[@'Status da atividade']"
SI = "[@'Status do IOS']"
SIT = "[@'Situação do relatório']"
# Registro em aberto: atividades PENDENTE / EM ANDAMENTO; IOS que não está Concluído nem Cancelado
ABERTO = (f"If(rlt_secao = {SEC}.'IOS informados', Not(rlt_statusios = {SI}.Concluído || rlt_statusios = {SI}.Cancelado), "
          f"rlt_status = {ST}.PENDENTE || rlt_status = {ST}.'EM ANDAMENTO')")
REFRESH = ("ClearCollect(colRegs, Filter(Registros, rlt_relatorio.rlt_relatorioid = gblRel.rlt_relatorioid));\n"
           "ClearCollect(colEquipe, Filter('Equipe do plantão', rlt_relatorio.rlt_relatorioid = gblRel.rlt_relatorioid && IsBlank(rlt_retiradoem)))")
ORDEM_SEC = (f"Switch(rlt_secao, {SEC}.Eletromecânica, 1, {SEC}.Eletroeletrônica, 2, {SEC}.BHS, 3, {SEC}.Civil, 4, {SEC}.Outros, 5, "
             f"{SEC}.'Fator Q (Z9)', 6, {SEC}.'Preventiva (ZM02)', 7, 8)")
ABERTO_REL = f"!IsBlank(gblRel) && gblRel.rlt_situacao = {SIT}.Aberto"
# Só o líder edita as listas (RF-021; decisão de 25/11/2026). Avisos: todos.
LIDER = "(!IsBlank(gblUsuario) && gblUsuario.rlt_perfil = [@Perfil].Líder)"


# Nomes das opções da coluna de sistema Status neste ambiente (conferidos no Studio em 25/11/2026)
OP_ATIVO, OP_INATIVO = "'Ativo(a)'", "'Inativo(a)'"


def ativo(tabela, ativo=True):
    """Condição de item ativo (coluna de sistema Status). Itens das listas não se excluem: o líder desativa."""
    return f"statecode = 'Status ({tabela})'.{OP_ATIVO if ativo else OP_INATIVO}"


def ativos(tabela):
    return f"Filter({tabela}, {ativo(tabela)})"


def hist(campo, registro="Blank()"):
    return (f"Patch(Histórico, Defaults(Histórico), {{rlt_campo: {campo}, rlt_quando: Now(), rlt_quem: gblUsuario, "
            f"rlt_relatorio: gblRel, rlt_registro: {registro}}})")


# ------------------------------------------------------------------ moldura comum (topo + menu)
MENU = [("Relatório", "scrRelatorio", "▤"), ("Chamados", "scrChamados", "◔"), ("Histórico", "scrHistorico", "↺"),
        ("Painel geral", "scrPainel", "◈"), ("Fechar", "scrFechar", "➤")]
FQ_SEM_SAP = f"CountRows(Filter(colRegs, rlt_secao = {SEC}.'Fator Q (Z9)' && IsBlank(rlt_equipamento)))"


def iniciais(nome):
    """Duas letras para o avatar: primeira do primeiro nome e do último sobrenome."""
    return f'Upper(Left(Trim({nome}), 1) & If(CountRows(Split(Trim({nome}), " ")) > 1, Left(Last(Split(Trim({nome}), " ")).Value, 1), ""))'


# ------------------------------------------------------------------ componentes visuais do protótipo
# O retângulo do Power Apps não arredonda: cartões, etiquetas e avatares são botões desativados (que arredondam).
def cartao(nome, x, y, w, h, fill="Color.White", borda="corLinha", raio=10, espessura=1, **extra):
    r = str(raio)
    props = dict(Text='""', DisplayMode="DisplayMode.Disabled", TabIndex="-1", X=str(x), Y=str(y), Width=str(w), Height=str(h),
                 Fill=fill, DisabledFill=fill, BorderColor=borda, DisabledBorderColor=borda, BorderThickness=str(espessura),
                 RadiusTopLeft=r, RadiusTopRight=r, RadiusBottomLeft=r, RadiusBottomRight=r)
    props.update(extra)
    return C(nome, BTN, **props)


def chip(nome, texto, x, y, w, fill, cor, borda, h=24, **extra):
    """Etiqueta arredondada (status, ABERTO, HERDADA, SEM SAP)."""
    return cartao(nome, x, y, w, h, fill=fill, borda=borda, raio=12, Text=texto, Color=cor, DisabledColor=cor,
                  Size="9", FontWeight="FontWeight.Bold", **extra)


def avatar(nome, nome_pessoa, x, y, d=36, fill="corVerde", **extra):
    return cartao(nome, x, y, d, d, fill=fill, borda=fill, raio=d // 2, espessura=0, Text=iniciais(nome_pessoa),
                  Color="Color.White", DisabledColor="Color.White", Size=str(max(8, d // 4)), FontWeight="FontWeight.Bold", **extra)


def moldura(p, atual):
    nome_usuario = "Coalesce(gblUsuario.rlt_nome, User().FullName)"
    itens = [
        C(f"{p}Topo", RET, Fill="corAzul", X="0", Y="0", Width="Parent.Width", Height="56"),
        C(f"{p}Faixa", RET, Fill="corVerde", X="0", Y="56", Width="Parent.Width", Height="5"),
        C(f"{p}Marca", LBL, Text='"RLT · CCM"', Color="Color.White", Size="14", FontWeight="FontWeight.Bold", Font=FONTE_TIT,
          X="20", Y="7", Width="300", Height="24"),
        C(f"{p}Marca2", LBL, Text='"Passagem de Turno"', Color="Color.White", Size="10", FontWeight="FontWeight.Semibold",
          X="20", Y="29", Width="300", Height="20"),
        C(f"{p}Usuario", LBL, Text=nome_usuario, Color="Color.White", Size="12", FontWeight="FontWeight.Bold", Align="Align.Right",
          X="Parent.Width - 470", Y="8", Width="410", Height="22"),
        C(f"{p}Perfil", LBL, Text='If(IsBlank(gblUsuario), "fora da lista de pessoas", Text(gblUsuario.rlt_perfil) & If(IsBlank(gblUsuario.rlt_cargo), "", " · " & Lower(gblUsuario.rlt_cargo)))',
          Color="Color.White", Size="9", Align="Align.Right", X="Parent.Width - 470", Y="29", Width="410", Height="18"),
        avatar(f"{p}Avatar", nome_usuario, "Parent.Width - 52", 10),
        C(f"{p}MenuFundo", RET, Fill="Color.White", BorderColor="corLinha", BorderThickness="1", X="0", Y="61", Width="200", Height="Parent.Height - 61"),
    ]
    for i, (rot, destino, icone) in enumerate(MENU):
        on = destino == atual
        y = 76 + i * 50
        ir = "Navigate(scrHistorico, ScreenTransition.None, {locHistReg: Blank()})" if destino == "scrHistorico" else f"Navigate({destino}, ScreenTransition.None)"
        itens.append(C(f"{p}Menu{i}", BTN, Text=f'"{icone}    {rot}"', OnSelect=ir,
                       Fill="corAzul10" if on else "Color.White", Color="corAzul" if on else "corMuted", HoverFill="corAzul10", HoverColor="corAzul",
                       PressedFill="corAzul10", BorderThickness="0", Align="Align.Left", PaddingLeft="22",
                       FontWeight="FontWeight.Bold" if on else "FontWeight.Normal", Size="12",
                       X="0", Y=str(y), Width="200", Height="46",
                       RadiusTopLeft="0", RadiusTopRight="0", RadiusBottomLeft="0", RadiusBottomRight="0"))
        if on:
            itens.append(C(f"{p}MenuMarca", RET, Fill="corVerde", X="0", Y=str(y), Width="4", Height="46"))
        if destino == "scrPainel":  # bolha vermelha: Fator Q sem código SAP
            itens.append(chip(f"{p}MenuBolha", FQ_SEM_SAP, 166, y + 14, 22, "corVerm", "Color.White", "corVerm", h=18,
                              Visible=f"{FQ_SEM_SAP} > 0"))
    return itens


def titulo(p, texto, sub=None, y=78):
    out = [C(f"{p}Acento", RET, Fill="corVerde", X="224", Y=str(y - 2), Width="36", Height="4"),
           C(f"{p}Tit", LBL, Text=texto, Color="corAzul", Size="20", FontWeight="FontWeight.Bold", Font=FONTE_TIT,
             X="224", Y=str(y + 4), Width="Parent.Width - 460", Height="34")]
    if sub:
        out.append(C(f"{p}Sub", LBL, Text=sub, Color="corMuted", Size="10", X="224", Y=str(y + 38), Width="Parent.Width - 460", Height="24",
                     VerticalAlign="VerticalAlign.Top"))
    return out


def botao(nome, texto, onselect, x, y, w=170, h=40, primario=True, **extra):
    props = dict(Text=texto, OnSelect=onselect, X=str(x), Y=str(y), Width=str(w), Height=str(h), Size="12", FontWeight="FontWeight.Semibold",
                 Fill="corAzul" if primario else "Color.White", Color="Color.White" if primario else "corAzul",
                 BorderColor="corAzul", BorderThickness="1", HoverFill="corAzul80" if primario else "corAzul10",
                 HoverColor="Color.White" if primario else "corAzul",
                 RadiusTopLeft="8", RadiusTopRight="8", RadiusBottomLeft="8", RadiusBottomRight="8")
    props.update(extra)
    return C(nome, BTN, **props)


def rotulo(nome, texto, x, y, w=300, vis="true"):
    return C(nome, LBL, Text=texto, Color="corMuted", Size="10", FontWeight="FontWeight.Semibold", X=str(x), Y=str(y), Width=str(w), Height="22", Visible=vis)


# ================================================================== TELA RELATÓRIO
def tela_relatorio():
    """Painel do plantão, no layout do protótipo (telaRelatorio): plantão, indicadores, seções e últimas alterações."""
    p = "rel"
    off = f"If({FQ_SEM_SAP} > 0, 52, 0)"          # o aviso de Fator Q sem SAP empurra o resto para baixo
    y = lambda base: f"{base} + {off}"
    LARG = "Parent.Width - 248"                    # área útil à direita do menu
    ASIDE = 300                                    # coluna "Últimas alterações"
    ir_cha = lambda so_abertos, sec="Blank()": f"Navigate(scrChamados, ScreenTransition.None, {{locSoAbertos: {so_abertos}, locSecaoFiltro: {sec}}})"
    aberto = f"!IsBlank(gblRel) && gblRel.rlt_situacao = {SIT}.Aberto"
    filhos = moldura(p, "scrRelatorio") + titulo(
        p, 'If(IsBlank(gblRel), "NENHUM RELATÓRIO", "RELATÓRIO " & Text(gblRel.rlt_turno) & " " & Text(gblRel.rlt_data, "dd.mm.yyyy"))')
    filhos += [
        chip(f"{p}Situacao", 'If(IsBlank(gblRel), "SEM PLANTÃO", If(' + aberto + ', "ABERTO", "FECHADO"))', 224, 118, 84,
             f"If({aberto}, RGBA(227, 242, 218, 1), corAzul10)", f"If({aberto}, RGBA(47, 98, 20, 1), corAzul)", f"If({aberto}, RGBA(191, 226, 168, 1), corLinha)", h=22),
        C(f"{p}Pdf", LBL, Text='If(IsBlank(gblRel), "Abra o plantão para começar.", gblRel.rlt_nome & ".pdf")', Color="corMuted", Size="10",
          X="316", Y="117", Width="Parent.Width - 560", Height="24"),
        botao(f"{p}BtnAbrir", '"＋  Abrir plantão"', "Navigate(scrAbrir, ScreenTransition.None)", "Parent.Width - 214", 86, 190, 42, Visible=f"Not({ABERTO_REL})"),
        botao(f"{p}BtnFechar", '"➤  Fechar relatório"', "Navigate(scrFechar, ScreenTransition.None)", "Parent.Width - 214", 86, 190, 42, Visible=ABERTO_REL),
        # aviso: Fator Q sem código SAP (RF-020)
        cartao(f"{p}Aviso", 224, 146, LARG, 42, fill="corVerm20", borda="RGBA(231, 163, 179, 1)", Visible=f"{FQ_SEM_SAP} > 0"),
        C(f"{p}AvisoTxt", LBL, Text=f'"⚠   " & {FQ_SEM_SAP} & If({FQ_SEM_SAP} = 1, " chamado", " chamados") & " do Fator Q sem código SAP. Corrija no Painel geral de informações."',
          Color="RGBA(138, 0, 33, 1)", Size="11", FontWeight="FontWeight.Semibold", PaddingLeft="16", X="224", Y="146", Width=LARG, Height="42",
          Visible=f"{FQ_SEM_SAP} > 0", OnSelect="Navigate(scrPainel, ScreenTransition.None)"),
        # cartão do plantão
        cartao(f"{p}Cartao", 224, y(146), LARG, 150),
        rotulo(f"{p}RotTurno", '"TURNO"', 244, y(158), 120), rotulo(f"{p}RotData", '"DATA"', 380, y(158), 200),
        C(f"{p}Turno", LBL, Text='Text(gblRel.rlt_turno)', Color="corAzul", Size="17", FontWeight="FontWeight.Bold", Font=FONTE_TIT, X="244", Y=y(176), Width="130", Height="28"),
        C(f"{p}TurnoHoras", LBL, Text='If(IsBlank(gblRel), "", If(Text(gblRel.rlt_turno) = "ALFA", "07:00 às 19:00", "19:00 às 07:00"))', Color="corMuted", Size="9",
          X="244", Y=y(202), Width="130", Height="20"),
        C(f"{p}Data", LBL, Text='Text(gblRel.rlt_data, "dd/mm/yyyy")', Color="corAzul", Size="17", FontWeight="FontWeight.Bold", Font=FONTE_TIT, X="380", Y=y(176), Width="220", Height="28"),
        C(f"{p}Janela", LBL, Text='If(IsBlank(gblRel), "", Text(gblRel.rlt_inicio, "dd/mm/yyyy hh:mm") & " → " & Text(gblRel.rlt_fim, "dd/mm/yyyy hh:mm"))',
          Color="corMuted", Size="9", X="380", Y=y(202), Width="260", Height="20"),
    ]
    # andamento do turno (barra)
    pct = ("If(IsBlank(gblRel), 0, Max(0, Min(1, DateDiff(gblRel.rlt_inicio, Now(), TimeUnit.Minutes) / "
           "Max(1, DateDiff(gblRel.rlt_inicio, gblRel.rlt_fim, TimeUnit.Minutes)))))")
    xa, wa = "660", "Parent.Width - 24 - 20 - 660"
    filhos += [
        rotulo(f"{p}RotAnd", '"ANDAMENTO DO TURNO"', xa, y(158), 260),
        C(f"{p}AndFundo", RET, Fill="corAzul10", X=xa, Y=y(184), Width=wa, Height="8"),
        C(f"{p}AndBarra", RET, Fill="corVerde", X=xa, Y=y(184), Width=f"({wa}) * {pct}", Height="8"),
        C(f"{p}AndTxt", LBL, Color="corMuted", Size="9", X=xa, Y=y(196), Width=wa, Height="20",
          Text=(f'If(IsBlank(gblRel), "", If(Now() >= gblRel.rlt_fim, "Turno encerrado", Round({pct} * 100, 0) & "%  ·  faltam " & '
                'RoundDown(DateDiff(Now(), gblRel.rlt_fim, TimeUnit.Minutes) / 60, 0) & "h" & Text(Mod(DateDiff(Now(), gblRel.rlt_fim, TimeUnit.Minutes), 60), "00")))')),
        C(f"{p}Linha", RET, Fill="corLinha", X="244", Y=y(226), Width="Parent.Width - 288", Height="1"),
        rotulo(f"{p}RotEquipe", '"EQUIPE DO PLANTÃO (" & CountRows(colEquipe) & ")"', 244, y(234), 400),
        C(f"{p}GalEquipe", GAL, variante="Vertical", Items="Sort(colEquipe, rlt_nome)", WrapCount="4", TemplateSize="44", TemplatePadding="0",
          X="240", Y=y(254), Width="Parent.Width - 280", Height="44", ShowScrollbar="false",
          filhos=[
              cartao("relEqPilula", 4, 2, "Parent.TemplateWidth - 12", 40, raio=20),
              avatar("relEqAvatar", "ThisItem.rlt_nome", 10, 8, d=28),
              C("relEqNome", LBL, Text="ThisItem.rlt_nome", Color="corTexto", Size="10", FontWeight="FontWeight.Bold",
                X="44", Y="5", Width="Parent.TemplateWidth - 90", Height="18"),
              C("relEqPerfil", LBL, Text='Text(ThisItem.rlt_perfil) & If(IsBlank(ThisItem.rlt_entrouem), "", "  ·  login " & Text(ThisItem.rlt_entrouem, "hh:mm"))',
                Color="corMuted", Size="8", X="44", Y="22", Width="Parent.TemplateWidth - 90", Height="16"),
              C("relEqSair", BTN, Text='"×"', Visible=ABERTO_REL, X="Parent.TemplateWidth - 40", Y="8", Width="26", Height="28",
                Fill="Color.White", Color="corMuted", BorderThickness="0", HoverFill="corAzul10", HoverColor="corVerm", Size="12",
                OnSelect="Patch('Equipe do plantão', LookUp('Equipe do plantão', rlt_equipeid = ThisItem.rlt_equipeid), {rlt_retiradoem: Now(), rlt_retiradopor: gblUsuario});\n"
                         + hist('"Tirou " & ThisItem.rlt_nome & " da equipe do plantão"') + ";\n" + REFRESH),
          ]),
    ]
    # indicadores (cartões com borda colorida à esquerda)
    kpis = [("Em aberto", f"CountRows(Filter(colRegs, {ABERTO}))", "corLaranja", ir_cha("true")),
            ("Concluídos ou encerrados", f"CountRows(Filter(colRegs, Not({ABERTO})))", "corVerde", ir_cha("false")),
            ("Herdados ainda abertos", f"CountRows(Filter(colRegs, rlt_herdado && {ABERTO}))", "corAzul", ir_cha("true")),
            ("Fator Q sem código SAP", FQ_SEM_SAP, f"If({FQ_SEM_SAP} > 0, corVerm, corVerde)", "Navigate(scrPainel, ScreenTransition.None)")]
    for i, (rot, conta, cor, nav) in enumerate(kpis):
        x = f"224 + {i} * (({LARG} - 36) / 4 + 12)"
        w = f"({LARG} - 36) / 4"
        filhos += [
            cartao(f"{p}Kpi{i}", x, y(306), w, 64),
            C(f"{p}KpiBarra{i}", RET, Fill=cor, X=x, Y=y(308), Width="4", Height="60"),
            C(f"{p}KpiNum{i}", LBL, Text=conta, Color="If(" + conta + ' > 0 && "' + rot + '" = "Fator Q sem código SAP", RGBA(138, 0, 33, 1), corAzul)',
              Size="20", FontWeight="FontWeight.Bold", X=f"{x} + 14", Y=y(310), Width=f"{w} - 20", Height="32", OnSelect=nav),
            C(f"{p}KpiRot{i}", LBL, Text=f'"{rot}"', Color="corMuted", Size="10", X=f"{x} + 14", Y=y(342), Width=f"{w} - 20", Height="22", OnSelect=nav),
        ]
    # seções (grade de cartões) + últimas alterações
    larg_sec = f"Parent.Width - 236 - {ASIDE} - 24"
    pct_ok = "(t - a) / Max(1, t)"
    filhos += [
        C(f"{p}SecTit", LBL, Text='"SEÇÕES"', Color="corAzul", Size="14", FontWeight="FontWeight.Bold", Font=FONTE_TIT, X="224", Y=y(380), Width="200", Height="28"),
        C(f"{p}VerTodos", LBL, Text='"Ver todos os chamados"', Color="corAzul", Size="10", Underline="true", Align="Align.Right",
          X=f"224 + {larg_sec} - 220 - 6", Y=y(382), Width="220", Height="24", OnSelect=ir_cha("false")),
        C(f"{p}GalSecoes", GAL, variante="Vertical", Items="tabSecoes", WrapCount="3", TemplateSize="150", TemplatePadding="6",
          X="218", Y=y(408), Width=larg_sec, Height=f"Parent.Height - ({y(408)}) - 8",
          filhos=[
              cartao("relSecCor", 0, 0, "Parent.TemplateWidth", "Parent.TemplateHeight", fill="ThisItem.Cor", borda="ThisItem.Cor"),
              cartao("relSecFundo", 0, 4, "Parent.TemplateWidth", "Parent.TemplateHeight - 4"),
              C("relSecNome", LBL, Text="Upper(ThisItem.Nome)", Color="corAzul", Size="10", FontWeight="FontWeight.Bold", Font=FONTE_TIT,
                X="14", Y="14", Width="Parent.TemplateWidth - 28", Height="20", OnSelect=ir_cha("false", "ThisItem.Valor")),
              C("relSecTotal", LBL, Text="CountRows(Filter(colRegs, rlt_secao = ThisItem.Valor))", Color="corAzul", Size="22", FontWeight="FontWeight.Bold",
                X="14", Y="34", Width="100", Height="36", OnSelect=ir_cha("false", "ThisItem.Valor")),
              chip("relSecSemSap", f'{FQ_SEM_SAP} & " SEM SAP"', "Parent.TemplateWidth - 104", 42, 90, "corVerm20", "RGBA(138, 0, 33, 1)", "corVerm20", h=20,
                   Visible=f'ThisItem.Tipo = "fq" && {FQ_SEM_SAP} > 0'),
              C("relSecBarraFundo", RET, Fill="corAzul10", X="14", Y="74", Width="Parent.TemplateWidth - 28", Height="6"),
              C("relSecBarraOk", RET, Fill="corVerde", X="14", Y="74", Height="6",
                Width=f"With({{a: CountRows(Filter(colRegs, rlt_secao = ThisItem.Valor && {ABERTO})), t: CountRows(Filter(colRegs, rlt_secao = ThisItem.Valor))}}, (Parent.TemplateWidth - 28) * {pct_ok})"),
              C("relSecBarraAb", RET, Fill="corLaranja", Y="74", Height="6",
                X=f"14 + With({{a: CountRows(Filter(colRegs, rlt_secao = ThisItem.Valor && {ABERTO})), t: CountRows(Filter(colRegs, rlt_secao = ThisItem.Valor))}}, (Parent.TemplateWidth - 28) * {pct_ok})",
                Width=f"With({{a: CountRows(Filter(colRegs, rlt_secao = ThisItem.Valor && {ABERTO})), t: CountRows(Filter(colRegs, rlt_secao = ThisItem.Valor))}}, (Parent.TemplateWidth - 28) * a / Max(1, t))"),
              C("relSecResumo", LBL, Color="corMuted", Size="9", X="14", Y="84", Width="Parent.TemplateWidth - 28", Height="20",
                Text=f'With({{a: CountRows(Filter(colRegs, rlt_secao = ThisItem.Valor && {ABERTO})), t: CountRows(Filter(colRegs, rlt_secao = ThisItem.Valor))}}, '
                     f'If(t = 0, "Sem registros", If(a > 0, a & " em aberto  ·  ", "") & (t - a) & " concluído" & If(t - a = 1, "", "s")))'),
              C("relSecLinha", RET, Fill="corLinha", X="1", Y="Parent.TemplateHeight - 41", Width="Parent.TemplateWidth - 2", Height="1", Visible=ABERTO_REL),
              C("relSecAdd", BTN, Text='"＋  Registrar"', Visible=ABERTO_REL, X="1", Y="Parent.TemplateHeight - 40", Width="Parent.TemplateWidth - 2", Height="39",
                Fill="Color.White", Color="corAzul", BorderThickness="0", HoverFill="corAzul", HoverColor="Color.White", PressedFill="corAzul80", Size="11",
                FontWeight="FontWeight.Bold", RadiusTopLeft="0", RadiusTopRight="0", RadiusBottomLeft="9", RadiusBottomRight="9",
                OnSelect="Navigate(scrRegistro, ScreenTransition.None, {locId: Blank(), locSecao: ThisItem.Valor})"),
          ]),
        # últimas alterações
        cartao(f"{p}Recentes", f"Parent.Width - 24 - {ASIDE}", y(380), ASIDE, f"Parent.Height - ({y(380)}) - 14"),
        C(f"{p}RecTit", LBL, Text='"ÚLTIMAS ALTERAÇÕES"', Color="corAzul", Size="11", FontWeight="FontWeight.Bold", Font=FONTE_TIT,
          X=f"Parent.Width - 24 - {ASIDE} + 16", Y=y(392), Width="190", Height="22"),
        C(f"{p}RecHist", LBL, Text='"Histórico"', Color="corAzul", Size="9", Underline="true", Align="Align.Right",
          X=f"Parent.Width - 24 - 96", Y=y(392), Width="80", Height="22", OnSelect="Navigate(scrHistorico, ScreenTransition.None, {locHistReg: Blank()})"),
        C(f"{p}GalRec", GAL, variante="Vertical", TemplateSize="64", TemplatePadding="0", ShowScrollbar="false",
          Items="FirstN(Sort(Filter(Histórico, rlt_relatorio.rlt_relatorioid = gblRel.rlt_relatorioid), rlt_quando, SortOrder.Descending), 8)",
          X=f"Parent.Width - 24 - {ASIDE} + 8", Y=y(420), Width=str(ASIDE - 16), Height=f"Parent.Height - ({y(420)}) - 22",
          filhos=[
              avatar("relRecAvatar", "Coalesce(ThisItem.rlt_quem.rlt_nome, \"?\")", 8, 6, d=28, fill="RGBA(153, 175, 193, 1)"),
              C("relRecQuem", LBL, Text='First(Split(Coalesce(ThisItem.rlt_quem.rlt_nome, "—"), " ")).Value & "  ·  " & ThisItem.rlt_campo',
                Color="corTexto", Size="9", FontWeight="FontWeight.Semibold", X="44", Y="2", Width="Parent.TemplateWidth - 48", Height="20"),
              C("relRecReg", LBL, Text='If(IsBlank(ThisItem.rlt_registro), "", Left(ThisItem.rlt_registro.rlt_titulo, 40) & If(Len(ThisItem.rlt_registro.rlt_titulo) > 40, "…", ""))',
                Color="corAzul", Size="9", Underline="true", X="44", Y="21", Width="Parent.TemplateWidth - 48", Height="20",
                OnSelect="If(!IsBlank(ThisItem.rlt_registro), Navigate(scrRegistro, ScreenTransition.None, {locId: ThisItem.rlt_registro.rlt_registroid, locSecao: ThisItem.rlt_registro.rlt_secao}))"),
              C("relRecQuando", LBL, Text='Text(ThisItem.rlt_quando, "dd/mm/yyyy hh:mm")', Color="corMuted", Size="8", X="44", Y="41", Width="Parent.TemplateWidth - 48", Height="18"),
          ]),
        C(f"{p}RecVazio", LBL, Text='"Nada registrado ainda."', Color="corMuted", Size="10", Visible=f"CountRows({p}GalRec.AllItems) = 0",
          X=f"Parent.Width - 24 - {ASIDE} + 16", Y=y(424), Width=str(ASIDE - 32), Height="24"),
    ]
    return tela("scrRelatorio", {"Fill": "corFundo", "OnVisible": "If(!IsBlank(gblRel), Set(gblRel, LookUp(Relatórios, rlt_relatorioid = gblRel.rlt_relatorioid)));\n" + REFRESH}, filhos)


# ================================================================== TELA CHAMADOS
# Cores das etiquetas de status do protótipo (.st-*): (fundo, texto, borda)
CHIP_STATUS = [
    (["CONCLUÍDO"], "RGBA(227, 242, 218, 1)", "RGBA(47, 98, 20, 1)", "RGBA(191, 226, 168, 1)"),
    (["EM ANDAMENTO"], "corLaranja20", "corLaranjaTxt", "RGBA(247, 201, 140, 1)"),
    (["PENDENTE"], "Color.White", "corLaranjaTxt", "corLaranja"),
    (["CHAMADO FALSO", "SUSPENSO"], "RGBA(236, 239, 242, 1)", "RGBA(71, 82, 94, 1)", "RGBA(207, 214, 221, 1)"),
    (["AGENDADO"], "corAzul10", "corAzul", "RGBA(204, 215, 224, 1)"),
    (["CANCELADO"], "corVerm20", "RGBA(138, 0, 33, 1)", "RGBA(231, 163, 179, 1)"),
    (["NÃO INFORMADO (NI)"], "Color.White", "RGBA(71, 82, 94, 1)", "RGBA(142, 153, 164, 1)"),
]


def cor_status(st, i, padrao):
    """Switch sobre o texto do status (em maiúsculas) devolvendo fundo (i=1), texto (i=2) ou borda (i=3)."""
    pares = ", ".join(f'"{s}", {c[i]}' for c in CHIP_STATUS for s in c[0])
    return f"Switch(Upper({st}), {pares}, {padrao})"


def tela_chamados():
    """Chamados do plantão agrupados por seção, no layout do protótipo (telaPendencias)."""
    p = "cha"
    filtro = f"(!locSoAbertos || {ABERTO})"
    do_grupo = f"Sort(Filter(colRegs, rlt_secao = ThisItem.Valor && {filtro}), rlt_inicio)"
    grupos = (f"Filter(tabSecoes, (IsBlank(locSecaoFiltro) || Valor = locSecaoFiltro) && "
              f"CountRows(Filter(colRegs, rlt_secao = Valor && {filtro})) > 0)")
    reg = "LookUp(Registros, rlt_registroid = ThisItem.rlt_registroid)"
    concluir = (f"With({{r: {reg}}},\n"
                f"  If(ThisItem.rlt_secao = {SEC}.'IOS informados',\n"
                f"    Patch(Registros, r, {{rlt_conclusao: Now(), rlt_ni: false, rlt_statusios: {SI}.Concluído}}),\n"
                f"    Patch(Registros, r, {{rlt_conclusao: Now(), rlt_ni: false, rlt_status: {ST}.CONCLUÍDO}})));\n"
                + hist('"Hora de conclusão e status"', reg) + ";\n"
                + REFRESH + ";\nNotify(\"Concluído: \" & Left(ThisItem.rlt_titulo, 50), NotificationType.Success)")
    limpar = (f"With({{r: {reg}}},\n"
              f"  If(ThisItem.rlt_secao = {SEC}.'IOS informados',\n"
              f"    Patch(Registros, r, {{rlt_conclusao: Blank(), rlt_statusios: If(ThisItem.rlt_statusios = {SI}.Concluído, {SI}.'Em andamento', ThisItem.rlt_statusios)}}),\n"
              f"    Patch(Registros, r, {{rlt_conclusao: Blank(), rlt_status: If(ThisItem.rlt_status = {ST}.CONCLUÍDO, {ST}.'EM ANDAMENTO', ThisItem.rlt_status)}})));\n"
              + hist('"Hora de conclusão"', reg) + ";\n" + REFRESH)
    st = f"If(ThisItem.rlt_secao = {SEC}.'IOS informados', Text(ThisItem.rlt_statusios), Text(ThisItem.rlt_status))"
    aberto_item = ABERTO.replace("rlt_", "ThisItem.rlt_")
    larg_chip = f"Len({st}) * 8 + 44"  # uma linha só, mesmo em "EM ANDAMENTO"
    ALT = 112  # altura de cada chamado (cartão de 102 + 10 de espaço)

    filhos = moldura(p, "scrChamados") + titulo(
        p, '"CHAMADOS DO PLANTÃO"',
        'If(IsBlank(gblRel), "", "Todos os registros do turno " & Text(gblRel.rlt_turno) & " " & Text(gblRel.rlt_data, "dd.mm.yyyy") & '
        '", incluindo os concluídos. Os abertos passam para o próximo turno (RN-009).")')
    pilula = dict(RadiusTopLeft="18", RadiusTopRight="18", RadiusBottomLeft="18", RadiusBottomRight="18", BorderColor="If(Self.Fill = corAzul, corAzul, RGBA(197, 206, 215, 1))")
    filhos += [
        botao(f"{p}Todos", '"Todos (" & CountRows(colRegs) & ")"', "UpdateContext({locSoAbertos: false})", 224, 146, 130, 34,
              Fill="If(locSoAbertos, Color.White, corAzul)", Color="If(locSoAbertos, corTexto, Color.White)", HoverFill="If(locSoAbertos, corAzul10, corAzul80)",
              HoverColor="If(locSoAbertos, corTexto, Color.White)", Size="11", **pilula),
        botao(f"{p}Abertos", f'"Só em aberto (" & CountRows(Filter(colRegs, {ABERTO})) & ")"', "UpdateContext({locSoAbertos: true})", 362, 146, 160, 34,
              Fill="If(locSoAbertos, corAzul, Color.White)", Color="If(locSoAbertos, Color.White, corTexto)", HoverFill="If(locSoAbertos, corAzul80, corAzul10)",
              HoverColor="If(locSoAbertos, Color.White, corTexto)", Size="11", **pilula),
        botao(f"{p}LimpaSec", '"Seção: " & LookUp(tabSecoes, Valor = locSecaoFiltro).Nome & "   ×"', "UpdateContext({locSecaoFiltro: Blank()})", 530, 146, 240, 34,
              primario=False, Visible="!IsBlank(locSecaoFiltro)", Size="11", **{**pilula, "BorderColor": "corAzul"}),
        C(f"{p}Grupos", GAL, variante="VariableHeight", Items=grupos, TemplateSize="60", TemplatePadding="0",
          X="224", Y="188", Width="Parent.Width - 236", Height="Parent.Height - 194",
          filhos=[
              C("chaGrpNome", LBL, Text="Upper(ThisItem.Nome)", Color="corAzul", Size="13", FontWeight="FontWeight.Bold", Font=FONTE_TIT,
                X="0", Y="12", Width="Len(ThisItem.Nome) * 11 + 12", Height="26"),
              chip("chaGrpQtd", f"CountRows(Filter(colRegs, rlt_secao = ThisItem.Valor && {filtro}))", "Len(ThisItem.Nome) * 11 + 14", 16, 24,
                   "corAzul10", "corAzul", "corAzul10", h=18),
              C("chaGal", GAL, variante="Vertical", Items=do_grupo, TemplateSize=str(ALT), TemplatePadding="0", ShowScrollbar="false",
                X="0", Y="44", Width="Parent.TemplateWidth - 12", Height=f"CountRows({do_grupo}) * {ALT}",
                filhos=[
                    cartao("chaBorda", 0, 0, "Parent.TemplateWidth", ALT - 10,
                           fill=f"If({aberto_item}, corLaranja, corVerde)", borda=f"If({aberto_item}, corLaranja, corVerde)"),
                    cartao("chaFundo", 4, 0, "Parent.TemplateWidth - 4", ALT - 10),
                    chip("chaStatus", f'"●  " & Upper({st})', 18, 12, larg_chip,
                         cor_status(st, 1, "Color.White"), cor_status(st, 2, "corTexto"), cor_status(st, 3, "corLinha"), h=22),
                    chip("chaHerdada", '"HERDADA"', f"18 + {larg_chip} + 8", 13, 70, "RGBA(255, 243, 224, 1)", "corLaranjaTxt", "RGBA(255, 243, 224, 1)", h=20,
                         Visible="ThisItem.rlt_herdado", RadiusTopLeft="4", RadiusTopRight="4", RadiusBottomLeft="4", RadiusBottomRight="4"),
                    C("chaTitulo", LBL, Text="ThisItem.rlt_titulo", Color="corTexto", Size="11", FontWeight="FontWeight.Bold",
                      X="18", Y="38", Width="Parent.TemplateWidth - 470", Height="38", VerticalAlign="VerticalAlign.Top"),
                    C("chaMeta", LBL, Color="corMuted", Size="9", X="18", Y="76", Width="Parent.TemplateWidth - 470", Height="20",
                      Text=('"Início " & Text(ThisItem.rlt_inicio, "dd/mm/yyyy hh:mm") & '
                            'If(IsBlank(ThisItem.rlt_local), "", "     " & ThisItem.rlt_local.rlt_nome) & '
                            'If(IsBlank(ThisItem.rlt_numero), "", "     Nº " & ThisItem.rlt_numero) & '
                            f'If({aberto_item} && DateDiff(ThisItem.rlt_inicio, Now(), TimeUnit.Days) >= 1, "     aberto há " & DateDiff(ThisItem.rlt_inicio, Now(), TimeUnit.Days) & '
                            'If(DateDiff(ThisItem.rlt_inicio, Now(), TimeUnit.Days) = 1, " dia", " dias"), "")')),
                    C("chaRotConcl", LBL, Text='"Conclusão"', Color="corMuted", Size="9", FontWeight="FontWeight.Bold", Align="Align.Right",
                      X="Parent.TemplateWidth - 430", Y="14", Width="90", Height="30"),
                    cartao("chaConcl", "Parent.TemplateWidth - 334", 12, 180, 34, borda="RGBA(197, 206, 215, 1)", raio=8,
                           Text='If(IsBlank(ThisItem.rlt_conclusao), If(ThisItem.rlt_ni, "N/I – não informado", "dd/mm/aaaa  --:--"), Text(ThisItem.rlt_conclusao, "dd/mm/yyyy  hh:mm"))',
                           Color="If(IsBlank(ThisItem.rlt_conclusao), corMuted, corTexto)", DisabledColor="If(IsBlank(ThisItem.rlt_conclusao), corMuted, corTexto)",
                           Size="10", Align="Align.Left", PaddingLeft="12"),
                    botao("chaAgora", '"Concluir agora"', concluir, "Parent.TemplateWidth - 146", 12, 132, 34, Size="10",
                          Visible=f"{ABERTO_REL} && IsBlank(ThisItem.rlt_conclusao) && !ThisItem.rlt_chamadofalso"),
                    botao("chaLimpar", '"Limpar"', limpar, "Parent.TemplateWidth - 146", 12, 132, 34, primario=False, Size="10",
                          Visible=f"{ABERTO_REL} && !IsBlank(ThisItem.rlt_conclusao)"),
                    botao("chaEditar", 'If(' + ABERTO_REL + ', "Editar", "Ver")', "Navigate(scrRegistro, ScreenTransition.None, {locId: ThisItem.rlt_registroid, locSecao: ThisItem.rlt_secao})",
                          "Parent.TemplateWidth - 146", 54, 132, 34, primario=False, Size="10"),
                ]),
          ]),
        C(f"{p}Vazio", LBL, Text='"Nenhum chamado " & If(locSoAbertos, "em aberto.", "neste plantão.")', Visible=f"CountRows({p}Grupos.AllItems) = 0",
          Color="corMuted", Size="12", Align="Align.Center", X="224", Y="260", Width="Parent.Width - 248", Height="40"),
    ]
    return tela("scrChamados", {"Fill": "corFundo", "OnVisible": REFRESH}, filhos)


# ================================================================== TELA REGISTRO (formulário)
# Controle de arquivo do formulário frmAnexo (janela "Anexar foto ou arquivo"). O código do formulário vem do
# Studio (Inserir > Formulário de edição, fonte Anexos, campos Nome/Arquivo/Registro > Copiar código), porque o
# YAML de formulários e cartões não é documentado. Enquanto ele não existe, a janela mostra só um aviso.
FORM_ANEXO = None  # preenchido logo abaixo de janela_anexo(): form_anexo
EXT_IMAGEM = '["jpg", "jpeg", "png", "gif", "bmp", "webp", "heic"]'


def tela_registro():
    """Formulário do chamado, no layout do protótipo (telaItem): página rolável com um cartão de campos,
    "Fotos e arquivos" embaixo e Cancelar/Salvar. Os campos ficam numa galeria de altura flexível de uma linha
    (é ela que rola); por isso o "Reset" dos campos é feito pela propriedade Reset = locResetar."""
    p = "reg"
    tipo = "LookUp(tabSecoes, Valor = locSecao).Tipo"
    ro = f"If({ABERTO_REL}, DisplayMode.Edit, DisplayMode.View)"
    ao_abrir = (
        "UpdateContext({locReg: If(IsBlank(locId), Blank(), LookUp(Registros, rlt_registroid = locId))});\n"
        # Uma variável por UpdateContext: se o Studio acusar tipo incompatível, ele sublinha só a variável com problema.
        "UpdateContext({locIni: Coalesce(locReg.rlt_inicio, Now())});\n"
        "UpdateContext({locFim: locReg.rlt_conclusao});\n"
        # Sim/Não do Dataverse não é o mesmo tipo que true/false: If() converte para booleano puro.
        "UpdateContext({locNI: If(locReg.rlt_ni, true, false)});\n"
        "UpdateContext({locFalso: If(locReg.rlt_chamadofalso, true, false)});\n"
        "UpdateContext({locStatus: If(IsBlank(locReg.rlt_status), \"EM ANDAMENTO\", Text(locReg.rlt_status))});\n"
        "UpdateContext({locStatusIos: If(IsBlank(locReg.rlt_statusios), \"Em andamento\", Text(locReg.rlt_statusios))});\n"
        "UpdateContext({locArea: locReg.rlt_local.rlt_area});\n"
        "UpdateContext({locFeedback: Coalesce(locReg.rlt_feedback, \"\")});\n"
        "UpdateContext({locErro: \"\"});\n"
        "UpdateContext({locAnexar: false});\n"
        "UpdateContext({locFicar: false});\n"
        # campos dentro da galeria: Reset() não alcança, então eles leem Reset = locResetar
        "UpdateContext({locResetar: true});\n"
        "UpdateContext({locResetar: false});\n"
        "ResetForm(frmAnexo)")
    # Cancelamento (RN-014, ampliada em 25/11/2026): IOS "Cancelado" ou atividade "CANCELADO"; o motivo é obrigatório nos dois
    # Chamados que vão no relatório diário da Eletromecânica: corretiva Eletromecânica, Fator Q e Preventiva
    ELETRO = f'(locSecao = {SEC}.Eletromecânica || {tipo} in ["fq", "prev"])'
    CANCELADO = (f'({tipo} = "ios" && regStatusIos.Selected.Value = "Cancelado") || '
                 f'({tipo} <> "ios" && !regFalso.Value && regStatus.Selected.Value = "CANCELADO")')
    v_ini = "DateTime(Year(regIniData.SelectedDate), Month(regIniData.SelectedDate), Day(regIniData.SelectedDate), Value(regIniH.Selected.Value), Value(regIniM.Selected.Value), 0)"
    v_fim = ("If(IsBlank(regFimData.SelectedDate), Blank(), DateTime(Year(regFimData.SelectedDate), Month(regFimData.SelectedDate), Day(regFimData.SelectedDate), "
             "Value(Coalesce(regFimH.Selected.Value, \"0\")), Value(Coalesce(regFimM.Selected.Value, \"0\")), 0))")
    salvar = f"""With({{vIni: {v_ini}, vFim: {v_fim}, vTipo: {tipo}}},
  UpdateContext({{locErro: Concat(Filter(Table(
    {{m: If(vTipo in ["corretiva", "ios"] && IsBlank(Trim(regDesc.Text)), "Informe a descrição.", "")}},
    {{m: If(vTipo = "corretiva" && IsBlank(regLocal.Selected), "Escolha o local.", "")}},
    {{m: If(vTipo in ["fq", "prev"] && IsBlank(regEquip.Selected) && !(regForaLista.Value && !IsBlank(Trim(regEquipLivre.Text))), "Escolha o equipamento.", "")}},
    {{m: If(vTipo in ["fq", "prev", "ios"] && IsBlank(Trim(regNum.Text)), "Informe o número.", "")}},
    {{m: If(vTipo = "ios" && !IsMatch(regNum.Text, "\\d{{8}}"), "Nº IOS deve ter 8 dígitos: ano + número.", "")}},
    {{m: If(({CANCELADO}) && IsBlank(Trim(regMotivo.Text)), "Informe o motivo do cancelamento.", "")}},
    {{m: If(IsBlank(regIniData.SelectedDate), "Informe o início.", "")}},
    {{m: If(!IsBlank(vFim) && vFim < vIni, "A hora de conclusão está antes do início.", "")}}
  ), !IsBlank(m)), m, "  ")}});
  If(IsBlank(locErro),
    Set(gblSalvo, Patch(Registros, If(IsBlank(locId), Defaults(Registros), locReg), {{
      rlt_titulo: Left(Coalesce(If(vTipo in ["fq", "prev"], Coalesce(regEquip.Selected.rlt_nome, regEquipLivre.Text), regDesc.Text), "(sem descrição)"), 200),
      rlt_secao: locSecao,
      rlt_relatorio: If(IsBlank(locId), gblRel, locReg.rlt_relatorio),
      rlt_descricao: regDesc.Text,
      rlt_local: If(vTipo = "corretiva", regLocal.Selected, Blank()),
      rlt_equipamento: If(vTipo in ["fq", "prev"] && !regForaLista.Value, regEquip.Selected, Blank()),
      rlt_equipamentolivre: If(regForaLista.Value, regEquipLivre.Text, ""),
      rlt_numero: regNum.Text,
      rlt_inicio: vIni,
      rlt_conclusao: vFim,
      rlt_ni: regNI.Value && IsBlank(vFim),
      rlt_chamadofalso: regFalso.Value,
      rlt_limpezatecnica: regLimpeza.Value,
      rlt_status: If(vTipo = "ios", Blank(), regFalso.Value, {ST}.'CHAMADO FALSO', regNI.Value && IsBlank(vFim), {ST}.'EM ANDAMENTO', Switch(regStatus.Selected.Value, "PENDENTE", {ST}.PENDENTE, "CONCLUÍDO", {ST}.CONCLUÍDO, "CANCELADO", {ST}.CANCELADO, {ST}.'EM ANDAMENTO')),
      rlt_statusios: If(vTipo <> "ios", Blank(), regNI.Value && IsBlank(vFim), {SI}.'Não informado (NI)', Switch(regStatusIos.Selected.Value, "Agendado", {SI}.Agendado, "Suspenso", {SI}.Suspenso, "Concluído", {SI}.Concluído, "Cancelado", {SI}.Cancelado, "Não informado (NI)", {SI}.'Não informado (NI)', {SI}.'Em andamento')),
      rlt_motivocancelamento: regMotivo.Text,
      rlt_feedback: If({ELETRO}, Trim(regFeedback.Text), "")
    }}));
    If(IsBlank(locId),
      {hist('"Registro criado"', "gblSalvo")},
      ForAll(Filter(Table(
          {{c: "Descrição", m: Coalesce(locReg.rlt_descricao, "") <> regDesc.Text}},
          {{c: "Local", m: locReg.rlt_local.rlt_localid <> regLocal.Selected.rlt_localid}},
          {{c: "Equipamento", m: locReg.rlt_equipamento.rlt_equipamentoid <> gblSalvo.rlt_equipamento.rlt_equipamentoid || Coalesce(locReg.rlt_equipamentolivre, "") <> Coalesce(gblSalvo.rlt_equipamentolivre, "")}},
          {{c: "Número", m: Coalesce(locReg.rlt_numero, "") <> regNum.Text}},
          {{c: "Início", m: locReg.rlt_inicio <> vIni}},
          {{c: "Hora de conclusão", m: locReg.rlt_conclusao <> vFim}},
          {{c: "N/I", m: locReg.rlt_ni <> gblSalvo.rlt_ni}},
          {{c: "Status", m: locReg.rlt_status <> gblSalvo.rlt_status || locReg.rlt_statusios <> gblSalvo.rlt_statusios}},
          {{c: "Chamado falso", m: locReg.rlt_chamadofalso <> regFalso.Value}},
          {{c: "Limpeza técnica", m: locReg.rlt_limpezatecnica <> regLimpeza.Value}},
          {{c: "Motivo do cancelamento", m: Coalesce(locReg.rlt_motivocancelamento, "") <> regMotivo.Text}},
          {{c: "Feedback para a Eletromecânica", m: Coalesce(locReg.rlt_feedback, "") <> Coalesce(gblSalvo.rlt_feedback, "")}}
        ), m),
        {hist("c", "gblSalvo")})
    );
    Notify(If(vTipo = "fq" && IsBlank(gblSalvo.rlt_equipamento), "Salvo sem código SAP: aparece no Painel Geral de informações.", "Registro salvo."), NotificationType.Success);
    If(locFicar,
      UpdateContext({{locId: gblSalvo.rlt_registroid}});
      UpdateContext({{locReg: gblSalvo}});
      UpdateContext({{locFicar: false}});
      UpdateContext({{locAnexar: true}}),
      Back())
  )
)"""
    status_fim = (f"UpdateContext({{locFim: {v_fim}}}); If(!IsBlank(locFim), UpdateContext({{locNI: false, locStatus: \"CONCLUÍDO\", locStatusIos: \"Concluído\"}}))")
    agora = 'UpdateContext({locFim: Now(), locNI: false, locStatus: "CONCLUÍDO", locStatusIos: "Concluído"})'
    limpar = (f"UpdateContext({{locFim: Blank(), locStatus: If(locStatus = \"CONCLUÍDO\", \"EM ANDAMENTO\", locStatus), "
              f"locStatusIos: If(locStatusIos = \"Concluído\", \"Em andamento\", locStatusIos)}});\n"
              "UpdateContext({locResetFim: true});\nUpdateContext({locResetFim: false})")

    # ---------- geometria (dentro da linha da galeria): coluna esquerda/direita do cartão
    TW = "Parent.TemplateWidth - 14"
    xl, xr = "18", f"(18 + ({TW} - 36) / 2 + 12)"
    w, full = f"(({TW} - 36) / 2 - 12)", f"({TW} - 36)"
    em = lambda *tipos: f"{tipo} in [{', '.join(chr(34) + t + chr(34) for t in tipos)}]"
    D = f"If({em('corretiva', 'ios')}, 116, 0)"            # descrição
    R2 = f"If({em('corretiva', 'fq', 'prev')}, 96, 0)"     # local ou equipamento
    N = f"If({em('fq', 'prev', 'ios')}, 76, 0)"            # número
    F = f"If({em('corretiva', 'fq')}, 64, 0)"              # chamado falso
    y_row2 = f"18 + {D}"
    y_num = f"18 + {D} + {R2}"
    y_ini = f"18 + {D} + {R2} + {N}"
    y_st = f"({y_ini}) + 104"
    y_falso = f"({y_st}) + 96"
    y_feed = f"({y_falso}) + {F}"
    FB = f"If({ELETRO}, 124, 0)"                          # feedback para a Eletromecânica
    y_fotos = f"({y_feed}) + {FB}"
    anexos = "Filter(Anexos, rlt_registro.rlt_registroid = locId)"
    n_anx = f"If(IsBlank(locId), 0, CountRows({anexos}))"
    ALT_ANX = 46
    h_fotos = f"(24 + If({n_anx} > 0, {n_anx} * {ALT_ANX} + 6, 0) + 40 + 30)"
    h_card = f"({y_fotos}) + {h_fotos} + 10"
    y_botoes = f"({h_card}) + 16"

    # ---------- estilo dos campos (protótipo: borda #c5ced7, raio 8, foco verde)
    BORDA = "RGBA(197, 206, 215, 1)"
    estilo_campo = dict(BorderColor=BORDA, BorderThickness="1", HoverBorderColor="corAzul80", FocusedBorderColor="corVerde", FocusedBorderThickness="2",
                        Size="11", Color="corTexto", Reset="locResetar")
    estilo_lista = dict(ChevronBackground="Color.White", ChevronFill="corTexto", ChevronHoverBackground="corAzul10", ChevronHoverFill="corTexto",
                        ChevronDisabledBackground="Color.White", SelectionFill="corAzul", HoverFill="corAzul10")
    estilo_check = dict(CheckboxBorderColor="RGBA(91, 104, 118, 1)", CheckboxSize="20", CheckmarkFill="Color.White", CheckboxBackgroundFill="Color.White",
                        Color="corTexto", Size="11", FontWeight="FontWeight.Semibold", Reset="locResetar")

    def ent(nome, controle, x, y, largura, **kw):
        base = dict(X=str(x), Y=str(y), Width=largura, Height="40", DisplayMode=ro)
        base.update({k: v for k, v in estilo_campo.items() if controle != CHK})
        if controle in (DDL, CBX):
            base.update(estilo_lista)
        if controle == TXT:
            base.update(RadiusTopLeft="8", RadiusTopRight="8", RadiusBottomLeft="8", RadiusBottomRight="8", PaddingLeft="12")
        if controle == DTP:
            base.pop("HoverBorderColor", None)  # o seletor de data clássico não tem borda de "hover"
            base.update(IconBackground="Color.White", IconFill="corTexto")
        if controle == CHK:
            base.update(estilo_check)
        base.update(kw)
        return C(nome, controle, **base)

    def rot(nome, texto, x, y, larg="400", vis="true"):
        return C(nome, LBL, Text=texto, Color="corMuted", Size="9", FontWeight="FontWeight.Bold", X=str(x), Y=str(y), Width=larg, Height="20", Visible=vis)

    def ajuda(nome, texto, x, y, larg, vis="true", h="20"):
        return C(nome, LBL, Text=texto, Color="corMuted", Size="9", X=str(x), Y=str(y), Width=larg, Height=h, Visible=vis, VerticalAlign="VerticalAlign.Top")

    ini_ro = f"If({ABERTO_REL} && !locReg.rlt_herdado, DisplayMode.Edit, DisplayMode.View)"
    nome_secao = "LookUp(tabSecoes, Valor = locSecao).Nome"
    pagina = [
        cartao("regCartao", 0, 0, TW, h_card),
        # descrição / assunto
        rot("regRotDesc", f'If({tipo} = "ios", "ASSUNTO *", "DESCRIÇÃO DA ATIVIDADE *")', xl, 18, vis=em("corretiva", "ios")),
        ent("regDesc", TXT, xl, 40, full, Mode="TextMode.MultiLine", Height="80", Default="locReg.rlt_descricao", Visible=em("corretiva", "ios")),
        # local (corretivas): área e local específico
        rot("regRotArea", '"LOCAL – ÁREA"', xl, y_row2, vis=em("corretiva")),
        rot("regRotLocal", '"LOCAL – ESPECÍFICO *"', xr, y_row2, vis=em("corretiva")),
        ent("regArea", DDL, xl, f"({y_row2}) + 22", w, Items=f"Sort(Distinct({ativos('Locais')}, rlt_area), Value)", Default="locArea", Visible=em("corretiva")),
        ent("regLocal", CBX, xr, f"({y_row2}) + 22", w, Items=f"Filter(Locais, rlt_area = regArea.Selected.Value && {ativo('Locais')})", DisplayFields='["rlt_nome"]', SearchFields='["rlt_nome"]',
            SelectMultiple="false", DefaultSelectedItems="Filter(Locais, rlt_localid = locReg.rlt_local.rlt_localid)", InputTextPlaceholder='"Escolha a área primeiro"',
            Visible=em("corretiva")),
        ajuda("regAjudaLocal", f'"Lista de " & CountIf(Locais, {ativo("Locais")}) & " locais (código SAP), escolhida em dois passos."', xr, f"({y_row2}) + 66", w, em("corretiva")),
        # equipamento (Fator Q e Preventiva)
        rot("regRotEquip", '"EQUIPAMENTO *"', xl, y_row2, vis=em("fq", "prev")),
        ent("regEquip", CBX, xl, f"({y_row2}) + 22", w, Items=ativos("Equipamentos"), DisplayFields='["rlt_nome"]', SearchFields='["rlt_nome", "rlt_codigosap"]',
            SelectMultiple="false", DefaultSelectedItems="Filter(Equipamentos, rlt_equipamentoid = locReg.rlt_equipamento.rlt_equipamentoid)",
            InputTextPlaceholder='"Buscar por nome ou código"', Visible=f"{em('fq', 'prev')} && !regForaLista.Value"),
        ent("regEquipLivre", TXT, xl, f"({y_row2}) + 22", w, Default="locReg.rlt_equipamentolivre", HintText='"Descreva o equipamento"',
            Visible=f"{em('fq')} && regForaLista.Value"),
        ajuda("regEquipSap", 'If(IsBlank(regEquip.Selected), "Buscar por nome ou código SAP.", "SAP " & regEquip.Selected.rlt_codigosap & "  ·  " & Text(regEquip.Selected.rlt_tipo) & "   (o código aparece no app, não no PDF – RF-018)")',
              xl, f"({y_row2}) + 66", w, f"{em('fq', 'prev')} && !regForaLista.Value"),
        ent("regForaLista", CHK, xr, f"({y_row2}) + 24", w, Height="36", Text='"Equipamento fora da lista"', Default="!IsBlank(locReg.rlt_equipamentolivre)",
            Visible=em("fq")),
        ajuda("regAjudaFora", '"Não bloqueia: vai para o Painel geral de informações (RN-017)."', f"{xr} + 30", f"({y_row2}) + 60", f"{w} - 30", em("fq")),
        # número
        rot("regRotNum", f'Switch({tipo}, "fq", "Nº DO CHAMADO *", "prev", "Nº DA ORDEM DE SERVIÇO *", "Nº IOS * (8 dígitos: ano + número)")', xl, y_num, vis=em("fq", "prev", "ios")),
        ent("regNum", TXT, xl, f"({y_num}) + 22", w, Default="locReg.rlt_numero", Visible=em("fq", "prev", "ios")),
        # início
        rot("regRotIni", '"INÍCIO (DATA E HORA) *"', xl, y_ini),
        ent("regIniData", DTP, xl, f"({y_ini}) + 22", f"{w} - 172", DefaultDate="locIni", Format='"dd/mm/yyyy"', DisplayMode=ini_ro),
        ent("regIniH", DDL, f"{xl} + {w} - 164", f"({y_ini}) + 22", "78", Items="tabHoras", Default='Text(Hour(locIni), "00")', DisplayMode=ini_ro),
        ent("regIniM", DDL, f"{xl} + {w} - 80", f"({y_ini}) + 22", "80", Items="tabMinutos", Default='Text(Minute(locIni), "00")', DisplayMode=ini_ro),
        ent("regNI", CHK, xl, f"({y_ini}) + 68", "300", Height="30", Text='"N/I – não informado"', Default="locNI",
            OnCheck="UpdateContext({locNI: true})", OnUncheck="UpdateContext({locNI: false})",
            DisplayMode=f"If({ABERTO_REL} && IsBlank(locFim), DisplayMode.Edit, DisplayMode.Disabled)"),
        # conclusão
        rot("regRotFim", '"HORA DE CONCLUSÃO"', xr, y_ini),
        ent("regFimData", DTP, xr, f"({y_ini}) + 22", f"{w} - 340", DefaultDate="locFim", Format='"dd/mm/yyyy"', OnChange=status_fim,
            Reset="locResetar || locResetFim",
            InputTextPlaceholder='"dd/mm/aaaa"'),  # o padrão do controle mostra a data de exemplo 31/12/2001
        ent("regFimH", DDL, f"{xr} + {w} - 332", f"({y_ini}) + 22", "78", Items="tabHoras", Default='If(IsBlank(locFim), "", Text(Hour(locFim), "00"))',
            AllowEmptySelection="true", OnChange=status_fim, Reset="locResetar || locResetFim"),
        ent("regFimM", DDL, f"{xr} + {w} - 248", f"({y_ini}) + 22", "78", Items="tabMinutos", Default='If(IsBlank(locFim), "", Text(Minute(locFim), "00"))',
            AllowEmptySelection="true", OnChange=status_fim, Reset="locResetar || locResetFim"),
        botao("regAgora", '"Agora"', agora, f"{xr} + {w} - 162", f"({y_ini}) + 22", 76, 40, primario=False, Size="10", Visible=ABERTO_REL),
        botao("regLimpar", '"Limpar"', limpar, f"{xr} + {w} - 78", f"({y_ini}) + 22", 78, 40, primario=False, Size="10", Visible=ABERTO_REL),
        ajuda("regAjudaFim", 'If(IsBlank(locFim), "Preencha quando o chamado for concluído. O status muda sozinho.", "")', xr, f"({y_ini}) + 68", w),
        # status
        rot("regRotStatus", f'If({tipo} = "ios", "STATUS DO IOS *", "STATUS *")', xl, y_st),
        ent("regStatus", DDL, xl, f"({y_st}) + 22", w, Default="locStatus", Visible=f'{tipo} <> "ios"',
            Items='Filter(["PENDENTE", "EM ANDAMENTO", "CONCLUÍDO", "CANCELADO"], !IsBlank(locFim) || Value <> "CONCLUÍDO")',
            OnChange="UpdateContext({locStatus: Self.Selected.Value})",
            DisplayMode=f"If({ABERTO_REL} && !regFalso.Value && !(regNI.Value && IsBlank(locFim)), DisplayMode.Edit, DisplayMode.Disabled)"),
        ent("regStatusIos", DDL, xl, f"({y_st}) + 22", w, Default="locStatusIos", Visible=f'{tipo} = "ios"',
            Items='Filter(["Agendado", "Em andamento", "Suspenso", "Concluído", "Cancelado", "Não informado (NI)"], !IsBlank(locFim) || Value <> "Concluído")',
            OnChange="UpdateContext({locStatusIos: Self.Selected.Value})",
            DisplayMode=f"If({ABERTO_REL} && !(regNI.Value && IsBlank(locFim)), DisplayMode.Edit, DisplayMode.Disabled)"),
        ajuda("regAjudaStatus", f'If(regFalso.Value, "Chamado falso não vira pendência.", regNI.Value && IsBlank(locFim), "EM ANDAMENTO porque está marcado N/I.", '
                                f'{tipo} = "ios" && regStatusIos.Selected.Value = "Cancelado" || {tipo} <> "ios" && locStatus = "CANCELADO", "Cancelado: conta como encerrado e não passa para o próximo turno.", '
                                f'!IsBlank(locFim) && locStatus = "CONCLUÍDO", "CONCLUÍDO porque a hora de conclusão foi preenchida. Você pode trocar o status.", '
                                f'"Sem hora de conclusão o chamado continua aberto e passa para o próximo turno.")', xl, f"({y_st}) + 66", w),
        rot("regRotMotivo", '"MOTIVO DO CANCELAMENTO *"', xr, y_st, vis=CANCELADO),
        ent("regMotivo", TXT, xr, f"({y_st}) + 22", w, Default="locReg.rlt_motivocancelamento", Visible=CANCELADO),
        ajuda("regAjudaMotivo", f'If({tipo} = "ios", "Obrigatório para IOS cancelado (RN-014).", "Obrigatório para chamado cancelado (RN-014).")', xr, f"({y_st}) + 66", w, CANCELADO),
        ent("regLimpeza", CHK, xr, f"({y_st}) + 24", w, Height="36", Text='"Limpeza técnica (fora de preventiva x corretiva)"',
            Default="Coalesce(locReg.rlt_limpezatecnica, false)", Visible=f"locSecao = {SEC}.Outros && !({CANCELADO})"),
        # chamado falso
        ent("regFalso", CHK, xl, y_falso, "300", Height="30", Text='"Chamado falso"', Default="locFalso",
            OnCheck="UpdateContext({locFalso: true})", OnUncheck="UpdateContext({locFalso: false})", Visible=em("corretiva", "fq")),
        ajuda("regAjudaFalso", f'"Status CHAMADO FALSO: conta como encerrado, não vira pendência e fica fora de preventiva x corretiva (RN-011" & If({tipo} = "fq", ").", "; nesta seção, conforme a proposta do PRD 1.2).")',
              f"{xl} + 30", f"({y_falso}) + 28", f"{full} - 30", em("corretiva", "fq")),
        # feedback para a Eletromecânica (coluna "Feedback Coordenação Responsável" do relatório diário)
        rot("regRotFeedback", '"FEEDBACK PARA A ELETROMECÂNICA  (sai no relatório diário da Eletromecânica)"', xl, y_feed, larg=full, vis=ELETRO),
        ent("regFeedback", TXT, xl, f"({y_feed}) + 22", full, Default="locFeedback", OnChange="UpdateContext({locFeedback: Self.Text})",
            HintText='"Ex.: MOTIVO: BOTÃO STOP.  ou  IOS 1414_2026 - CCM - MEC - ATUALIZAÇÃO.2"', MaxLength="2000", Visible=ELETRO),
        ent("regVincIos", DDL, xl, f"({y_feed}) + 70", f"{w} - 122", AllowEmptySelection="true", Default='""', Visible=f"{ELETRO} && {ABERTO_REL}",
            Items=(f'ForAll(Filter(colRegs, rlt_secao = {SEC}.\'IOS informados\'), '
                   '{Value: "IOS " & Mid(rlt_numero, 5) & "_" & Left(rlt_numero, 4) & " - " & Upper(rlt_titulo)})'),
            OnChange=('If(!IsBlank(Self.Selected.Value), UpdateContext({locFeedback: Trim(locFeedback & '
                      'If(IsBlank(Trim(locFeedback)), "", "  ·  ") & Self.Selected.Value)}))')),
        botao("regBtnMotivo", '"MOTIVO:"', 'If(!StartsWith(Upper(Trim(locFeedback)), "MOTIVO:"), UpdateContext({locFeedback: "MOTIVO: " & locFeedback}))',
              f"{xl} + {w} - 110", f"({y_feed}) + 70", 110, 40, primario=False, Size="10", Visible=f"{ELETRO} && {ABERTO_REL}"),
        ajuda("regAjudaFeedback", '"A lista ao lado tem os IOS informados neste plantão: escolher um escreve a referência no feedback."',
              xr, f"({y_feed}) + 72", w, f"{ELETRO} && {ABERTO_REL}", h="36"),
        # fotos e arquivos (RF-007)
        C("regRotFotos", LBL, Text='"FOTOS E ARQUIVOS  (opcional)"', Color="corMuted", Size="9", FontWeight="FontWeight.Bold", X=xl, Y=y_fotos, Width="400", Height="20"),
        C("regGalAnexos", GAL, variante="Vertical", Items=anexos, TemplateSize=str(ALT_ANX), TemplatePadding="0", ShowScrollbar="false",
          X=xl, Y=f"({y_fotos}) + 24", Width=full, Height=f"{n_anx} * {ALT_ANX}", Visible=f"{n_anx} > 0",
          filhos=[
              cartao("regAnxFundo", 0, 3, "Parent.TemplateWidth", ALT_ANX - 6, raio=8),
              C("regAnxIcone", LBL, Text=f'If(Lower(Coalesce(ThisItem.rlt_tipo, "")) in {EXT_IMAGEM}, "▣", "▤")', Color="corAzul", Size="14", Align="Align.Center",
                X="8", Y="3", Width="30", Height=str(ALT_ANX - 6)),
              C("regAnxNome", LBL, Text='ThisItem.rlt_nome & If(IsBlank(ThisItem.rlt_tamanho), "", "   ·   " & Round(ThisItem.rlt_tamanho / 1024, 0) & " KB")',
                Color="corTexto", Size="10", X="42", Y="3", Width="Parent.TemplateWidth - 240", Height=str(ALT_ANX - 6)),
              C("regAnxAbrir", LBL, Text='"Abrir"', Color="corAzul", Underline="true", Size="10", Align="Align.Right",
                X="Parent.TemplateWidth - 190", Y="3", Width="80", Height=str(ALT_ANX - 6), OnSelect="Download(ThisItem.rlt_arquivo.Value)"),
              C("regAnxExcluir", LBL, Text='"Excluir"', Color="RGBA(138, 0, 33, 1)", Underline="true", Size="10", Align="Align.Right", Visible=ABERTO_REL,
                X="Parent.TemplateWidth - 100", Y="3", Width="86", Height=str(ALT_ANX - 6),
                OnSelect=("Remove(Anexos, LookUp(Anexos, rlt_anexoid = ThisItem.rlt_anexoid));\n"
                          + hist('"Anexo excluído: " & ThisItem.rlt_nome', "locReg") + ";\nNotify(\"Anexo excluído.\", NotificationType.Success)")),
          ]),
        botao("regAnexar", 'If(IsBlank(locId), "＋  Salvar e anexar foto ou arquivo", "＋  Anexar foto ou arquivo")',
              f"If(IsBlank(locId), UpdateContext({{locFicar: true}}); {salvar}, UpdateContext({{locAnexar: true}}))",
              xl, f"({y_fotos}) + 24 + If({n_anx} > 0, {n_anx} * {ALT_ANX} + 6, 0)", 'If(IsBlank(locId), 280, 220)', 40,
              primario=False, Size="10", Visible=ABERTO_REL),
        ajuda("regAjudaFotos", '"Fotos aparecem no PDF, no fim do relatório. Outros arquivos ficam guardados com o chamado e são listados no PDF."',
              xl, f"({y_fotos}) + 24 + If({n_anx} > 0, {n_anx} * {ALT_ANX} + 6, 0) + 46", full),
        # erros e botões
        C("regErro", LBL, Text="locErro", Visible="!IsBlank(locErro)", Color="RGBA(138, 0, 33, 1)", Fill="corVerm20", Size="10", FontWeight="FontWeight.Semibold",
          PaddingLeft="12", X="0", Y=y_botoes, Width=f"{TW} - 380", Height="44"),
        botao("regCancelar", 'If(' + ABERTO_REL + ', "Cancelar", "Voltar")', "Back()", f"{TW} - 190 - 108", y_botoes, 100, 44, primario=False),
        botao("regSalvar", '"Salvar"', "UpdateContext({locFicar: false});\n" + salvar, f"{TW} - 190", y_botoes, 190, 44, Visible=ABERTO_REL),
        C("regEspaco", RET, Fill="Color.Transparent", X="0", Y=f"({y_botoes}) + 44", Width="10", Height="24"),
    ]
    filhos = moldura(p, "scrChamados") + [
        C("regVoltar", LBL, Text=f'"‹  " & {nome_secao}', Color="corAzul", Size="10", Underline="true", X="224", Y="70", Width="300", Height="22",
          OnSelect="Back()"),
    ] + titulo(p, 'If(IsBlank(locId), "NOVO REGISTRO", "REGISTRO")',
               f'{nome_secao} & If(locReg.rlt_herdado, "   ·   Pendência herdada: a data de início original é mantida (RN-009).", "")', y=100)
    filhos += [
        # histórico só deste chamado (como no protótipo); também dá tipo (GUID) à variável locHistReg da tela Histórico
        C(f"{p}VerHist", LBL, Text='"↺  Histórico deste chamado"', Color="corAzul", Size="10", Underline="true", Align="Align.Right",
          Visible="!IsBlank(locId)", X="Parent.Width - 244", Y="112", Width="220", Height="24",
          OnSelect="Navigate(scrHistorico, ScreenTransition.None, {locHistReg: locId})"),
        C(f"{p}Pagina", GAL, variante="VariableHeight", Items="Table({b: 1})", TemplateSize="400", TemplatePadding="0",
          X="224", Y="168", Width="Parent.Width - 230", Height="Parent.Height - 172", filhos=pagina),
    ] + janela_anexo()
    return tela("scrRegistro", {"Fill": "corFundo", "OnVisible": ao_abrir}, filhos)


def janela_anexo():
    """Janela por cima da tela para anexar um arquivo (formulário de edição frmAnexo, fonte Anexos)."""
    vis = "locAnexar"
    W, H = "560", "330"
    x, y = f"(Parent.Width - {W}) / 2", f"(Parent.Height - {H}) / 2"
    out = [
        C("regJanFundo", RET, Fill="RGBA(0, 0, 0, 0.45)", X="0", Y="0", Width="Parent.Width", Height="Parent.Height", Visible=vis),
        cartao("regJanCartao", x, y, W, H, raio=12, Visible=vis),
        C("regJanAcento", RET, Fill="corVerde", X=f"{x} + 24", Y=f"{y} + 20", Width="36", Height="4", Visible=vis),
        C("regJanTit", LBL, Text='"ANEXAR FOTO OU ARQUIVO"', Color="corAzul", Size="14", FontWeight="FontWeight.Bold", Font=FONTE_TIT,
          X=f"{x} + 24", Y=f"{y} + 28", Width=f"{W} - 48", Height="30", Visible=vis),
        C("regJanSub", LBL, Text='Coalesce(locReg.rlt_titulo, "")', Color="corMuted", Size="10", X=f"{x} + 24", Y=f"{y} + 58", Width=f"{W} - 48", Height="22", Visible=vis),
    ]
    if FORM_ANEXO:
        out += FORM_ANEXO(x, y, W, vis)
    else:
        out.append(C("regJanAviso", LBL, Text='"O campo de arquivo entra quando o formulário frmAnexo for colado do Studio."', Color="corLaranjaTxt",
                     Size="10", X=f"{x} + 24", Y=f"{y} + 100", Width=f"{W} - 48", Height="60", Visible=vis))
    out.append(botao("regJanFechar", '"Cancelar"', "UpdateContext({locAnexar: false})" + ("; ResetForm(frmAnexo)" if FORM_ANEXO else ""),
                     f"{x} + {W} - 24 - 150 - 8 - 110", f"{y} + {H} - 64", 110, 40, primario=False, Visible=vis))
    return out


# Formulário de anexo, no formato que o Studio gera (Copiar código de um formulário ligado a Anexos):
# Form@2.4.4 (Classic) com cartões TypedDataCard@1.0.8; o arquivo usa o controle Attachments@2.3.0.
CARD = "TypedDataCard@1.0.8"
COR_FORM = "RGBA(197, 206, 215, 1)"


def _filhos_cartao(n, valor, nome_valor=None):
    """Rótulo, valor, mensagem de erro e asterisco, com os MetadataKey que o cartão bloqueado exige."""
    return [
        C(f"anxChave{n}", LBL, chaves={"MetadataKey": "FieldName"}, AutoHeight="true", Color="corMuted", Size="9", FontWeight="FontWeight.Bold",
          Height="24", Text="Parent.DisplayName", Width="Parent.Width - 30", Wrap="false", X="0", Y="4"),
        valor,
        C(f"anxErro{n}", LBL, chaves={"MetadataKey": "ErrorMessage"}, AutoHeight="true", Color="RGBA(138, 0, 33, 1)", Size="10", FontWeight="FontWeight.Semibold",
          Height="10", Live="Live.Assertive", PaddingBottom="0", PaddingLeft="0", PaddingRight="0", PaddingTop="0", Text="Parent.Error",
          Visible="Parent.DisplayMode = DisplayMode.Edit", Width="Parent.Width", X="0",
          Y=f"{nome_valor or f'anxValor{n}'}.Y + {nome_valor or f'anxValor{n}'}.Height"),
        C(f"anxObrig{n}", LBL, chaves={"MetadataKey": "FieldRequired"}, Align="Align.Center", Color="corVerm", Height=f"anxChave{n}.Height",
          Text='"*"', Visible="false", Width="20", Wrap="false", X="Parent.Width - 24", Y=f"anxChave{n}.Y"),
    ]


def _cartao_texto(nome, n, campo, rotulo, update, y):
    """Cartão de texto escondido, preenchido a partir do arquivo escolhido (o usuário não digita)."""
    valor = C(f"anxValor{n}", TXT, chaves={"MetadataKey": "FieldValue"}, Default="Parent.Default", DelayOutput="true", DisplayMode="Parent.DisplayMode",
              MaxLength="Parent.MaxLength", Width="Parent.Width", X="0", Y=f"anxChave{n}.Y + anxChave{n}.Height + 4")
    return C(nome, CARD, variante="ClassicTextualEdit", chaves={"IsLocked": "true"},
             DataField=f'"{campo}"', Default=f"ThisItem.{campo}", DisplayName=f'"{rotulo}"', MaxLength=f"DataSourceInfo([@Anexos], DataSourceInfo.MaxLength, {campo})",
             Required="false", Update=update, Visible="false", Width="500", X="0", Y=str(y), filhos=_filhos_cartao(n, valor))


def form_anexo(x, y, W, vis):
    escolhido = "First(anxArquivo.Attachments)"
    arquivo_valor = C("anxArquivo", "Attachments@2.3.0", chaves={"MetadataKey": "FieldValue"},
                      AddAttachmentText='"＋  Escolher foto ou arquivo"', NoAttachmentsText='"Nenhum arquivo escolhido."', MaxAttachments="1", MaxAttachmentsText='""',
                      BorderColor=f"If(IsBlank(Parent.Error), {COR_FORM}, corVerm)", DisplayMode="Parent.DisplayMode", Font=FONTE, Size="11",
                      Color="corAzul", Fill="Color.White", HoverFill="corAzul10", ItemColor="Color.White", ItemFill="corAzul", ItemHoverFill="corAzul80",
                      PressedColor="Color.White", PressedFill="corAzul", Items="Parent.Default", Height="96",
                      PaddingBottom="6", PaddingLeft="8", PaddingRight="8", PaddingTop="6", Tooltip="Parent.DisplayName",
                      Width="Parent.Width", X="0", Y="anxChave1.Y + anxChave1.Height + 4")
    cartao_arquivo = C("anxArquivoCard", CARD, variante="ClassicFileEdit", chaves={"IsLocked": "true"},
                       DataField='"rlt_arquivo"', Default="If(!IsBlank(ThisItem.Arquivo.FileName), Table({DisplayName: ThisItem.Arquivo.FileName, Value: ThisItem.Arquivo.Value}), Blank())",
                       DisplayName='"FOTO OU ARQUIVO"', Required="false", Update="anxArquivo.Attachments", Width="500", X="0", Y="0",
                       filhos=_filhos_cartao(1, arquivo_valor, "anxArquivo"))
    ao_salvar = ("Patch(Anexos, LookUp(Anexos, rlt_anexoid = frmAnexo.LastSubmit.rlt_anexoid), {rlt_registro: locReg});\n"
                 + hist('"Anexo incluído: " & frmAnexo.LastSubmit.rlt_nome', "locReg") + ";\n"
                 "UpdateContext({locAnexar: false});\nResetForm(frmAnexo);\nNotify(\"Anexo salvo.\", NotificationType.Success)")
    form = C("frmAnexo", "Form@2.4.4", variante="Classic", chaves={"Layout": "Vertical"},
             DataSource="Anexos", DefaultMode="FormMode.New", BorderColor="Color.Transparent", Visible=vis,
             X=f"{x} + 24", Y=f"{y} + 88", Width=f"{W} - 48", Height="170",
             OnSuccess=ao_salvar,
             OnFailure='Notify("Não foi possível salvar o anexo: " & frmAnexo.Error, NotificationType.Error)',
             filhos=[cartao_arquivo,
                     _cartao_texto("anxNomeCard", 2, "rlt_nome", "Nome", f'If(IsEmpty(anxArquivo.Attachments), "", {escolhido}.Name)', 1),
                     _cartao_texto("anxTipoCard", 3, "rlt_tipo", "Tipo",
                                   f'If(IsEmpty(anxArquivo.Attachments), "", Lower(Last(Split({escolhido}.Name, ".")).Value))', 2)])
    salvar = botao("regJanSalvar", '"Salvar anexo"',
                   'If(IsEmpty(anxArquivo.Attachments), Notify("Escolha uma foto ou arquivo.", NotificationType.Warning), SubmitForm(frmAnexo))',
                   f"{x} + {W} - 24 - 150", f"{y} + 330 - 64", 150, 40, Visible=vis)
    return [form, salvar]


FORM_ANEXO = form_anexo


# ================================================================== TELA HISTÓRICO
def tela_historico():
    """Histórico de alterações (RF-012, RN-021, RNF-003), em tabela como no protótipo (telaHistorico).

    Mostra as alterações do relatório atual; com locHistReg (id de um registro) mostra só as daquele registro.
    Só leitura: a tela não tem nenhuma ação que altere o histórico.
    """
    p = "his"
    reg = "LookUp(Registros, rlt_registroid = locHistReg)"
    itens = ("Sort(If(IsBlank(locHistReg), Filter(Histórico, rlt_relatorio.rlt_relatorioid = gblRel.rlt_relatorioid), "
             "Filter(Histórico, rlt_registro.rlt_registroid = locHistReg)), rlt_quando, SortOrder.Descending)")
    W = "Parent.Width - 248"
    col = {"quando": ("12", "140"), "quem": ("152", "150"), "registro": ("310", f"{W} - 310 - 230"), "campo": (f"{W} - 220", "208")}
    filhos = moldura(p, "scrHistorico") + titulo(
        p, '"HISTÓRICO DE ALTERAÇÕES"',
        f'If(IsBlank(locHistReg), "Todas as alterações do relatório", {reg}.rlt_titulo) & ". Guarda quem alterou, quando e o campo. Não pode ser alterado (RN-021, RNF-003)."')
    filhos += [
        C(f"{p}Voltar", LBL, Text='"‹  Voltar ao registro"', Color="corAzul", Size="10", Underline="true", Visible="!IsBlank(locHistReg)",
          X="Parent.Width - 224", Y="86", Width="200", Height="24", Align="Align.Right",
          OnSelect=f"Navigate(scrRegistro, ScreenTransition.None, {{locId: locHistReg, locSecao: {reg}.rlt_secao}})"),
        cartao(f"{p}Tabela", 224, 146, W, "Parent.Height - 160"),
    ]
    for chave, rot in [("quando", "QUANDO"), ("quem", "QUEM"), ("registro", "REGISTRO"), ("campo", "CAMPO")]:
        x, w = col[chave]
        filhos.append(C(f"{p}Cab{chave.capitalize()}", LBL, Text=f'"{rot}"', Color="corMuted", Size="9", FontWeight="FontWeight.Bold",
                        X=f"224 + {x}", Y="152", Width=w, Height="30"))
    filhos += [
        C(f"{p}CabLinha", RET, Fill="corLinha", X="225", Y="182", Width=f"{W} - 2", Height="2"),
        C(f"{p}Gal", GAL, variante="Vertical", Items=itens, TemplateSize="58", TemplatePadding="0",
          X="225", Y="184", Width=f"{W} - 2", Height="Parent.Height - 184 - 16",
          filhos=[
              C("hisQuando", LBL, Text='Text(ThisItem.rlt_quando, "dd/mm/yyyy hh:mm")', Color="corTexto", Size="10",
                X=col["quando"][0], Y="8", Width=col["quando"][1], Height="22"),
              C("hisQuem", LBL, Text='Coalesce(ThisItem.rlt_quem.rlt_nome, "—")', Color="corTexto", Size="10",
                X=col["quem"][0], Y="8", Width=col["quem"][1], Height="22"),
              C("hisQuemPerfil", LBL, Text='If(IsBlank(ThisItem.rlt_quem), "", Text(ThisItem.rlt_quem.rlt_perfil))', Color="corMuted", Size="9",
                X=col["quem"][0], Y="28", Width=col["quem"][1], Height="20"),
              C("hisReg", LBL, Text='If(IsBlank(ThisItem.rlt_registro), "—", Left(ThisItem.rlt_registro.rlt_titulo, 70))',
                Color="If(IsBlank(ThisItem.rlt_registro), corMuted, corAzul)", Underline="!IsBlank(ThisItem.rlt_registro)", Size="10",
                X=col["registro"][0], Y="8", Width=col["registro"][1], Height="22",
                OnSelect="If(!IsBlank(ThisItem.rlt_registro), Navigate(scrRegistro, ScreenTransition.None, {locId: ThisItem.rlt_registro.rlt_registroid, locSecao: ThisItem.rlt_registro.rlt_secao}))"),
              C("hisSecao", LBL, Text='If(IsBlank(ThisItem.rlt_registro), "", LookUp(tabSecoes, Valor = ThisItem.rlt_registro.rlt_secao).Nome)',
                Color="corMuted", Size="9", X=col["registro"][0], Y="28", Width=col["registro"][1], Height="20"),
              C("hisCampo", LBL, Text="ThisItem.rlt_campo", Color="corTexto", Size="10", FontWeight="FontWeight.Bold",
                X=col["campo"][0], Y="8", Width=col["campo"][1], Height="40", VerticalAlign="VerticalAlign.Top"),
              C("hisLinha", RET, Fill="corLinha", X="0", Y="Parent.TemplateHeight - 1", Width="Parent.TemplateWidth", Height="1"),
          ]),
        C(f"{p}Vazio", LBL, Text='"Nenhuma alteração registrada."', Color="corMuted", Size="11", Align="Align.Center",
          Visible=f"CountRows({p}Gal.AllItems) = 0", X="224", Y="220", Width=W, Height="40"),
    ]
    return tela("scrHistorico", {"Fill": "corFundo"}, filhos)


# ================================================================== TELA PAINEL GERAL
def tela_painel():
    """Painel geral de informações (RF-020, RF-021), no layout do protótipo (telaLider).

    A página é uma galeria de altura flexível com um cartão por linha: assim ela rola como no protótipo
    e cada cartão cresce com o conteúdo (controles invisíveis não contam na altura da linha).
    """
    p = "pai"
    sem_sap = f"Filter(colRegs, rlt_secao = {SEC}.'Fator Q (Z9)' && IsBlank(rlt_equipamento))"
    velhas = f"Sort(Filter(colRegs, {ABERTO} && DateDiff(rlt_inicio, Now(), TimeUnit.Days) > 7), rlt_inicio)"
    corrigir = ("If(IsBlank(paiCbx.Selected), Notify(\"Escolha o equipamento na lista.\", NotificationType.Warning),\n"
                "  Patch(Registros, LookUp(Registros, rlt_registroid = ThisItem.rlt_registroid), {rlt_equipamento: paiCbx.Selected, rlt_equipamentolivre: \"\"});\n  "
                + hist('"Código SAP corrigido: " & paiCbx.Selected.rlt_codigosap', "LookUp(Registros, rlt_registroid = ThisItem.rlt_registroid)")
                + ";\n  " + REFRESH.replace("\n", "\n  ") + ";\n  Notify(\"Corrigido: \" & paiCbx.Selected.rlt_nome, NotificationType.Success))")
    st = "Text(ThisItem.rlt_status)"
    larg_chip = f"Len({st}) * 8 + 44"
    TW = "Parent.TemplateWidth - 14"         # largura dos cartões (sobra espaço para a barra de rolagem)
    ALT_FQ, ALT_VELHA = 136, 44
    n_fq, n_velha = f"CountRows({sem_sap})", f"CountRows({velhas})"
    vis = lambda b: f"ThisItem.b = {b}"
    h1 = f"84 + If({n_fq} = 0, 40, {n_fq} * {ALT_FQ})"
    h2 = f"64 + If({n_velha} = 0, 40, {n_velha} * {ALT_VELHA} + 2) + 14"
    h3 = "262"

    def tit(nome, texto, b):
        return C(nome, LBL, Text=f'"{texto}"', Color="corAzul", Size="13", FontWeight="FontWeight.Bold", Font=FONTE_TIT,
                 X="16", Y="14", Width=f"{TW} - 200", Height="26", Visible=vis(b))

    def espaco(nome, h, b):  # espaço de 12 px entre os cartões
        return C(nome, RET, Fill="Color.Transparent", X="0", Y=h, Width="10", Height="12", Visible=vis(b))

    pagina = [
        # ---------- 1. Fator Q sem código SAP (RF-020)
        cartao("paiC1", 0, 0, TW, h1, Visible=vis(1)),
        tit("paiT1", "FATOR Q SEM CÓDIGO SAP", 1),
        chip("paiTag1", f'If({n_fq} > 0, {n_fq} & " PARA CORRIGIR", "TUDO CERTO")', f"{TW} - 150", 16, 134,
             f"If({n_fq} > 0, corVerm20, corAzul10)", f"If({n_fq} > 0, RGBA(138, 0, 33, 1), corAzul)", f"If({n_fq} > 0, corVerm20, corAzul10)",
             h=22, Visible=vis(1), RadiusTopLeft="4", RadiusTopRight="4", RadiusBottomLeft="4", RadiusBottomRight="4"),
        C("paiD1", LBL, Text='"Chamados registrados com equipamento fora da lista. Ficam sem tipo e fora da Tela 3 do dashboard até a correção (RN-017, RN-018)."',
          Color="corMuted", Size="10", X="16", Y="44", Width=f"{TW} - 32", Height="24", Visible=vis(1)),
        C("paiVazio1", LBL, Text='"Nenhum chamado sem código SAP."', Color="corMuted", Size="10", Align="Align.Center",
          X="16", Y="76", Width=f"{TW} - 32", Height="32", Visible=f"{vis(1)} && {n_fq} = 0"),
        C("paiGal1", GAL, variante="Vertical", Items=sem_sap, TemplateSize=str(ALT_FQ), TemplatePadding="0", ShowScrollbar="false",
          X="16", Y="76", Width=f"{TW} - 32", Height=f"{n_fq} * {ALT_FQ}", Visible=f"{vis(1)} && {n_fq} > 0",
          filhos=[
              cartao("paiBorda", 0, 0, "Parent.TemplateWidth", ALT_FQ - 10, fill="corVerm", borda="corVerm"),
              cartao("paiFundo", 4, 0, "Parent.TemplateWidth - 4", ALT_FQ - 10),
              chip("paiStatus", f'"●  " & Upper({st})', 18, 12, larg_chip,
                   cor_status(st, 1, "Color.White"), cor_status(st, 2, "corTexto"), cor_status(st, 3, "corLinha"), h=22),
              chip("paiSemSap", '"SEM SAP"', f"18 + {larg_chip} + 8", 13, 70, "corVerm20", "RGBA(138, 0, 33, 1)", "corVerm20", h=20,
                   RadiusTopLeft="4", RadiusTopRight="4", RadiusBottomLeft="4", RadiusBottomRight="4"),
              C("paiNome", LBL, Text="Coalesce(ThisItem.rlt_equipamentolivre, ThisItem.rlt_titulo)", Color="corTexto", Size="11", FontWeight="FontWeight.Bold",
                X="18", Y="38", Width="Parent.TemplateWidth - 36", Height="24"),
              C("paiMeta", LBL, Text='"Chamado " & ThisItem.rlt_numero & "     Início " & Text(ThisItem.rlt_inicio, "dd/mm/yyyy hh:mm")',
                Color="corMuted", Size="9", X="18", Y="60", Width="Parent.TemplateWidth - 36", Height="20"),
              C("paiCbx", CBX, Items=f"Filter(Equipamentos, rlt_tipo <> [@'Tipo de equipamento'].Bagagem && {ativo('Equipamentos')})", DisplayFields='["rlt_nome"]',
                SearchFields='["rlt_nome", "rlt_codigosap"]', SelectMultiple="false", InputTextPlaceholder='"Escolher o equipamento correto…"',
                X="18", Y="84", Width="Parent.TemplateWidth - 36 - 112", Height="36",
                DisplayMode=f"If({ABERTO_REL}, DisplayMode.Edit, DisplayMode.View)"),
              botao("paiCorrigir", '"Corrigir"', corrigir, "Parent.TemplateWidth - 18 - 100", 84, 100, 36, Size="10", Visible=ABERTO_REL),
          ]),
        espaco("paiE1", h1, 1),
        # ---------- 2. Pendências abertas há mais de 7 dias
        cartao("paiC2", 0, 0, TW, h2, Visible=vis(2)),
        tit("paiT2", "PENDÊNCIAS ABERTAS HÁ MAIS DE 7 DIAS", 2),
        C("paiVazio2", LBL, Text='"Nenhuma."', Color="corMuted", Size="10", Align="Align.Center",
          X="16", Y="58", Width=f"{TW} - 32", Height="32", Visible=f"{vis(2)} && {n_velha} = 0"),
        cartao("paiTab2", 16, 52, f"{TW} - 32", f"{n_velha} * {ALT_VELHA} + 2", raio=8, Visible=f"{vis(2)} && {n_velha} > 0"),
        C("paiGal2", GAL, variante="Vertical", Items=velhas, TemplateSize=str(ALT_VELHA), TemplatePadding="0", ShowScrollbar="false",
          X="17", Y="53", Width=f"{TW} - 34", Height=f"{n_velha} * {ALT_VELHA}", Visible=f"{vis(2)} && {n_velha} > 0",
          filhos=[
              C("paiVSecao", LBL, Text="LookUp(tabSecoes, Valor = ThisItem.rlt_secao).Nome", Color="corTexto", Size="10",
                X="12", Y="0", Width="130", Height=str(ALT_VELHA)),
              C("paiVTitulo", LBL, Text="ThisItem.rlt_titulo", Color="corAzul", Underline="true", Size="10",
                X="150", Y="0", Width="Parent.TemplateWidth - 150 - 300", Height=str(ALT_VELHA),
                OnSelect="Navigate(scrRegistro, ScreenTransition.None, {locId: ThisItem.rlt_registroid, locSecao: ThisItem.rlt_secao})"),
              C("paiVDesde", LBL, Text='"desde " & Text(ThisItem.rlt_inicio, "dd/mm/yyyy")', Color="corTexto", Size="10",
                X="Parent.TemplateWidth - 290", Y="0", Width="130", Height=str(ALT_VELHA)),
              chip("paiVStatus", f'"●  " & Upper({st})', "Parent.TemplateWidth - 12 - (" + larg_chip + ")", 11, larg_chip,
                   cor_status(st, 1, "Color.White"), cor_status(st, 2, "corTexto"), cor_status(st, 3, "corLinha"), h=22),
              C("paiVLinha", RET, Fill="corLinha", X="0", Y="Parent.TemplateHeight - 1", Width="Parent.TemplateWidth", Height="1"),
          ]),
        espaco("paiE2", h2, 2),
        # ---------- 3. Listas usadas pelo app (RF-021)
        cartao("paiC3", 0, 0, TW, h3, Visible=vis(3)),
        tit("paiT3", "LISTAS USADAS PELO APP", 3),
        cartao("paiTab3", 16, 52, f"{TW} - 32", 32 + 3 * 38 + 2, raio=8, Visible=vis(3)),
    ]
    # tabela das listas: cabeçalho e 3 linhas
    linhas = [("LISTA", "ITENS", "ORIGEM", True),
              # CountIf(..., true) conta no Dataverse; CountRows pode devolver um valor em cache (aviso do Studio)
              ('"Equipamentos (Fator Q e Preventiva)"', f"CountIf(Equipamentos, {ativo('Equipamentos')})", '"aba codigo_sap_equipamento"', False),
              ('"Locais"', f"CountIf(Locais, {ativo('Locais')})", '"aba codigo_sap"', False),
              ('"Pessoas e perfis"', f"CountIf(Pessoas, {ativo('Pessoas')})", '"aba tbl_rh"', False)]
    for i, (a, b, c, cab) in enumerate(linhas):
        yl = 52 + (0 if i == 0 else 32 + (i - 1) * 38)
        hl = 32 if cab else 38
        estilo = dict(Color="corMuted", Size="8", FontWeight="FontWeight.Bold") if cab else dict(Color="corTexto", Size="10")
        for j, (txt, xl) in enumerate([(a, "28"), (b, f"16 + ({TW} - 32) * 0.6"), (c, f"16 + ({TW} - 32) * 0.72")]):
            pagina.append(C(f"paiL{i}{j}", LBL, Text=f'"{txt}"' if cab else txt, X=xl, Y=str(yl), Width=f"({TW} - 32) * 0.3", Height=str(hl),
                            Visible=vis(3), **estilo))
        if i < 3:
            pagina.append(C(f"paiL{i}Linha", RET, Fill="corLinha", X="17", Y=str(yl + hl), Width=f"{TW} - 34", Height="2" if cab else "1", Visible=vis(3)))
    pagina += [
        botao("paiAtualizar", '"Atualizar listas"', 'Navigate(scrListas, ScreenTransition.None)',
              16, 52 + 32 + 3 * 38 + 14, 140, 34, primario=False, Size="10", Visible=f"{vis(3)} && {LIDER}"),
        C("paiSoLider", LBL, Text='"Só o líder atualiza as listas."', Color="corMuted", Size="9",
          X="16", Y=str(52 + 32 + 3 * 38 + 14), Width="300", Height="34", Visible=f"{vis(3)} && !{LIDER}"),
        espaco("paiE3", h3, 3),
    ]
    pagina += cartao_avisos(TW, vis, tit, espaco)
    filhos = moldura(p, "scrPainel") + titulo(p, '"PAINEL GERAL DE INFORMAÇÕES"', '"Correções, pendências antigas, listas do app e avisos. Todos os usuários podem ver."')
    filhos.append(C(f"{p}Pagina", GAL, variante="VariableHeight", Items="Table({b: 1}, {b: 2}, {b: 3}, {b: 4})", TemplateSize="100", TemplatePadding="0",
                    X="224", Y="146", Width="Parent.Width - 230", Height="Parent.Height - 150", filhos=pagina))
    filhos += janela_aviso()
    return tela("scrPainel", {"Fill": "corFundo", "OnVisible": REFRESH + ";\nUpdateContext({locJanAviso: \"\"})"}, filhos)


# ---------- Avisos do Painel geral (decisão de 25/11/2026): todos publicam, atualizam e excluem
AVISOS = "Sort(Avisos, rlt_publicadoem, SortOrder.Descending)"
N_AVISOS = "CountIf(Avisos, true)"


def cartao_avisos(TW, vis, tit, espaco):
    ALT = 132
    n = N_AVISOS
    h4 = f"64 + If({n} = 0, 40, {n} * {ALT}) + 14"
    abrir_novo = 'UpdateContext({locAviso: Blank(), locJanAviso: "editar"}); Reset(avTitulo); Reset(avTexto)'
    return [
        cartao("paiC4", 0, 0, TW, h4, Visible=vis(4)),
        tit("paiT4", "AVISOS", 4),
        botao("paiNovoAviso", '"＋  Novo aviso"', abrir_novo, f"{TW} - 16 - 140", 12, 140, 32, primario=False, Size="10",
              Visible=vis(4)),
        C("paiVazio4", LBL, Text='"Nenhum aviso."', Color="corMuted", Size="10", Align="Align.Center",
          X="16", Y="58", Width=f"{TW} - 32", Height="32", Visible=f"{vis(4)} && {n} = 0"),
        C("paiGal4", GAL, variante="Vertical", Items=AVISOS, TemplateSize=str(ALT), TemplatePadding="0", ShowScrollbar="false",
          X="16", Y="52", Width=f"{TW} - 32", Height=f"{n} * {ALT}", Visible=f"{vis(4)} && {n} > 0",
          filhos=[
              cartao("paiAvBorda", 0, 0, "Parent.TemplateWidth", ALT - 10, fill="corLaranja", borda="corLaranja"),
              cartao("paiAvFundo", 4, 0, "Parent.TemplateWidth - 4", ALT - 10),
              C("paiAvTit", LBL, Text="ThisItem.rlt_titulo", Color="corTexto", Size="11", FontWeight="FontWeight.Bold",
                X="18", Y="8", Width="Parent.TemplateWidth - 36 - 190", Height="26"),
              C("paiAvTexto", LBL, Text="ThisItem.rlt_texto", Color="corTexto", Size="10", VerticalAlign="VerticalAlign.Top",
                X="18", Y="36", Width="Parent.TemplateWidth - 36", Height="56"),
              C("paiAvMeta", LBL, Color="corMuted", Size="9", X="18", Y=str(ALT - 10 - 28), Width="Parent.TemplateWidth - 36", Height="22",
                Text=('"Publicado por " & Coalesce(ThisItem.rlt_autor.rlt_nome, "—") & " em " & Text(ThisItem.rlt_publicadoem, "dd/mm/yyyy hh:mm") & '
                      'If(DateDiff(ThisItem.rlt_publicadoem, ThisItem.modifiedon, TimeUnit.Minutes) > 1, "   ·   atualizado em " & Text(ThisItem.modifiedon, "dd/mm/yyyy hh:mm"), "")')),
              C("paiAvEditar", LBL, Text='"Atualizar"', Color="corAzul", Underline="true", Size="10", Align="Align.Right",
                X="Parent.TemplateWidth - 200", Y="8", Width="90", Height="26",
                OnSelect='UpdateContext({locAviso: ThisItem, locJanAviso: "editar"}); Reset(avTitulo); Reset(avTexto)'),
              C("paiAvExcluir", LBL, Text='"Excluir"', Color="RGBA(138, 0, 33, 1)", Underline="true", Size="10", Align="Align.Right",
                X="Parent.TemplateWidth - 100", Y="8", Width="84", Height="26",
                OnSelect='UpdateContext({locAviso: ThisItem, locJanAviso: "excluir"})'),
          ]),
        espaco("paiE4", h4, 4),
    ]


def janela_aviso():
    """Janela por cima do Painel: publicar/atualizar (locJanAviso = "editar") ou confirmar a exclusão ("excluir")."""
    ed, ex = 'locJanAviso = "editar"', 'locJanAviso = "excluir"'
    vis = f"{ed} || {ex}"
    W = "620"
    H = f'If({ex}, 230, 420)'
    x, y = f"(Parent.Width - {W}) / 2", f"(Parent.Height - ({H})) / 2"
    registro = "LookUp(Avisos, rlt_avisoid = locAviso.rlt_avisoid)"
    salvar = (
        'If(IsBlank(Trim(avTitulo.Text)), Notify("Informe o título do aviso.", NotificationType.Warning),\n'
        '  If(IsBlank(locAviso),\n'
        '    Patch(Avisos, Defaults(Avisos), {rlt_titulo: Trim(avTitulo.Text), rlt_texto: avTexto.Text, rlt_publicadoem: Now(), rlt_autor: gblUsuario}),\n'
        f'    Patch(Avisos, {registro}, {{rlt_titulo: Trim(avTitulo.Text), rlt_texto: avTexto.Text}}));\n'
        '  ' + hist('"Aviso " & If(IsBlank(locAviso), "publicado", "atualizado") & ": " & Trim(avTitulo.Text)') + ';\n'
        '  Notify(If(IsBlank(locAviso), "Aviso publicado.", "Aviso atualizado."), NotificationType.Success);\n'
        '  UpdateContext({locJanAviso: ""}))')
    excluir = (f'Remove(Avisos, {registro});\n'
               + hist('"Aviso excluído: " & locAviso.rlt_titulo') + ';\n'
               'Notify("Aviso excluído.", NotificationType.Success);\nUpdateContext({locJanAviso: ""})')
    campo = dict(BorderColor="RGBA(197, 206, 215, 1)", BorderThickness="1", FocusedBorderColor="corVerde", FocusedBorderThickness="2",
                 Size="11", Color="corTexto", PaddingLeft="12", RadiusTopLeft="8", RadiusTopRight="8", RadiusBottomLeft="8", RadiusBottomRight="8")
    return [
        C("avJanFundo", RET, Fill="RGBA(0, 0, 0, 0.45)", X="0", Y="0", Width="Parent.Width", Height="Parent.Height", Visible=vis),
        cartao("avJanCartao", x, y, W, H, raio=12, Visible=vis),
        C("avJanAcento", RET, Fill="corVerde", X=f"{x} + 24", Y=f"{y} + 20", Width="36", Height="4", Visible=vis),
        C("avJanTit", LBL, Text=f'If({ex}, "EXCLUIR AVISO", IsBlank(locAviso), "NOVO AVISO", "ATUALIZAR AVISO")', Color="corAzul", Size="14",
          FontWeight="FontWeight.Bold", Font=FONTE_TIT, X=f"{x} + 24", Y=f"{y} + 28", Width=f"{W} - 48", Height="30", Visible=vis),
        # editar
        rotulo("avRotTitulo", '"TÍTULO *"', f"{x} + 24", f"{y} + 72", vis=ed),
        C("avTitulo", TXT, Default="locAviso.rlt_titulo", MaxLength="200", X=f"{x} + 24", Y=f"{y} + 96", Width=f"{W} - 48", Height="40", Visible=ed, **campo),
        rotulo("avRotTexto", '"TEXTO"', f"{x} + 24", f"{y} + 146", vis=ed),
        C("avTexto", TXT, Default="locAviso.rlt_texto", Mode="TextMode.MultiLine", MaxLength="4000", X=f"{x} + 24", Y=f"{y} + 170",
          Width=f"{W} - 48", Height="150", Visible=ed, **campo),
        botao("avSalvar", 'If(IsBlank(locAviso), "Publicar", "Salvar")', salvar, f"{x} + {W} - 24 - 150", f"{y} + ({H}) - 64", 150, 40, Visible=ed),
        # excluir
        C("avExTexto", LBL, Text='"Excluir o aviso “" & locAviso.rlt_titulo & "”? Ele sai do Painel para todos."', Color="corTexto", Size="11",
          X=f"{x} + 24", Y=f"{y} + 72", Width=f"{W} - 48", Height="60", Visible=ex),
        botao("avExcluir", '"Excluir"', excluir, f"{x} + {W} - 24 - 150", f"{y} + ({H}) - 64", 150, 40, Visible=ex,
              Fill="RGBA(138, 0, 33, 1)", BorderColor="RGBA(138, 0, 33, 1)", HoverFill="corVerm"),
        botao("avCancelar", '"Cancelar"', 'UpdateContext({locJanAviso: ""})', f"{x} + {W} - 24 - 150 - 8 - 120", f"{y} + ({H}) - 64", 120, 40,
              primario=False, Visible=vis),
    ]


# ================================================================== TELA FECHAR
DESTINATARIOS_RN005 = ("Manutencao_Civil_SBBR@inframerica.aero; SupervisoresBHS@inframerica.aero; eletroeletronica@inframerica.aero; "
                       "Eletromecanica@inframerica.aero; WCirilo@inframerica.aero; JValadao@inframerica.aero; admcomercial@inframerica.aero; "
                       "NCampos@inframerica.aero; LideresVip_SBBR@inframerica.aero; LideresAtendimento_SBBR@inframerica.aero")


def tela_fechar():
    """Fechar relatório (RF-013 a RF-016), no layout do protótipo (telaFechar).

    Página rolável (galeria de altura flexível, um cartão por linha): equipe, resumo, campos a conferir,
    o que acontece ao confirmar e a confirmação. O envio é feito pelo fluxo "RLT – Fechar e enviar",
    que grava o resultado em rlt_resultadoenvio; esta tela mostra esse resultado.
    """
    p = "fec"
    aberto_rel = ABERTO_REL
    # ---- campos a conferir (RN-008: não impedem o fechamento)
    corretiva = 'LookUp(tabSecoes, Valor = rlt_secao).Tipo = "corretiva"'
    sem_local = f"Filter(colRegs, {corretiva} && IsBlank(rlt_local))"
    fq_sem_sap = f"Filter(colRegs, rlt_secao = {SEC}.'Fator Q (Z9)' && IsBlank(rlt_equipamento))"
    ios_sem_motivo = (f"Filter(colRegs, (If(rlt_secao = {SEC}.'IOS informados', rlt_statusios = {SI}.Cancelado, rlt_status = {ST}.CANCELADO)) "
                      f"&& IsBlank(Trim(rlt_motivocancelamento)))")
    sem_tec = "CountRows(Filter(colEquipe, rlt_perfil = [@Perfil].'Técnico(a)')) = 0"
    sem_op = "CountRows(Filter(colEquipe, rlt_perfil = [@Perfil].'Operador(a)')) = 0"
    n_avisos = (f"(If({sem_tec}, 1, 0) + If({sem_op}, 1, 0) + CountRows({sem_local}) + CountRows({fq_sem_sap}) + CountRows({ios_sem_motivo}))")
    avisos = (f'If({sem_tec}, "•  Nenhum técnico fez login neste plantão." & Char(10), "") & '
              f'If({sem_op}, "•  Nenhum operador fez login neste plantão." & Char(10), "") & '
              f'Concat({sem_local}, "•  " & LookUp(tabSecoes, Valor = rlt_secao).Nome & ": “" & Left(rlt_titulo, 50) & "” sem local." & Char(10)) & '
              f'Concat({fq_sem_sap}, "•  Fator Q: chamado " & rlt_numero & " sem código SAP (vai sem tipo para o dashboard)." & Char(10)) & '
              f'Concat({ios_sem_motivo}, "•  " & If(rlt_secao = {SEC}.\'IOS informados\', "IOS " & rlt_numero, '
              f'LookUp(tabSecoes, Valor = rlt_secao).Nome & ": “" & Left(rlt_titulo, 50) & "”") & " cancelado sem motivo." & Char(10))')
    # ---- ações (mesma lógica de antes)
    fechar = (f"Patch(Relatórios, LookUp(Relatórios, rlt_relatorioid = gblRel.rlt_relatorioid), {{rlt_situacao: {SIT}.Fechado, rlt_fechadoem: Now(), rlt_fechadopor: gblUsuario}});\n"
              + hist('"Relatório fechado e enviado"') + ";\n"
              "Set(gblRel, LookUp(Relatórios, rlt_relatorioid = gblRel.rlt_relatorioid));\n"
              "Reset(fecConf);\n"
              "Notify(\"Relatório fechado. O PDF e o e-mail estão sendo enviados: o resultado aparece nesta tela em cerca de 1 minuto.\", NotificationType.Success)")
    atualizar = "If(!IsBlank(gblRel), Refresh(Relatórios); Set(gblRel, LookUp(Relatórios, rlt_relatorioid = gblRel.rlt_relatorioid)))"
    falhou = 'StartsWith(Coalesce(gblRel.rlt_resultadoenvio, ""), "FALHA")'
    turno_nome = 'If(Text(gblRel.rlt_turno) = "ALFA", "Alfa", "Bravo")'
    data_ponto = 'Text(gblRel.rlt_data, "dd.mm.yyyy")'
    prox = ('If(Text(gblRel.rlt_turno) = "ALFA", "BRAVO " & Text(DateAdd(gblRel.rlt_data, 1, TimeUnit.Days), "dd.mm.yyyy"), '
            '"ALFA " & Text(gblRel.rlt_data, "dd.mm.yyyy"))')
    n_abertos = f"CountRows(Filter(colRegs, {ABERTO}))"

    TW = "Parent.TemplateWidth - 14"
    # avisos (3) e "o que acontece" (4) só existem com o relatório aberto; fechado, a página mostra equipe, resumo e resultado
    vis = lambda b: f"ThisItem.b = {b}" + (f" && {aberto_rel}" if b in (3, 4) else "")
    n_eq = "CountRows(colEquipe)"
    h1 = f"52 + Max(1, RoundUp({n_eq} / 5, 0)) * 50 + 30 + 10"
    h2 = 52 + 76 + 12 + 8 * 38 + 2 + 16
    h3 = f"If({n_avisos} = 0, 48, 58 + {n_avisos} * 20 + 10)"
    h4 = 470
    h5 = f"If({aberto_rel}, 112, 118)"

    def tit(nome, texto, b):
        return C(nome, LBL, Text=f'"{texto}"', Color="corAzul", Size="13", FontWeight="FontWeight.Bold", Font=FONTE_TIT,
                 X="16", Y="14", Width=f"{TW} - 32", Height="26", Visible=vis(b))

    def rot(nome, texto, y, b):
        return C(nome, LBL, Text=f'"{texto}"', Color="corMuted", Size="9", FontWeight="FontWeight.Bold", X="16", Y=str(y), Width="400", Height="20", Visible=vis(b))

    def espaco(nome, h, b):
        return C(nome, RET, Fill="Color.Transparent", X="0", Y=str(h), Width="10", Height="12", Visible=vis(b))

    pagina = [
        # ---------- 1. Equipe que vai no PDF
        cartao("fecC1", 0, 0, TW, h1, Visible=vis(1)),
        tit("fecT1", "EQUIPE QUE VAI NO PDF", 1),
        C("fecEqVazio", LBL, Text='"Ninguém da equipe fez login."', Color="corMuted", Size="10", X="16", Y="52", Width="400", Height="40",
          Visible=f"{vis(1)} && {n_eq} = 0"),
        C("fecGalEq", GAL, variante="Vertical", Items="Sort(colEquipe, rlt_nome)", WrapCount="5", TemplateSize="50", TemplatePadding="0", ShowScrollbar="false",
          X="12", Y="50", Width=f"{TW} - 24", Height=f"Max(1, RoundUp({n_eq} / 5, 0)) * 50", Visible=f"{vis(1)} && {n_eq} > 0",
          filhos=[
              cartao("fecEqPilula", 4, 4, "Parent.TemplateWidth - 12", 42, raio=21),
              avatar("fecEqAvatar", "ThisItem.rlt_nome", 10, 11, d=28),
              C("fecEqNome", LBL, Text="ThisItem.rlt_nome", Color="corTexto", Size="10", FontWeight="FontWeight.Bold", X="44", Y="7", Width="Parent.TemplateWidth - 60", Height="18"),
              C("fecEqPerfil", LBL, Text="Text(ThisItem.rlt_perfil)", Color="corMuted", Size="8", X="44", Y="25", Width="Parent.TemplateWidth - 60", Height="16"),
          ]),
        C("fecEqNota", LBL, Text='"Para corrigir a equipe, volte ao Relatório."', Color="corTexto", Size="10",
          X="16", Y=f"52 + Max(1, RoundUp({n_eq} / 5, 0)) * 50 + 4", Width="400", Height="22", Visible=vis(1),
          OnSelect="Navigate(scrRelatorio, ScreenTransition.None)"),
        espaco("fecE1", h1, 1),
        # ---------- 2. Resumo
        cartao("fecC2", 0, 0, TW, h2, Visible=vis(2)),
        tit("fecT2", "RESUMO", 2),
    ]
    for i, (rotulo_kpi, conta) in enumerate([("Registros", "CountRows(colRegs)"), ("Passam ao próximo turno", n_abertos),
                                             ("Fator Q sem SAP", f"CountRows({fq_sem_sap})")]):
        x = f"16 + {i} * (({TW} - 32 - 24) / 3 + 12)"
        w = f"({TW} - 32 - 24) / 3"
        pagina += [
            cartao(f"fecKpi{i}", x, 52, w, 76, Visible=vis(2)),
            C(f"fecKpiNum{i}", LBL, Text=conta, Color="corAzul", Size="20", FontWeight="FontWeight.Bold", X=f"{x} + 14", Y="58", Width=f"{w} - 20", Height="34", Visible=vis(2)),
            C(f"fecKpiRot{i}", LBL, Text=f'"{rotulo_kpi}"', Color="corMuted", Size="10", X=f"{x} + 14", Y="94", Width=f"{w} - 20", Height="24", Visible=vis(2)),
        ]
    pagina += [
        cartao("fecTabSec", 16, 140, f"{TW} - 32", 8 * 38 + 2, raio=8, Visible=vis(2)),
        C("fecGalSec", GAL, variante="Vertical", Items="tabSecoes", TemplateSize="38", TemplatePadding="0", ShowScrollbar="false",
          X="17", Y="141", Width=f"{TW} - 34", Height=str(8 * 38), Visible=vis(2),
          filhos=[
              C("fecSecNome", LBL, Text="ThisItem.Nome", Color="corTexto", Size="10", X="12", Y="0", Width="Parent.TemplateWidth - 100", Height="38"),
              C("fecSecQtd", LBL, Text="CountRows(Filter(colRegs, rlt_secao = ThisItem.Valor))", Color="corTexto", Size="10", FontWeight="FontWeight.Bold",
                Align="Align.Right", X="Parent.TemplateWidth - 92", Y="0", Width="80", Height="38"),
              C("fecSecLinha", RET, Fill="corLinha", X="0", Y="37", Width="Parent.TemplateWidth", Height="1", Visible="ThisItem.Ordem < 8"),
          ]),
        espaco("fecE2", h2, 2),
        # ---------- 3. Campos a conferir (RN-008)
        cartao("fecC3", 0, 0, TW, h3, fill=f"If({n_avisos} = 0, RGBA(227, 242, 218, 1), RGBA(255, 246, 232, 1))",
               borda=f"If({n_avisos} = 0, RGBA(191, 226, 168, 1), RGBA(247, 201, 140, 1))", Visible=f"{vis(3)} && {aberto_rel}"),
        C("fecAvTit", LBL, Color=f"If({n_avisos} = 0, RGBA(47, 98, 20, 1), corLaranjaTxt)", Size="11", FontWeight="FontWeight.Bold",
          X="16", Y="12", Width=f"{TW} - 32", Height="24", Visible=f"{vis(3)} && {aberto_rel}",
          Text=f'If({n_avisos} = 0, "✓   Nenhum campo vazio encontrado.", "⚠   " & {n_avisos} & " campo(s) a conferir.")'),
        C("fecAvSub", LBL, Text='"Campos vazios não impedem o fechamento (RN-008, a confirmar), mas o PDF sai assim:"', Color="corLaranjaTxt", Size="10",
          X="44", Y="34", Width=f"{TW} - 60", Height="22", Visible=f"{vis(3)} && {aberto_rel} && {n_avisos} > 0"),
        C("fecAvLista", LBL, Text=avisos, Color="corLaranjaTxt", Size="10", VerticalAlign="VerticalAlign.Top",
          X="44", Y="58", Width=f"{TW} - 60", Height=f"{n_avisos} * 20 + 4", Visible=f"{vis(3)} && {aberto_rel} && {n_avisos} > 0"),
        espaco("fecE3", h3, 3),
        # ---------- 4. O que acontece ao confirmar
        cartao("fecC4", 0, 0, TW, h4, Visible=f"{vis(4)} && {aberto_rel}"),
        tit("fecT4", "O QUE ACONTECE AO CONFIRMAR", 4),
        rot("fecRotPdf", "PDF", 50, 4),
        C("fecPdf", LBL, Text='gblRel.rlt_nome & ".pdf"', Color="corTexto", Size="11", FontWeight="FontWeight.Bold", X="16", Y="70", Width=f"{TW} - 32", Height="24",
          Visible=f"{vis(4)} && {aberto_rel}"),
        rot("fecRotEmail", "E-MAIL PARA OS DESTINATÁRIOS DA RN-005", 104, 4),
        cartao("fecEmail", 16, 126, f"{TW} - 32", 196, raio=8, Visible=f"{vis(4)} && {aberto_rel}"),
        C("fecParaRot", LBL, Text='"Para"', Color="corMuted", Size="10", FontWeight="FontWeight.Bold", X="28", Y="134", Width="70", Height="22", Visible=f"{vis(4)} && {aberto_rel}"),
        C("fecPara", LBL, Text=f'"{DESTINATARIOS_RN005}"', Color="corTexto", Size="10", VerticalAlign="VerticalAlign.Top",
          X="100", Y="136", Width=f"{TW} - 32 - 96", Height="42", Visible=f"{vis(4)} && {aberto_rel}"),
        C("fecEmailL1", RET, Fill="corLinha", X="17", Y="182", Width=f"{TW} - 34", Height="1", Visible=f"{vis(4)} && {aberto_rel}"),
        C("fecAssuntoRot", LBL, Text='"Assunto"', Color="corMuted", Size="10", FontWeight="FontWeight.Bold", X="28", Y="186", Width="70", Height="30", Visible=f"{vis(4)} && {aberto_rel}"),
        C("fecAssunto", LBL, Text=f'"Relatório de Passagem do Turno " & {turno_nome} & " do CCM - " & {data_ponto}', Color="corTexto", Size="10",
          X="100", Y="186", Width=f"{TW} - 32 - 96", Height="30", Visible=f"{vis(4)} && {aberto_rel}"),
        C("fecEmailL2", RET, Fill="corLinha", X="17", Y="218", Width=f"{TW} - 34", Height="1", Visible=f"{vis(4)} && {aberto_rel}"),
        C("fecCorpo", LBL, Color="corTexto", Size="10", VerticalAlign="VerticalAlign.Top", X="28", Y="226", Width=f"{TW} - 56", Height="92",
          Visible=f"{vis(4)} && {aberto_rel}",
          Text=f'"Prezados," & Char(10) & Char(10) & "Encaminho, em anexo, o Relatório de Passagem do Turno " & {turno_nome} & " do CCM, referente ao dia " & {data_ponto} & "." & Char(10) & Char(10) & "Atenciosamente,"'),
        C("fecNotaTeste", LBL, Text='"Nos testes, o e-mail vai só para quem está na variável de ambiente RLT – Destinatários do e-mail."',
          Color="corMuted", Size="9", X="16", Y="326", Width=f"{TW} - 32", Height="20", Visible=f"{vis(4)} && {aberto_rel}"),
        rot("fecRotArq", "ARQUIVO", 354, 4),
        C("fecArq", LBL, Text='"Pasta RLT-CCM /" & Text(gblRel.rlt_data, "yyyy") & "/" & Text(gblRel.rlt_data, "mm") & "/ no OneDrive (PDF)"',
          Color="corTexto", Size="11", X="16", Y="374", Width=f"{TW} - 32", Height="24", Visible=f"{vis(4)} && {aberto_rel}"),
        rot("fecRotProx", "PRÓXIMO TURNO", 408, 4),
        C("fecProx", LBL, Text=f'{prox} & " recebe " & {n_abertos} & " pendência(s) com a data de início original."',
          Color="corTexto", Size="11", X="16", Y="428", Width=f"{TW} - 32", Height="24", Visible=f"{vis(4)} && {aberto_rel}"),
        espaco("fecE4", h4, 4),
        # ---------- 5. Confirmação (aberto) ou resultado do envio (fechado)
        cartao("fecC5", 0, 0, TW, f"If({aberto_rel}, 100, 106)", Visible=f"{vis(5)} && {aberto_rel}"),
        C("fecConf", CHK, Text='"Eu, " & Coalesce(gblUsuario.rlt_nome, User().FullName) & ", confirmo que revisei o relatório e quero fechar e enviar. Depois do envio o PDF não pode ser alterado."',
          X="16", Y="12", Width=f"{TW} - 32", Height="36", Size="10", Visible=f"{vis(5)} && {aberto_rel}"),
        botao("fecBtn", '"➤  Fechar e enviar"', fechar, f"{TW} - 16 - 170", 52, 170, 40, Visible=f"{vis(5)} && {aberto_rel}",
              DisplayMode="If(fecConf.Value, DisplayMode.Edit, DisplayMode.Disabled)", DisabledFill="RGBA(153, 175, 193, 1)",
              DisabledColor="Color.White", DisabledBorderColor="RGBA(153, 175, 193, 1)"),
        cartao("fecFechadoFundo", 0, 0, TW, 106, fill=f"If({falhou}, corVerm20, corAzul10)", borda=f"If({falhou}, RGBA(231, 163, 179, 1), RGBA(204, 215, 224, 1))",
               Visible=f"{vis(5)} && Not({aberto_rel})"),
        C("fecFechado", LBL, Visible=f"{vis(5)} && Not({aberto_rel})", Size="11", PaddingLeft="16", PaddingTop="12", VerticalAlign="VerticalAlign.Top",
          X="0", Y="0", Width=TW, Height="106", Color=f"If({falhou}, RGBA(138, 0, 33, 1), corAzul)", OnSelect=atualizar,
          Text='If(IsBlank(gblRel), "Nenhum relatório.", "Relatório fechado em " & Text(gblRel.rlt_fechadoem, "dd/mm/yyyy hh:mm") & " por " & Coalesce(gblRel.rlt_fechadopor.rlt_nome, "—") & "." & Char(10) & '
               'If(IsBlank(gblRel.rlt_resultadoenvio), "PDF e e-mail: envio em andamento. Toque aqui para atualizar.", '
               '"PDF e e-mail: " & gblRel.rlt_resultadoenvio) & Char(10) & "Abra o próximo plantão na tela Relatório.")'),
        espaco("fecE5", h5, 5),
    ]
    titulo_sub = '"Qualquer usuário pode fechar e enviar (RN-007, alteração de 19/11). O envio fica registrado com o nome de quem enviou."'
    filhos = moldura(p, "scrFechar") + titulo(p, '"FECHAR RELATÓRIO"', titulo_sub)
    # Relatório diário da Eletromecânica: o Bravo envia às 24:00 (decisão de 25/11/2026)
    filhos.append(botao(f"{p}Eletro", '"Relatório da Eletromecânica  ›"', "Navigate(scrEletro, ScreenTransition.None)",
                        "Parent.Width - 24 - 230", 86, 230, 40, primario=False, Size="10"))
    filhos.append(C(f"{p}Pagina", GAL, variante="VariableHeight", Items="Table({b: 1}, {b: 2}, {b: 3}, {b: 4}, {b: 5})", TemplateSize="60", TemplatePadding="0",
                    X="224", Y="146", Width="Parent.Width - 230", Height="Parent.Height - 150", filhos=pagina))
    return tela("scrFechar", {"Fill": "corFundo", "OnVisible": atualizar + ";\n" + REFRESH}, filhos)


# ================================================================== TELA ABRIR PLANTÃO
def tela_abrir():
    p = "abr"
    ao_abrir = ("UpdateContext({locProxTurno: If(IsBlank(gblRel), If(Hour(Now()) >= 7 && Hour(Now()) < 19, \"ALFA\", \"BRAVO\"), "
                "If(Text(gblRel.rlt_turno) = \"ALFA\", \"BRAVO\", \"ALFA\"))});\n"
                "UpdateContext({locProxData: If(IsBlank(gblRel), If(Hour(Now()) >= 19, DateAdd(Today(), 1, TimeUnit.Days), Today()), "
                "If(Text(gblRel.rlt_turno) = \"ALFA\", DateAdd(gblRel.rlt_data, 1, TimeUnit.Days), gblRel.rlt_data))});\n"
                + REFRESH + ";\nReset(abrTurno); Reset(abrData)")
    vT = 'If(abrTurno.Selected.Value = "ALFA", [@Turno].ALFA, [@Turno].BRAVO)'
    abrir = f"""With({{vT: {vT}, vD: abrData.SelectedDate}},
  With({{vIni: If(abrTurno.Selected.Value = "ALFA", DateAdd(vD, 7, TimeUnit.Hours), DateAdd(DateAdd(vD, -1, TimeUnit.Days), 19, TimeUnit.Hours)),
         vFim: If(abrTurno.Selected.Value = "ALFA", DateAdd(vD, 19, TimeUnit.Hours), DateAdd(vD, 7, TimeUnit.Hours))}},
    ClearCollect(colHerdar, Filter(colRegs, {ABERTO}));
    Set(gblRel, Patch(Relatórios, Defaults(Relatórios), {{rlt_nome: "RLT-PASSAGEM DE TURNO " & abrTurno.Selected.Value & " " & Text(vD, "dd.mm.yyyy"),
      rlt_turno: vT, rlt_data: vD, rlt_inicio: vIni, rlt_fim: vFim, rlt_situacao: {SIT}.Aberto}}));
    ForAll(colHerdar As r,
      Patch(Registros, Defaults(Registros), {{rlt_titulo: r.rlt_titulo, rlt_secao: r.rlt_secao, rlt_relatorio: gblRel, rlt_descricao: r.rlt_descricao,
        rlt_local: r.rlt_local, rlt_equipamento: r.rlt_equipamento, rlt_equipamentolivre: r.rlt_equipamentolivre, rlt_numero: r.rlt_numero,
        rlt_inicio: r.rlt_inicio, rlt_ni: r.rlt_ni, rlt_status: r.rlt_status, rlt_statusios: r.rlt_statusios, rlt_chamadofalso: r.rlt_chamadofalso,
        rlt_limpezatecnica: r.rlt_limpezatecnica, rlt_motivocancelamento: r.rlt_motivocancelamento, rlt_herdado: true,
        rlt_origem: LookUp(Registros, rlt_registroid = r.rlt_registroid)}}));
    If(!IsBlank(gblUsuario),
      Patch('Equipe do plantão', Defaults('Equipe do plantão'), {{rlt_nome: gblUsuario.rlt_nome, rlt_pessoa: gblUsuario, rlt_relatorio: gblRel,
        rlt_perfil: gblUsuario.rlt_perfil, rlt_entrouem: Now()}}));
    {hist('"Relatório aberto com " & CountRows(colHerdar) & " pendência(s) herdada(s)"')};
    Notify("Relatório " & abrTurno.Selected.Value & " " & Text(vD, "dd.mm.yyyy") & " aberto com " & CountRows(colHerdar) & " pendência(s) herdada(s).", NotificationType.Success);
    Navigate(scrRelatorio, ScreenTransition.None)
  )
)"""
    filhos = moldura(p, "scrRelatorio") + titulo(p, '"ABRIR PLANTÃO"', '"O relatório é criado no início do plantão (RF-001). A equipe entra pelo login de cada pessoa."')
    filhos += [
        rotulo(f"{p}RotTurno", '"TURNO *"', 224, 156), rotulo(f"{p}RotData", '"DATA DO RELATÓRIO *"', 424, 156),
        C("abrTurno", DDL, Items='["ALFA", "BRAVO"]', Default="locProxTurno", X="224", Y="178", Width="180", Height="40"),
        C("abrData", DTP, DefaultDate="locProxData", Format='"dd/mm/yyyy"', X="424", Y="178", Width="220", Height="40"),
        C(f"{p}Ajuda", LBL, Color="corMuted", Size="11", X="224", Y="226", Width="Parent.Width - 248", Height="44",
          Text='If(abrTurno.Selected.Value = "ALFA", "ALFA: 07:00 às 19:00 do mesmo dia.", "BRAVO: 19:00 do dia anterior às 07:00 desta data. O Bravo usa a data em que o plantão termina (RN-003).")'),
        C(f"{p}Herd", LBL, Color="corTexto", Size="12", Fill="Color.White", PaddingLeft="16", X="224", Y="280", Width="Parent.Width - 248", Height="56",
          Text=f'"Pendências herdadas: " & CountRows(Filter(colRegs, {ABERTO})) & ". Entram com a data de início original (RN-009)."'),
        C(f"{p}Aviso", LBL, Visible=ABERTO_REL, Color="corLaranjaTxt", Fill="corLaranja20", Size="12", PaddingLeft="16", X="224", Y="346", Width="Parent.Width - 248", Height="48",
          Text='"O relatório " & gblRel.rlt_nome & " ainda está aberto. Feche-o antes de abrir o próximo."'),
        botao(f"{p}Btn", '"Abrir relatório"', abrir, "Parent.Width - 210", "Parent.Height - 70", 190, 48,
              DisplayMode=f"If({ABERTO_REL} || IsBlank(abrData.SelectedDate), DisplayMode.Disabled, DisplayMode.Edit)"),
        botao(f"{p}Voltar", '"Voltar"', "Back()", "Parent.Width - 410", "Parent.Height - 70", 180, 48, primario=False),
    ]
    return tela("scrAbrir", {"Fill": "corFundo", "OnVisible": ao_abrir}, filhos)


# ================================================================== TELA LISTAS (RF-021)
# Abas: tabela do Dataverse, rótulo, coluna da chave e colunas da grade (rótulo, fórmula, largura relativa)
ABAS = [
    ("eq", "Equipamentos", "Equipamentos", "rlt_equipamentoid", "locEq",
     [("DESCRIÇÃO", "ThisItem.rlt_nome", 0.46), ("CÓDIGO SAP", "ThisItem.rlt_codigosap", 0.16), ("TIPO", "Text(ThisItem.rlt_tipo)", 0.16)]),
    ("loc", "Locais", "Locais", "rlt_localid", "locLoc",
     [("LOCAL ESPECÍFICO", "ThisItem.rlt_nome", 0.34), ("CÓDIGO SAP", "ThisItem.rlt_codigosap", 0.14), ("ÁREA", "ThisItem.rlt_area", 0.2),
      ("LADO", "ThisItem.rlt_lado", 0.1)]),
    ("pes", "Pessoas e perfis", "Pessoas", "rlt_pessoaid", "locPes",
     [("NOME", "ThisItem.rlt_nome", 0.28), ("CARGO", "ThisItem.rlt_cargo", 0.2), ("PERFIL", "Text(ThisItem.rlt_perfil)", 0.12),
      ("E-MAIL DO LOGIN", "ThisItem.rlt_email", 0.18)]),
]


def tela_listas():
    """Atualizar listas (RF-021): o líder inclui, altera, desativa e reativa equipamentos, locais e pessoas.
    Nada se exclui: chamados e relatórios antigos apontam para esses itens. Item desativado some das listas do app."""
    p = "lis"
    X0, LARG = "224", "Parent.Width - 248"
    ALT = 44
    y_abas, y_busca, y_cab = 150, 204, 258
    filhos = moldura(p, "scrPainel") + [
        C(f"{p}Voltar", LBL, Text='"‹  Painel geral"', Color="corAzul", Size="10", Underline="true", X="224", Y="70", Width="300", Height="22",
          OnSelect="Back()"),
    ] + titulo(p, '"ATUALIZAR LISTAS"', '"Inclua, altere ou desative itens. Item desativado some das listas do app, mas continua nos relatórios antigos (RF-021)."', y=100)
    # abas
    for i, (aba, rot, tab, *_r) in enumerate(ABAS):
        on = f'locAba = "{aba}"'
        filhos.append(C(f"{p}Aba{i}", BTN, Text=f'"{rot}  (" & CountIf({tab}, {ativo(tab)}) & ")"', OnSelect=f'UpdateContext({{locAba: "{aba}"}}); Reset(lisBusca)',
                        X=f"224 + {i} * 214", Y=str(y_abas), Width="206", Height="40", Size="11",
                        FontWeight=f"If({on}, FontWeight.Bold, FontWeight.Normal)", Fill=f"If({on}, corAzul, Color.White)", Color=f"If({on}, Color.White, corAzul)",
                        HoverFill=f"If({on}, corAzul80, corAzul10)", HoverColor=f"If({on}, Color.White, corAzul)", BorderColor="corAzul", BorderThickness="1",
                        RadiusTopLeft="8", RadiusTopRight="8", RadiusBottomLeft="8", RadiusBottomRight="8"))
    # busca, desativados e incluir
    filhos += [
        C("lisBusca", TXT, Default='""', HintText='"Buscar por nome ou código SAP"', X=X0, Y=str(y_busca), Width="360", Height="40",
          BorderColor="RGBA(197, 206, 215, 1)", FocusedBorderColor="corVerde", FocusedBorderThickness="2", Size="11", PaddingLeft="12",
          RadiusTopLeft="8", RadiusTopRight="8", RadiusBottomLeft="8", RadiusBottomRight="8"),
        C("lisInativos", CHK, Text='"Mostrar desativados"', Default="false", X="600", Y=str(y_busca + 4), Width="240", Height="32", Size="11",
          CheckboxBorderColor="RGBA(91, 104, 118, 1)", CheckboxSize="20", CheckmarkFill="Color.White", Color="corTexto"),
        botao(f"{p}Incluir", '"＋  Incluir"', 'UpdateContext({locNovo: true, locJan: true, locErroLista: ""}); Reset(ediT1); Reset(ediT2); Reset(ediT3); Reset(ediT4); Reset(ediTipo); Reset(ediPerfil)',
              "Parent.Width - 24 - 150", y_busca, 150, 40),
        cartao(f"{p}Grade", X0, y_cab, LARG, f"Parent.Height - {y_cab} - 16", raio=8),
    ]
    for aba, rot, tab, chave, var, cols in ABAS:
        on = f'locAba = "{aba}"'
        busca = " || ".join(f"lisBusca.Text in {c}" for c in (["rlt_nome", "rlt_codigosap"] if aba != "pes" else ["rlt_nome", "rlt_email", "rlt_cargo"]))
        itens = f"Sort(Filter({tab}, (lisInativos.Value || {ativo(tab)}) && (IsBlank(Trim(lisBusca.Text)) || {busca})), rlt_nome)"
        reg = f"LookUp({tab}, {chave} = ThisItem.{chave})"
        eh_ativo = f"ThisItem.{ativo(tab)}"
        proprio = f"{eh_ativo} && ThisItem.rlt_pessoaid = gblUsuario.rlt_pessoaid" if aba == "pes" else "false"
        alternar = (f"If({proprio}, "
                    f"Notify(\"Você não pode desativar o seu próprio cadastro.\", NotificationType.Warning),\n"
                    f"  Patch({tab}, {reg}, {{statecode: If({eh_ativo}, 'Status ({tab})'.{OP_INATIVO}, 'Status ({tab})'.{OP_ATIVO})}});\n  "
                    + hist(f'"Lista {rot}: " & If({eh_ativo}, "desativado ", "reativado ") & ThisItem.rlt_nome')
                    + f";\n  Notify(ThisItem.rlt_nome & If({eh_ativo}, \" desativado.\", \" reativado.\"), NotificationType.Success))")
        alterar = (f'UpdateContext({{{var}: ThisItem, locNovo: false, locJan: true, locErroLista: ""}}); '
                   "Reset(ediT1); Reset(ediT2); Reset(ediT3); Reset(ediT4); Reset(ediTipo); Reset(ediPerfil)")
        # cabeçalho da grade
        xs, acc = [], 0.0
        for c in cols:
            xs.append(acc)
            acc += c[2]
        for j, (cab, _f, larg) in enumerate(cols):
            filhos.append(C(f"{p}Cab{aba}{j}", LBL, Text=f'"{cab}"', Color="corMuted", Size="8", FontWeight="FontWeight.Bold",
                            X=f"{X0} + 12 + ({LARG} - 24) * {xs[j]}", Y=str(y_cab), Width=f"({LARG} - 24) * {larg}", Height="34", Visible=on))
        filhos.append(C(f"{p}CabSit{aba}", LBL, Text='"SITUAÇÃO"', Color="corMuted", Size="8", FontWeight="FontWeight.Bold",
                        X=f"{X0} + 12 + ({LARG} - 24) * {acc}", Y=str(y_cab), Width="100", Height="34", Visible=on))
        filhos.append(C(f"{p}CabLinha{aba}", RET, Fill="corLinha", X=f"{X0} + 1", Y=str(y_cab + 34), Width=f"{LARG} - 2", Height="2", Visible=on))
        celulas = [C(f"{p}C{aba}{j}", LBL, Text=f, Color="corTexto", Size="10", X=f"12 + (Parent.TemplateWidth - 24) * {xs[j]}", Y="0",
                     Width=f"(Parent.TemplateWidth - 24) * {larg} - 8", Height=str(ALT))
                   for j, (_c, f, larg) in enumerate(cols)]
        celulas += [
            chip(f"{p}Sit{aba}", f'If({eh_ativo}, "ATIVO", "DESATIVADO")', f"12 + (Parent.TemplateWidth - 24) * {acc}", 11, 96,
                 f"If({eh_ativo}, RGBA(227, 242, 218, 1), RGBA(236, 239, 242, 1))", f"If({eh_ativo}, RGBA(47, 98, 20, 1), RGBA(71, 82, 94, 1))",
                 f"If({eh_ativo}, RGBA(191, 226, 168, 1), RGBA(207, 214, 221, 1))", h=22),
            C(f"{p}Alt{aba}", LBL, Text='"Alterar"', Color="corAzul", Underline="true", Size="10", Align="Align.Right",
              X="Parent.TemplateWidth - 190", Y="0", Width="76", Height=str(ALT), OnSelect=alterar),
            C(f"{p}Des{aba}", LBL, Text=f'If({eh_ativo}, "Desativar", "Reativar")', Color=f"If({eh_ativo}, RGBA(138, 0, 33, 1), corAzul)",
              Underline="true", Size="10", Align="Align.Right", X="Parent.TemplateWidth - 104", Y="0", Width="92", Height=str(ALT), OnSelect=alternar),
            C(f"{p}Linha{aba}", RET, Fill="corLinha", X="0", Y=f"Parent.TemplateHeight - 1", Width="Parent.TemplateWidth", Height="1"),
        ]
        filhos.append(C(f"{p}Gal{aba}", GAL, variante="Vertical", Items=itens, TemplateSize=str(ALT), TemplatePadding="0",
                        X=f"{X0} + 1", Y=str(y_cab + 36), Width=f"{LARG} - 2", Height=f"Parent.Height - {y_cab + 36} - 18", Visible=on, filhos=celulas))
    filhos += janela_lista()
    ao_abrir = ('If(!' + LIDER + ', Notify("Só o líder atualiza as listas.", NotificationType.Warning); Back());\n'
                'UpdateContext({locAba: Coalesce(locAba, "eq"), locJan: false, locErroLista: ""})')
    return tela("scrListas", {"Fill": "corFundo", "OnVisible": ao_abrir}, filhos)


def janela_lista():
    """Janela de inclusão/alteração de um item da aba atual (locAba). Os campos de texto são os mesmos nas três abas:
         eq:  ediT1 Descrição | ediT2 Código SAP | ediTipo Tipo
         loc: ediT1 Local específico | ediT2 Código SAP | ediT3 Área | ediT4 Lado
         pes: ediT1 Nome | ediT2 Cargo | ediPerfil Perfil | ediT3 E-mail do login"""
    vis = "locJan"
    W, H = "680", "440"
    x, y = f"(Parent.Width - {W}) / 2", f"(Parent.Height - {H}) / 2"
    meio = f"({W} - 48 - 16) / 2"
    xe, xd = f"{x} + 24", f"{x} + 24 + {meio} + 16"
    ya, yb, yc = f"{y} + 76", f"{y} + 152", f"{y} + 228"
    aba = lambda *a: "locAba in [" + ", ".join(f'"{s}"' for s in a) + "]"
    sw = lambda eq, loc, pes: f'Switch(locAba, "eq", {eq}, "loc", {loc}, {pes})'
    campo = dict(BorderColor="RGBA(197, 206, 215, 1)", BorderThickness="1", FocusedBorderColor="corVerde", FocusedBorderThickness="2",
                 Size="11", Color="corTexto")
    txt = dict(campo, PaddingLeft="12", RadiusTopLeft="8", RadiusTopRight="8", RadiusBottomLeft="8", RadiusBottomRight="8")
    lista = dict(campo, ChevronBackground="Color.White", ChevronFill="corTexto", SelectionFill="corAzul", HoverFill="corAzul10")
    t1, t2, t3, t4 = "Trim(ediT1.Text)", "Trim(ediT2.Text)", "Trim(ediT3.Text)", "Trim(ediT4.Text)"
    # registros a gravar (Defaults quando é inclusão)
    alvo = lambda tab, chave, var: f"If(locNovo, Defaults({tab}), LookUp({tab}, {chave} = {var}.{chave}))"
    dup_eq = f"LookUp(Equipamentos, rlt_codigosap = {t2})"
    dup_pes = f"LookUp(Pessoas, rlt_email = Lower({t3}))"
    validar = (f"UpdateContext({{locErroLista: Concat(Filter(Table(\n"
               f"  {{m: If(IsBlank({t1}), \"Preencha o \" & {sw(chr(34)+'campo Descrição'+chr(34), chr(34)+'campo Local específico'+chr(34), chr(34)+'campo Nome'+chr(34))} & \".\", \"\")}},\n"
               f"  {{m: If(locAba <> \"pes\" && IsBlank({t2}), \"Preencha o código SAP.\", \"\")}},\n"
               f"  {{m: If(locAba = \"loc\" && IsBlank({t3}), \"Preencha a área.\", \"\")}},\n"
               f"  {{m: If(locAba = \"eq\" && !IsBlank({t2}) && !IsBlank({dup_eq}) && (locNovo || {dup_eq}.rlt_equipamentoid <> locEq.rlt_equipamentoid), "
               f"\"Já existe um equipamento com esse código SAP: \" & {dup_eq}.rlt_nome & \".\", \"\")}},\n"
               f"  {{m: If(locAba = \"pes\" && !IsBlank({t3}) && !IsMatch({t3}, Match.Email), \"E-mail inválido.\", \"\")}},\n"
               f"  {{m: If(locAba = \"pes\" && !IsBlank({t3}) && !IsBlank({dup_pes}) && (locNovo || {dup_pes}.rlt_pessoaid <> locPes.rlt_pessoaid), "
               f"\"Esse e-mail já é de \" & {dup_pes}.rlt_nome & \".\", \"\")}},\n"
               f"  {{m: If(locAba = \"pes\" && IsBlank(ediPerfil.Selected), \"Escolha o perfil.\", \"\")}}\n"
               f"), !IsBlank(m)), m, \"  \")}})")
    gravar = (f"Switch(locAba,\n"
              f"  \"eq\", Patch(Equipamentos, {alvo('Equipamentos', 'rlt_equipamentoid', 'locEq')}, {{rlt_nome: {t1}, rlt_codigosap: {t2}, rlt_tipo: ediTipo.Selected.Value}}),\n"
              f"  \"loc\", Patch(Locais, {alvo('Locais', 'rlt_localid', 'locLoc')}, {{rlt_nome: {t1}, rlt_codigosap: {t2}, rlt_area: {t3}, rlt_lado: {t4}}}),\n"
              f"  Patch(Pessoas, {alvo('Pessoas', 'rlt_pessoaid', 'locPes')}, {{rlt_nome: {t1}, rlt_cargo: {t2}, rlt_email: Lower({t3}), rlt_perfil: ediPerfil.Selected.Value}}))")
    rotulo_aba = sw('"Equipamentos"', '"Locais"', '"Pessoas"')
    salvar = (validar + ";\nIf(IsBlank(locErroLista),\n  " + gravar + ";\n  "
              + hist(f'"Lista " & {rotulo_aba} & If(locNovo, ": incluído ", ": alterado ") & {t1}')
              + f";\n  Notify(If(locNovo, \"Incluído: \", \"Alterado: \") & {t1}, NotificationType.Success);\n  UpdateContext({{locJan: false}}))")
    dflt = lambda eq, loc, pes: f'If(locNovo, "", {sw(eq, loc, pes)})'

    def rot(nome, texto, xx, yy, v):
        return C(nome, LBL, Text=texto, Color="corMuted", Size="9", FontWeight="FontWeight.Bold", X=xx, Y=yy, Width=meio, Height="20", Visible=f"{vis} && ({v})")

    return [
        C("ediFundo", RET, Fill="RGBA(0, 0, 0, 0.45)", X="0", Y="0", Width="Parent.Width", Height="Parent.Height", Visible=vis),
        cartao("ediCartao", x, y, W, H, raio=12, Visible=vis),
        C("ediAcento", RET, Fill="corVerde", X=f"{x} + 24", Y=f"{y} + 20", Width="36", Height="4", Visible=vis),
        C("ediTit", LBL, Text=f'If(locNovo, "INCLUIR – ", "ALTERAR – ") & Upper({rotulo_aba})', Color="corAzul", Size="14", FontWeight="FontWeight.Bold",
          Font=FONTE_TIT, X=f"{x} + 24", Y=f"{y} + 28", Width=f"{W} - 48", Height="30", Visible=vis),
        # linha A: nome (largura toda)
        rot("ediRot1", sw('"DESCRIÇÃO *"', '"LOCAL ESPECÍFICO *"', '"NOME *"'), xe, ya, "true"),
        C("ediT1", TXT, Default=dflt("locEq.rlt_nome", "locLoc.rlt_nome", "locPes.rlt_nome"), X=xe, Y=f"{ya} + 22", Width=f"{W} - 48", Height="40",
          Visible=vis, **txt),
        # linha B: código SAP ou cargo | tipo, área ou perfil
        rot("ediRot2", sw('"CÓDIGO SAP *"', '"CÓDIGO SAP *"', '"CARGO"'), xe, yb, "true"),
        C("ediT2", TXT, Default=dflt("locEq.rlt_codigosap", "locLoc.rlt_codigosap", "locPes.rlt_cargo"), X=xe, Y=f"{yb} + 22", Width=meio, Height="40",
          Visible=vis, **txt),
        rot("ediRotTipo", '"TIPO"', xd, yb, aba("eq")),
        C("ediTipo", DDL, Items="Choices([@'Tipo de equipamento'])", Default='If(locNovo, "Outro", Text(locEq.rlt_tipo))', X=xd, Y=f"{yb} + 22", Width=meio,
          Height="40", Visible=f"{vis} && {aba('eq')}", **lista),
        rot("ediRotPerfil", '"PERFIL *"', xd, yb, aba("pes")),
        C("ediPerfil", DDL, Items="Choices([@Perfil])", Default='If(locNovo, "Técnico(a)", Text(locPes.rlt_perfil))', X=xd, Y=f"{yb} + 22", Width=meio,
          Height="40", Visible=f"{vis} && {aba('pes')}", **lista),
        # ediT3: área (loc, linha B à direita) ou e-mail (pes, linha C)
        rot("ediRot3", 'If(locAba = "loc", "ÁREA *", "E-MAIL DO LOGIN")', f'If(locAba = "loc", {xd}, {xe})', f'If(locAba = "loc", {yb}, {yc})', aba("loc", "pes")),
        C("ediT3", TXT, Default=dflt('""', "locLoc.rlt_area", "locPes.rlt_email"), X=f'If(locAba = "loc", {xd}, {xe})', Y=f'If(locAba = "loc", {yb}, {yc}) + 22',
          Width=f'If(locAba = "loc", {meio}, {W} - 48)', Height="40", Visible=f"{vis} && {aba('loc', 'pes')}",
          HintText='If(locAba = "loc", "Mesma grafia das áreas que já existem", "nome@inframerica.aero")', **txt),
        # ediT4: lado (loc, linha C)
        rot("ediRot4", '"LADO"', xe, yc, aba("loc")),
        C("ediT4", TXT, Default=dflt('""', "locLoc.rlt_lado", '""'), X=xe, Y=f"{yc} + 22", Width=meio, Height="40", Visible=f"{vis} && {aba('loc')}", **txt),
        C("ediAjuda", LBL, Color="corMuted", Size="9", X=f"{x} + 24", Y=f"{yc} + 70", Width=f"{W} - 48", Height="36", Visible=vis,
          VerticalAlign="VerticalAlign.Top",
          Text=sw('"O tipo define a Tela 3 do dashboard (Fator Q por tipo de equipamento)."',
                  '"O app agrupa os locais pela área: use a mesma grafia das áreas que já existem."',
                  '"O e-mail liga a pessoa ao login no app. O perfil Líder libera esta tela e os avisos do Painel."')),
        C("ediErro", LBL, Text="locErroLista", Visible=f"{vis} && !IsBlank(locErroLista)", Color="RGBA(138, 0, 33, 1)", Fill="corVerm20", Size="10",
          FontWeight="FontWeight.Semibold", PaddingLeft="12", X=f"{x} + 24", Y=f"{y} + {H} - 64", Width=f"{W} - 48 - 150 - 8 - 120 - 8", Height="40"),
        botao("ediSalvar", '"Salvar"', salvar, f"{x} + {W} - 24 - 150", f"{y} + {H} - 64", 150, 40, Visible=vis),
        botao("ediCancelar", '"Cancelar"', "UpdateContext({locJan: false})", f"{x} + {W} - 24 - 150 - 8 - 120", f"{y} + {H} - 64", 120, 40,
              primario=False, Visible=vis),
    ]


# ================================================================== TELA RELATÓRIO DA ELETROMECÂNICA (25/11/2026)
ENVIOS = "'Envios Eletromecânica'"


def tela_eletro():
    """Relatório diário da Eletromecânica (Fator Q): o Bravo confere e envia às 24:00. O app cria um Envio Eletromecânica;
    o fluxo "RLT – Relatório da Eletromecânica" gera o PDF, guarda no OneDrive e envia o e-mail (ferramentas/fluxos/fluxo_eletro.py).
    A prévia usa a mesma regra do fluxo: chamados que começaram, terminaram ou ficaram abertos no dia; de uma pendência
    herdada, só a cópia mais recente; preventivas de BHS ficam fora."""
    p = "ele"
    secs = f"(rlt_secao = {SEC}.Eletromecânica || rlt_secao = {SEC}.'Fator Q (Z9)' || rlt_secao = {SEC}.'Preventiva (ZM02)')"
    carregar = (
        "With({d: Coalesce(eleData.SelectedDate, locEleData)},\n"
        "  With({ini: DateTime(Year(d), Month(d), Day(d), 0, 0, 0)},\n"
        f"    ClearCollect(colDia, Filter(Registros, {secs} && rlt_inicio < DateAdd(ini, 1, TimeUnit.Days) && "
        "(IsBlank(rlt_conclusao) || rlt_conclusao >= ini)));\n"
        "    ClearCollect(colEletro, Sort(Filter(colDia As r, IsBlank(LookUp(colDia As o, o.rlt_origem.rlt_registroid = r.rlt_registroid)) && "
        f"(r.rlt_secao <> {SEC}.'Preventiva (ZM02)' || IsBlank(r.rlt_equipamento) || r.rlt_equipamento.rlt_tipo <> [@'Tipo de equipamento'].Bagagem)), rlt_inicio));\n"
        f"    UpdateContext({{locEnvio: First(Sort(Filter({ENVIOS}, rlt_data = d), createdon, SortOrder.Descending)), locConfirma: false}})))")
    ao_abrir = ("UpdateContext({locEleData: If(Hour(Now()) < 12, DateAdd(Today(), -1, TimeUnit.Days), Today())});\n"
                f"UpdateContext({{locEleEquipe: Coalesce(First(Sort({ENVIOS}, createdon, SortOrder.Descending)).rlt_equipe, \"\")}});\n"
                "Reset(eleData); Reset(eleEquipe);\n" + carregar)
    enviar = (
        "If(!IsBlank(locEnvio) && !locConfirma,\n"
        "  UpdateContext({locConfirma: true});\n"
        "  Notify(\"Este dia já foi enviado. Toque em \" & Char(34) & \"Confirmar novo envio\" & Char(34) & \" para mandar outra vez.\", NotificationType.Warning),\n"
        f"  UpdateContext({{locEnvio: Patch({ENVIOS}, Defaults({ENVIOS}), {{rlt_nome: \"ELETROMECÂNICA \" & Text(eleData.SelectedDate, \"dd.mm.yyyy\"), "
        "rlt_data: eleData.SelectedDate, rlt_equipe: eleEquipe.Text, rlt_enviadopor: gblUsuario, rlt_enviadoem: Now()})});\n"
        "  UpdateContext({locConfirma: false});\n  "
        + hist('"Relatório da Eletromecânica enviado: " & Text(eleData.SelectedDate, "dd/mm/yyyy")')
        + ";\n  Notify(\"Enviado para o fluxo: o PDF e o e-mail saem em alguns minutos.\", NotificationType.Success))")
    atualizar = f"UpdateContext({{locEnvio: LookUp({ENVIOS}, rlt_envioeletroid = locEnvio.rlt_envioeletroid)}})"
    X0, LARG = "224", "Parent.Width - 248"
    campo = dict(BorderColor="RGBA(197, 206, 215, 1)", BorderThickness="1", FocusedBorderColor="corVerde", FocusedBorderThickness="2",
                 Size="11", Color="corTexto")
    filhos = moldura(p, "scrFechar") + [
        C(f"{p}Voltar", LBL, Text='"‹  Fechar"', Color="corAzul", Size="10", Underline="true", X="224", Y="70", Width="300", Height="22", OnSelect="Back()"),
    ] + titulo(p, '"RELATÓRIO DA ELETROMECÂNICA"',
               '"O Bravo envia às 24:00 os chamados do dia da Eletromecânica, do Fator Q (Z9) e das preventivas (ZM02, sem BHS), para Eletromecânica SBBR com cópia para o CCM."',
               y=100)
    filhos += [
        rotulo(f"{p}RotData", '"DATA DO RELATÓRIO *"', 224, 168, 200),
        C("eleData", DTP, DefaultDate="locEleData", Format='"dd/mm/yyyy"', OnChange=carregar, X="224", Y="192", Width="200", Height="40",
          IconBackground="Color.White", IconFill="corTexto", **campo),
        rotulo(f"{p}RotEquipe", '"ELETROMECÂNICA DE PLANTÃO  (cabeçalho do PDF)"', 444, 168, 500),
        C("eleEquipe", TXT, Default="locEleEquipe", Mode="TextMode.MultiLine", MaxLength="2000", X="444", Y="192",
          Width="Parent.Width - 444 - 24 - 250", Height="84", PaddingLeft="10",
          HintText='"Um por linha. Ex.: Wellington Alves - Plantão Alfa"', RadiusTopLeft="8", RadiusTopRight="8", RadiusBottomLeft="8",
          RadiusBottomRight="8", **campo),
        botao(f"{p}Enviar", 'If(IsBlank(locEnvio), "➤  Enviar para a Eletromecânica", locConfirma, "Confirmar novo envio", "Enviar de novo")', enviar,
              "Parent.Width - 24 - 230", 192, 230, 44, Size="11", DisplayMode="If(IsBlank(eleData.SelectedDate), DisplayMode.Disabled, DisplayMode.Edit)"),
        C(f"{p}Resultado", LBL, OnSelect=atualizar, Size="10", PaddingLeft="12", X=X0, Y="290", Width=LARG, Height="44",
          Fill="If(IsBlank(locEnvio), corAzul10, StartsWith(Coalesce(locEnvio.rlt_resultado, \"\"), \"FALHA\"), corVerm20, RGBA(227, 242, 218, 1))",
          Color="If(!IsBlank(locEnvio) && StartsWith(Coalesce(locEnvio.rlt_resultado, \"\"), \"FALHA\"), RGBA(138, 0, 33, 1), corTexto)",
          Text=('If(IsBlank(locEnvio), "Ainda não enviado para " & Text(eleData.SelectedDate, "dd/mm/yyyy") & ".", '
                '"Enviado por " & Coalesce(locEnvio.rlt_enviadopor.rlt_nome, "—") & " em " & Text(locEnvio.rlt_enviadoem, "dd/mm/yyyy hh:mm") & ".   " & '
                'If(IsBlank(locEnvio.rlt_resultado), "PDF e e-mail em andamento: toque aqui para atualizar.", locEnvio.rlt_resultado))')),
        C(f"{p}Qtd", LBL, Text='CountRows(colEletro) & If(CountRows(colEletro) = 1, " chamado", " chamados") & " no dia. Toque no chamado para completar o feedback."',
          Color="corMuted", Size="10", X=X0, Y="342", Width=LARG, Height="24"),
        cartao(f"{p}Grade", X0, 370, LARG, "Parent.Height - 370 - 16", raio=8),
    ]
    cols = [("REGISTRO / OCORRÊNCIA", 0.31), ("NOTA", 0.06), ("CHAMADO", 0.1), ("REGISTRO", 0.1), ("TÉRMINO", 0.1), ("STATUS", 0.13), ("FEEDBACK", 0.2)]
    acc, xs = 0.0, []
    for _c, larg in cols:
        xs.append(acc)
        acc += larg
    for j, (cab, larg) in enumerate(cols):
        filhos.append(C(f"{p}Cab{j}", LBL, Text=f'"{cab}"', Color="corMuted", Size="8", FontWeight="FontWeight.Bold",
                        X=f"{X0} + 12 + ({LARG} - 24) * {xs[j]}", Y="370", Width=f"({LARG} - 24) * {larg}", Height="34"))
    filhos.append(C(f"{p}CabLinha", RET, Fill="corLinha", X=f"{X0} + 1", Y="404", Width=f"{LARG} - 2", Height="2"))
    sec = "ThisItem.rlt_secao"
    equip = "Upper(Coalesce(ThisItem.rlt_equipamento.rlt_nome, ThisItem.rlt_equipamentolivre, ThisItem.rlt_titulo))"
    ocorr = (f"Switch({sec}, {SEC}.'Fator Q (Z9)', \"SOLICITAÇÃO DE ATENDIMENTO PARA INOPERÂNCIA – \" & {equip}, "
             f"{SEC}.'Preventiva (ZM02)', \"MANUTENÇÃO PREVENTIVA – \" & {equip}, Upper(Coalesce(ThisItem.rlt_descricao, ThisItem.rlt_titulo)))")
    eh_equip = f"({sec} = {SEC}.'Fator Q (Z9)' || {sec} = {SEC}.'Preventiva (ZM02)')"
    st = 'Switch(Text(ThisItem.rlt_status), "EM ANDAMENTO", "EM EXECUÇÃO", "CONCLUÍDO", "CONCLUÍDO / OPERACIONAL", Text(ThisItem.rlt_status))'
    fb = (f"If(IsBlank(Trim(ThisItem.rlt_feedback)) && ThisItem.rlt_status = {ST}.CANCELADO, \"MOTIVO: \" & ThisItem.rlt_motivocancelamento, "
          "Coalesce(ThisItem.rlt_feedback, \"\"))")
    valores = [ocorr, f'If({eh_equip}, If({sec} = {SEC}.\'Fator Q (Z9)\', "Z9", "ZM02"), "–")', f'If({eh_equip}, ThisItem.rlt_numero, "–")',
               'Text(ThisItem.rlt_inicio, "dd/mm hh:mm")',
               'If(!IsBlank(ThisItem.rlt_conclusao), Text(ThisItem.rlt_conclusao, "dd/mm hh:mm"), ThisItem.rlt_ni, "N/I", "–")', st,
               f'If(IsBlank({fb}), "(sem feedback)", {fb})']
    ALT = 56
    abrir = "Navigate(scrRegistro, ScreenTransition.None, {locId: ThisItem.rlt_registroid, locSecao: ThisItem.rlt_secao})"
    celulas = []
    for j, ((_c, larg), v) in enumerate(zip(cols, valores)):
        extra = {}
        if j == 0:
            extra = dict(Color="corAzul", Underline="true", OnSelect=abrir)
        elif j == 1:
            extra = dict(Color="RGBA(192, 0, 0, 1)", FontWeight="FontWeight.Bold")
        elif j == 6:
            extra = dict(Color=f'If(IsBlank({fb}), corMuted, corTexto)', Italic=f"IsBlank({fb})")
        celulas.append(C(f"{p}C{j}", LBL, Text=v, Size="9", X=f"12 + (Parent.TemplateWidth - 24) * {xs[j]}", Y="0",
                         Width=f"(Parent.TemplateWidth - 24) * {larg} - 8", Height=str(ALT), **{"Color": "corTexto", **extra}))
    celulas.append(C(f"{p}Linha", RET, Fill="corLinha", X="0", Y="Parent.TemplateHeight - 1", Width="Parent.TemplateWidth", Height="1"))
    filhos += [
        C(f"{p}Vazio", LBL, Text='"Nenhum chamado da Eletromecânica, do Fator Q ou de preventiva neste dia."', Color="corMuted", Size="10",
          Align="Align.Center", X=X0, Y="420", Width=LARG, Height="40", Visible="CountRows(colEletro) = 0"),
        C(f"{p}Gal", GAL, variante="Vertical", Items="colEletro", TemplateSize=str(ALT), TemplatePadding="0",
          X=f"{X0} + 1", Y="406", Width=f"{LARG} - 2", Height="Parent.Height - 406 - 18", filhos=celulas),
    ]
    return tela("scrEletro", {"Fill": "corFundo", "OnVisible": ao_abrir}, filhos)


# ================================================================== APP
APP = f"""App:
  Properties:
    Theme: =PowerAppsTheme
    StartScreen: =scrRelatorio
    Formulas: {bloco('''=corAzul = RGBA(0, 56, 99, 1);
corAzul80 = RGBA(51, 95, 130, 1);
corAzul10 = RGBA(232, 237, 242, 1);
corVerde = RGBA(114, 191, 68, 1);
corLaranja = RGBA(243, 139, 0, 1);
corLaranja20 = RGBA(253, 232, 204, 1);
corLaranjaTxt = RGBA(122, 70, 0, 1);
corVerm = RGBA(195, 0, 47, 1);
corVerm20 = RGBA(243, 204, 213, 1);
corFundo = RGBA(242, 244, 246, 1);
corLinha = RGBA(221, 227, 233, 1);
corTexto = RGBA(28, 39, 51, 1);
corMuted = RGBA(91, 104, 118, 1);
tabHoras = ForAll(Sequence(24, 0), Text(Value, "00"));
tabMinutos = ForAll(Sequence(60, 0), Text(Value, "00"));
tabSecoes = Table(
  {Ordem: 1, Nome: "Eletromecânica", Valor: [@'Seção'].Eletromecânica, Tipo: "corretiva", Cor: corAzul},
  {Ordem: 2, Nome: "Eletroeletrônica", Valor: [@'Seção'].Eletroeletrônica, Tipo: "corretiva", Cor: corAzul},
  {Ordem: 3, Nome: "BHS", Valor: [@'Seção'].BHS, Tipo: "corretiva", Cor: corAzul},
  {Ordem: 4, Nome: "Civil", Valor: [@'Seção'].Civil, Tipo: "corretiva", Cor: corAzul},
  {Ordem: 5, Nome: "Outros", Valor: [@'Seção'].Outros, Tipo: "corretiva", Cor: corAzul},
  {Ordem: 6, Nome: "Fator Q (Z9)", Valor: [@'Seção'].'Fator Q (Z9)', Tipo: "fq", Cor: corLaranja},
  {Ordem: 7, Nome: "Preventiva (ZM02)", Valor: [@'Seção'].'Preventiva (ZM02)', Tipo: "prev", Cor: corVerde},
  {Ordem: 8, Nome: "IOS informados", Valor: [@'Seção'].'IOS informados', Tipo: "ios", Cor: RGBA(153, 175, 193, 1)}
);''').replace(chr(10), chr(10) + '      ')}
    OnStart: {bloco(f'''=Set(gblUsuario, LookUp(Pessoas, rlt_email = User().Email && {ativo("Pessoas")}));
Set(gblRel, First(Sort(Filter(Relatórios, rlt_situacao = {SIT}.Aberto), createdon, SortOrder.Descending)));
If(IsBlank(gblRel), Set(gblRel, First(Sort(Relatórios, createdon, SortOrder.Descending))));
If(!IsBlank(gblUsuario) && {ABERTO_REL} &&
   IsBlank(LookUp('Equipe do plantão', rlt_relatorio.rlt_relatorioid = gblRel.rlt_relatorioid && rlt_pessoa.rlt_pessoaid = gblUsuario.rlt_pessoaid && rlt_retiradoem = Blank())),
  Patch('Equipe do plantão', Defaults('Equipe do plantão'), {{rlt_nome: gblUsuario.rlt_nome, rlt_pessoa: gblUsuario, rlt_relatorio: gblRel,
    rlt_perfil: gblUsuario.rlt_perfil, rlt_entrouem: Now()}});
  {hist('"Entrou no plantão (login)"')}
)''').replace(chr(10), chr(10) + '      ')}
"""

EDITOR = """EditorState:
  ScreensOrder:
    - scrRelatorio
    - scrChamados
    - scrRegistro
    - scrHistorico
    - scrPainel
    - scrListas
    - scrFechar
    - scrEletro
    - scrAbrir
"""

CABEC = "# Gerado por app/gerar_app.py a partir do protótipo validado. Edite o gerador, não este arquivo.\n"


def main(src):
    arquivos = {
        "App.pa.yaml": APP, "_EditorState.pa.yaml": EDITOR,
        "scrRelatorio.pa.yaml": tela_relatorio(), "scrChamados.pa.yaml": tela_chamados(), "scrRegistro.pa.yaml": tela_registro(),
        "scrHistorico.pa.yaml": tela_historico(), "scrPainel.pa.yaml": tela_painel(), "scrFechar.pa.yaml": tela_fechar(),
        "scrAbrir.pa.yaml": tela_abrir(), "scrListas.pa.yaml": tela_listas(), "scrEletro.pa.yaml": tela_eletro(),
    }
    velho = os.path.join(src, "Screen1.pa.yaml")
    if os.path.exists(velho):
        os.remove(velho)
    for nome, conteudo in arquivos.items():
        with open(os.path.join(src, nome), "w", encoding="utf-8", newline="\n") as f:
            f.write(CABEC + conteudo)
    print(f"{len(arquivos)} arquivos gerados em {src}")


if __name__ == "__main__":
    main(sys.argv[1])
