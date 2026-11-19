"""Gera o pacote de carga das listas do RLT (pessoas, locais e equipamentos) para o Dataverse.

O pacote segue o formato da Configuration Migration Tool e é importado com:
    pac data import --data ferramentas/dataverse/saida/listas.zip

Uso:
    python -E -P ferramentas/dataverse/gerar-carga-listas.py "Arquivos-testes/RLT-PASSAGEM DE TURNO BRAVO 31.10.2026.xlsx"

- Os IDs são fixos (derivados do nome/código), então importar de novo atualiza em vez de duplicar.
- Da aba tbl_rh só entram nome, cargo, perfil e e-mail (o celular fica de fora).
- A saída vai para ferramentas/dataverse/saida/, que fica fora do Git porque tem e-mails.
"""
import os
import sys
import uuid
import warnings
import zipfile
from xml.sax.saxutils import quoteattr

import openpyxl

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

OPT = 448170000
PERFIL = {"Líder": 0, "Técnico(a)": 1, "Operador(a)": 2, "Gestão": 3}
TIPO = {"ELEV": 0, "ESCR": 1, "ESRO": 1, "BHSI": 2, "PEBD": 3}  # 4 = Outro (RN-018)
NS = uuid.UUID("3f6b1c1e-7a5d-4c2e-9b0a-52c1d0a8e101")  # namespace fixo do RLT

# Pessoas que não estão na tbl_rh das planilhas e foram pedidas pela equipe (19/11/2026)
EXTRAS = [("Jeice Santos", "OPERADOR II DE MONITORAMENTO", "JASantos@inframerica.aero")]


def perfil(cargo):
    c = cargo.upper()
    if "LÍDER" in c or "LIDER" in c:
        return "Líder"
    if "TÉCN" in c or "TECN" in c:
        return "Técnico(a)"
    if "OPERAD" in c:
        return "Operador(a)"
    return "Gestão"


def gid(tabela, chave):
    return str(uuid.uuid5(NS, f"{tabela}:{chave}"))


def txt(v):
    return "" if v is None else str(v).strip()


def main(xlsx):
    wb = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)
    pessoas, locais, equips = [], [], []

    for r in list(wb["tbl_rh"].iter_rows(values_only=True))[1:]:
        nome, cargo, email = txt(r[1]), txt(r[2]), txt(r[3])
        if nome:
            pessoas.append((nome, cargo, email))
    nomes = {p[0] for p in pessoas}
    pessoas += [e for e in EXTRAS if e[0] not in nomes]

    vistos = set()
    for r in list(wb["codigo_sap"].iter_rows(values_only=True))[1:]:
        cod, lado, area, esp = txt(r[0]), txt(r[6]), txt(r[8]), txt(r[9])
        if cod and cod not in vistos:
            vistos.add(cod)
            locais.append((cod, lado, area, esp or area))

    vistos = set()
    for r in list(wb["codigo_sap_equipamento"].iter_rows(values_only=True))[1:]:
        cod, desc = txt(r[0]), txt(r[1])
        if cod and cod not in vistos:
            vistos.add(cod)
            equips.append((cod, desc or cod))

    # ---------- data_schema.xml ----------
    def schema(nome, rotulo, prim, campos):
        f = "".join(f'      <field displayname={quoteattr(c[1])} name="{c[0]}" type="{c[2]}" customfield="true" />\n' for c in campos)
        return (f'  <entity name="{nome}" displayname={quoteattr(rotulo)} primaryidfield="{nome}id" primarynamefield="{prim}" disableplugins="false">\n'
                f'    <fields>\n      <field displayname={quoteattr(rotulo)} name="{nome}id" type="guid" primaryKey="true" />\n{f}    </fields>\n'
                f'    <relationships />\n  </entity>\n')

    sch = "<entities>\n"
    sch += schema("rlt_pessoa", "Pessoa", "rlt_nome", [("rlt_nome", "Nome", "string"), ("rlt_cargo", "Cargo", "string"), ("rlt_perfil", "Perfil", "optionsetvalue"), ("rlt_email", "E-mail do login", "string")])
    sch += schema("rlt_local", "Local", "rlt_nome", [("rlt_nome", "Local específico", "string"), ("rlt_codigosap", "Código SAP", "string"), ("rlt_lado", "Lado", "string"), ("rlt_area", "Área", "string")])
    sch += schema("rlt_equipamento", "Equipamento", "rlt_nome", [("rlt_nome", "Descrição", "string"), ("rlt_codigosap", "Código SAP", "string"), ("rlt_tipo", "Tipo", "optionsetvalue")])
    sch += "</entities>\n"

    # ---------- data.xml ----------
    def registros(nome, rotulo, linhas):
        out = f'  <entity name="{nome}" displayname={quoteattr(rotulo)}>\n    <records>\n'
        for rid, campos in linhas:
            out += f'      <record id="{rid}">\n        <field name="{nome}id" value="{rid}" />\n'
            out += "".join(f'        <field name="{k}" value={quoteattr(str(v))} />\n' for k, v in campos if v != "")
            out += "      </record>\n"
        return out + "    </records>\n    <m2mrelationships />\n  </entity>\n"

    dat = '<entities xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" timestamp="2026-11-19T00:00:00.0000000Z">\n'
    dat += registros("rlt_pessoa", "Pessoa", [(gid("pessoa", n), [("rlt_nome", n), ("rlt_cargo", c), ("rlt_perfil", OPT + PERFIL[perfil(c)]), ("rlt_email", e)]) for n, c, e in pessoas])
    dat += registros("rlt_local", "Local", [(gid("local", cod), [("rlt_nome", esp[:200]), ("rlt_codigosap", cod), ("rlt_lado", lado), ("rlt_area", area)]) for cod, lado, area, esp in locais])
    dat += registros("rlt_equipamento", "Equipamento", [(gid("equip", cod), [("rlt_nome", d[:200]), ("rlt_codigosap", cod), ("rlt_tipo", OPT + TIPO.get(cod[:4].upper(), 4))]) for cod, d in equips])
    dat += "</entities>\n"

    saida = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saida")
    os.makedirs(saida, exist_ok=True)
    zp = os.path.join(saida, "listas.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="utf-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/octet-stream" /></Types>')
        z.writestr("data_schema.xml", sch)
        z.writestr("data.xml", dat)

    print(f"pessoas={len(pessoas)} locais={len(locais)} equipamentos={len(equips)} -> {zp}")
    por_perfil = {}
    for _, c, e in pessoas:
        por_perfil[perfil(c)] = por_perfil.get(perfil(c), 0) + 1
    print("perfis:", por_perfil, "| sem e-mail:", [n for n, _, e in pessoas if not e])
    por_tipo = {}
    for cod, _ in equips:
        por_tipo[cod[:4].upper() if cod[:4].upper() in TIPO else "Outro"] = por_tipo.get(cod[:4].upper() if cod[:4].upper() in TIPO else "Outro", 0) + 1
    print("equipamentos por prefixo:", por_tipo)


if __name__ == "__main__":
    main(sys.argv[1])
