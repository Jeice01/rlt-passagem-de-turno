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


def emitir(nome, controle, props, filhos=None, variante=None, nivel=0):
    ind = "  " * nivel
    out = [f"{ind}- {nome}:", f"{ind}    Control: {controle}"]
    if variante:
        out.append(f"{ind}    Variant: {variante}")
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


def C(nome, controle, variante=None, filhos=None, **props):
    return lambda nivel: emitir(nome, controle, props, filhos, variante, nivel)


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


def hist(campo, registro="Blank()"):
    return (f"Patch(Histórico, Defaults(Histórico), {{rlt_campo: {campo}, rlt_quando: Now(), rlt_quem: gblUsuario, "
            f"rlt_relatorio: gblRel, rlt_registro: {registro}}})")


# ------------------------------------------------------------------ moldura comum (topo + menu)
MENU = [("Relatório", "scrRelatorio"), ("Chamados", "scrChamados"), ("Histórico", "scrHistorico"),
        ("Painel geral", "scrPainel"), ("Fechar", "scrFechar")]


def moldura(p, atual):
    itens = [
        C(f"{p}Topo", RET, Fill="corAzul", X="0", Y="0", Width="Parent.Width", Height="56"),
        C(f"{p}Faixa", RET, Fill="corVerde", X="0", Y="56", Width="Parent.Width", Height="5"),
        C(f"{p}Marca", LBL, Text='"RLT · CCM   Passagem de Turno"', Color="Color.White", Size="15", FontWeight="FontWeight.Semibold",
          X="20", Y="0", Width="500", Height="56"),
        C(f"{p}Usuario", LBL, Text='If(IsBlank(gblUsuario), User().FullName & "  (fora da lista de pessoas)", gblUsuario.rlt_nome & "  ·  " & Text(gblUsuario.rlt_perfil))',
          Color="Color.White", Size="13", Align="Align.Right", X="Parent.Width - 620", Y="0", Width="600", Height="56"),
        C(f"{p}MenuFundo", RET, Fill="Color.White", BorderColor="corLinha", BorderThickness="1", X="0", Y="61", Width="200", Height="Parent.Height - 61"),
    ]
    for i, (rot, destino) in enumerate(MENU):
        on = destino == atual
        itens.append(C(f"{p}Menu{i}", BTN, Text=f'"{rot}"', OnSelect=f"Navigate({destino}, ScreenTransition.None)",
                       Fill="corAzul10" if on else "Color.White", Color="corAzul", HoverFill="corAzul10", HoverColor="corAzul",
                       PressedFill="corAzul10", BorderThickness="0", Align="Align.Left", PaddingLeft="20",
                       FontWeight="FontWeight.Semibold" if on else "FontWeight.Normal", Size="13",
                       X="0", Y=str(76 + i * 50), Width="200", Height="46",
                       RadiusTopLeft="0", RadiusTopRight="0", RadiusBottomLeft="0", RadiusBottomRight="0"))
        if on:
            itens.append(C(f"{p}MenuMarca", RET, Fill="corVerde", X="0", Y=str(76 + i * 50), Width="5", Height="46"))
    return itens


def titulo(p, texto, sub=None, y=78):
    out = [C(f"{p}Tit", LBL, Text=texto, Color="corAzul", Size="20", FontWeight="FontWeight.Bold", X="224", Y=str(y), Width="Parent.Width - 460", Height="36")]
    if sub:
        out.append(C(f"{p}Sub", LBL, Text=sub, Color="corMuted", Size="11", X="224", Y=str(y + 34), Width="Parent.Width - 460", Height="26"))
    return out


def botao(nome, texto, onselect, x, y, w=170, h=40, primario=True, **extra):
    props = dict(Text=texto, OnSelect=onselect, X=str(x), Y=str(y), Width=str(w), Height=str(h), Size="12", FontWeight="FontWeight.Semibold",
                 Fill="corAzul" if primario else "Color.White", Color="Color.White" if primario else "corAzul",
                 BorderColor="corAzul", BorderThickness="1", HoverFill="corAzul80" if primario else "corAzul10",
                 HoverColor="Color.White" if primario else "corAzul",
                 RadiusTopLeft="8", RadiusTopRight="8", RadiusBottomLeft="8", RadiusBottomRight="8")
    props.update(extra)
    return C(nome, BTN, **props)


def rotulo(nome, texto, x, y, w=300):
    return C(nome, LBL, Text=texto, Color="corMuted", Size="10", FontWeight="FontWeight.Semibold", X=str(x), Y=str(y), Width=str(w), Height="22")


# ================================================================== TELA RELATÓRIO
def tela_relatorio():
    p = "rel"
    kpis = [("Em aberto", f"CountRows(Filter(colRegs, {ABERTO}))", "corLaranja", "Navigate(scrChamados, ScreenTransition.None, {locSoAbertos: true, locSecaoFiltro: Blank()})"),
            ("Concluídos ou encerrados", f"CountRows(Filter(colRegs, Not({ABERTO})))", "corVerde", "Navigate(scrChamados, ScreenTransition.None, {locSoAbertos: false, locSecaoFiltro: Blank()})"),
            ("Herdados ainda abertos", f"CountRows(Filter(colRegs, rlt_herdado && {ABERTO}))", "corAzul", "Navigate(scrChamados, ScreenTransition.None, {locSoAbertos: true, locSecaoFiltro: Blank()})"),
            ("Fator Q sem código SAP", f"CountRows(Filter(colRegs, rlt_secao = {SEC}.'Fator Q (Z9)' && IsBlank(rlt_equipamento)))", "corVerm", "Navigate(scrPainel, ScreenTransition.None)")]
    filhos = moldura(p, "scrRelatorio") + titulo(
        p, 'If(IsBlank(gblRel), "NENHUM RELATÓRIO ABERTO", "RELATÓRIO " & Text(gblRel.rlt_turno) & " " & Text(gblRel.rlt_data, "dd.mm.yyyy"))',
        'If(IsBlank(gblRel), "Abra o plantão para começar.", gblRel.rlt_nome & ".pdf  ·  " & Text(gblRel.rlt_situacao))')
    filhos += [
        botao(f"{p}BtnAbrir", '"Abrir plantão"', "Navigate(scrAbrir, ScreenTransition.None)", "Parent.Width - 210", 84, Visible=f"Not({ABERTO_REL})"),
        botao(f"{p}BtnFechar", '"Fechar relatório"', "Navigate(scrFechar, ScreenTransition.None)", "Parent.Width - 210", 84, Visible=ABERTO_REL),
        # cartão do plantão
        C(f"{p}Cartao", RET, Fill="Color.White", BorderColor="corLinha", BorderThickness="1", X="224", Y="146", Width="Parent.Width - 248", Height="150"),
        rotulo(f"{p}RotTurno", '"TURNO"', 244, 158), rotulo(f"{p}RotData", '"DATA"', 404, 158),
        C(f"{p}Turno", LBL, Text='Text(gblRel.rlt_turno)', Color="corAzul", Size="17", FontWeight="FontWeight.Bold", X="244", Y="178", Width="150", Height="30"),
        C(f"{p}Data", LBL, Text='Text(gblRel.rlt_data, "dd/mm/yyyy")', Color="corAzul", Size="17", FontWeight="FontWeight.Bold", X="404", Y="178", Width="200", Height="30"),
        C(f"{p}Janela", LBL, Text='If(IsBlank(gblRel), "", Text(gblRel.rlt_inicio, "dd/mm hh:mm") & " → " & Text(gblRel.rlt_fim, "dd/mm hh:mm"))',
          Color="corMuted", Size="11", X="404", Y="206", Width="300", Height="22"),
        rotulo(f"{p}RotEquipe", '"EQUIPE DO PLANTÃO (" & CountRows(colEquipe) & ")"', 244, 232, 400),
        C(f"{p}GalEquipe", GAL, variante="Vertical", Items="Sort(colEquipe, rlt_nome)", WrapCount="4", TemplateSize="40", TemplatePadding="2",
          X="240", Y="254", Width="Parent.Width - 280", Height="40", ShowScrollbar="false",
          filhos=[
              C("relEqNome", LBL, Text='ThisItem.rlt_nome & "  ·  " & Text(ThisItem.rlt_perfil)', Color="corTexto", Size="11",
                X="4", Y="4", Width="Parent.TemplateWidth - 44", Height="30", Fill="corAzul10",
                PaddingLeft="10"),
              C("relEqSair", BTN, Text='"×"', Visible=ABERTO_REL, X="Parent.TemplateWidth - 40", Y="4", Width="32", Height="30",
                Fill="corAzul10", Color="corMuted", BorderThickness="0", HoverFill="corLinha", HoverColor="corVerm", Size="13",
                OnSelect="Patch('Equipe do plantão', LookUp('Equipe do plantão', rlt_equipeid = ThisItem.rlt_equipeid), {rlt_retiradoem: Now(), rlt_retiradopor: gblUsuario});\n"
                         + hist('"Tirou " & ThisItem.rlt_nome & " da equipe do plantão"') + ";\n" + REFRESH),
          ]),
    ]
    # indicadores
    for i, (rot, conta, cor, nav) in enumerate(kpis):
        x = f"224 + {i} * (Parent.Width - 248 + 12) / 4"
        w = "(Parent.Width - 248 - 36) / 4"
        filhos += [
            C(f"{p}Kpi{i}", LBL, Text=f'{conta} & Char(10) & "{rot}"', OnSelect=nav, Fill="Color.White", BorderColor=cor, BorderThickness="1",
              Color="corAzul", Size="13", FontWeight="FontWeight.Semibold", PaddingLeft="16", X=x, Y="308", Width=w, Height="70"),
            C(f"{p}KpiBarra{i}", RET, Fill=cor, X=x, Y="308", Width="5", Height="70"),
        ]
    filhos += [
        C(f"{p}SecTit", LBL, Text='"SEÇÕES"', Color="corAzul", Size="14", FontWeight="FontWeight.Bold", X="224", Y="390", Width="300", Height="30"),
        C(f"{p}GalSecoes", GAL, variante="Vertical", Items="tabSecoes", WrapCount="4", TemplateSize="150", TemplatePadding="6",
          X="218", Y="420", Width="Parent.Width - 236", Height="Parent.Height - 428",
          filhos=[
              C("relSecFundo", RET, Fill="Color.White", BorderColor="corLinha", BorderThickness="1", X="0", Y="0", Width="Parent.TemplateWidth", Height="Parent.TemplateHeight"),
              C("relSecCor", RET, Fill="ThisItem.Cor", X="0", Y="0", Width="Parent.TemplateWidth", Height="4"),
              C("relSecNome", LBL, Text="Upper(ThisItem.Nome)", Color="corAzul", Size="11", FontWeight="FontWeight.Bold", X="14", Y="12", Width="Parent.TemplateWidth - 28", Height="24",
                OnSelect="Navigate(scrChamados, ScreenTransition.None, {locSoAbertos: false, locSecaoFiltro: ThisItem.Valor})"),
              C("relSecTotal", LBL, Text="CountRows(Filter(colRegs, rlt_secao = ThisItem.Valor))", Color="corAzul", Size="24", FontWeight="FontWeight.Bold",
                X="14", Y="38", Width="120", Height="40",
                OnSelect="Navigate(scrChamados, ScreenTransition.None, {locSoAbertos: false, locSecaoFiltro: ThisItem.Valor})"),
              C("relSecResumo", LBL, Color="corMuted", Size="10", X="14", Y="78", Width="Parent.TemplateWidth - 28", Height="22",
                Text=f'With({{a: CountRows(Filter(colRegs, rlt_secao = ThisItem.Valor && {ABERTO})), t: CountRows(Filter(colRegs, rlt_secao = ThisItem.Valor))}}, '
                     f'If(t = 0, "Sem registros", If(a > 0, a & " em aberto  ·  ", "") & (t - a) & " concluído" & If(t - a = 1, "", "s")))'),
              C("relSecAdd", BTN, Text='"+ Registrar"', Visible=ABERTO_REL, X="0", Y="Parent.TemplateHeight - 40", Width="Parent.TemplateWidth", Height="40",
                Fill="Color.White", Color="corAzul", BorderColor="corLinha", BorderThickness="1", HoverFill="corAzul", HoverColor="Color.White", Size="12",
                FontWeight="FontWeight.Semibold", RadiusTopLeft="0", RadiusTopRight="0", RadiusBottomLeft="0", RadiusBottomRight="0",
                OnSelect="Navigate(scrRegistro, ScreenTransition.None, {locId: Blank(), locSecao: ThisItem.Valor})"),
          ]),
    ]
    return tela("scrRelatorio", {"Fill": "corFundo", "OnVisible": "If(!IsBlank(gblRel), Set(gblRel, LookUp(Relatórios, rlt_relatorioid = gblRel.rlt_relatorioid)));\n" + REFRESH}, filhos)


# ================================================================== TELA CHAMADOS
def tela_chamados():
    p = "cha"
    itens = (f"Sort(AddColumns(Filter(colRegs, (!locSoAbertos || {ABERTO}) && (IsBlank(locSecaoFiltro) || rlt_secao = locSecaoFiltro)), "
             f"Ordem, {ORDEM_SEC} * 10000000000000 + Value(rlt_inicio)), Ordem)")
    concluir = (f"With({{r: LookUp(Registros, rlt_registroid = ThisItem.rlt_registroid)}},\n"
                f"  If(ThisItem.rlt_secao = {SEC}.'IOS informados',\n"
                f"    Patch(Registros, r, {{rlt_conclusao: Now(), rlt_ni: false, rlt_statusios: {SI}.Concluído}}),\n"
                f"    Patch(Registros, r, {{rlt_conclusao: Now(), rlt_ni: false, rlt_status: {ST}.CONCLUÍDO}})));\n"
                + hist('"Hora de conclusão e status"', "LookUp(Registros, rlt_registroid = ThisItem.rlt_registroid)") + ";\n"
                + REFRESH + ";\nNotify(\"Concluído: \" & Left(ThisItem.rlt_titulo, 50), NotificationType.Success)")
    filhos = moldura(p, "scrChamados") + titulo(p, '"CHAMADOS DO PLANTÃO"',
                                               '"Todos os registros do turno, por seção e hora de início. Os que ficarem em aberto passam para o próximo turno (RN-009)."')
    filhos += [
        botao(f"{p}Todos", '"Todos (" & CountRows(colRegs) & ")"', "UpdateContext({locSoAbertos: false})", 224, 146, 150, 36,
              primario=True, Fill="If(locSoAbertos, Color.White, corAzul)", Color="If(locSoAbertos, corAzul, Color.White)"),
        botao(f"{p}Abertos", f'"Só em aberto (" & CountRows(Filter(colRegs, {ABERTO})) & ")"', "UpdateContext({locSoAbertos: true})", 382, 146, 170, 36,
              primario=True, Fill="If(locSoAbertos, corAzul, Color.White)", Color="If(locSoAbertos, Color.White, corAzul)"),
        botao(f"{p}LimpaSec", '"Seção: " & LookUp(tabSecoes, Valor = locSecaoFiltro).Nome & "  ×"', "UpdateContext({locSecaoFiltro: Blank()})", 560, 146, 260, 36,
              primario=False, Visible="!IsBlank(locSecaoFiltro)"),
        C(f"{p}Gal", GAL, variante="Vertical", Items=itens, TemplateSize="104", TemplatePadding="6", X="218", Y="190", Width="Parent.Width - 236", Height="Parent.Height - 198",
          filhos=[
              C("chaFundo", RET, Fill="Color.White", BorderColor="corLinha", BorderThickness="1", X="0", Y="0", Width="Parent.TemplateWidth", Height="Parent.TemplateHeight"),
              C("chaBarra", RET, Fill=f"If({ABERTO.replace('rlt_', 'ThisItem.rlt_')}, corLaranja, corVerde)", X="0", Y="0", Width="5", Height="Parent.TemplateHeight"),
              C("chaSecao", LBL, Text="Upper(LookUp(tabSecoes, Valor = ThisItem.rlt_secao).Nome)", Color="corAzul", Size="9", FontWeight="FontWeight.Bold",
                X="18", Y="6", Width="220", Height="20"),
              C("chaStatus", LBL, Text=f"If(ThisItem.rlt_secao = {SEC}.'IOS informados', Text(ThisItem.rlt_statusios), Text(ThisItem.rlt_status)) & If(ThisItem.rlt_herdado, \"  ·  HERDADA\", \"\")",
                Color="corLaranjaTxt", Size="9", FontWeight="FontWeight.Bold", X="240", Y="6", Width="300", Height="20"),
              C("chaTitulo", LBL, Text="ThisItem.rlt_titulo", Color="corTexto", Size="12", FontWeight="FontWeight.Semibold", X="18", Y="26", Width="Parent.TemplateWidth - 420", Height="40"),
              C("chaMeta", LBL, Color="corMuted", Size="10", X="18", Y="68", Width="Parent.TemplateWidth - 420", Height="24",
                Text='"Início " & Text(ThisItem.rlt_inicio, "dd/mm hh:mm") & If(IsBlank(ThisItem.rlt_local), "", "  ·  " & ThisItem.rlt_local.rlt_nome) & '
                     'If(IsBlank(ThisItem.rlt_numero), "", "  ·  Nº " & ThisItem.rlt_numero) & If(ThisItem.rlt_ni && IsBlank(ThisItem.rlt_conclusao), "  ·  Conclusão N/I", "")'),
              C("chaConcl", LBL, Text='If(IsBlank(ThisItem.rlt_conclusao), If(ThisItem.rlt_ni, "Conclusão: N/I", "Conclusão: em aberto"), "Conclusão: " & Text(ThisItem.rlt_conclusao, "dd/mm hh:mm"))',
                Color="corTexto", Size="11", Align="Align.Right", X="Parent.TemplateWidth - 400", Y="10", Width="380", Height="26"),
              botao("chaAgora", '"Concluir agora"', concluir, "Parent.TemplateWidth - 330", 50, 150, 36,
                    Visible=f"{ABERTO_REL} && IsBlank(ThisItem.rlt_conclusao) && !ThisItem.rlt_chamadofalso"),
              botao("chaEditar", 'If(' + ABERTO_REL + ', "Editar", "Ver")', "Navigate(scrRegistro, ScreenTransition.None, {locId: ThisItem.rlt_registroid, locSecao: ThisItem.rlt_secao})",
                    "Parent.TemplateWidth - 170", 50, 150, 36, primario=False),
          ]),
        C(f"{p}Vazio", LBL, Text='"Nenhum chamado " & If(locSoAbertos, "em aberto.", "neste plantão.")', Visible=f"CountRows({p}Gal.AllItems) = 0",
          Color="corMuted", Size="13", Align="Align.Center", X="224", Y="260", Width="Parent.Width - 248", Height="40"),
    ]
    return tela("scrChamados", {"Fill": "corFundo", "OnVisible": REFRESH}, filhos)


# ================================================================== TELA REGISTRO (formulário)
def tela_registro():
    p = "reg"
    tipo = "LookUp(tabSecoes, Valor = locSecao).Tipo"
    ro = f"If({ABERTO_REL}, DisplayMode.Edit, DisplayMode.View)"
    ao_abrir = (
        "UpdateContext({locReg: If(IsBlank(locId), Blank(), LookUp(Registros, rlt_registroid = locId))});\n"
        "UpdateContext({locIni: Coalesce(locReg.rlt_inicio, Now()), locFim: locReg.rlt_conclusao, locNI: Coalesce(locReg.rlt_ni, false),\n"
        f"  locFalso: Coalesce(locReg.rlt_chamadofalso, false), locStatus: Coalesce(locReg.rlt_status, {ST}.'EM ANDAMENTO'),\n"
        f"  locStatusIos: Coalesce(locReg.rlt_statusios, {SI}.'Em andamento'), locArea: locReg.rlt_local.rlt_area, locErro: \"\"}});\n"
        "Reset(regDesc); Reset(regNum); Reset(regMotivo); Reset(regEquipLivre); Reset(regForaLista); Reset(regLimpeza); Reset(regFalso); Reset(regNI);\n"
        "Reset(regArea); Reset(regLocal); Reset(regEquip); Reset(regIniData); Reset(regIniH); Reset(regIniM); Reset(regFimData); Reset(regFimH); Reset(regFimM);\n"
        "Reset(regStatus); Reset(regStatusIos)")
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
    {{m: If(vTipo = "ios" && regStatusIos.Selected.Value = {SI}.Cancelado && IsBlank(Trim(regMotivo.Text)), "Informe o motivo do cancelamento.", "")}},
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
      rlt_status: If(vTipo = "ios", Blank(), regFalso.Value, {ST}.'CHAMADO FALSO', regNI.Value && IsBlank(vFim), {ST}.'EM ANDAMENTO', regStatus.Selected.Value),
      rlt_statusios: If(vTipo <> "ios", Blank(), regNI.Value && IsBlank(vFim), {SI}.'Não informado (NI)', regStatusIos.Selected.Value),
      rlt_motivocancelamento: regMotivo.Text
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
          {{c: "Motivo do cancelamento", m: Coalesce(locReg.rlt_motivocancelamento, "") <> regMotivo.Text}}
        ), m),
        {hist("c", "gblSalvo")})
    );
    Notify(If(vTipo = "fq" && IsBlank(gblSalvo.rlt_equipamento), "Salvo sem código SAP: aparece no Painel Geral de informações.", "Registro salvo."), NotificationType.Success);
    Back()
  )
)"""
    status_fim = (f"UpdateContext({{locFim: {v_fim}}}); If(!IsBlank(locFim), UpdateContext({{locNI: false, locStatus: {ST}.CONCLUÍDO, locStatusIos: {SI}.Concluído}}))")
    agora = f"UpdateContext({{locFim: Now(), locNI: false, locStatus: {ST}.CONCLUÍDO, locStatusIos: {SI}.Concluído}})"
    limpar = (f"UpdateContext({{locFim: Blank(), locStatus: If(locStatus = {ST}.CONCLUÍDO, {ST}.'EM ANDAMENTO', locStatus), "
              f"locStatusIos: If(locStatusIos = {SI}.Concluído, {SI}.'Em andamento', locStatusIos)}}); Reset(regFimData); Reset(regFimH); Reset(regFimM)")
    xl, xr, w = 224, "(224 + (Parent.Width - 248) / 2 + 12)", "((Parent.Width - 248) / 2 - 12)"

    def ent(nome, controle, x, y, largura, **kw):
        base = dict(X=str(x), Y=str(y), Width=largura, DisplayMode=ro)
        base.update(kw)
        return C(nome, controle, **base)

    filhos = moldura(p, "scrChamados") + titulo(
        p, 'If(IsBlank(locId), "NOVO REGISTRO", "REGISTRO") & "  ·  " & Upper(LookUp(tabSecoes, Valor = locSecao).Nome)',
        'If(locReg.rlt_herdado, "Pendência herdada: a data de início original é mantida (RN-009).", "Campos com * são obrigatórios.")')
    filhos += [
        C(f"{p}Fundo", RET, Fill="Color.White", BorderColor="corLinha", BorderThickness="1", X="218", Y="146", Width="Parent.Width - 236", Height="Parent.Height - 216"),
        # descrição / assunto
        rotulo(f"{p}RotDesc", f'If({tipo} = "ios", "ASSUNTO *", "DESCRIÇÃO DA ATIVIDADE *")', xl + 12, 156, 400),
        ent("regDesc", TXT, xl + 12, 178, "Parent.Width - 272", Mode="TextMode.MultiLine", Height="64", Default="locReg.rlt_descricao",
            Visible=f'{tipo} in ["corretiva", "ios"]'),
        # local (corretivas)
        rotulo(f"{p}RotArea", '"LOCAL – ÁREA"', xl + 12, 252), rotulo(f"{p}RotLocal", '"LOCAL – ESPECÍFICO *"', f"{xr}", 252),
        ent("regArea", DDL, xl + 12, 274, w, Height="40", Items="Sort(Distinct(Locais, rlt_area), Value)", Default="locArea", Visible=f'{tipo} = "corretiva"'),
        ent("regLocal", CBX, xr, 274, w, Height="40", Items="Filter(Locais, rlt_area = regArea.Selected.Value)", DisplayFields='["rlt_nome"]', SearchFields='["rlt_nome"]',
            SelectMultiple="false", DefaultSelectedItems="Filter(Locais, rlt_localid = locReg.rlt_local.rlt_localid)", Visible=f'{tipo} = "corretiva"'),
        # equipamento (Fator Q e Preventiva)
        rotulo(f"{p}RotEquip", '"EQUIPAMENTO *"', xl + 12, 252, 300),
        ent("regEquip", CBX, xl + 12, 274, w, Height="40", Items="Equipamentos", DisplayFields='["rlt_nome"]', SearchFields='["rlt_nome", "rlt_codigosap"]',
            SelectMultiple="false", DefaultSelectedItems="Filter(Equipamentos, rlt_equipamentoid = locReg.rlt_equipamento.rlt_equipamentoid)",
            Visible=f'{tipo} in ["fq", "prev"] && !regForaLista.Value'),
        ent("regForaLista", CHK, xr, 270, w, Height="24", Text='"Equipamento fora da lista (vai para o Painel geral)"', Default="!IsBlank(locReg.rlt_equipamentolivre)",
            Visible=f'{tipo} = "fq"', Size="11"),
        ent("regEquipLivre", TXT, xl + 12, 274, w, Height="40", Default="locReg.rlt_equipamentolivre", HintText='"Descreva o equipamento"',
            Visible=f'{tipo} = "fq" && regForaLista.Value'),
        ent("regEquipSap", LBL, xr, 296, w, Height="24", Text='If(IsBlank(regEquip.Selected), "", "Código SAP " & regEquip.Selected.rlt_codigosap & "  ·  " & Text(regEquip.Selected.rlt_tipo))',
            Color="corMuted", Size="10", Visible=f'{tipo} in ["fq", "prev"] && !regForaLista.Value'),
        # número
        rotulo(f"{p}RotNum", f'Switch({tipo}, "fq", "Nº DO CHAMADO *", "prev", "Nº DA ORDEM DE SERVIÇO *", "Nº IOS * (8 dígitos)")', xl + 12, 324),
        ent("regNum", TXT, xl + 12, 346, w, Height="40", Default="locReg.rlt_numero", Visible=f'{tipo} in ["fq", "prev", "ios"]'),
        # início
        rotulo(f"{p}RotIni", '"INÍCIO (DATA E HORA) *"', xl + 12, 396),
        ent("regIniData", DTP, xl + 12, 418, "200", Height="40", DefaultDate="locIni", Format='"dd/mm/yyyy"',
            DisplayMode=f"If({ABERTO_REL} && !locReg.rlt_herdado, DisplayMode.Edit, DisplayMode.View)"),
        ent("regIniH", DDL, xl + 220, 418, "80", Height="40", Items="tabHoras", Default='Text(Hour(locIni), "00")',
            DisplayMode=f"If({ABERTO_REL} && !locReg.rlt_herdado, DisplayMode.Edit, DisplayMode.View)"),
        ent("regIniM", DDL, xl + 306, 418, "80", Height="40", Items="tabMinutos", Default='Text(Minute(locIni), "00")',
            DisplayMode=f"If({ABERTO_REL} && !locReg.rlt_herdado, DisplayMode.Edit, DisplayMode.View)"),
        ent("regNI", CHK, xl + 12, 466, "300", Height="30", Text='"N/I – não informado"', Default="locNI", Size="12",
            OnCheck="UpdateContext({locNI: true})", OnUncheck="UpdateContext({locNI: false})",
            DisplayMode=f"If({ABERTO_REL} && IsBlank(locFim), DisplayMode.Edit, DisplayMode.Disabled)"),
        # conclusão
        rotulo(f"{p}RotFim", '"HORA DE CONCLUSÃO"', xr, 396),
        ent("regFimData", DTP, xr, 418, "200", Height="40", DefaultDate="locFim", Format='"dd/mm/yyyy"', OnChange=status_fim),
        ent("regFimH", DDL, f"{xr} + 208", 418, "80", Height="40", Items="tabHoras", Default='If(IsBlank(locFim), "", Text(Hour(locFim), "00"))',
            AllowEmptySelection="true", OnChange=status_fim),
        ent("regFimM", DDL, f"{xr} + 294", 418, "80", Height="40", Items="tabMinutos", Default='If(IsBlank(locFim), "", Text(Minute(locFim), "00"))',
            AllowEmptySelection="true", OnChange=status_fim),
        botao("regAgora", '"Agora"', agora, f"{xr} + 382", 418, 80, 40, primario=False, Visible=ABERTO_REL),
        botao("regLimpar", '"Limpar"', limpar, f"{xr} + 468", 418, 80, 40, primario=False, Visible=ABERTO_REL),
        C(f"{p}AjudaFim", LBL, Text='If(IsBlank(locFim), "Preencha quando o chamado for concluído. O status muda sozinho.", "")', Color="corMuted", Size="10",
          X=xr, Y="462", Width=w, Height="22"),
        # status
        rotulo(f"{p}RotStatus", f'If({tipo} = "ios", "STATUS DO IOS *", "STATUS *")', xl + 12, 506),
        ent("regStatus", DDL, xl + 12, 528, w, Height="40", Default="locStatus", Visible=f'{tipo} <> "ios"',
            Items=f"Filter(Choices({ST}), Value <> {ST}.'CHAMADO FALSO' && (!IsBlank(locFim) || Value <> {ST}.CONCLUÍDO))",
            OnChange="UpdateContext({locStatus: Self.Selected.Value})",
            DisplayMode=f"If({ABERTO_REL} && !regFalso.Value && !(regNI.Value && IsBlank(locFim)), DisplayMode.Edit, DisplayMode.Disabled)"),
        ent("regStatusIos", DDL, xl + 12, 528, w, Height="40", Default="locStatusIos", Visible=f'{tipo} = "ios"',
            Items=f"Filter(Choices({SI}), !IsBlank(locFim) || Value <> {SI}.Concluído)",
            OnChange="UpdateContext({locStatusIos: Self.Selected.Value})",
            DisplayMode=f"If({ABERTO_REL} && !(regNI.Value && IsBlank(locFim)), DisplayMode.Edit, DisplayMode.Disabled)"),
        C(f"{p}AjudaStatus", LBL, Color="corMuted", Size="10", X=str(xl + 12), Y="572", Width=w, Height="22",
          Text=f'If(regFalso.Value, "Chamado falso não vira pendência.", regNI.Value && IsBlank(locFim), "EM ANDAMENTO porque está marcado N/I.", '
               f'!IsBlank(locFim) && locStatus = {ST}.CONCLUÍDO, "CONCLUÍDO porque a hora de conclusão foi preenchida. Você pode trocar o status.", '
               f'"Sem hora de conclusão o chamado continua aberto e passa para o próximo turno.")'),
        rotulo(f"{p}RotMotivo", '"MOTIVO DO CANCELAMENTO *"', xr, 506),
        ent("regMotivo", TXT, xr, 528, w, Height="40", Default="locReg.rlt_motivocancelamento",
            Visible=f'{tipo} = "ios" && regStatusIos.Selected.Value = {SI}.Cancelado'),
        ent("regFalso", CHK, xl + 12, 600, "400", Height="30", Text='"Chamado falso"', Default="locFalso", Size="12",
            OnCheck="UpdateContext({locFalso: true})", OnUncheck="UpdateContext({locFalso: false})", Visible=f'{tipo} in ["corretiva", "fq"]'),
        ent("regLimpeza", CHK, xr, 600, w, Height="30", Text='"Limpeza técnica (fora de preventiva x corretiva)"', Default="Coalesce(locReg.rlt_limpezatecnica, false)",
            Size="12", Visible=f"locSecao = {SEC}.Outros"),
        C(f"{p}Erro", LBL, Text="locErro", Visible="!IsBlank(locErro)", Color="corVerm", Fill="corVerm20", Size="11", FontWeight="FontWeight.Semibold",
          PaddingLeft="12", X="224", Y="Parent.Height - 62", Width="Parent.Width - 600", Height="48"),
        botao(f"{p}Cancelar", 'If(' + ABERTO_REL + ', "Cancelar", "Voltar")', "Back()", "Parent.Width - 360", "Parent.Height - 58", 160, 44, primario=False),
        botao(f"{p}Salvar", '"Salvar"', salvar, "Parent.Width - 190", "Parent.Height - 58", 170, 44, Visible=ABERTO_REL),
    ]
    return tela("scrRegistro", {"Fill": "corFundo", "OnVisible": ao_abrir}, filhos)


# ================================================================== TELA HISTÓRICO
def tela_historico():
    p = "his"
    filhos = moldura(p, "scrHistorico") + titulo(p, '"HISTÓRICO DE ALTERAÇÕES"',
                                                '"Quem alterou, quando e o campo. Ninguém pode alterar o histórico (RN-021)."')
    filhos += [
        C(f"{p}Gal", GAL, variante="Vertical", TemplateSize="64", TemplatePadding="4", X="218", Y="146", Width="Parent.Width - 236", Height="Parent.Height - 154",
          Items="Sort(Filter(Histórico, rlt_relatorio.rlt_relatorioid = gblRel.rlt_relatorioid), rlt_quando, SortOrder.Descending)",
          filhos=[
              C("hisFundo", RET, Fill="Color.White", BorderColor="corLinha", BorderThickness="1", X="0", Y="0", Width="Parent.TemplateWidth", Height="Parent.TemplateHeight"),
              C("hisQuando", LBL, Text='Text(ThisItem.rlt_quando, "dd/mm/yyyy hh:mm")', Color="corMuted", Size="11", X="14", Y="6", Width="150", Height="24"),
              C("hisQuem", LBL, Text='Coalesce(ThisItem.rlt_quem.rlt_nome, "—") & If(IsBlank(ThisItem.rlt_quem), "", "  ·  " & Text(ThisItem.rlt_quem.rlt_perfil))',
                Color="corTexto", Size="11", FontWeight="FontWeight.Semibold", X="170", Y="6", Width="320", Height="24"),
              C("hisCampo", LBL, Text="ThisItem.rlt_campo", Color="corAzul", Size="11", FontWeight="FontWeight.Bold", X="500", Y="6", Width="Parent.TemplateWidth - 520", Height="24"),
              C("hisReg", LBL, Text='Coalesce(ThisItem.rlt_registro.rlt_titulo, "")', Color="corMuted", Size="10", X="170", Y="32", Width="Parent.TemplateWidth - 190", Height="24"),
          ]),
    ]
    return tela("scrHistorico", {"Fill": "corFundo"}, filhos)


# ================================================================== TELA PAINEL GERAL
def tela_painel():
    p = "pai"
    sem_sap = f"Filter(colRegs, rlt_secao = {SEC}.'Fator Q (Z9)' && IsBlank(rlt_equipamento))"
    corrigir = ("If(IsBlank(paiCbx.Selected), Notify(\"Escolha o equipamento na lista.\", NotificationType.Warning),\n"
                "  Patch(Registros, LookUp(Registros, rlt_registroid = ThisItem.rlt_registroid), {rlt_equipamento: paiCbx.Selected, rlt_equipamentolivre: \"\"});\n  "
                + hist('"Código SAP corrigido: " & paiCbx.Selected.rlt_codigosap', "LookUp(Registros, rlt_registroid = ThisItem.rlt_registroid)")
                + ";\n  " + REFRESH.replace("\n", "\n  ") + ";\n  Notify(\"Corrigido.\", NotificationType.Success))")
    filhos = moldura(p, "scrPainel") + titulo(p, '"PAINEL GERAL DE INFORMAÇÕES"', '"Correções, pendências antigas e listas do app. Todos os usuários podem ver."')
    filhos += [
        C(f"{p}T1", LBL, Text=f'"FATOR Q SEM CÓDIGO SAP (" & CountRows({sem_sap}) & ")"', Color="corAzul", Size="13", FontWeight="FontWeight.Bold",
          X="224", Y="146", Width="600", Height="28"),
        C(f"{p}Gal1", GAL, variante="Vertical", Items=sem_sap, TemplateSize="64", TemplatePadding="4", X="218", Y="176", Width="Parent.Width - 236", Height="210",
          filhos=[
              C("paiFundo", RET, Fill="Color.White", BorderColor="corVerm", BorderThickness="1", X="0", Y="0", Width="Parent.TemplateWidth", Height="Parent.TemplateHeight"),
              C("paiNome", LBL, Text='Coalesce(ThisItem.rlt_equipamentolivre, ThisItem.rlt_titulo) & "  ·  Chamado " & ThisItem.rlt_numero',
                Color="corTexto", Size="11", FontWeight="FontWeight.Semibold", X="14", Y="16", Width="Parent.TemplateWidth - 560", Height="28"),
              C("paiCbx", CBX, Items="Filter(Equipamentos, rlt_tipo <> [@'Tipo de equipamento'].Bagagem)", DisplayFields='["rlt_nome"]',
                SearchFields='["rlt_nome", "rlt_codigosap"]', SelectMultiple="false", X="Parent.TemplateWidth - 540", Y="12", Width="380", Height="40",
                DisplayMode=f"If({ABERTO_REL}, DisplayMode.Edit, DisplayMode.View)"),
              botao("paiCorrigir", '"Corrigir"', corrigir, "Parent.TemplateWidth - 150", 12, 130, 40, Visible=ABERTO_REL),
          ]),
        C(f"{p}T2", LBL, Text=f'"PENDÊNCIAS ABERTAS HÁ MAIS DE 7 DIAS"', Color="corAzul", Size="13", FontWeight="FontWeight.Bold",
          X="224", Y="396", Width="600", Height="28"),
        C(f"{p}Gal2", GAL, variante="Vertical", Items=f"Filter(colRegs, {ABERTO} && DateDiff(rlt_inicio, Now(), TimeUnit.Days) > 7)",
          TemplateSize="44", TemplatePadding="2", X="218", Y="426", Width="Parent.Width - 236", Height="Parent.Height - 520",
          filhos=[
              C("paiVelha", LBL, Text='Upper(LookUp(tabSecoes, Valor = ThisItem.rlt_secao).Nome) & "  ·  " & ThisItem.rlt_titulo & "  ·  desde " & Text(ThisItem.rlt_inicio, "dd/mm/yyyy")',
                Color="corTexto", Size="11", Fill="Color.White", PaddingLeft="12", X="0", Y="0", Width="Parent.TemplateWidth", Height="40"),
          ]),
        C(f"{p}Listas", LBL, Color="corMuted", Size="11", X="224", Y="Parent.Height - 84", Width="Parent.Width - 248", Height="60",
          Text='"Listas usadas pelo app:  " & CountRows(Equipamentos) & " equipamentos  ·  " & CountRows(Locais) & " locais  ·  " & CountRows(Pessoas) & " pessoas e perfis"'),
    ]
    return tela("scrPainel", {"Fill": "corFundo", "OnVisible": REFRESH}, filhos)


# ================================================================== TELA FECHAR
def tela_fechar():
    p = "fec"
    avisos = (f'Concat(Filter(Table('
              f'{{m: If(CountRows(Filter(colEquipe, rlt_perfil = [@Perfil].\'Técnico(a)\')) = 0, "Nenhum técnico fez login neste plantão.", "")}},'
              f'{{m: If(CountRows(Filter(colEquipe, rlt_perfil = [@Perfil].\'Operador(a)\')) = 0, "Nenhum operador fez login neste plantão.", "")}},'
              f'{{m: If(CountRows(Filter(colRegs, rlt_secao = {SEC}.\'Fator Q (Z9)\' && IsBlank(rlt_equipamento))) > 0, "Há chamados do Fator Q sem código SAP.", "")}}'
              f'), !IsBlank(m)), "•  " & m, Char(10))')
    fechar = (f"Patch(Relatórios, LookUp(Relatórios, rlt_relatorioid = gblRel.rlt_relatorioid), {{rlt_situacao: {SIT}.Fechado, rlt_fechadoem: Now(), rlt_fechadopor: gblUsuario}});\n"
              + hist('"Relatório fechado e enviado"') + ";\n"
              "Set(gblRel, LookUp(Relatórios, rlt_relatorioid = gblRel.rlt_relatorioid));\n"
              "Reset(fecConf);\n"
              "Notify(\"Relatório fechado. O PDF e o e-mail entram com o fluxo Fechar e enviar (próxima etapa).\", NotificationType.Success);\n"
              "Navigate(scrRelatorio, ScreenTransition.None)")
    filhos = moldura(p, "scrFechar") + titulo(p, '"FECHAR RELATÓRIO"',
                                             '"Qualquer usuário pode fechar e enviar (RN-007). O envio fica registrado com o nome de quem enviou."')
    filhos += [
        C(f"{p}Resumo", LBL, Color="corTexto", Size="12", Fill="Color.White", PaddingLeft="16", PaddingTop="12", VerticalAlign="VerticalAlign.Top",
          X="224", Y="146", Width="(Parent.Width - 248) / 2 - 8", Height="300",
          Text='"RESUMO" & Char(10) & Char(10) & Concat(tabSecoes, Nome & ": " & CountRows(Filter(colRegs, rlt_secao = Valor)), Char(10)) & Char(10) & Char(10) & '
               f'"Passam ao próximo turno: " & CountRows(Filter(colRegs, {ABERTO}))'),
        C(f"{p}Avisos", LBL, Color="corLaranjaTxt", Size="12", Fill="corLaranja20", PaddingLeft="16", PaddingTop="12", VerticalAlign="VerticalAlign.Top",
          X="224 + (Parent.Width - 248) / 2 + 8", Y="146", Width="(Parent.Width - 248) / 2 - 8", Height="300",
          Text=f'If(IsBlank({avisos}), "Nenhum ponto a conferir.", "A CONFERIR (não impedem o fechamento)" & Char(10) & Char(10) & {avisos})'),
        C(f"{p}Equipe", LBL, Color="corTexto", Size="12", X="224", Y="456", Width="Parent.Width - 248", Height="60",
          Text='"Equipe que vai no PDF: " & Concat(colEquipe, rlt_nome & " (" & Text(rlt_perfil) & ")", ", ")'),
        C("fecConf", CHK, Text='"Eu, " & Coalesce(gblUsuario.rlt_nome, User().FullName) & ", confirmo que revisei o relatório e quero fechar e enviar."',
          X="224", Y="524", Width="Parent.Width - 248", Height="40", Size="12", Visible=ABERTO_REL),
        botao(f"{p}Btn", '"Fechar e enviar"', fechar, "Parent.Width - 210", "Parent.Height - 70", 190, 48, Visible=ABERTO_REL,
              DisplayMode="If(fecConf.Value, DisplayMode.Edit, DisplayMode.Disabled)"),
        C(f"{p}Fechado", LBL, Visible=f"Not({ABERTO_REL})", Color="corAzul", Fill="corAzul10", Size="12", PaddingLeft="16", X="224", Y="524", Width="Parent.Width - 248", Height="48",
          Text='If(IsBlank(gblRel), "Nenhum relatório.", "Relatório fechado em " & Text(gblRel.rlt_fechadoem, "dd/mm/yyyy hh:mm") & " por " & Coalesce(gblRel.rlt_fechadopor.rlt_nome, "—") & ". Abra o próximo plantão na tela Relatório.")'),
    ]
    return tela("scrFechar", {"Fill": "corFundo", "OnVisible": REFRESH}, filhos)


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
    OnStart: {bloco(f'''=Set(gblUsuario, LookUp(Pessoas, Lower(rlt_email) = Lower(User().Email)));
Set(gblRel, First(Sort(Filter(Relatórios, rlt_situacao = {SIT}.Aberto), createdon, SortOrder.Descending)));
If(IsBlank(gblRel), Set(gblRel, First(Sort(Relatórios, createdon, SortOrder.Descending))));
If(!IsBlank(gblUsuario) && {ABERTO_REL} &&
   IsBlank(LookUp('Equipe do plantão', rlt_relatorio.rlt_relatorioid = gblRel.rlt_relatorioid && rlt_pessoa.rlt_pessoaid = gblUsuario.rlt_pessoaid && IsBlank(rlt_retiradoem))),
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
    - scrFechar
    - scrAbrir
"""

CABEC = "# Gerado por app/gerar_app.py a partir do protótipo validado. Edite o gerador, não este arquivo.\n"


def main(src):
    arquivos = {
        "App.pa.yaml": APP, "_EditorState.pa.yaml": EDITOR,
        "scrRelatorio.pa.yaml": tela_relatorio(), "scrChamados.pa.yaml": tela_chamados(), "scrRegistro.pa.yaml": tela_registro(),
        "scrHistorico.pa.yaml": tela_historico(), "scrPainel.pa.yaml": tela_painel(), "scrFechar.pa.yaml": tela_fechar(),
        "scrAbrir.pa.yaml": tela_abrir(),
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
