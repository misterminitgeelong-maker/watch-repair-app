package au.mainspring.nativeapp.ui.screens

import au.mainspring.nativeapp.ui.SecondaryAction as OutlinedButton
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import au.mainspring.nativeapp.QuoteSignatureViewModel
import au.mainspring.nativeapp.ui.formatShopDate

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun QuoteSignatureScreen(jobId: String, quoteId: String, onBack: () -> Unit,
    model: QuoteSignatureViewModel = viewModel(factory = QuoteSignatureViewModel.factory(jobId,quoteId))) {
    val state by model.state.collectAsStateWithLifecycle()
    Scaffold(topBar = { au.mainspring.nativeapp.ui.AtelierTopAppBar(title = { Text("Customer signature") }, navigationIcon = { au.mainspring.nativeapp.ui.BackButton(onBack) }) }) { padding ->
        Column(Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if(state.loading) CircularProgressIndicator()
            state.error?.let { au.mainspring.nativeapp.ui.ErrorBanner(it) }
            state.quote?.let { quote ->
                Text("Quote status: ${quote.status}")
                quote.signer?.let { Text("Signed by $it", style = MaterialTheme.typography.titleMedium) }
                quote.signedAt?.let { Text("Signed ${formatShopDate(it)}") }
            }
            state.bitmap?.let { bitmap -> Image(bitmap.asImageBitmap(), contentDescription = "Customer's recorded quote signature", modifier = Modifier.fillMaxWidth().aspectRatio(bitmap.width.toFloat()/bitmap.height).background(Color.White)) }
            androidx.compose.material3.TextButton(model::load, enabled = !state.loading) { Text("Refresh") }
        }
    }
}
