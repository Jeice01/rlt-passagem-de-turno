"""Fluxo "RLT – Relatório da Eletromecânica" (decisão de 25/11/2026), gerado junto com a solução RLT_Fluxos
por gerar_fluxo_fechar.py.

1. Dispara quando o app cria um Envio Eletromecânica (rlt_envioeletro): o Bravo envia às 24:00 o relatório do dia.
2. Lista os chamados do dia (00:00 às 24:00, horário de Brasília) que começaram, terminaram ou ficaram abertos no dia:
   corretivas da Eletromecânica, Fator Q (Z9) e Preventivas (ZM02) que não são de BHS. De uma pendência herdada,
   entra só a cópia mais recente (a que não foi herdada por outro relatório).
3. Monta o PDF no layout da planilha "Registro de Ocorrências Eletromecânica Equipamentos FATOR Q",
   guarda em <pasta>/<ano>/<mês>/dd.mm.aaaa_CHAMADOS ELETROMECANICA_FATOR Q.pdf
4. Envia para rlt_emaileletro com cópia para rlt_copiaeletro (no piloto: Eletromecanica@ e CCM@inframerica.aero;
   nos testes: o e-mail de quem testa). Vazias = nada é enviado.
5. Grava o resultado (ou o erro) em rlt_resultado do envio.
"""
from gerar_fluxo_fechar import (DATAVERSE, ONEDRIVE, OUTLOOK, FMT, P_PASTA, SEC, TZ, CANCELADO, depois, dh, esc, it, op, q, so_data)

FLUXO_ID = "3e8b5a21-6c4d-4f7e-9a12-5b6c7d8e9f03"  # fixo: importar de novo atualiza o mesmo fluxo
FLUXO_NOME = "RLT – Relatório da Eletromecânica"
ARQ_FLUXO = f"RLT-RelatriodaEletromecnica-{FLUXO_ID.upper()}.json"

P_PARA = "RLT – E-mail da Eletromecânica (rlt_emaileletro)"
P_COPIA = "RLT – Cópia do e-mail da Eletromecânica (rlt_copiaeletro)"
P_COORD = "RLT – Coordenador da Eletromecânica (rlt_coordeletro)"
VARS = [
    ("rlt_emaileletro", "RLT – E-mail da Eletromecânica",
     "Para quem vai o relatório diário da Eletromecânica. No piloto: Eletromecanica@inframerica.aero. Nos testes: o e-mail de quem testa.", ""),
    ("rlt_copiaeletro", "RLT – Cópia do e-mail da Eletromecânica",
     "Cópia do relatório diário da Eletromecânica. No piloto: CCM@inframerica.aero. Nos testes: vazio ou o e-mail de quem testa.", ""),
    ("rlt_coordeletro", "RLT – Coordenador da Eletromecânica",
     "Nome impresso no cabeçalho do relatório da Eletromecânica.", "Eng. Rogério Santos de Oliveira"),
]

BAGAGEM = 448170002  # Tipo de equipamento: Bagagem (BHS) fica fora das preventivas deste relatório
STATUS = ["PENDENTE", "EM EXECUÇÃO", "CONCLUÍDO / OPERACIONAL", "CHAMADO FALSO", "CANCELADO"]  # nomes da planilha da Eletromecânica
J = "outputs('Janela')"

FETCH = ("<fetch><entity name=\"rlt_registro\">"
         + "".join(f"<attribute name=\"{a}\"/>" for a in ["rlt_registroid", "rlt_titulo", "rlt_descricao", "rlt_secao", "rlt_numero", "rlt_inicio",
                                                         "rlt_conclusao", "rlt_ni", "rlt_status", "rlt_equipamento", "rlt_equipamentolivre",
                                                         "rlt_feedback", "rlt_motivocancelamento"])
         + "<order attribute=\"rlt_inicio\"/><filter type=\"and\">"
         f"<condition attribute=\"rlt_secao\" operator=\"in\"><value>{SEC['elm']}</value><value>{SEC['fq']}</value><value>{SEC['prev']}</value></condition>"
         f"<condition attribute=\"rlt_inicio\" operator=\"lt\" value=\"@{{{J}?['fim']}}\"/>"
         f"<filter type=\"or\"><condition attribute=\"rlt_conclusao\" operator=\"null\"/>"
         f"<condition attribute=\"rlt_conclusao\" operator=\"ge\" value=\"@{{{J}?['ini']}}\"/></filter>"
         "<condition entityname=\"suc\" attribute=\"rlt_registroid\" operator=\"null\"/>"
         f"<filter type=\"or\"><condition attribute=\"rlt_secao\" operator=\"ne\" value=\"{SEC['prev']}\"/>"
         f"<condition entityname=\"eq\" attribute=\"rlt_tipo\" operator=\"ne\" value=\"{BAGAGEM}\"/>"
         "<condition entityname=\"eq\" attribute=\"rlt_tipo\" operator=\"null\"/></filter>"
         "</filter>"
         "<link-entity name=\"rlt_registro\" from=\"rlt_origem\" to=\"rlt_registroid\" link-type=\"outer\" alias=\"suc\"/>"
         "<link-entity name=\"rlt_equipamento\" from=\"rlt_equipamentoid\" to=\"rlt_equipamento\" link-type=\"outer\" alias=\"eq\"/>"
         "</entity></fetch>")

# ------------------------------------------------------------------ uma linha da tabela
secao = it("rlt_secao")
eh_fq, eh_prev = f"equals({secao}, {SEC['fq']})", f"equals({secao}, {SEC['prev']})"
equip = f"toUpper(coalesce({it('_rlt_equipamento_value' + FMT)}, {it('rlt_equipamentolivre')}, {it('rlt_titulo')}, ''))"
ocorr = esc(f"if({eh_fq}, concat('SOLICITAÇÃO DE ATENDIMENTO PARA INOPERÂNCIA – ', {equip}), "
            f"if({eh_prev}, concat('MANUTENÇÃO PREVENTIVA – ', {equip}), toUpper(coalesce({it('rlt_descricao')}, {it('rlt_titulo')}, ''))))")
nota = f"if({eh_fq}, 'Z9', if({eh_prev}, 'ZM02', '–'))"
chamado = f"if(or({eh_fq}, {eh_prev}), {esc(it('rlt_numero'))}, '–')"
tem_fim = f"not(empty(coalesce({it('rlt_conclusao')}, '')))"
ni = f"equals({it('rlt_ni')}, true)"
hora_fim = f"if({tem_fim}, {dh(it('rlt_conclusao'), 'HH:mm')}, if({ni}, 'N/I', '–'))"
data_fim = f"if({tem_fim}, {dh(it('rlt_conclusao'), 'dd.MM.yyyy')}, '–')"
idx = f"sub(coalesce({it('rlt_status')}, 448170001), 448170000)"
status = f"createArray({', '.join(q(s) for s in STATUS)})[{idx}]"
feedback = esc(f"if(empty(trim(coalesce({it('rlt_feedback')}, ''))), "
               f"if(equals({it('rlt_status')}, {CANCELADO}), concat('MOTIVO: ', coalesce({it('rlt_motivocancelamento')}, '')), ''), {it('rlt_feedback')})")
LINHA = (f"@concat('<tr><td class=\"oc\">', {ocorr}, '</td><td class=\"c nota\">', {nota}, '</td><td class=\"c\">', {chamado}, "
         f"'</td><td class=\"c\">', {dh(it('rlt_inicio'), 'dd.MM.yyyy')}, '</td><td class=\"c\">', {dh(it('rlt_inicio'), 'HH:mm')}, "
         f"'</td><td class=\"c\">', {dh(it('rlt_inicio'), 'dd.MM.yyyy')}, '</td><td class=\"c\">', {hora_fim}, '</td><td class=\"c\">', {data_fim}, "
         f"'</td><td class=\"c st st', string({idx}), '\">', {status}, '</td><td class=\"c\">', {feedback}, '</td></tr>')")

CSS = ("@page{size:A4 landscape;margin:12mm}"
       "body{font-family:Calibri,Arial,Helvetica,sans-serif;font-size:8.5pt;color:#111;margin:0}"
       ".cab{width:100%;border-collapse:collapse;margin-bottom:6px}.cab td{border:0;vertical-align:top}"
       ".marca{font-size:15pt;color:#003863;font-weight:bold;line-height:1.1;width:18%}.marca span{font-size:10pt;font-weight:normal;display:block}"
       ".tit{text-align:center;color:#1f4e79;font-style:italic;font-weight:bold;font-family:Arial,Helvetica,sans-serif;font-size:10pt;line-height:1.5}"
       ".tit .g{font-size:9.5pt}.reg{width:22%;text-align:right}"
       ".reg table{border-collapse:collapse;margin-left:auto}.reg td{background:#fde9b4;padding:4px 14px;font-weight:bold;font-size:10pt;border:0}"
       ".eq{white-space:pre-line;text-align:center;font-size:8.5pt;line-height:1.6;margin:6px 0 10px}"
       "table.t{width:100%;border-collapse:collapse}.t th{background:#5b9bd5;color:#fff;font-size:8.5pt;padding:6px 4px;border:1px dotted #fff}"
       ".t td{border:1px dotted #555;padding:6px 5px;vertical-align:middle}.t tr:nth-child(even) td{background:#ddebf7}"
       ".c{text-align:center}.nota{color:#c00000;font-weight:bold}.oc{width:30%}"
       ".st2{background:#70ad47 !important;color:#fff;font-weight:bold}.st1{background:#ffd966 !important;font-weight:bold}"
       ".st0{background:#f4b183 !important;font-weight:bold}.st3,.st4{background:#d0cece !important;font-weight:bold}"
       ".vazio{color:#888;text-align:center}.rod{margin-top:14px;font-size:8pt;color:#1f4e79}")

COLS = ["Registro / Ocorrência", "Tipo de Nota", "Chamado Nº", "Data do Registro", "Hora do Registro", "Data Início do Serviço",
        "Hora Término do Serviço", "Data Término do Serviço", "Status", "Feedback Coordenação Responsável"]
ENV = "triggerOutputs()?['body/rlt_envioeletroid']"
TRIG_EQUIPE = "triggerOutputs()?['body/rlt_equipe']"
D = "outputs('Dados')"
HTML = ("@concat('<!DOCTYPE html><html><head><meta charset=\"utf-8\"><title>', " + D + "?['nome'], '</title><style>" + CSS + "</style></head><body>"
        "<table class=\"cab\"><tr><td class=\"marca\"><span>Aeroporto de</span>Brasília</td><td class=\"tit\">"
        "CCM – CENTRO DE CONTROLE DE MANUTENÇÃO<br>COORDENAÇÃO DE PLANEJAMENTO E CONTROLE DE MANUTENÇÃO - PCM<br><span class=\"g\">GERÊNCIA DE MANUTENÇÃO</span><br><br>"
        "Registro de Ocorrências Eletromecânica Equipamentos &quot;FATOR Q&quot;<br>Coordenador Responsável: ', "
        f"{esc(f'parameters({q(P_COORD)})')}, '</td><td class=\"reg\"><table><tr><td>Registro</td><td>', " + D + "?['dataBarra'], "
        "'</td></tr></table></td></tr></table><div class=\"eq\">', " + D + "?['equipe'], '</div>"
        "<table class=\"t\"><thead><tr>" + "".join(f"<th>{c}</th>" for c in COLS) + "</tr></thead><tbody>', "
        "if(empty(body('Linhas')), '<tr><td colspan=\"10\" class=\"vazio\">Nenhum chamado da Eletromecânica no dia</td></tr>', join(body('Linhas'), '')), "
        "'</tbody></table><div class=\"rod\">Enviado por ', " + D + "?['enviadoPor'], ' em ', " + D + "?['enviadoEm'], "
        "' &nbsp;·&nbsp; Classificação: Interno</div></body></html>')")


def montar_definicao():
    data = "triggerOutputs()?['body/rlt_data']"
    ini = f"convertToUtc(concat({so_data(data, 'yyyy-MM-dd')}, 'T00:00:00'), {q(TZ)})"
    dados = {
        "nome": f"@{{concat({so_data(data, 'dd.MM.yyyy')}, '_CHAMADOS ELETROMECANICA_FATOR Q')}}",
        "dataPonto": f"@{{{so_data(data, 'dd.MM.yyyy')}}}",
        "dataBarra": f"@{{{so_data(data, 'dd/MM/yyyy')}}}",
        "ano": f"@{{{so_data(data, 'yyyy')}}}",
        "mes": f"@{{{so_data(data, 'MM')}}}",
        "equipe": f"@{{{esc(TRIG_EQUIPE)}}}",
        "enviadoPor": f"@{{{esc('triggerOutputs()?[' + q('body/_rlt_enviadopor_value' + FMT) + ']')}}}",
        "enviadoEm": f"@{{{dh('triggerOutputs()?[' + q('body/rlt_enviadoem') + ']')}}}",
    }
    pasta = f"parameters('{P_PASTA}')"
    nome_pdf = f"{D}?['nome']"

    def registrar(texto):
        return op(DATAVERSE, "UpdateOnlyRecord", {"entityName": "rlt_envioeletros", "recordId": f"@{ENV}", "item/rlt_resultado": texto})

    escopo = {
        "Janela": {"type": "Compose", "inputs": {"ini": f"@{{{ini}}}", "fim": f"@{{addDays({ini}, 1)}}"}, "runAfter": {}},
        "Dados": {"type": "Compose", "inputs": dados, "runAfter": {}},
        "Listar_chamados": op(DATAVERSE, "ListRecords", {"entityName": "rlt_registros", "fetchXml": FETCH}, depois("Janela")),
        "Linhas": {"type": "Select", "inputs": {"from": "@body('Listar_chamados')?['value']", "select": LINHA}, "runAfter": depois("Listar_chamados")},
        "HTML": {"type": "Compose", "inputs": HTML, "runAfter": depois("Linhas", "Dados")},
        "Verificar_destinatarios": {
            "type": "If", "expression": {"and": [{"equals": [f"@empty(trim(coalesce(parameters('{P_PARA}'), '')))", True]}]},
            "actions": {
                "Registrar_sem_destinatarios": registrar("FALHA: a variável de ambiente RLT – E-mail da Eletromecânica está vazia. Nada foi enviado."),
                "Sem_destinatarios": {"type": "Terminate", "inputs": {"runStatus": "Failed", "runError": {
                    "code": "SemDestinatarios", "message": "A variável de ambiente rlt_emaileletro está vazia."}},
                    "runAfter": depois("Registrar_sem_destinatarios", status=("Succeeded", "Failed"))}},
            "else": {"actions": {}}, "runAfter": depois("HTML")},
        "Criar_HTML_temporario": op(ONEDRIVE, "CreateFile", {
            "folderPath": f"@{{concat({pasta}, '/_temp')}}", "name": "@{concat(guid(), '.html')}", "body": "@outputs('HTML')"},
            depois("Verificar_destinatarios")),
        "Converter_em_PDF": op(ONEDRIVE, "ConvertFile", {"id": "@body('Criar_HTML_temporario')?['Id']", "type": "PDF"}, depois("Criar_HTML_temporario")),
        "Salvar_PDF": op(ONEDRIVE, "CreateFile", {
            "folderPath": f"@{{concat({pasta}, '/', {D}?['ano'], '/', {D}?['mes'])}}", "name": f"@{{concat({nome_pdf}, '.pdf')}}",
            "body": "@body('Converter_em_PDF')"}, depois("Converter_em_PDF")),
        "Apagar_HTML_temporario": op(ONEDRIVE, "DeleteFile", {"id": "@body('Criar_HTML_temporario')?['Id']"},
                                     depois("Salvar_PDF", status=("Succeeded", "Failed", "Skipped", "TimedOut"))),
        "Enviar_email": op(OUTLOOK, "SendEmailV2", {
            "emailMessage/To": f"@parameters('{P_PARA}')",
            "emailMessage/Cc": f"@{{trim(coalesce(parameters('{P_COPIA}'), ''))}}",
            "emailMessage/Subject": f"@{{concat('Registro de Ocorrências Eletromecânica – Equipamentos Fator Q – ', {D}?['dataPonto'])}}",
            "emailMessage/Body": (f"<p>Prezados,</p><p>Encaminho, em anexo, o Registro de Ocorrências da Eletromecânica (equipamentos Fator Q) "
                                  f"referente ao dia @{{{D}?['dataPonto']}}.</p><p>Atenciosamente,<br>CCM – Centro de Controle de Manutenção</p>"),
            "emailMessage/Attachments": [{"Name": f"@{{concat({nome_pdf}, '.pdf')}}", "ContentBytes": "@body('Converter_em_PDF')"}],
            "emailMessage/Importance": "Normal"}, depois("Salvar_PDF")),
        "Registrar_envio": registrar(
            f"@{{concat('Enviado em ', convertFromUtc(utcNow(), {q(TZ)}, 'dd/MM/yyyy HH:mm'), ' para ', parameters('{P_PARA}'), "
            f"if(empty(trim(coalesce(parameters('{P_COPIA}'), ''))), '', concat(' (cópia: ', parameters('{P_COPIA}'), ')')), "
            f"'. ', string(length(body('Linhas'))), ' chamado(s). PDF: ', body('Salvar_PDF')?['Path'])}}"),
    }
    escopo["Registrar_envio"]["runAfter"] = depois("Enviar_email")
    acoes = {"Gerar_e_enviar": {"type": "Scope", "actions": escopo, "runAfter": {}}}
    acoes["Erros"] = {"type": "Query", "inputs": {"from": "@result('Gerar_e_enviar')", "where": "@equals(item()?['status'], 'Failed')"},
                      "runAfter": depois("Gerar_e_enviar", status=("Failed", "TimedOut"))}
    acoes["Registrar_falha"] = registrar(
        f"@{{concat('FALHA em ', convertFromUtc(utcNow(), {q(TZ)}, 'dd/MM/yyyy HH:mm'), ' na etapa ', coalesce(first(body('Erros'))?['name'], '?'), ': ', "
        "coalesce(first(body('Erros'))?['error']?['message'], string(first(body('Erros'))?['outputs']?['body']), 'erro desconhecido'))}")
    acoes["Registrar_falha"]["runAfter"] = depois("Erros")
    acoes["Terminar_com_falha"] = {"type": "Terminate", "inputs": {"runStatus": "Failed", "runError": {
        "code": "FalhaNoEnvio", "message": "O PDF ou o e-mail da Eletromecânica não foi enviado. Veja rlt_resultado no envio."}},
        "runAfter": depois("Registrar_falha", status=("Succeeded", "Failed"))}

    gatilho = {"Quando_um_envio_e_criado": {
        "type": "OpenApiConnectionWebhook",
        "inputs": {"host": {"connectionName": DATAVERSE, "operationId": "SubscribeWebhookTrigger",
                            "apiId": f"/providers/Microsoft.PowerApps/apis/{DATAVERSE}"},
                   "parameters": {"subscriptionRequest/message": 1, "subscriptionRequest/entityname": "rlt_envioeletro",
                                  "subscriptionRequest/scope": 4},
                   "authentication": "@parameters('$authentication')"}}}
    parametros = {P_PARA: ("rlt_emaileletro", ""), P_COPIA: ("rlt_copiaeletro", ""), P_COORD: ("rlt_coordeletro", VARS[2][3])}
    return gatilho, acoes, parametros
