# App de tela – RLT Passagem de Turno

O app é gerado a partir do protótipo validado (`prototipo/index.html`, PRD 1.3).

- `gerar_app.py` – gera as telas em Power Apps YAML (`*.pa.yaml`). **Edite o gerador, não os arquivos gerados.**
- `fonte/` – código-fonte do app no formato *SourceCode*: `Src/*.pa.yaml` (telas) e o `.msapr` (dados, conexões, tema).

## Como montar uma versão nova

1. `python -E -P app/gerar_app.py app/fonte/Src`
2. `pac canvas pack --sources app/fonte --msapp <saida>.msapp --layout SourceCode`
3. Copiar o `.msapp` para `CanvasApps/rlt_rltpassagemdeturno_1ffb1_DocumentUri.msapp` da solução desempacotada, `pac solution pack` e `pac solution import`.
4. Abrir o app **uma vez** no Power Apps Studio, corrigir o que o verificador apontar, salvar e publicar (exigência do `pac` para apps montados a partir de YAML).
   - Erros `ComboBoxSample` / `Value1` em `.SearchItems` de `regLocal`, `regEquip` e `paiCbx`: `SearchItems` é uma propriedade oculta do ComboBox clássico e o YAML não aceita defini-la. Em cada um desses controles, abra a propriedade **Items**, recorte a fórmula (Ctrl+A, Ctrl+X) e cole de volta (Ctrl+V): o Studio recalcula o `SearchItems` e os erros somem.
   - Depois disso, o Studio volta o `SearchFields` para `["rlt_nome"]`. Em `regEquip` e `paiCbx`, reponha `["rlt_nome"; "rlt_codigosap"]` para a busca pelo código SAP voltar a funcionar.
5. Exportar a solução (não gerenciada) e sincronizar `solution/RLT_CCM/src` com `pac solution unpack --zipfile <zip> --folder <pasta temporária> --packagetype Unmanaged` e cópia do resultado. A pasta `src/CanvasApps` guarda o app como foi publicado no Studio.
   - O `pac` vem com a extensão Power Platform Tools do VS Code: `%APPDATA%\Code\User\globalStorage\microsoft-isvexptools.powerplatform-vscode\pac\tools\pac.exe`.

Ainda não estão no app: anexos (fotos e arquivos) e o fluxo Fechar e enviar (PDF e e-mail).