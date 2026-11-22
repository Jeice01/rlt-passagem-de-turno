# Andamento – RLT Passagem de Turno (CCM)

Situação em 22/11/2026. Piloto previsto para 30/11/2026 (PRD).

## Pronto

| Parte | Onde | Situação |
|---|---|---|
| Tabelas, escolhas e perfil de acesso no Dataverse | `solution/RLT_CCM` | Em uso no ambiente |
| App de tela, visual do protótipo: Relatório, Chamados (por seção), Histórico (geral e de um chamado), Painel geral, Fechar e formulário do chamado | `app/gerar_app.py` → `app/fonte/Src` | Publicado (solução RLT_CCM 1.3.0.8) |
| Anexos (RF-007): fotos e arquivos no formulário do chamado, janela "Anexar foto ou arquivo", Abrir e Excluir | idem | Publicado e testado |
| Fluxo "RLT – Fechar e enviar": PDF no layout do protótipo, OneDrive `RLT-CCM/ano/mês`, e-mail da RN-005, resultado na tela Fechar | `ferramentas/fluxos/gerar_fluxo_fechar.py` → `solution/RLT_Fluxos` | Testado com PDF e e-mail |
| Fluxo: seção "Anexos dos chamados" no PDF e cópia dos anexos no OneDrive (RF-016) | idem | Importado; **falta testar** fechando um relatório com foto |

Como montar e importar o app: `app/LEIA-ME.md`. O fluxo é importado pelo portal (Soluções > Importar) a partir do zip gerado em `ferramentas/fluxos/saida/` (fora do Git).

## Configuração de teste no ambiente

- Variável de ambiente **RLT – Destinatários do e-mail** com o e-mail pessoal de quem testa: nenhum teste chega às áreas.
- Remetente: conta de quem é dono do fluxo. Pasta: OneDrive da mesma conta, `/RLT-CCM`.
- Antes do piloto: definir remetente, pasta definitiva (SharePoint do CCM?) e esvaziar ou trocar a variável de destinatários.

## Próximos passos (pedidos em 22/11/2026)

### 1. Fechar: prévia do PDF e e-mail editável (em andamento)
- Para, Assunto e Mensagem editáveis na tela Fechar (botão "Editar e-mail"; destinatários em pílulas com ×, campo para adicionar e "Restaurar lista padrão"), gravados no relatório.
- Fluxo: com a variável de destinatários **preenchida**, o envio vai só para ela (modo de teste); **vazia**, vai para o Para da tela.
- Link "pré-visualizar" no nome do PDF: tela de prévia dentro do app, com o mesmo layout do PDF (controle Texto HTML).
- Corrigir a lista "Para" cortada na tela Fechar.
- **Muda a RN-005** (destinatários, assunto e corpo fixos): registrar a decisão no PRD.

**Pendente de quem usa o Studio/portal:**
- Criar 4 colunas em Relatório (Opções avançadas > Nome do esquema):
  `rlt_emailpara` (várias linhas, 4000), `rlt_emailassunto` (linha única, 400), `rlt_emailmensagem` (várias linhas, 4000), `rlt_observacoes` (várias linhas, 4000).
- Copiar o código de um controle **Texto HTML** (Inserir > Texto HTML > botão direito > Copiar código) para o gerador saber o tipo e a versão.

### 2. Observações do plantão no PDF
Cartão "Observações do plantão" na tela Relatório (aparece também em Fechar), gravado em `rlt_observacoes` e impresso no PDF depois da equipe.

### 3. Editar as listas (RF-021)
"Atualizar listas" no Painel geral abre uma tela com abas Equipamentos, Locais e Pessoas: busca, incluir, alterar e desativar.

### 4. Outros
- Tela Abrir plantão no visual novo.
- PDF: marca do Aeroporto de Brasília no cabeçalho (falta o arquivo do logo) e coluna Cargo na equipe.
- Exportar a solução RLT_CCM e sincronizar `solution/RLT_CCM/src` (o app no repositório é o da 1.2.0.1).
- Fotos HEIC (iPhone) não aparecem no PDF; ficam só como arquivo.
