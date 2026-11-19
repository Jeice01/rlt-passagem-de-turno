# App de tela – RLT Passagem de Turno

O app é gerado a partir do protótipo validado (`prototipo/index.html`, PRD 1.3).

- `gerar_app.py` – gera as telas em Power Apps YAML (`*.pa.yaml`). **Edite o gerador, não os arquivos gerados.**
- `fonte/` – código-fonte do app no formato *SourceCode*: `Src/*.pa.yaml` (telas) e o `.msapr` (dados, conexões, tema).

## Como montar uma versão nova

1. `python -E -P app/gerar_app.py app/fonte/Src`
2. `pac canvas pack --sources app/fonte --msapp <saida>.msapp --layout SourceCode`
3. Copiar o `.msapp` para `CanvasApps/rlt_rltpassagemdeturno_1ffb1_DocumentUri.msapp` da solução desempacotada, `pac solution pack` e `pac solution import`.
4. Abrir o app **uma vez** no Power Apps Studio, corrigir o que o verificador apontar, salvar e publicar (exigência do `pac` para apps montados a partir de YAML).
5. Exportar a solução e sincronizar `solution/RLT_CCM/src`.

Ainda não estão no app: anexos (fotos e arquivos) e o fluxo Fechar e enviar (PDF e e-mail).