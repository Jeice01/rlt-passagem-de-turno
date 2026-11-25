<#
  Gera o perfil de segurança "RLT - Usuário" na solução RLT_CCM desempacotada (src/Roles) e o registra
  como componente raiz em Solution.xml. Depois: pac solution pack + import.

  Regra (decisão de 19/11/2026): acesso igual para todos os perfis.
    - Tabelas de operação e listas: criar, ler, alterar, anexar e ser anexado, no ambiente inteiro (Global).
    - Histórico: só criar e ler (ninguém altera nem apaga o histórico - RN-021).
    - Nenhuma exclusão: engano vira cancelamento ou chamado falso. Exceção: avisos do Painel (25/11/2026).
    - Listas (equipamentos, locais, pessoas): não se excluem; o líder desativa (Status = Inativo).
  O perfil "Usuário Básico" da Microsoft continua sendo atribuído a todos automaticamente.

  Uso: powershell -File ferramentas\dataverse\gerar-perfil.ps1 -Src solution\RLT_CCM\src
#>
param([Parameter(Mandatory)] [string]$Src)
$ErrorActionPreference = "Stop"
$ID = "{6a1f3c52-8d4e-4b7a-9e21-3c5d7f9a0b14}"   # fixo, para reimportar sem duplicar
$NOME = "RLT - Usuário"

$completo = "Create", "Read", "Write", "Append", "AppendTo"
$tabelas = [ordered]@{
  rlt_relatorio = $completo; rlt_registro = $completo; rlt_equipe = $completo; rlt_anexo = $completo
  rlt_pessoa = $completo; rlt_local = $completo; rlt_equipamento = $completo
  rlt_historico = @("Create", "Read", "Append", "AppendTo")
  rlt_envioeletro = $completo   # envio diário da Eletromecânica (25/11/2026)
  rlt_aviso = @("Create", "Read", "Write", "Delete", "Append", "AppendTo")   # avisos do Painel: todos podem excluir (25/11/2026)
}
$linhas = foreach ($t in $tabelas.Keys) { foreach ($p in $tabelas[$t]) { "    <RolePrivilege name=`"prv$p$t`" level=`"Global`" />" } }

$xml = @"
<?xml version="1.0" encoding="utf-8"?>
<Role id="$ID" name="$NOME" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <IsAutoAssigned>0</IsAutoAssigned>
  <AppliesTo>Users</AppliesTo>
  <Description>App RLT do CCM: acesso igual para todos. Cria, lê e altera relatórios, registros, equipe, anexos e listas; histórico só criar e ler; sem exclusão.</Description>
  <RolePrivileges>
$($linhas -join "`r`n")
  </RolePrivileges>
</Role>
"@
$utf8 = New-Object Text.UTF8Encoding $false
New-Item -ItemType Directory -Force "$Src\Roles" | Out-Null
[IO.File]::WriteAllText("$Src\Roles\$NOME.xml", $xml, $utf8)

$sol = "$Src\Other\Solution.xml"
$x = [IO.File]::ReadAllText($sol)
if ($x -notmatch [regex]::Escape($ID)) {
  $x = $x.Replace("</RootComponents>", "  <RootComponent type=`"20`" id=`"$ID`" behavior=`"0`" />`r`n    </RootComponents>")
  [IO.File]::WriteAllText($sol, $x, $utf8)
}
"Perfil '$NOME' gerado com $(@($linhas).Count) privilégios."
