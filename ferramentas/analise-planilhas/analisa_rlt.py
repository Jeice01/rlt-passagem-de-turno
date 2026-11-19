"""
Análise consolidada das planilhas de RLT (Relatório de Passagem de Turno) do CCM.

Lê todas as planilhas .xlsx de uma pasta (abas passagem_turno e pendencia) e mostra:
cabeçalho (líder/técnicos/operador), registros e status por seção, uso de "chamado falso",
hora fim x status (inclusive N/I), formatos do Nº IOS, atividades que cruzam a meia-noite,
pendências herdadas e dupla contagem, preventiva x corretiva e aderência às listas SAP.

Uso (na raiz do projeto):
    python -m pip install --user openpyxl        # uma vez
    python -E -P ferramentas/analise-planilhas/analisa_rlt.py "Arquivos-testes"
    python -E -P ferramentas/analise-planilhas/analisa_rlt.py "Arquivos-testes" > resultado.txt

Primeira execução: 18/11/2026, 63 planilhas de outubro/2026 (achados registrados no PRD, PRD 1.2).
"""
import sys, os, re, glob, warnings, datetime as dt, json
from collections import Counter, defaultdict
import openpyxl
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

PASTA = sys.argv[1]
SEC_MAP = [
    ("ELETROMEC", "Eletromecânica"), ("ELETROELET", "Eletroeletrônica"), ("BHS", "BHS"),
    ("CIVIL", "Civil"), ("FATOR", "Fator Q"), ("PREVENTIVA", "Preventiva"),
    ("IOS", "IOS"), ("APÊNDICE", "Apêndice"), ("APENDICE", "Apêndice"), ("OUTROS", "Outros"),
]

def sec_of(text):
    t = str(text).upper()
    if not (t.startswith("MANUT") or t.startswith("OUTROS") or t.startswith("IOS") or t.startswith("APÊNDICE") or t.startswith("APENDICE")):
        return None
    for k, v in SEC_MAP:
        if k in t:
            return v
    return None

def kind(v):
    if v is None or (isinstance(v, str) and v.strip() == ""): return "vazio"
    if isinstance(v, (dt.datetime, dt.time)): return "data/hora"
    s = str(v).strip().upper().replace(" ", "")
    if s in ("-", "–"): return "'-'"
    if s in ("N/I", "NI", "N/A"): return s
    return "texto:" + str(v).strip()[:25]

def parse_sheet(ws, with_header=True):
    head, items, sec = {}, [], None
    rows = list(ws.iter_rows(values_only=True))
    for r in rows:
        r = list(r) + [None] * 8
        a = r[0]
        if with_header and isinstance(a, str):
            au = a.strip().upper()
            for k in ("DATA:", "TURNO:", "LÍDER:", "TÉCNICO:", "OPERADOR:"):
                if au.startswith(k):
                    head[k[:-1]] = [x for x in r[1:6] if x not in (None, "")]
        s = sec_of(a) if a is not None else None
        if s:
            sec = s; continue
        if sec is None: continue
        if any(isinstance(x, str) and x.strip().upper().startswith("QUANTIDADE") for x in r[:5]):
            sec = None; continue
        if all(x in (None, "") for x in r[:6]): continue
        if sec == "Fator Q" and a is None and r[1] is None and r[2] is None:
            sec = None; continue  # linha de contagem sem rótulo
        items.append(dict(sec=sec, a=a, b=r[1], ini=r[2], fim=r[3], status=r[4], falso=r[5]))
    return head, items

def norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().upper()[:60]

files = sorted(glob.glob(os.path.join(PASTA, "*.xlsx")))
reports, all_items, pend_items = [], [], []
erros = []
for f in files:
    nome = os.path.basename(f)
    m = re.search(r"(ALFA|BRAVO)\s+(\d{2})\.(\d{2})\.(\d{4})", nome)
    turno, data = (m.group(1), dt.date(int(m.group(4)), int(m.group(3)), int(m.group(2)))) if m else (None, None)
    try:
        wb = openpyxl.load_workbook(f, data_only=True)
    except Exception as e:
        erros.append((nome, str(e))); continue
    abas = wb.sheetnames
    if "passagem_turno" not in abas:
        erros.append((nome, "sem aba passagem_turno: " + ",".join(abas))); continue
    head, items = parse_sheet(wb["passagem_turno"])
    for it in items:
        it.update(file=nome, turno=turno, data=data)
    all_items += items
    pi = []
    if "pendencia" in abas:
        _, pi = parse_sheet(wb["pendencia"], with_header=False)
        for it in pi: it.update(file=nome, turno=turno, data=data)
        pend_items += pi
    reports.append(dict(file=nome, turno=turno, data=data, head=head, n=len(items), npend=len(pi), abas=abas))

out = []
P = out.append
P(f"ARQUIVOS: {len(files)}  lidos: {len(reports)}  erros: {len(erros)}")
for e in erros: P(f"  ERRO {e}")
P("Turnos: " + str(Counter(r['turno'] for r in reports)))
P("Abas (conjuntos distintos): " + str(Counter(tuple(r['abas']) for r in reports).most_common(3)))

# Cabeçalho
lid_vazio = sum(1 for r in reports if not r['head'].get('LÍDER'))
P(f"\n== CABEÇALHO ==\nLíder vazio: {lid_vazio}/{len(reports)}")
P("Nº de técnicos por relatório: " + str(Counter(len(r['head'].get('TÉCNICO', [])) for r in reports)))
P("Nº de operadores por relatório: " + str(Counter(len(r['head'].get('OPERADOR', [])) for r in reports)))
dif = [r for r in reports if r['head'].get('DATA') and isinstance(r['head']['DATA'][0], dt.datetime) and r['head']['DATA'][0].date() != r['data']]
P(f"DATA do cabeçalho diferente da data do nome do arquivo: {len(dif)} " + str([(d['file'], str(d['head']['DATA'][0].date())) for d in dif][:5]))

# Convenção da data do Bravo: atividades iniciadas dentro do turno
bravo_ini = Counter()
for it in all_items:
    if it['turno'] == 'BRAVO' and isinstance(it['ini'], dt.datetime) and it['sec'] not in ('IOS', 'Apêndice'):
        d = (it['ini'].date() - it['data']).days
        bravo_ini[d] += 1
P("Bravo: dias entre início das atividades e a data do arquivo (0=mesmo dia, 1=dia seguinte, <0=herdadas): " + str(sorted(bravo_ini.items())))

# Seções
P("\n== REGISTROS POR SEÇÃO (aba passagem_turno, soma dos 63 relatórios) ==")
sc = Counter(it['sec'] for it in all_items)
for k, v in sc.most_common(): P(f"  {k:18} {v}")

P("\n== STATUS USADOS POR SEÇÃO ==")
for s in sc:
    P(f"  {s:18} " + str(Counter(norm(it['status']) or '(vazio)' for it in all_items if it['sec'] == s).most_common(10)))

P("\n== COLUNA 'FALSO' preenchida, por seção ==")
for s in sc:
    c = Counter(norm(it['falso']) for it in all_items if it['sec'] == s and it['falso'] not in (None, ""))
    if c: P(f"  {s:18} {dict(c)}")

P("\n== HORA FIM: tipo de valor x STATUS (seções de atividade) ==")
ft = defaultdict(Counter)
for it in all_items:
    if it['sec'] in ('IOS', 'Apêndice'): continue
    ft[kind(it['fim'])][norm(it['status']) or '(vazio)'] += 1
for k, c in sorted(ft.items(), key=lambda x: -sum(x[1].values())): P(f"  fim={k:28} -> {dict(c)}")

P("\n== IOS: HORA FIM x STATUS ==")
ft = defaultdict(Counter)
for it in all_items:
    if it['sec'] != 'IOS': continue
    ft[kind(it['fim'])][norm(it['status']) or '(vazio)'] += 1
for k, c in sorted(ft.items(), key=lambda x: -sum(x[1].values())): P(f"  fim={k:28} -> {dict(c)}")
fmt = Counter()
for it in all_items:
    if it['sec'] == 'IOS':
        v = str(it['b']).strip() if it['b'] is not None else ''
        fmt[re.sub(r"\d", "9", v)] += 1
P("  Formatos do Nº IOS: " + str(fmt.most_common(8)))

# Atravessa meia-noite / validade do fim
P("\n== HORÁRIOS ==")
cruza = sum(1 for it in all_items if isinstance(it['ini'], dt.datetime) and isinstance(it['fim'], dt.datetime) and it['fim'].date() > it['ini'].date())
neg = [it for it in all_items if isinstance(it['ini'], dt.datetime) and isinstance(it['fim'], dt.datetime) and it['fim'] < it['ini']]
zero = sum(1 for it in all_items if isinstance(it['ini'], dt.datetime) and isinstance(it['fim'], dt.datetime) and it['fim'] == it['ini'])
P(f"  Início e fim com data completa (data+hora): {sum(1 for it in all_items if isinstance(it['ini'], dt.datetime))}/{len(all_items)} inícios")
P(f"  Fim em dia posterior ao início: {cruza}   Fim antes do início: {len(neg)}   Fim = início (evento instantâneo): {zero}")
for it in neg[:3]: P(f"     ex.: {it['file']} {it['sec']} ini={it['ini']} fim={it['fim']}")

# Herança / dupla contagem
P("\n== PENDÊNCIAS HERDADAS E DUPLA CONTAGEM ==")
chave = lambda it: (it['sec'], norm(it['a']), str(it['ini']))
ativ = [it for it in all_items if it['sec'] not in ('IOS', 'Apêndice')]
cnt = Counter(chave(it) for it in ativ)
P(f"  Linhas de atividade: {len(ativ)}   Atividades únicas (seção+descrição+início): {len(cnt)}")
P(f"  Atividades que aparecem em mais de 1 relatório: {sum(1 for v in cnt.values() if v > 1)}   maior repetição: {max(cnt.values())}")
herd = Counter()
for it in ativ:
    if isinstance(it['ini'], dt.datetime):
        shift_start = dt.datetime.combine(it['data'], dt.time(7)) if it['turno'] == 'ALFA' else dt.datetime.combine(it['data'], dt.time(19))
        herd['herdada (início antes do turno)' if it['ini'] < shift_start - dt.timedelta(minutes=1) else 'do próprio turno'] += 1
P("  " + str(dict(herd)) + "  (Bravo considerando data = início do plantão, padrão atual)")

def prev_corr(items, unico):
    seen, c = set(), Counter()
    for it in items:
        if it['sec'] in ('IOS', 'Apêndice'): continue
        if norm(it['falso']) not in ('', 'NONE') or 'FALSO' in norm(it['status']):
            c['falso'] += 1; continue
        k = chave(it)
        if unico and k in seen: continue
        seen.add(k)
        c['Preventiva' if it['sec'] == 'Preventiva' else 'Corretiva'] += 1
    t = c['Preventiva'] + c['Corretiva']
    return c, (100 * c['Preventiva'] / t if t else 0), (100 * c['Corretiva'] / t if t else 0)
for unico in (False, True):
    c, p, k = prev_corr(all_items, unico)
    P(f"  Preventiva x Corretiva ({'atividades únicas' if unico else 'por linha, como RN-019 hoje'}): prev={c['Preventiva']} corr={c['Corretiva']} falsos={c['falso']} -> {p:.1f}% x {k:.1f}%")
limp = sum(1 for k in cnt if k[0] == 'Outros' and 'LIMPEZA T' in k[1])
P(f"  'Limpeza técnica' em Outros (atividades únicas): {limp} de {sum(1 for k in cnt if k[0]=='Outros')} em Outros")
c, p, k = prev_corr([it for it in all_items if not (it['sec']=='Outros' and 'LIMPEZA T' in norm(it['a']))], True)
P(f"  Prev x Corr únicas SEM limpeza técnica: {p:.1f}% x {k:.1f}%")

# Aba pendencia
P("\n== ABA 'pendencia' ==")
P(f"  Relatórios com aba pendencia: {sum(1 for r in reports if 'pendencia' in r['abas'])}   linhas: {len(pend_items)}")
P("  Status: " + str(Counter(norm(it['status']) or '(vazio)' for it in pend_items).most_common()))
anos = Counter(it['ini'].year for it in pend_items if isinstance(it['ini'], dt.datetime))
P("  Ano de início das pendências: " + str(sorted(anos.items())))
uniq_p = {chave(it) for it in pend_items}
P(f"  Pendências únicas na aba: {len(uniq_p)}")
ultimo = max(reports, key=lambda r: (r['data'], r['turno'] == 'BRAVO'))
P(f"  Último relatório: {ultimo['file']} com {ultimo['npend']} linhas na aba pendencia")
abertas_ult = [it for it in pend_items if it['file'] == ultimo['file'] and norm(it['status']) in ('PENDENTE', 'EM ANDAMENTO', '')]
P(f"  Abertas no último relatório (para carga inicial): {len(abertas_ult)} " + str(Counter(it['sec'] for it in abertas_ult)))

# Listas de referência
P("\n== REFERÊNCIAS ==")
wb = openpyxl.load_workbook(files[-1], data_only=True)
equip = {norm(r[1]) for r in wb['codigo_sap_equipamento'].iter_rows(min_row=2, values_only=True) if r[1]}
locais = {norm(r[9]) for r in wb['codigo_sap'].iter_rows(min_row=2, values_only=True) if r[9]}
fq = [it for it in all_items if it['sec'] in ('Fator Q', 'Preventiva')]
P(f"  Equipamentos (Fator Q + Preventiva) encontrados na lista: {sum(1 for it in fq if norm(it['a']) in equip)}/{len(fq)}")
P("  Exemplos fora da lista: " + str(Counter(norm(it['a']) for it in fq if norm(it['a']) not in equip).most_common(6)))
loc = [it for it in all_items if it['sec'] in ('Eletromecânica', 'Eletroeletrônica', 'BHS', 'Civil', 'Outros')]
P(f"  Locais das corretivas encontrados na lista: {sum(1 for it in loc if norm(it['b']) in locais)}/{len(loc)}")
P("  Exemplos fora da lista: " + str(Counter(norm(it['b']) for it in loc if norm(it['b']) not in locais).most_common(8)))
P("  Setores do Apêndice usados: " + str(Counter(norm(it['status']) for it in all_items if it['sec'] == 'Apêndice').most_common(8)))
P(f"  Erros '#VALUE!'/'#REF!' em células: {sum(1 for it in all_items + pend_items for v in (it['a'], it['b']) if isinstance(v, str) and v.startswith('#'))}")

print("\n".join(out))
