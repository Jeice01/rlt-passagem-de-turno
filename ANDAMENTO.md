# Andamento – RLT Passagem de Turno (CCM)

Situação em 25/11/2026. Piloto previsto para 30/11/2026 (PRD).

## Pronto

| Parte | Onde | Situação |
|---|---|---|
| Tabelas, escolhas e perfil de acesso no Dataverse | `solution/RLT_CCM` | Em uso no ambiente |
| App de tela, visual do protótipo: Relatório, Chamados (por seção), Histórico (geral e de um chamado), Painel geral, Fechar e formulário do chamado | `app/gerar_app.py` → `app/fonte/Src` | Publicado (solução RLT_CCM 1.3.0.8) |
| Anexos (RF-007): fotos e arquivos no formulário do chamado, janela "Anexar foto ou arquivo", Abrir e Excluir | idem | Publicado e testado |
| Fluxo "RLT – Fechar e enviar": PDF no layout do protótipo, OneDrive `RLT-CCM/ano/mês`, e-mail da RN-005, resultado na tela Fechar | `ferramentas/fluxos/gerar_fluxo_fechar.py` → `solution/RLT_Fluxos` | Testado com PDF e e-mail |
| Fluxo: seção "Anexos dos chamados" no PDF e cópia dos anexos no OneDrive (RF-016) | idem | Importado; **falta testar** fechando um relatório com foto |

## Versão 1.4.0.0 (25/11/2026): gerada, falta importar e testar

| Mudança | O que faz |
|---|---|
| Status **CANCELADO** nas atividades (corretivas, Fator Q e Preventiva) | Nova opção na escolha "Status da atividade". Conta como encerrado (não passa para o próximo turno). Motivo do cancelamento obrigatório, como no IOS (RN-014 ampliada). Aviso na tela Fechar e motivo impresso no PDF. |
| **Atualizar listas** (RF-021), tela `scrListas` | Botão no Painel geral só para o perfil **Líder**. Abas Equipamentos, Locais e Pessoas e perfis: busca, Incluir, Alterar, Desativar/Reativar (coluna de sistema Status). Nada é excluído; item desativado some das listas do app. |
| **Avisos** no fim do Painel geral | Tabela nova `rlt_aviso` (título, texto, publicado em, publicado por). Todos publicam, atualizam e excluem (exclusão com confirmação). Único caso de exclusão no perfil "RLT - Usuário". |
| Hora de conclusão vazia | Mostrava a data de exemplo 31/12/2001; agora mostra "dd/mm/aaaa". |

Pacotes (fora do Git): `solution/RLT_CCM/out/RLT_CCM_1_4_0_0.zip` e `ferramentas/fluxos/saida/RLT_Fluxos_1_0_1_0.zip`.

**Para colocar no ar (quem usa o portal/Studio):**
1. Importar `RLT_CCM_1_4_0_0.zip` e depois `RLT_Fluxos_1_0_1_0.zip` (Soluções > Importar).
2. Abrir o app no Studio > Dados > Adicionar dados > **Avisos** (tabela nova; até isso, o Painel acusa erro em "Avisos").
3. Corrigir o que o verificador apontar (ver `app/LEIA-ME.md`, passo 5), salvar e publicar.
4. Para testar como líder: na tabela Pessoa, pôr o perfil **Líder** no cadastro de quem testa.
5. Exportar a solução e sincronizar `solution/RLT_CCM/src`.

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
Feito na 1.4.0.0 (ver acima).

### 4. Outros
- Tela Abrir plantão no visual novo.
- PDF: marca do Aeroporto de Brasília no cabeçalho (falta o arquivo do logo) e coluna Cargo na equipe.
- Exportar a solução RLT_CCM e sincronizar `solution/RLT_CCM/src` (o app no repositório é o da 1.2.0.1).
- Fotos HEIC (iPhone) não aparecem no PDF; ficam só como arquivo.
