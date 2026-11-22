# App de tela – RLT Passagem de Turno

O app é gerado a partir do protótipo validado (`prototipo/index.html`, PRD 1.3), com o mesmo visual: cartões arredondados, etiquetas de status, avatares e páginas que rolam.

- `gerar_app.py` – gera as telas em Power Apps YAML (`*.pa.yaml`). **Edite o gerador, não os arquivos gerados.**
- `fonte/` – código-fonte do app no formato *SourceCode*: `Src/*.pa.yaml` (telas) e o `.msapr` (dados, conexões, tema), copiado do app publicado.

## Como montar uma versão nova

1. `python -E -P app/gerar_app.py app/fonte/Src`
2. Casca do app publicado: `pac canvas unpack --msapp solution/RLT_CCM/src/CanvasApps/rlt_rltpassagemdeturno_1ffb1_DocumentUri.msapp --sources <casca> --layout SourceCode`.
   Copie `app/fonte/Src/*.pa.yaml` por cima de `<casca>/Src` e `pac canvas pack --sources <casca> --msapp <saida>.msapp --overwrite`.
3. Numa cópia de `solution/RLT_CCM/src`: troque `CanvasApps/rlt_rltpassagemdeturno_1ffb1_DocumentUri.msapp` pelo novo, suba a `<Version>` em `Other/Solution.xml` e
   `pac solution pack --zipfile <zip> --folder <cópia> --packagetype Unmanaged`.
4. Importe o zip pelo portal (Soluções > Importar solução). A importação automática pelo `pac` fica bloqueada nesta máquina porque altera o ambiente.
5. Abra o app **uma vez** no Power Apps Studio, corrija o que o verificador apontar, salve e publique (exigência do `pac` para apps montados a partir de YAML).
   - Erros `ComboBoxSample` / `Value1` em `.SearchItems` de `regLocal`, `regEquip` (scrRegistro > regPagina) e `paiCbx` (scrPainel > paiPagina > paiGal1):
     `SearchItems` é uma propriedade oculta do ComboBox clássico e o YAML não aceita defini-la. Em cada um, abra **Items**, recorte a fórmula (Ctrl+A, Ctrl+X)
     e cole de volta (Ctrl+V): o Studio recalcula o `SearchItems` e os erros somem. Como o `paiCbx` só aparece quando há Fator Q sem SAP, chegue nele pela árvore.
   - Depois disso, o Studio volta o `SearchFields` para `["rlt_nome"]`. Em `regEquip` e `paiCbx`, reponha `["rlt_nome"; "rlt_codigosap"]` para a busca pelo código SAP voltar a funcionar.
6. Exporte a solução (não gerenciada) e sincronize `solution/RLT_CCM/src` com `pac solution unpack --zipfile <zip> --folder <pasta temporária> --packagetype Unmanaged`
   e cópia do resultado. A pasta `src/CanvasApps` guarda o app como foi publicado no Studio.
   - O `pac` vem com a extensão Power Platform Tools do VS Code: `%APPDATA%\Code\User\globalStorage\microsoft-isvexptools.powerplatform-vscode\pac\tools\pac.exe`.

## Coisas que só o Studio confirma

O `pac canvas pack` não valida os controles (aceita até nome inexistente). Quando o formato de um controle não está documentado, ele foi copiado do Studio
(clique com o botão direito no controle > **Copiar código**):
- galeria de altura flexível: `Gallery@2.15.0`, `Variant: VariableHeight` (agrupamento por seção em Chamados e páginas roláveis em Painel, Fechar e Registro);
- formulário de anexo: `Form@2.4.4` (Classic), cartões `TypedDataCard@1.0.8` (`ClassicFileEdit` para o arquivo) e controle `Attachments@2.3.0`.

Decisões de visual que vêm de limitações do Power Apps:
- retângulos não arredondam: cartões, etiquetas e avatares são botões desativados (`cartao()`, `chip()`, `avatar()`);
- formulários não podem ficar dentro de galerias: o anexo é feito numa janela por cima da tela (`janela_anexo()`), e os campos do chamado,
  que ficam na página rolável, são limpos pela propriedade `Reset = locResetar` em vez de `Reset()`;
- a fonte Saira do protótipo não existe no Power Apps: títulos em Open Sans Condensed e texto em Arial.

Ainda não estão no app: a tela Abrir plantão no visual novo e as fotos no PDF (fluxo Fechar e enviar).
