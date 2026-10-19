package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.screens.LinkAction as OutlinedButton
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.*
import au.mainspring.nativeapp.api.TeamUser
import au.mainspring.nativeapp.ui.*
import com.google.gson.JsonParser

@OptIn(ExperimentalMaterial3Api::class)
@Composable fun TeamScreen(onBack: () -> Unit,model: TeamViewModel = viewModel(),embedded: Boolean = false) {
    val state by model.state.collectAsStateWithLifecycle()
    var editing by remember {mutableStateOf<TeamUser?>(null)}
    var editorOpen by remember {mutableStateOf(false)}
    var deleting by remember {mutableStateOf<TeamUser?>(null)}
    LaunchedEffect(state.info) {if(state.info=="Account saved.") editorOpen=false}
    RefreshOnResume(model::refresh)
    Scaffold(contentWindowInsets=if(embedded) WindowInsets(0,0,0,0) else ScaffoldDefaults.contentWindowInsets,containerColor=MaterialTheme.colorScheme.background,topBar={if(!embedded) Column {
        au.mainspring.nativeapp.ui.BackLargeHeader("More","People & network","Team",onBack)
        if(TokenStore.canManageTeam()) { if(au.mainspring.nativeapp.ui.LocalCalibre.current) OutlinedButton({editing=null;editorOpen=true},enabled=!state.busy && !state.loading && !state.uncertain,modifier=Modifier.padding(start=20.dp)) {Text("Add account")}
            else TextButton({editing=null;editorOpen=true},enabled=!state.busy && !state.loading && !state.uncertain,modifier=Modifier.padding(start=12.dp)) {Text("Add account")} }
    }}) {padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding),contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
            item {
                Row(Modifier.horizontalScroll(rememberScrollState()),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                    listOf("week" to "This week","month" to "This month","90" to "Last 90 days").forEach {(key,label)->au.mainspring.nativeapp.ui.TabChip(state.period==key,{model.period(key)},label={Text(label)})}
                }
                if(au.mainspring.nativeapp.ui.LocalCalibre.current) MonoLabel("${state.users.count {it.active}} active accounts · ${state.users.size} total") else
                Text("${state.users.count {it.active}} active accounts · ${state.users.size} total",style=MaterialTheme.typography.labelSmall)
                androidx.compose.material3.TextButton(model::refresh,enabled=!state.busy && !state.loading) { Text("Refresh") }
                if(state.loading || state.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                state.error?.let {au.mainspring.nativeapp.ui.ErrorBanner(it)};state.info?.let {Text(it)}
                if(state.uncertain) OutlinedButton(model::reviewedWrite,enabled=state.reviewed && !state.loading && !state.busy) {Text("I have reviewed the account records")}
                SectionLabel("Accounts")
            }
            items(state.users,key={it.id}) {user->
                val commission=state.commissions?.getAsJsonArray("technicians")?.firstOrNull {it.asJsonObject.get("user_id")?.asString==user.id}?.asJsonObject
                FlatPanel {
                    Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.SpaceBetween) {Text(user.name,style=MaterialTheme.typography.titleMedium);StatusPill(if(user.active) "Active" else "Inactive")}
                    Text("${user.role.replaceFirstChar {it.uppercase()}} · ${user.email.orEmpty()}",style=if(au.mainspring.nativeapp.ui.LocalCalibre.current) Calibre.label else MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
                    commission?.let {c->
                        MetricStrip(listOf("Eligible jobs" to (c.getAsJsonArray("lines")?.size()?.toString() ?: "0"),"Commission" to commissionAmount(c,"raw_commission_cents"),"Bonus" to commissionAmount(c,"bonus_payable_cents")))
                        Text("Retainer ${commissionAmount(c,"retainer_cents")}. Amounts use the shop's commission rules.",style=MaterialTheme.typography.bodySmall)
                    }
                    if(user.commissionRules!=null) Text("Commission rules configured",style=MaterialTheme.typography.labelSmall)
                    if(TokenStore.canManageTeam()) { if(au.mainspring.nativeapp.ui.LocalCalibre.current) OutlinedButton({editing=user;editorOpen=true},enabled=!state.busy && !state.uncertain) {Text("Edit account")}
                    else TextButton({editing=user;editorOpen=true},enabled=!state.busy && !state.uncertain) {Text("Edit account")} }
                    if(TokenStore.canManageTeam()) TextButton({deleting=user},enabled=!state.busy && !state.uncertain,colors=ButtonDefaults.textButtonColors(contentColor=MaterialTheme.colorScheme.error),modifier=Modifier.testTag("team-delete-${user.id}")) {Text("Delete account")}
                }
            }
            item {Text("Commission eligibility follows each account's saved rules and filters jobs by their creation date. The report does not identify currency.",style=MaterialTheme.typography.bodySmall)}
            if(state.commissions==null && !state.loading) item {Text("Commission report unavailable.",style=MaterialTheme.typography.bodySmall)}
        }
    }
    deleting?.let {user->
        AlertDialog(onDismissRequest={if(!state.busy) deleting=null},title={Text("Delete ${user.name}?")},
            text={Text("This permanently removes the login. Jobs and notes they created are kept. To keep the account but stop it signing in, use Edit account and untick Active instead.")},
            confirmButton={TextButton({model.delete(user);deleting=null},enabled=!state.busy,colors=ButtonDefaults.textButtonColors(contentColor=MaterialTheme.colorScheme.error),modifier=Modifier.testTag("team-delete-confirm")) {Text("Delete account")}},
            dismissButton={TextButton({deleting=null}) {Text("Cancel")}})
    }
    if(editorOpen) TeamEditor(editing,busy=state.busy,serverError=state.error,onClose={if(!state.busy) editorOpen=false},onSave={name,email,password,role,active,rules->
        model.save(editing,name,email,password,role,active,rules)
    })
}

private fun commissionAmount(value: com.google.gson.JsonObject,key: String) = java.math.BigDecimal.valueOf(value.get(key)?.asLong ?: 0,2).toPlainString()
@Composable private fun TeamEditor(original: TeamUser?,busy: Boolean,serverError: String?,onClose: () -> Unit,onSave: (String,String,String,String,Boolean,String?)->Unit) {
    var name by remember {mutableStateOf(original?.name.orEmpty())};var email by remember {mutableStateOf(original?.email.orEmpty())}
    var password by remember {mutableStateOf("")};var role by remember {mutableStateOf(original?.role ?: "tech")};var active by remember {mutableStateOf(original?.active ?: true)}
    val parsed=remember {try {original?.commissionRules?.let {JsonParser.parseString(it).asJsonObject}} catch(_: Exception) {null}}
    var comm by remember {mutableStateOf(parsed?.get("enabled")?.asBoolean ?: false)}
    var retainer by remember {mutableStateOf(java.math.BigDecimal.valueOf(parsed?.get("retainer_cents_per_period")?.asLong ?: 0,2).toPlainString())}
    var shop by remember {mutableStateOf(java.math.BigDecimal.valueOf(parsed?.getAsJsonObject("rates_bp")?.get("shop_referred")?.asLong ?: 3000,2).toPlainString())}
    var self by remember {mutableStateOf(java.math.BigDecimal.valueOf(parsed?.getAsJsonObject("rates_bp")?.get("tech_sourced")?.asLong ?: 5000,2).toPlainString())}
    var minit by remember {mutableStateOf(java.math.BigDecimal.valueOf(parsed?.getAsJsonObject("rates_bp")?.get("minit_sourced")?.asLong ?: 4000,2).toPlainString())}
    var error by remember {mutableStateOf<String?>(null)}
    AlertDialog(onDismissRequest=onClose,title={Text(if(original==null) "Add account" else "Edit account")},text={Column(Modifier.verticalScroll(rememberScrollState()),verticalArrangement=Arrangement.spacedBy(8.dp)) {
        au.mainspring.nativeapp.ui.AtelierTextField(name,{name=it},enabled=!busy,label={Text("Full name")},singleLine=true)
        if(original==null) {au.mainspring.nativeapp.ui.AtelierTextField(email,{email=it},enabled=!busy,label={Text("Email")},singleLine=true);au.mainspring.nativeapp.ui.AtelierTextField(password,{password=it},enabled=!busy,label={Text("Initial password")},singleLine=true,visualTransformation=PasswordVisualTransformation())}
        listOf("owner","manager","tech","intake").forEach {option->au.mainspring.nativeapp.ui.LabeledRadio(role==option,{role=option},enabled=!busy) {Text(option.replaceFirstChar {it.uppercase()})}}
        if(original!=null) au.mainspring.nativeapp.ui.LabeledCheckbox(active,{active=it},enabled=!busy) {Text("Active account")}
        au.mainspring.nativeapp.ui.LabeledCheckbox(comm,{comm=it},enabled=!busy) {Text("Commission tracking")}
        if(comm) {
            Text("Bonus is commission above the retainer. Existing eligibility and custom rate tiers are retained.",style=MaterialTheme.typography.bodySmall)
            listOf("Retainer per period" to Pair(retainer,{v:String->retainer=v}),"Shop referred (%)" to Pair(shop,{v:String->shop=v}),"Tech sourced (%)" to Pair(self,{v:String->self=v}),"Minit sourced (%)" to Pair(minit,{v:String->minit=v})).forEach {(label,input)->au.mainspring.nativeapp.ui.AtelierTextField(input.first,input.second,enabled=!busy,label={Text(label)},singleLine=true)}
        }
        (error ?: serverError)?.let {au.mainspring.nativeapp.ui.ErrorBanner(it)}
        if(busy) LinearProgressIndicator(Modifier.fillMaxWidth())
        Text("Saving changes account access and commission settings. Review the role and active state before confirming.",style=MaterialTheme.typography.bodySmall)
    }},confirmButton={TextButton({try {
        require(original?.commissionRules.isNullOrBlank() || parsed!=null) {"Existing commission rules could not be read. Refresh this account before saving."}
        val rules=if(comm) (parsed?.deepCopy() ?: com.google.gson.JsonObject()).apply {
            addProperty("enabled",true)
            addProperty("retainer_cents_per_period",java.math.BigDecimal(retainer).also {require(it.signum()>=0)}.movePointRight(2).intValueExact())
            val rates=getAsJsonObject("rates_bp") ?: com.google.gson.JsonObject()
            listOf("shop_referred" to shop,"tech_sourced" to self,"minit_sourced" to minit).forEach {(key,value)->val n=java.math.BigDecimal(value);require(n>=java.math.BigDecimal.ZERO && n<=java.math.BigDecimal("100")) {"Rates must be between 0 and 100."};rates.addProperty(key,n.movePointRight(2).intValueExact())}
            add("rates_bp",rates)
        }.toString() else ""
        onSave(name,email,password,role,active,rules);password=""
    } catch(e: Exception) {error=e.userMessage()} },enabled=!busy) {Text("Confirm save")}},dismissButton={TextButton(onClose,enabled=!busy) {Text("Cancel")}})
}
