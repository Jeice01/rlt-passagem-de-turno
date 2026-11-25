"""Gera a solução RLT_Fluxos (fluxo "RLT – Fechar e enviar") no formato do pac solution unpack.

Uso:
    python -E -P ferramentas/fluxos/gerar_fluxo_fechar.py
    pac solution pack --zipfile ferramentas/fluxos/saida/RLT_Fluxos.zip --folder solution/RLT_Fluxos/src --packagetype Unmanaged

O fluxo (RF-013 a RF-016, RN-004, RN-005, RN-008, RF-018):
1. Dispara quando um relatório passa para Fechado (rlt_situacao).
2. Lê o relatório, os registros e a equipe no Dataverse.
3. Monta o HTML do PDF no layout do protótipo validado (prototipo/index.html, telaPDF).
   O código SAP do Fator Q não entra no PDF (RF-018).
4. Cria o HTML numa pasta temporária do OneDrive, converte em PDF e guarda o PDF em
   <pasta>/<ano>/<mês>/RLT-PASSAGEM DE TURNO <TURNO> <dd.mm.aaaa>.pdf.
5. Envia o e-mail da RN-005 aos destinatários da variável de ambiente rlt_destinatarios.
6. Grava o resultado (ou o erro) em rlt_resultadoenvio do relatório.

Fica fora do Git: ferramentas/fluxos/saida/ (zip e arquivo de configuração com e-mails).
"""
import json
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DESTINO = os.path.join(RAIZ, "solution", "RLT_Fluxos", "src")

FLUXO_ID = "7c1d2e3f-4a5b-4c6d-8e9f-0a1b2c3d4e51"  # fixo: importar de novo atualiza o mesmo fluxo
FLUXO_NOME = "RLT – Fechar e enviar"
ARQ_FLUXO = f"RLT-Fecharenviar-{FLUXO_ID.upper()}.json"

TZ = "E. South America Standard Time"  # horário de Brasília (RNF-006)
FECHADO = 448170001
SEC = {"elm": 448170000, "ele": 448170001, "bhs": 448170002, "civ": 448170003, "out": 448170004,
       "fq": 448170005, "prev": 448170006, "ios": 448170007}
PENDENTE, IOS_CANCELADO, TURNO_ALFA = 448170000, 448170004, 448170000
CANCELADO = 448170004  # status da atividade CANCELADO (25/11/2026)

# Seções do PDF, na ordem e com os títulos do protótipo validado
COLS_CORR = ["Descrição da atividade", "Local", "Hora início", "Hora de conclusão", "Status"]
SECOES = [
    ("elm", "MANUT. CORRETIVA NÃO PROGRAMADA – ELETROMECÂNICA", COLS_CORR),
    ("ele", "MANUT. CORRETIVA NÃO PROGRAMADA – ELETROELETRÔNICA", COLS_CORR),
    ("bhs", "MANUT. CORRETIVA NÃO PROGRAMADA – BHS", COLS_CORR),
    ("civ", "MANUT. CORRETIVA NÃO PROGRAMADA – CIVIL", COLS_CORR),
    ("out", "OUTROS", COLS_CORR),
    ("fq", "MANUT. CORRETIVA NÃO PROGRAMADA – FATOR Q (Z9)", ["Equipamento", "Chamado", "Hora início", "Hora de conclusão", "Status"]),
    ("prev", "MANUT. PREVENTIVA – (ZM02)", ["Equipamento", "Ordem de serviço", "Hora início", "Hora de conclusão", "Status"]),
    ("ios", "IOS INFORMADOS AO CCM", ["Assunto", "Nº IOS", "Hora início", "Hora de conclusão", "Status do IOS"]),
]

P_DEST = "RLT – Destinatários do e-mail (rlt_destinatarios)"
P_PASTA = "RLT – Pasta dos PDFs no OneDrive (rlt_pastapdf)"
FMT = "@OData.Community.Display.V1.FormattedValue"

DATAVERSE, ONEDRIVE, OUTLOOK = "shared_commondataserviceforapps", "shared_onedriveforbusiness", "shared_office365"
CONEXOES = {
    DATAVERSE: ("rlt_dataverse", "RLT – Dataverse"),
    ONEDRIVE: ("rlt_onedrive", "RLT – OneDrive for Business"),
    OUTLOOK: ("rlt_outlook", "RLT – Office 365 Outlook"),
}


# ------------------------------------------------------------------ expressões
def q(s):
    """Literal de texto numa expressão do fluxo."""
    return "'" + s.replace("'", "''") + "'"


def esc(x):
    """Escapa texto para HTML."""
    return f"replace(replace(replace(coalesce({x}, ''), '&', '&amp;'), '<', '&lt;'), '>', '&gt;')"


def dh(x, fmt="dd/MM/yyyy HH:mm"):
    """Data e hora de Brasília; vazio quando não há data (não depende do if ser preguiçoso)."""
    return f"if(empty(coalesce({x}, '')), '', convertFromUtc(coalesce({x}, '2000-01-01T00:00:00Z'), {q(TZ)}, {q(fmt)}))"


def so_data(x, fmt):
    """Coluna "só data" (Behavior DateOnly, como rlt_data): vem sem fuso, então não converte de UTC."""
    return f"if(empty(coalesce({x}, '')), '', formatDateTime(coalesce({x}, '2000-01-01T00:00:00'), {q(fmt)}))"


def it(campo):
    return f"item()?['{campo}']"


def op(conector, operacao, parametros, run_after=None):
    a = {"type": "OpenApiConnection",
         "inputs": {"host": {"connectionName": conector, "operationId": operacao, "apiId": f"/providers/Microsoft.PowerApps/apis/{conector}"},
                    "parameters": parametros, "authentication": "@parameters('$authentication')"},
         "runAfter": run_after or {}}
    return a


def depois(*nomes, status=("Succeeded",)):
    return {n: list(status) for n in nomes}


# ------------------------------------------------------------------ linhas das tabelas
eh_equip = f"or(equals({it('rlt_secao')}, {SEC['fq']}), equals({it('rlt_secao')}, {SEC['prev']}))"
eh_ios = f"equals({it('rlt_secao')}, {SEC['ios']})"
equipamento = esc(f"coalesce({it('_rlt_equipamento_value' + FMT)}, {it('rlt_equipamentolivre')})")
descricao = esc(f"coalesce({it('rlt_descricao')}, {it('rlt_titulo')})")
motivo = (f"if(or(and({eh_ios}, equals({it('rlt_statusios')}, {IOS_CANCELADO})), and(not({eh_ios}), equals({it('rlt_status')}, {CANCELADO}))), "
          f"concat('<br><i>Motivo: ', {esc(it('rlt_motivocancelamento'))}, '</i>'), '')")
col1 = f"if({eh_equip}, concat({equipamento}, {motivo}), concat({descricao}, {motivo}))"
col2 = f"if(or({eh_equip}, {eh_ios}), {esc(it('rlt_numero'))}, {esc(it('_rlt_local_value' + FMT))})"
fim = (f"if(not(empty(coalesce({it('rlt_conclusao')}, ''))), {dh(it('rlt_conclusao'))}, "
       f"if(equals({it('rlt_ni')}, true), 'N/I', if(equals({it('rlt_status')}, {PENDENTE}), '–', '')))")
status = f"if({eh_ios}, coalesce({it('rlt_statusios' + FMT)}, ''), coalesce({it('rlt_status' + FMT)}, ''))"
herdada = f"if(equals({it('rlt_herdado')}, true), ' <span class=\"h\">(herdada)</span>', '')"
# Cada linha começa com S<seção>| para o filtro por seção; o prefixo sai no join.
linha = (f"@concat('S', string({it('rlt_secao')}), '|<tr><td>', {col1}, {herdada}, '</td><td>', {col2}, '</td><td>', "
         f"{dh(it('rlt_inicio'))}, '</td><td>', {fim}, '</td><td>', {status}, '</td></tr>')")


def tabela(sec, titulo, cols):
    f = f"body('Filtrar_{sec}')"
    corpo = f"if(empty({f}), '<tr><td colspan=\"5\" class=\"vazio\">Sem registros</td></tr>', replace(join({f}, ''), 'S{SEC[sec]}|', ''))"
    return (f"'<h4>{titulo}</h4><table><thead><tr>{''.join(f'<th>{c}</th>' for c in cols)}</tr></thead><tbody>', "
            f"{corpo}, '</tbody></table><div class=\"qtd\">QUANTIDADE: ', string(length({f})), '</div>'")


CSS = ("body{font-family:Arial,Helvetica,sans-serif;font-size:10pt;color:#111;margin:0}"
       ".ph{border-bottom:3px solid #72BF44;padding-bottom:8px;text-align:right;font-size:9pt;line-height:1.5;color:#003863}"
       ".ph b{float:left;font-size:13pt;text-align:left;line-height:1.3}"
       ".tit{text-align:center;text-transform:uppercase;font-size:13pt;font-weight:bold;color:#003863;margin:12px 0 8px;letter-spacing:1px}"
       "h4{text-transform:uppercase;font-size:10.5pt;color:#fff;background:#003863;padding:5px 8px;margin:14px 0 0}"
       "table{width:100%;border-collapse:collapse}td,th{border:1px solid #c9d2db;padding:4px 6px;text-align:left;vertical-align:top}"
       "th{background:#e8edf2;font-size:8.5pt;text-transform:uppercase}"
       ".qtd{text-align:right;font-weight:bold;padding:3px 6px;background:#f5f7f9;border:1px solid #c9d2db;border-top:0}"
       "img.foto{max-width:220px;max-height:220px;border:1px solid #c9d2db}"
       ".vazio{color:#888}.h{color:#5b6876;font-size:8.5pt}.env{margin-top:6px}"
       ".rod{margin-top:18px;border-top:1px solid #c9d2db;padding-top:6px;font-size:8.5pt;color:#5b6876}")

# ------------------------------------------------------------------ anexos dos chamados (RF-007, RF-016)
# FetchXML: anexos dos registros deste relatório, com título, seção e início do registro (link-entity "r").
FETCH_ANEXOS = ("<fetch><entity name=\"rlt_anexo\"><attribute name=\"rlt_anexoid\"/><attribute name=\"rlt_nome\"/><attribute name=\"rlt_tipo\"/>"
                "<order attribute=\"createdon\"/>"
                "<link-entity name=\"rlt_registro\" from=\"rlt_registroid\" to=\"rlt_registro\" alias=\"r\">"
                "<attribute name=\"rlt_titulo\"/><attribute name=\"rlt_secao\"/><attribute name=\"rlt_inicio\"/>"
                "<filter><condition attribute=\"rlt_relatorio\" operator=\"eq\" value=\"@{triggerOutputs()?['body/rlt_relatorioid']}\"/></filter>"
                "</link-entity></entity></fetch>")


def ia(campo):
    """Campo do registro ligado (alias r): o Dataverse devolve "r.campo" ou "r_x002e_campo", conforme a versão."""
    return f"coalesce(items('Para_cada_anexo')?['r.{campo}'], items('Para_cada_anexo')?['r_x002e_{campo}'])"


EXT = "toLower(coalesce(items('Para_cada_anexo')?['rlt_tipo'], ''))"
EH_FOTO = f"contains(createArray('jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'), {EXT})"
MIME = f"if(equals({EXT}, 'jpg'), 'jpeg', {EXT})"
NOME_ANEXO = esc("items('Para_cada_anexo')?['rlt_nome']")
LINHA_ANEXO = (f"@concat('<tr><td>', {esc(ia('rlt_secao' + FMT))}, '</td><td>', {esc(ia('rlt_titulo'))}, "
               f"'<br><span class=\"h\">Início ', {dh(ia('rlt_inicio'))}, '</span></td><td>', "
               f"if({EH_FOTO}, concat('<img class=\"foto\" src=\"data:image/', {MIME}, ';base64,', base64(body('Baixar_arquivo')), '\">'), "
               f"concat('Arquivo: ', {NOME_ANEXO})), '</td></tr>')")


D = "outputs('Dados')"
html = ("@concat('<!DOCTYPE html><html><head><meta charset=\"utf-8\"><title>', " + D + "?['nome'], '</title><style>" + CSS + "</style></head><body>"
        "<div class=\"ph\"><b>Aeroporto de Brasília</b>AEROPORTO INTERNACIONAL DE BRASÍLIA<br>GERÊNCIA DE MANUTENÇÃO<br>"
        "COORDENAÇÃO DE PLANEJAMENTO E CONTROLE DE MANUTENÇÃO<br>CENTRO DE CONTROLE DE MANUTENÇÃO</div>"
        "<div class=\"tit\">Relatório de Passagem de Turno – ', " + D + "?['turno'], ' – ', " + D + "?['dataBarra'], '</div>"
        "<table><tbody><tr><th style=\"width:18%\">Data</th><td>', " + D + "?['dataBarra'], ' (', " + D + "?['periodo'], ')</td>"
        "<th style=\"width:14%\">Turno</th><td>', " + D + "?['turno'], '</td></tr></tbody></table>"
        "<h4>Equipe do plantão</h4><table><thead><tr><th>Nome</th><th>Perfil</th></tr></thead><tbody>', "
        "if(empty(body('Linhas_equipe')), '<tr><td colspan=\"2\" class=\"vazio\">Ninguém fez login</td></tr>', join(body('Linhas_equipe'), '')), "
        "'</tbody></table><div class=\"env\">Enviado por <b>', " + D + "?['fechadoPor'], '</b> em ', " + D + "?['fechadoEm'], '</div>', "
        + ", ".join(tabela(s, t, c) for s, t, c in SECOES) +
        ", '<h4>Anexos dos chamados</h4><table><thead><tr><th style=\"width:22%\">Seção</th><th>Chamado</th><th style=\"width:36%\">Fotos e arquivos</th></tr></thead><tbody>', "
        "if(empty(variables('linhasAnexos')), '<tr><td colspan=\"3\" class=\"vazio\">Sem anexos</td></tr>', join(variables('linhasAnexos'), '')), "
        "'</tbody></table><div class=\"qtd\">QUANTIDADE: ', string(length(variables('linhasAnexos'))), '</div>'"
        ", '<div class=\"rod\">Classificação: <b>Interno</b> &nbsp;·&nbsp; ', " + D + "?['nome'], '</div></body></html>')")

REL = "body('Obter_relatorio')"
DATA_REL = f"{REL}?['rlt_data']"
TURNO = f"if(equals({REL}?['rlt_turno'], {TURNO_ALFA}), 'ALFA', 'BRAVO')"
dados = {
    "turno": f"@{{{TURNO}}}",
    "turnoNome": f"@{{if(equals({REL}?['rlt_turno'], {TURNO_ALFA}), 'Alfa', 'Bravo')}}",
    "nome": f"@{{concat('RLT-PASSAGEM DE TURNO ', {TURNO}, ' ', {so_data(DATA_REL, 'dd.MM.yyyy')})}}",  # RN-004
    "dataPonto": f"@{{{so_data(DATA_REL, 'dd.MM.yyyy')}}}",
    "dataBarra": f"@{{{so_data(DATA_REL, 'dd/MM/yyyy')}}}",
    "ano": f"@{{{so_data(DATA_REL, 'yyyy')}}}",
    "mes": f"@{{{so_data(DATA_REL, 'MM')}}}",
    "periodo": f"@{{concat({dh(REL + '?[' + q('rlt_inicio') + ']')}, ' a ', {dh(REL + '?[' + q('rlt_fim') + ']')})}}",
    "fechadoPor": f"@{{{esc(REL + '?[' + q('_rlt_fechadopor_value' + FMT) + ']')}}}",
    "fechadoEm": f"@{{{dh(REL + '?[' + q('rlt_fechadoem') + ']')}}}",
}


def montar_definicao():
    rel_id = "@triggerOutputs()?['body/rlt_relatorioid']"
    acoes = {
        "Obter_relatorio": op(DATAVERSE, "GetItem", {"entityName": "rlt_relatorios", "recordId": rel_id}),
        "Listar_registros": op(DATAVERSE, "ListRecords", {
            "entityName": "rlt_registros", "$orderby": "rlt_inicio asc",
            "$filter": "_rlt_relatorio_value eq @{triggerOutputs()?['body/rlt_relatorioid']}"}, depois("Obter_relatorio")),
        "Listar_equipe": op(DATAVERSE, "ListRecords", {
            "entityName": "rlt_equipes", "$orderby": "rlt_nome asc",
            "$filter": "_rlt_relatorio_value eq @{triggerOutputs()?['body/rlt_relatorioid']} and rlt_retiradoem eq null"}, depois("Obter_relatorio")),
        "Dados": {"type": "Compose", "inputs": dados, "runAfter": depois("Obter_relatorio")},
        "Linhas": {"type": "Select", "inputs": {"from": "@body('Listar_registros')?['value']", "select": linha}, "runAfter": depois("Listar_registros")},
        "Linhas_equipe": {"type": "Select", "inputs": {
            "from": "@body('Listar_equipe')?['value']",
            "select": f"@concat('<tr><td>', {esc(it('rlt_nome'))}, '</td><td>', coalesce({it('rlt_perfil' + FMT)}, ''), '</td></tr>')"},
            "runAfter": depois("Listar_equipe")},
    }
    anterior = "Linhas"
    for s, _, _ in SECOES:
        nome = f"Filtrar_{s}"
        acoes[nome] = {"type": "Query", "inputs": {"from": "@body('Linhas')", "where": f"@startsWith(item(), 'S{SEC[s]}|')"},
                       "runAfter": depois(anterior)}
        anterior = nome
    acoes["Listar_anexos"] = op(DATAVERSE, "ListRecords", {"entityName": "rlt_anexos", "fetchXml": FETCH_ANEXOS}, depois("Obter_relatorio"))
    acoes["Para_cada_anexo"] = {
        "type": "Foreach", "foreach": "@body('Listar_anexos')?['value']", "runtimeConfiguration": {"concurrency": {"repetitions": 1}},
        "runAfter": depois("Listar_anexos", "Dados"),
        "actions": {
            "Baixar_arquivo": op(DATAVERSE, "GetEntityFileImageFieldContent", {
                "entityName": "rlt_anexos", "recordId": "@items('Para_cada_anexo')?['rlt_anexoid']", "fileImageFieldName": "rlt_arquivo"}),
            # RF-016: fotos e arquivos também na pasta do mês, ao lado do PDF
            "Guardar_anexo": op(ONEDRIVE, "CreateFile", {
                "folderPath": f"@{{concat(parameters('{P_PASTA}'), '/', {D}?['ano'], '/', {D}?['mes'], '/', {D}?['nome'], ' - anexos')}}",
                "name": "@{concat(substring(items('Para_cada_anexo')?['rlt_anexoid'], 0, 8), ' - ', items('Para_cada_anexo')?['rlt_nome'])}",
                "body": "@body('Baixar_arquivo')"}, depois("Baixar_arquivo")),
            "Linha_anexo": {"type": "AppendToArrayVariable", "inputs": {"name": "linhasAnexos", "value": LINHA_ANEXO},
                            "runAfter": depois("Guardar_anexo", status=("Succeeded", "Failed"))},
        },
    }
    acoes["HTML"] = {"type": "Compose", "inputs": html, "runAfter": depois(anterior, "Linhas_equipe", "Dados", "Para_cada_anexo")}

    nome_pdf = f"{D}?['nome']"
    pasta = f"parameters('{P_PASTA}')"
    escopo = dict(acoes)  # tudo dentro do escopo: qualquer falha cai em Registrar_falha
    escopo.update({
        "Verificar_destinatarios": {
            "type": "If", "expression": {"and": [{"equals": [f"@empty(trim(coalesce(parameters('{P_DEST}'), '')))", True]}]},
            "actions": {
                "Registrar_sem_destinatarios": op(DATAVERSE, "UpdateOnlyRecord", {
                    "entityName": "rlt_relatorios", "recordId": rel_id,
                    "item/rlt_resultadoenvio": "FALHA: a variável de ambiente RLT – Destinatários do e-mail está vazia. Nada foi enviado."}),
                "Sem_destinatarios": {"type": "Terminate", "inputs": {"runStatus": "Failed", "runError": {
                    "code": "SemDestinatarios", "message": "A variável de ambiente rlt_destinatarios está vazia: informe os e-mails separados por ponto e vírgula."}},
                    "runAfter": depois("Registrar_sem_destinatarios", status=("Succeeded", "Failed"))}},
            "else": {"actions": {}}, "runAfter": depois("HTML")},
        "Criar_HTML_temporario": op(ONEDRIVE, "CreateFile", {
            "folderPath": f"@{{concat({pasta}, '/_temp')}}", "name": f"@{{concat(guid(), '.html')}}", "body": "@outputs('HTML')"},
            depois("Verificar_destinatarios")),
        "Converter_em_PDF": op(ONEDRIVE, "ConvertFile", {"id": "@body('Criar_HTML_temporario')?['Id']", "type": "PDF"}, depois("Criar_HTML_temporario")),
        "Salvar_PDF": op(ONEDRIVE, "CreateFile", {
            "folderPath": f"@{{concat({pasta}, '/', {D}?['ano'], '/', {D}?['mes'])}}", "name": f"@{{concat({nome_pdf}, '.pdf')}}",
            "body": "@body('Converter_em_PDF')"}, depois("Converter_em_PDF")),
        "Apagar_HTML_temporario": op(ONEDRIVE, "DeleteFile", {"id": "@body('Criar_HTML_temporario')?['Id']"},
                                     depois("Salvar_PDF", status=("Succeeded", "Failed", "Skipped", "TimedOut"))),
        "Enviar_email": op(OUTLOOK, "SendEmailV2", {
            "emailMessage/To": f"@parameters('{P_DEST}')",
            "emailMessage/Subject": f"@{{concat('Relatório de Passagem do Turno ', {D}?['turnoNome'], ' do CCM - ', {D}?['dataPonto'])}}",
            "emailMessage/Body": (f"<p>Prezados,</p><p>Encaminho, em anexo, o Relatório de Passagem do Turno @{{{D}?['turnoNome']}} do CCM, "
                                  f"referente ao dia @{{{D}?['dataPonto']}}.</p><p>Atenciosamente,</p>"),
            "emailMessage/Attachments": [{"Name": f"@{{concat({nome_pdf}, '.pdf')}}", "ContentBytes": "@body('Converter_em_PDF')"}],
            "emailMessage/Importance": "Normal"}, depois("Salvar_PDF")),
        "Registrar_envio": op(DATAVERSE, "UpdateOnlyRecord", {
            "entityName": "rlt_relatorios", "recordId": rel_id,
            "item/rlt_resultadoenvio": (f"@{{concat('Enviado em ', convertFromUtc(utcNow(), {q(TZ)}, 'dd/MM/yyyy HH:mm'), "
                                        f"' para ', parameters('{P_DEST}'), '. PDF: ', body('Salvar_PDF')?['Path'])}}")},
            depois("Enviar_email")),
    })
    acoes = {"Iniciar_anexos": {"type": "InitializeVariable", "inputs": {"variables": [{"name": "linhasAnexos", "type": "array", "value": []}]},
                                "runAfter": {}},
             "Gerar_e_enviar": {"type": "Scope", "actions": escopo, "runAfter": depois("Iniciar_anexos")}}
    acoes["Erros"] = {"type": "Query", "inputs": {"from": "@result('Gerar_e_enviar')", "where": "@equals(item()?['status'], 'Failed')"},
                      "runAfter": depois("Gerar_e_enviar", status=("Failed", "TimedOut"))}
    acoes["Registrar_falha"] = op(DATAVERSE, "UpdateOnlyRecord", {
        "entityName": "rlt_relatorios", "recordId": rel_id,
        "item/rlt_resultadoenvio": (f"@{{concat('FALHA em ', convertFromUtc(utcNow(), {q(TZ)}, 'dd/MM/yyyy HH:mm'), "
                                    "' na etapa ', coalesce(first(body('Erros'))?['name'], '?'), ': ', "
                                    "coalesce(first(body('Erros'))?['error']?['message'], string(first(body('Erros'))?['outputs']?['body']), 'erro desconhecido'))}")},
        depois("Erros"))
    acoes["Terminar_com_falha"] = {"type": "Terminate", "inputs": {"runStatus": "Failed", "runError": {
        "code": "FalhaNoEnvio", "message": "O PDF ou o e-mail não foi enviado. Veja rlt_resultadoenvio no relatório."}},
        "runAfter": depois("Registrar_falha", status=("Succeeded", "Failed"))}

    gatilho = {"Quando_um_relatorio_e_fechado": {
        "type": "OpenApiConnectionWebhook",
        "inputs": {"host": {"connectionName": DATAVERSE, "operationId": "SubscribeWebhookTrigger",
                            "apiId": f"/providers/Microsoft.PowerApps/apis/{DATAVERSE}"},
                   "parameters": {"subscriptionRequest/message": 3, "subscriptionRequest/entityname": "rlt_relatorio",
                                  "subscriptionRequest/scope": 4, "subscriptionRequest/filteringattributes": "rlt_situacao",
                                  "subscriptionRequest/filterexpression": f"rlt_situacao eq {FECHADO}"},
                   "authentication": "@parameters('$authentication')"}}}

    return {"properties": {
        "connectionReferences": {c: {"runtimeSource": "embedded", "connection": {"connectionReferenceLogicalName": n},
                                     "api": {"name": c}} for c, (n, _) in CONEXOES.items()},
        "definition": {
            "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
            "contentVersion": "1.0.0.0",
            "parameters": {
                "$connections": {"defaultValue": {}, "type": "Object"},
                "$authentication": {"defaultValue": {}, "type": "SecureObject"},
                P_DEST: {"defaultValue": "", "type": "String", "metadata": {"schemaName": "rlt_destinatarios"}},
                P_PASTA: {"defaultValue": "/RLT-CCM", "type": "String", "metadata": {"schemaName": "rlt_pastapdf"}},
            },
            "triggers": gatilho, "actions": acoes},
        "templateName": ""}, "schemaVersion": "1.0.0.0"}


# ------------------------------------------------------------------ arquivos da solução
def var_ambiente(schema, nome, descricao, padrao):
    pad = f"  <defaultvalue>{padrao}</defaultvalue>\n" if padrao else ""
    return (f'<environmentvariabledefinition schemaname="{schema}">\n{pad}'
            f'  <description default="{descricao}">\n    <label description="{descricao}" languagecode="1046" />\n  </description>\n'
            f'  <displayname default="{nome}">\n    <label description="{nome}" languagecode="1046" />\n  </displayname>\n'
            "  <introducedversion>1.0.0.0</introducedversion>\n  <iscustomizable>1</iscustomizable>\n  <isrequired>0</isrequired>\n"
            "  <secretstore>0</secretstore>\n  <type>100000000</type>\n</environmentvariabledefinition>\n")


VARS = [
    ("rlt_destinatarios", "RLT – Destinatários do e-mail",
     "E-mails que recebem o PDF, separados por ponto e vírgula (RN-005). Nos testes, só o e-mail de quem testa.", ""),
    ("rlt_pastapdf", "RLT – Pasta dos PDFs no OneDrive",
     "Pasta do OneDrive onde o PDF é guardado em ano/mês (RF-016).", "/RLT-CCM"),
]


def solucao_xml():
    with open(os.path.join(RAIZ, "solution", "RLT_CCM", "src", "Other", "Solution.xml"), encoding="utf-8-sig") as f:
        base = f.read()
    ini, fim = base.index("<Publisher>"), base.index("</Publisher>") + len("</Publisher>")
    raizes = [f'      <RootComponent type="29" id="{{{FLUXO_ID}}}" behavior="0" />'] + \
             [f'      <RootComponent type="380" schemaName="{s}" behavior="0" />' for s, *_ in VARS]
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<ImportExportXml version="9.2.26111.138" SolutionPackageVersion="9.2" languagecode="1046" generatedBy="CrmLive" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" OrganizationVersion="9.2.26111.138" OrganizationSchemaType="Standard" '
            'CRMServerServiceabilityVersion="9.2.26111.00138">\n  <SolutionManifest>\n    <UniqueName>RLT_Fluxos</UniqueName>\n'
            '    <LocalizedNames>\n      <LocalizedName description="RLT – Fluxos" languagecode="1046" />\n    </LocalizedNames>\n'
            '    <Descriptions>\n      <Description description="Fluxos do RLT – Passagem de Turno do CCM (Fechar e enviar: PDF e e-mail)." languagecode="1046" />\n'
            '    </Descriptions>\n    <Version>1.0.1.0</Version>\n    <Managed>0</Managed>\n    '
            + base[ini:fim] + "\n    <RootComponents>\n" + "\n".join(raizes) + "\n    </RootComponents>\n    <MissingDependencies />\n"
            "  </SolutionManifest>\n</ImportExportXml>\n")


def customizacoes_xml():
    refs = "\n".join(
        f'    <connectionreference connectionreferencelogicalname="{n}">\n'
        f"      <connectionreferencedisplayname>{d}</connectionreferencedisplayname>\n"
        f"      <connectorid>/providers/Microsoft.PowerApps/apis/{c}</connectorid>\n"
        "      <iscustomizable>1</iscustomizable>\n      <promptingbehavior>0</promptingbehavior>\n"
        "      <statecode>0</statecode>\n      <statuscode>1</statuscode>\n    </connectionreference>"
        for c, (n, d) in CONEXOES.items())
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<ImportExportXml xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" OrganizationVersion="9.2.26111.138" '
            'OrganizationSchemaType="Standard" CRMServerServiceabilityVersion="9.2.26111.00138">\n'
            "  <Entities />\n  <Roles />\n  <Workflows />\n"
            "  <FieldSecurityProfiles />\n  <Templates />\n  <EntityMaps />\n  <EntityRelationships />\n  <OrganizationSettings />\n"
            "  <optionsets />\n  <CustomControls />\n  <EntityDataProviders />\n"
            f"  <connectionreferences>\n{refs}\n  </connectionreferences>\n"
            "  <Languages>\n    <Language>1046</Language>\n  </Languages>\n</ImportExportXml>\n")


def fluxo_xml():
    campos = [("Type", 1), ("Subprocess", 0), ("Category", 5), ("Mode", 0), ("Scope", 4), ("OnDemand", 0), ("TriggerOnCreate", 0),
              ("TriggerOnDelete", 0), ("AsyncAutodelete", 0), ("SyncWorkflowLogOnFailure", 0),
              ("StateCode", 1), ("StatusCode", 2),  # ligado: a importação pelo portal pede as conexões e ativa o fluxo
              ("RunAs", 1), ("IsTransacted", 1), ("IntroducedVersion", "1.0.0.0"), ("IsCustomizable", 1), ("BusinessProcessType", 0),
              ("IsCustomProcessingStepAllowedForOtherPublishers", 1), ("PrimaryEntity", "none")]
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            f'<Workflow WorkflowId="{{{FLUXO_ID}}}" Name="{FLUXO_NOME}" '
            'Description="Gera o PDF do relatório fechado, guarda no OneDrive e envia o e-mail (RF-013 a RF-016)." '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
            f"  <JsonFileName>/Workflows/{ARQ_FLUXO}</JsonFileName>\n"
            + "".join(f"  <{k}>{v}</{k}>\n" for k, v in campos)
            + f'  <LocalizedNames>\n    <LocalizedName languagecode="1046" description="{FLUXO_NOME}" />\n  </LocalizedNames>\n</Workflow>\n')


def escrever(rel, texto):
    caminho = os.path.join(DESTINO, rel)
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)


def main():
    if os.path.isdir(DESTINO):
        shutil.rmtree(DESTINO)
    escrever("Other/Solution.xml", solucao_xml())
    escrever("Other/Customizations.xml", customizacoes_xml())
    escrever(f"Workflows/{ARQ_FLUXO}", json.dumps(montar_definicao(), ensure_ascii=False, indent=2) + "\n")
    escrever(f"Workflows/{ARQ_FLUXO}.data.xml", fluxo_xml())
    for schema, nome, desc, padrao in VARS:
        escrever(f"environmentvariabledefinitions/{schema}/environmentvariabledefinition.xml", var_ambiente(schema, nome, desc, padrao))
    print(f"Solução RLT_Fluxos gerada em {os.path.relpath(DESTINO, RAIZ)}")


if __name__ == "__main__":
    main()
