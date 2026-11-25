<#
  Gera o esquema do RLT (escolhas globais, tabelas, colunas e relações) como arquivos da solução RLT_CCM
  desempacotada, para importar com o Power Platform CLI (pac solution pack + import).

  Por que arquivos e não a API: a política de acesso da Inframerica bloqueia o login por código de dispositivo,
  então só o pac (login interativo) consegue gravar no Dataverse.

  Uso:
    powershell -File ferramentas\dataverse\gerar-tabelas.ps1 -Src solution\RLT_CCM\src [-Somente rlt_local]

  Modelo de dados: relatório de arquitetura do RLT, seção "Modelo de dados no Dataverse".
#>
param(
  [Parameter(Mandatory)] [string]$Src,
  [string[]]$Somente
)
$ErrorActionPreference = "Stop"
$LANG = 1046
$OPT = 448170000
$utf8 = New-Object Text.UTF8Encoding $false
function X([string]$s) { [Security.SecurityElement]::Escape($s) }
function Grava($caminho, $texto) { New-Item -ItemType Directory -Force (Split-Path $caminho) | Out-Null; [IO.File]::WriteAllText($caminho, $texto, $utf8) }

# ================= MODELO =================
$ESCOLHAS = [ordered]@{
  rlt_turno             = @("Turno", @("ALFA", "BRAVO"))
  rlt_secao             = @("Seção", @("Eletromecânica", "Eletroeletrônica", "BHS", "Civil", "Outros", "Fator Q (Z9)", "Preventiva (ZM02)", "IOS informados"))
  rlt_statusatividade   = @("Status da atividade", @("PENDENTE", "EM ANDAMENTO", "CONCLUÍDO", "CHAMADO FALSO", "CANCELADO"))   # CANCELADO: 25/11/2026
  rlt_statusios         = @("Status do IOS", @("Agendado", "Em andamento", "Suspenso", "Concluído", "Cancelado", "Não informado (NI)"))
  rlt_perfil            = @("Perfil", @("Líder", "Técnico(a)", "Operador(a)", "Gestão"))
  rlt_situacaorelatorio = @("Situação do relatório", @("Aberto", "Fechado"))
  rlt_tipoequipamento   = @("Tipo de equipamento", @("Elevador", "Escada/esteira", "Bagagem", "Ponte de embarque", "Outro"))
}
# tabela: nome, singular, plural, descrição, dono, primária (nome, rótulo, tamanho), colunas [nome, rótulo, tipo, extra]
$TABELAS = @(
  @{ n = "rlt_pessoa"; s = "Pessoa"; p = "Pessoas"; d = "Lista de pessoas do CCM (tbl_rh): nome, cargo e perfil"; dono = "OrganizationOwned"; prim = @("rlt_nome", "Nome", 100)
     cols = @(@("rlt_cargo", "Cargo", "texto", 100), @("rlt_perfil", "Perfil", "escolha", "rlt_perfil"), @("rlt_email", "E-mail do login", "email", 200)) }
  @{ n = "rlt_local"; s = "Local"; p = "Locais"; d = "Locais com código SAP (aba codigo_sap)"; dono = "OrganizationOwned"; prim = @("rlt_nome", "Local específico", 200)
     cols = @(@("rlt_codigosap", "Código SAP", "texto", 40), @("rlt_lado", "Lado", "texto", 100), @("rlt_area", "Área", "texto", 200)) }
  @{ n = "rlt_equipamento"; s = "Equipamento"; p = "Equipamentos"; d = "Equipamentos com código SAP (aba codigo_sap_equipamento)"; dono = "OrganizationOwned"; prim = @("rlt_nome", "Descrição", 200)
     cols = @(@("rlt_codigosap", "Código SAP", "texto", 40), @("rlt_tipo", "Tipo", "escolha", "rlt_tipoequipamento")) }
  @{ n = "rlt_relatorio"; s = "Relatório"; p = "Relatórios"; d = "Um plantão (ALFA ou BRAVO) do CCM"; dono = "UserOwned"; prim = @("rlt_nome", "Nome do relatório", 100)
     cols = @(@("rlt_turno", "Turno", "escolha", "rlt_turno"), @("rlt_data", "Data", "data", $null), @("rlt_inicio", "Início do turno", "datahora", $null), @("rlt_fim", "Fim do turno", "datahora", $null),
              @("rlt_situacao", "Situação", "escolha", "rlt_situacaorelatorio"), @("rlt_fechadoem", "Fechado em", "datahora", $null), @("rlt_resultadoenvio", "Resultado do envio", "memo", 2000)) }
  @{ n = "rlt_registro"; s = "Registro"; p = "Registros"; d = "Atividade, chamado, preventiva ou IOS de um relatório"; dono = "UserOwned"; prim = @("rlt_titulo", "Título", 200)
     cols = @(@("rlt_secao", "Seção", "escolha", "rlt_secao"), @("rlt_descricao", "Descrição", "memo", 4000), @("rlt_equipamentolivre", "Equipamento fora da lista", "texto", 200),
              @("rlt_numero", "Nº do chamado, OS ou IOS", "texto", 20), @("rlt_inicio", "Início", "datahora", $null), @("rlt_conclusao", "Hora de conclusão", "datahora", $null),
              @("rlt_ni", "N/I – não informado", "simnao", $null), @("rlt_status", "Status", "escolha", "rlt_statusatividade"), @("rlt_statusios", "Status do IOS", "escolha", "rlt_statusios"),
              @("rlt_chamadofalso", "Chamado falso", "simnao", $null), @("rlt_limpezatecnica", "Limpeza técnica", "simnao", $null),
              @("rlt_motivocancelamento", "Motivo do cancelamento", "texto", 500), @("rlt_herdado", "Herdado", "simnao", $null)) }
  @{ n = "rlt_equipe"; s = "Membro da equipe"; p = "Equipe do plantão"; d = "Quem fez login no plantão"; dono = "UserOwned"; prim = @("rlt_nome", "Nome", 100)
     cols = @(@("rlt_perfil", "Perfil", "escolha", "rlt_perfil"), @("rlt_entrouem", "Entrou em", "datahora", $null), @("rlt_retiradoem", "Retirado em", "datahora", $null)) }
  @{ n = "rlt_anexo"; s = "Anexo"; p = "Anexos"; d = "Foto ou arquivo de um registro"; dono = "UserOwned"; prim = @("rlt_nome", "Nome do arquivo", 200)
     cols = @(@("rlt_arquivo", "Arquivo", "arquivo", 10240), @("rlt_tipo", "Tipo do arquivo", "texto", 100), @("rlt_tamanho", "Tamanho (bytes)", "inteiro", $null)) }
  @{ n = "rlt_historico"; s = "Histórico"; p = "Histórico"; d = "Cada alteração: quem, quando e o campo (RN-021)"; dono = "UserOwned"; prim = @("rlt_campo", "Campo alterado", 200)
     cols = @(, @("rlt_quando", "Quando", "datahora", $null)) }   # vírgula: evita que a lista de uma coluna só seja achatada
  @{ n = "rlt_aviso"; s = "Aviso"; p = "Avisos"; d = "Avisos do Painel geral de informações, publicados pelo líder"; dono = "UserOwned"; prim = @("rlt_titulo", "Título", 200)
     cols = @(@("rlt_texto", "Texto", "memo", 4000), @("rlt_publicadoem", "Publicado em", "datahora", $null)) }
)
# relação: tabela filha, coluna, rótulo, tabela mãe, nome da relação
$RELACOES = @(
  @("rlt_registro", "rlt_relatorio", "Relatório", "rlt_relatorio", "rlt_relatorio_registro"),
  @("rlt_registro", "rlt_local", "Local", "rlt_local", "rlt_local_registro"),
  @("rlt_registro", "rlt_equipamento", "Equipamento", "rlt_equipamento", "rlt_equipamento_registro"),
  @("rlt_registro", "rlt_origem", "Registro de origem", "rlt_registro", "rlt_registro_origem"),
  @("rlt_equipe", "rlt_relatorio", "Relatório", "rlt_relatorio", "rlt_relatorio_equipe"),
  @("rlt_equipe", "rlt_pessoa", "Pessoa", "rlt_pessoa", "rlt_pessoa_equipe"),
  @("rlt_equipe", "rlt_retiradopor", "Retirado por", "rlt_pessoa", "rlt_pessoa_equipe_retiradopor"),
  @("rlt_anexo", "rlt_registro", "Registro", "rlt_registro", "rlt_registro_anexo"),
  @("rlt_historico", "rlt_relatorio", "Relatório", "rlt_relatorio", "rlt_relatorio_historico"),
  @("rlt_historico", "rlt_registro", "Registro", "rlt_registro", "rlt_registro_historico"),
  @("rlt_historico", "rlt_quem", "Quem", "rlt_pessoa", "rlt_pessoa_historico"),
  @("rlt_relatorio", "rlt_fechadopor", "Fechado por", "rlt_pessoa", "rlt_pessoa_relatorio_fechadopor"),
  @("rlt_aviso", "rlt_autor", "Publicado por", "rlt_pessoa", "rlt_pessoa_aviso")
)

# ================= XML =================
function Rot($t) { "<displaynames><displayname description=`"$(X $t)`" languagecode=`"$LANG`" /></displaynames>" }
function AtrBase($nome, $tipo, $rotulo, $req, $mask, [bool]$custom = $true) {
@"
        <attribute PhysicalName="$nome">
          <Type>$tipo</Type>
          <Name>$nome</Name>
          <LogicalName>$nome</LogicalName>
          <RequiredLevel>$req</RequiredLevel>
          <DisplayMask>$mask</DisplayMask>
          <ImeMode>auto</ImeMode>
          <ValidForUpdateApi>1</ValidForUpdateApi>
          <ValidForReadApi>1</ValidForReadApi>
          <ValidForCreateApi>1</ValidForCreateApi>
          <IsCustomField>$([int]$custom)</IsCustomField>
          <IsAuditEnabled>1</IsAuditEnabled>
          <IsSecured>0</IsSecured>
          <IntroducedVersion>1.0.0.0</IntroducedVersion>
          <IsCustomizable>1</IsCustomizable>
          <IsRenameable>1</IsRenameable>
          <CanModifySearchSettings>1</CanModifySearchSettings>
          <CanModifyRequirementLevelSettings>1</CanModifyRequirementLevelSettings>
          <CanModifyAdditionalSettings>1</CanModifyAdditionalSettings>
          <SourceType>0</SourceType>
          <IsGlobalFilterEnabled>0</IsGlobalFilterEnabled>
          <IsSortableEnabled>0</IsSortableEnabled>
          <CanModifyGlobalFilterSettings>1</CanModifyGlobalFilterSettings>
          <CanModifyIsSortableSettings>1</CanModifyIsSortableSettings>
          <IsDataSourceSecret>0</IsDataSourceSecret>
          <AutoNumberFormat></AutoNumberFormat>
          <IsSearchable>0</IsSearchable>
          <IsFilterable>0</IsFilterable>
          <IsRetrievable>0</IsRetrievable>
          <IsLocalizable>0</IsLocalizable>
"@
}
function AtrFim($rotulo) { "          $(Rot $rotulo)`r`n          <Descriptions />`r`n        </attribute>`r`n" }

function Coluna($tab, $c) {
  $nome, $rotulo, $tipo, $extra = $c
  $m = "ValidForAdvancedFind|ValidForForm|ValidForGrid"
  switch ($tipo) {
    "texto"   { (AtrBase $nome "nvarchar" $rotulo "none" $m) + "          <Format>text</Format>`r`n          <MaxLength>$extra</MaxLength>`r`n          <Length>$(2*$extra)</Length>`r`n" + (AtrFim $rotulo) }
    "email"   { (AtrBase $nome "nvarchar" $rotulo "none" $m) + "          <Format>email</Format>`r`n          <MaxLength>$extra</MaxLength>`r`n          <Length>$(2*$extra)</Length>`r`n" + (AtrFim $rotulo) }
    "memo"    { (AtrBase $nome "ntext" $rotulo "none" $m) + "          <Format>textarea</Format>`r`n          <MaxLength>$extra</MaxLength>`r`n          <Length>$(2*$extra)</Length>`r`n" + (AtrFim $rotulo) }
    "datahora"{ (AtrBase $nome "datetime" $rotulo "none" $m) + "          <Format>datetime</Format>`r`n          <CanChangeDateTimeBehavior>1</CanChangeDateTimeBehavior>`r`n          <Behavior>1</Behavior>`r`n" + (AtrFim $rotulo) }
    "data"    { (AtrBase $nome "datetime" $rotulo "none" $m) + "          <Format>date</Format>`r`n          <CanChangeDateTimeBehavior>0</CanChangeDateTimeBehavior>`r`n          <Behavior>2</Behavior>`r`n" + (AtrFim $rotulo) }
    "inteiro" { (AtrBase $nome "int" $rotulo "none" $m) + "          <Format></Format>`r`n          <MinValue>0</MinValue>`r`n          <MaxValue>2147483647</MaxValue>`r`n" + (AtrFim $rotulo) }
    "escolha" { (AtrBase $nome "picklist" $rotulo "none" $m) + "          <AppDefaultValue>-1</AppDefaultValue>`r`n          <OptionSetName>$extra</OptionSetName>`r`n" + (AtrFim $rotulo) }
    "simnao"  { (AtrBase $nome "bit" $rotulo "none" $m) + @"
          <AppDefaultValue>0</AppDefaultValue>
          <optionset Name="${tab}_$nome">
            <OptionSetType>bit</OptionSetType>
            <IntroducedVersion>1.0.0.0</IntroducedVersion>
            <IsCustomizable>1</IsCustomizable>
            $(Rot $rotulo)
            <Descriptions />
            <options>
              <option value="1" ExternalValue="" IsHidden="0"><labels><label description="Sim" languagecode="$LANG" /></labels></option>
              <option value="0" ExternalValue="" IsHidden="0"><labels><label description="Não" languagecode="$LANG" /></labels></option>
            </options>
          </optionset>

"@ + (AtrFim $rotulo) }
    "arquivo" { (AtrBase $nome "file" $rotulo "none" "ValidForForm") + "          <MaxSizeInKB>$extra</MaxSizeInKB>`r`n" + (AtrFim $rotulo) }   # até 10 MB por arquivo
    "pesquisa"{ (AtrBase $nome "lookup" $rotulo "none" $m) + "          <LookupStyle>single</LookupStyle>`r`n          <LookupTypes />`r`n" + (AtrFim $rotulo) }
  }
}

function EntidadeXml($t, $lookups) {
  $n = $t.n; $prim = $t.prim
  $attrs = (AtrBase "$($n)id" "primarykey" $t.s "systemrequired" "ValidForAdvancedFind|RequiredForGrid" $false) + (AtrFim $t.s)
  $attrs += (AtrBase $prim[0] "nvarchar" $prim[1] "required" "PrimaryName|ValidForAdvancedFind|ValidForForm|ValidForGrid|RequiredForForm") +
            "          <Format>text</Format>`r`n          <MaxLength>$($prim[2])</MaxLength>`r`n          <Length>$(2*$prim[2])</Length>`r`n" + (AtrFim $prim[1])
  foreach ($c in $t.cols) { $attrs += Coluna $n $c }
  foreach ($l in $lookups) { $attrs += Coluna $n @($l[1], $l[2], "pesquisa", $null) }
  $dono = if ($t.dono -eq "OrganizationOwned") { "OrgOwned" } else { "UserOwned" }
@"
<?xml version="1.0" encoding="utf-8"?>
<Entity xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Name LocalizedName="$(X $t.s)" OriginalName="$(X $t.s)">$n</Name>
  <EntityInfo>
    <entity Name="$n">
      <LocalizedNames>
        <LocalizedName description="$(X $t.s)" languagecode="$LANG" />
      </LocalizedNames>
      <LocalizedCollectionNames>
        <LocalizedCollectionName description="$(X $t.p)" languagecode="$LANG" />
      </LocalizedCollectionNames>
      <Descriptions>
        <Description description="$(X $t.d)" languagecode="$LANG" />
      </Descriptions>
      <attributes>
$attrs      </attributes>
      <EntitySetName>$($n)s</EntitySetName>
      <IsDuplicateCheckSupported>0</IsDuplicateCheckSupported>
      <IsBusinessProcessEnabled>0</IsBusinessProcessEnabled>
      <IsRequiredOffline>0</IsRequiredOffline>
      <IsInteractionCentricEnabled>0</IsInteractionCentricEnabled>
      <IsCollaboration>0</IsCollaboration>
      <AutoRouteToOwnerQueue>0</AutoRouteToOwnerQueue>
      <IsConnectionsEnabled>0</IsConnectionsEnabled>
      <EntityColor></EntityColor>
      <IsDocumentManagementEnabled>0</IsDocumentManagementEnabled>
      <AutoCreateAccessTeams>0</AutoCreateAccessTeams>
      <IsOneNoteIntegrationEnabled>0</IsOneNoteIntegrationEnabled>
      <IsKnowledgeManagementEnabled>0</IsKnowledgeManagementEnabled>
      <IsSLAEnabled>0</IsSLAEnabled>
      <IsDocumentRecommendationsEnabled>0</IsDocumentRecommendationsEnabled>
      <IsBPFEntity>0</IsBPFEntity>
      <OwnershipTypeMask>$dono</OwnershipTypeMask>
      <IsAuditEnabled>1</IsAuditEnabled>
      <IsRetrieveAuditEnabled>0</IsRetrieveAuditEnabled>
      <IsRetrieveMultipleAuditEnabled>0</IsRetrieveMultipleAuditEnabled>
      <IsActivity>0</IsActivity>
      <ActivityTypeMask></ActivityTypeMask>
      <IsActivityParty>0</IsActivityParty>
      <IsReplicated>0</IsReplicated>
      <IsReplicationUserFiltered>0</IsReplicationUserFiltered>
      <IsMailMergeEnabled>0</IsMailMergeEnabled>
      <IsVisibleInMobile>0</IsVisibleInMobile>
      <IsVisibleInMobileClient>0</IsVisibleInMobileClient>
      <IsReadOnlyInMobileClient>0</IsReadOnlyInMobileClient>
      <IsOfflineInMobileClient>0</IsOfflineInMobileClient>
      <DaysSinceRecordLastModified>0</DaysSinceRecordLastModified>
      <MobileOfflineFilters></MobileOfflineFilters>
      <IsMapiGridEnabled>1</IsMapiGridEnabled>
      <IsReadingPaneEnabled>1</IsReadingPaneEnabled>
      <IsQuickCreateEnabled>0</IsQuickCreateEnabled>
      <SyncToExternalSearchIndex>0</SyncToExternalSearchIndex>
      <IntroducedVersion>1.0.0.0</IntroducedVersion>
      <IsCustomizable>1</IsCustomizable>
      <IsRenameable>1</IsRenameable>
      <IsMappable>1</IsMappable>
      <CanModifyAuditSettings>1</CanModifyAuditSettings>
      <CanModifyMobileVisibility>1</CanModifyMobileVisibility>
      <CanModifyMobileClientVisibility>1</CanModifyMobileClientVisibility>
      <CanModifyMobileClientReadOnly>1</CanModifyMobileClientReadOnly>
      <CanModifyMobileClientOffline>1</CanModifyMobileClientOffline>
      <CanModifyConnectionSettings>1</CanModifyConnectionSettings>
      <CanModifyDuplicateDetectionSettings>1</CanModifyDuplicateDetectionSettings>
      <CanModifyMailMergeSettings>1</CanModifyMailMergeSettings>
      <CanModifyQueueSettings>1</CanModifyQueueSettings>
      <CanCreateAttributes>1</CanCreateAttributes>
      <CanCreateForms>1</CanCreateForms>
      <CanCreateCharts>1</CanCreateCharts>
      <CanCreateViews>1</CanCreateViews>
      <CanModifyAdditionalSettings>1</CanModifyAdditionalSettings>
      <CanEnableSyncToExternalSearchIndex>1</CanEnableSyncToExternalSearchIndex>
      <EnforceStateTransitions>0</EnforceStateTransitions>
      <CanChangeHierarchicalRelationship>1</CanChangeHierarchicalRelationship>
      <EntityHelpUrlEnabled>0</EntityHelpUrlEnabled>
      <ChangeTrackingEnabled>1</ChangeTrackingEnabled>
      <CanChangeTrackingBeEnabled>1</CanChangeTrackingBeEnabled>
      <IsEnabledForExternalChannels>0</IsEnabledForExternalChannels>
      <IsMSTeamsIntegrationEnabled>0</IsMSTeamsIntegrationEnabled>
      <IsSolutionAware>0</IsSolutionAware>
      <HasRelatedNotes>False</HasRelatedNotes>
      <HasRelatedActivities>False</HasRelatedActivities>
    </entity>
  </EntityInfo>
  <RibbonDiffXml />
</Entity>
"@
}

function EscolhaXml($nome, $def) {
  $i = 0
  $ops = ($def[1] | ForEach-Object { "      <option value=`"$($OPT + $i)`" ExternalValue=`"`" IsHidden=`"0`">`r`n        <labels><label description=`"$(X $_)`" languagecode=`"$LANG`" /></labels>`r`n      </option>"; $i++ }) -join "`r`n"
@"
<?xml version="1.0" encoding="utf-8"?>
<optionset Name="$nome" localizedName="$(X $def[0])" description="" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <OptionSetType>picklist</OptionSetType>
  <IsGlobal>1</IsGlobal>
  <IntroducedVersion>1.0.0.0</IntroducedVersion>
  <IsCustomizable>1</IsCustomizable>
  <displaynames><displayname description="$(X $def[0])" languagecode="$LANG" /></displaynames>
  <Descriptions />
  <options>
$ops
  </options>
</optionset>
"@
}

function RelacaoXml($r) {
  $filha, $col, $rot, $mae, $nome = $r
@"
  <EntityRelationship Name="$nome">
    <EntityRelationshipType>OneToMany</EntityRelationshipType>
    <IsCustomizable>1</IsCustomizable>
    <IntroducedVersion>1.0.0.0</IntroducedVersion>
    <IsHierarchical>0</IsHierarchical>
    <ReferencingEntityName>$filha</ReferencingEntityName>
    <ReferencedEntityName>$mae</ReferencedEntityName>
    <CascadeAssign>NoCascade</CascadeAssign>
    <CascadeDelete>RemoveLink</CascadeDelete>
    <CascadeArchive>NoCascade</CascadeArchive>
    <CascadeReparent>NoCascade</CascadeReparent>
    <CascadeShare>NoCascade</CascadeShare>
    <CascadeUnshare>NoCascade</CascadeUnshare>
    <CascadeRollupView>NoCascade</CascadeRollupView>
    <IsValidForAdvancedFind>1</IsValidForAdvancedFind>
    <ReferencingAttributeName>$col</ReferencingAttributeName>
    <RelationshipDescription>
      <Descriptions>
        <Description description="$(X $rot)" languagecode="$LANG" />
      </Descriptions>
    </RelationshipDescription>
    <EntityRelationshipRoles>
      <EntityRelationshipRole>
        <NavPaneDisplayOption>UseCollectionName</NavPaneDisplayOption>
        <NavPaneArea>Details</NavPaneArea>
        <NavPaneOrder>10000</NavPaneOrder>
        <NavigationPropertyName>$col</NavigationPropertyName>
        <RelationshipRoleType>1</RelationshipRoleType>
      </EntityRelationshipRole>
      <EntityRelationshipRole>
        <NavigationPropertyName>$nome</NavigationPropertyName>
        <RelationshipRoleType>0</RelationshipRoleType>
      </EntityRelationshipRole>
    </EntityRelationshipRoles>
  </EntityRelationship>
"@
}

# ================= GERAÇÃO =================
$tabs = @(if ($Somente) { $TABELAS | Where-Object { $Somente -contains $_.n } } else { $TABELAS })
$nomesTabs = @($tabs | ForEach-Object { $_.n })
$rels = @($RELACOES | Where-Object { $nomesTabs -contains $_[0] -and $nomesTabs -contains $_[3] })
$escUsadas = @($tabs | ForEach-Object { $_.cols } | Where-Object { $_[2] -eq "escolha" } | ForEach-Object { $_[3] } | Select-Object -Unique)

foreach ($e in $escUsadas) { Grava "$Src\OptionSets\$e.xml" (EscolhaXml $e $ESCOLHAS[$e]) }
foreach ($t in $tabs) {
  $lk = @($rels | Where-Object { $_[0] -eq $t.n })
  Grava "$Src\Entities\$($t.n)\Entity.xml" (EntidadeXml $t $lk)
}
# Relações: uma lista geral e um arquivo por tabela filha
$relNomes = ($rels | ForEach-Object { "  <EntityRelationship Name=`"$($_[4])`" />" }) -join "`r`n"
Grava "$Src\Other\Relationships.xml" "<?xml version=`"1.0`" encoding=`"utf-8`"?>`r`n<EntityRelationships xmlns:xsi=`"http://www.w3.org/2001/XMLSchema-instance`">`r`n$relNomes`r`n</EntityRelationships>`r`n"
foreach ($g in ($rels | Group-Object { $_[0] })) {
  $corpo = ($g.Group | ForEach-Object { RelacaoXml $_ }) -join ""
  Grava "$Src\Other\Relationships\$($g.Name).xml" "<?xml version=`"1.0`" encoding=`"utf-8`"?>`r`n<EntityRelationships xmlns:xsi=`"http://www.w3.org/2001/XMLSchema-instance`">`r`n$corpo</EntityRelationships>`r`n"
}
# Componentes raiz e idioma da solução
$sol = "$Src\Other\Solution.xml"
$x = [IO.File]::ReadAllText($sol)
$raiz = (($escUsadas | ForEach-Object { "      <RootComponent type=`"9`" schemaName=`"$_`" behavior=`"0`" />" }) + ($nomesTabs | ForEach-Object { "      <RootComponent type=`"1`" schemaName=`"$_`" behavior=`"0`" />" })) -join "`r`n"
$x = [regex]::Replace($x, "<RootComponents\s*/>|<RootComponents>[\s\S]*?</RootComponents>", "<RootComponents>`r`n$raiz`r`n    </RootComponents>")
$x = $x.Replace('languagecode="1033"', "languagecode=`"$LANG`"")
[IO.File]::WriteAllText($sol, $x, $utf8)
$cz = "$Src\Other\Customizations.xml"
[IO.File]::WriteAllText($cz, ([IO.File]::ReadAllText($cz)).Replace("<Language>1033</Language>", "<Language>$LANG</Language>"), $utf8)
"Gerado: $($escUsadas.Count) escolhas, $($tabs.Count) tabelas, $($rels.Count) relações em $Src"
