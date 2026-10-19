package au.mainspring.nativeapp

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import au.mainspring.nativeapp.api.*
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import retrofit2.HttpException
import java.time.LocalDate
import java.time.ZoneId

data class BusinessAccountsState(val accounts: List<CustomerAccountRead> = emptyList(), val loading: Boolean = false, val error: String? = null)
class BusinessAccountsViewModel : ViewModel() {
    private val api = ApiClient.api
    private val mutable = MutableStateFlow(BusinessAccountsState())
    val state = mutable.asStateFlow()
    init { refresh() }
    fun refresh() {
        if(mutable.value.loading) return
        mutable.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try { val rows = api.listCustomerAccounts(); mutable.update { it.copy(accounts = rows, loading = false) } }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
}

data class BusinessAccountState(
    val account: CustomerAccountRead? = null, val invoices: List<AccountInvoice> = emptyList(),
    val statement: AccountStatement? = null, val period: String = "", val tax: String = "0.00",
    val loading: Boolean = false, val busy: Boolean = false, val error: String? = null, val info: String? = null,
    val uncertain: Boolean = false, val historyChecked: Boolean = false,
    val customers: List<CustomerRead> = emptyList(), val members: List<CustomerRead> = emptyList(), val customerSearch: String = "", val searching: Boolean = false,
)

class BusinessAccountViewModel(private val accountId: String) : ViewModel() {
    private val api = ApiClient.api
    private val drafts = TokenStore.bindDrafts()
    private val key = "account-invoice/$accountId"
    private val today = LocalDate.now(ZoneId.of(TokenStore.calendarTimezone()))
    private val defaultPeriod = "%02d/%04d".format(today.monthValue, today.year)
    private val mutable = MutableStateFlow(BusinessAccountState(period = drafts.loadMessageDraft("$key/period").ifBlank { defaultPeriod }, tax = drafts.loadMessageDraft("$key/tax").ifBlank { "0.00" }, uncertain = drafts.pendingOperation(key)))
    val state = mutable.asStateFlow()
    init { refresh() }

    fun setPeriod(value: String) {
        if(mutable.value.busy || mutable.value.uncertain) return
        drafts.saveMessageDraft("$key/period", value)
        mutable.update { it.copy(period = value, statement = null) }
    }
    fun setTax(value: String) { if(!mutable.value.busy) { drafts.saveMessageDraft("$key/tax", value); mutable.update { it.copy(tax = value) } } }
    private fun period(): Pair<Int, Int> {
        val parts = mutable.value.period.trim().split('/')
        require(parts.size == 2) { "Enter the billing month as MM/YYYY." }
        val month = parts[0].toIntOrNull(); val year = parts[1].toIntOrNull()
        require(month != null && month in 1..12 && year != null && year in 2000..2100) { "Enter a valid billing month as MM/YYYY." }
        return year to month
    }
    fun refresh() {
        if(mutable.value.loading || mutable.value.busy) return
        mutable.update { it.copy(loading = true, historyChecked = false, error = null) }
        viewModelScope.launch {
            try {
                val account = api.customerAccount(accountId); val invoices = api.accountInvoices(accountId)
                val members = account.customerIds.mapNotNull { id ->
                    try { api.getCustomer(id) } catch(e: CancellationException) { throw e } catch(_: Exception) { null }
                }
                mutable.update { it.copy(account = account, invoices = invoices, members = members, loading = false, historyChecked = true,
                    info = if(members.size < account.customerIds.size) "Some linked customer names could not be loaded. Refresh to try again." else it.info) }
            } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(loading = false, error = e.userMessage()) } }
        }
    }
    fun preview() = action {
        val (year,month) = period(); val statement = api.accountStatement(accountId, year, month)
        mutable.update { it.copy(statement = statement) }
    }
    fun checkedHistory() {
        if(!mutable.value.historyChecked || mutable.value.busy) return
        drafts.setPendingOperation(key, false); mutable.update { it.copy(uncertain = false) }
    }
    fun generate() {
        if(mutable.value.uncertain || !TokenStore.canManageInvoices()) return
        action {
            val (year, month) = period()
            val snapshot = mutable.value
            require(snapshot.statement?.year == year && snapshot.statement.month == month && snapshot.statement.lines.isNotEmpty()) { "Preview the statement before generating an invoice." }
            require(snapshot.invoices.none { it.year == year && it.month == month }) { "An invoice already exists for this period." }
            val tax = dollarsToCentsChecked(snapshot.tax)
            check(drafts.setPendingOperation(key, true)) { "Could not save the invoice checkpoint. Free device storage before continuing." }
            try {
                val invoice = try { api.createAccountInvoice(accountId, AccountInvoiceCreate(year, month, tax)) }
                    catch(e: HttpException) { if(e.code() != 409) throw e
                        api.accountInvoices(accountId).firstOrNull { it.year == year && it.month == month } ?: throw e }
                drafts.setPendingOperation(key, false)
                mutable.update { it.copy(invoices = listOf(invoice) + it.invoices.filterNot { row -> row.id == invoice.id }, statement = null, uncertain = false, info = "Invoice ${invoice.number} is saved.") }
            } catch(e: Exception) {
                val unknown = e !is HttpException || e.code() >= 500
                drafts.setPendingOperation(key, unknown)
                mutable.update { it.copy(uncertain = unknown, historyChecked = false) }; throw e
            }
        }
    }
    fun searchCustomers(query: String) {
        if(mutable.value.busy || mutable.value.searching) return
        mutable.update { it.copy(customerSearch = query, searching = true) }
        viewModelScope.launch {
            try { val rows = api.listCustomers(q = query.trim().ifBlank { null }, limit = 30); mutable.update { it.copy(customers = rows, searching = false) } }
            catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(searching = false, error = e.userMessage()) } }
        }
    }
    fun member(id: String, add: Boolean) {
        if(!TokenStore.canManageInvoices()) return
        action {
            val account = if(add) api.addAccountMember(accountId, AccountMemberAdd(id)) else {
                val response = api.removeAccountMember(accountId, id)
                if(!response.isSuccessful) throw HttpException(response)
                api.customerAccount(accountId)
            }
            mutable.update { it.copy(account = account, members = if(add) (it.members + it.customers.filter { row -> row.id == id }).distinctBy { row -> row.id } else it.members.filterNot { row -> row.id == id },
                info = if(add) "Customer linked to account." else "Customer removed from account.") }
        }
    }
    private fun action(block: suspend () -> Unit) {
        if(mutable.value.busy || mutable.value.loading) return
        mutable.update { it.copy(busy = true, error = null, info = null) }
        viewModelScope.launch {
            try { block() } catch(e: CancellationException) { throw e }
            catch(e: Exception) { mutable.update { it.copy(error = e.userMessage()) } }
            finally { mutable.update { it.copy(busy = false) } }
        }
    }
    companion object { fun factory(id: String) = object : ViewModelProvider.Factory {
        override fun <T: ViewModel> create(modelClass: Class<T>): T { @Suppress("UNCHECKED_CAST") return BusinessAccountViewModel(id) as T }
    } }
}
