package au.mainspring.nativeapp.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import au.mainspring.nativeapp.TokenStore
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Shared conversation layout for customer messages and private/state shop chats. */
@Composable fun PhoneChatBubble(
    outgoing: Boolean,
    body: String,
    timestamp: String,
    sender: String? = null,
    status: String? = null,
    modifier: Modifier = Modifier,
    extra: @Composable ColumnScope.() -> Unit = {},
) {
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        Column(Modifier.align(if(outgoing) Alignment.TopEnd else Alignment.TopStart).widthIn(max = maxWidth * 0.86f),
            horizontalAlignment = if(outgoing) Alignment.End else Alignment.Start,
            verticalArrangement = Arrangement.spacedBy(4.dp)) {
            sender?.takeIf { it.isNotBlank() }?.let {
                Text(it, Modifier.padding(horizontal = 9.dp), style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Surface(modifier, shape = RoundedCornerShape(topStart = 19.dp, topEnd = 19.dp,
                bottomStart = if(outgoing) 19.dp else 5.dp, bottomEnd = if(outgoing) 5.dp else 19.dp),
                color = if(outgoing) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant,
                contentColor = if(outgoing) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant) {
                Column(Modifier.padding(horizontal = 15.dp, vertical = 11.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
                    if(body.isNotBlank()) Text(body, style = MaterialTheme.typography.bodyLarge)
                    extra()
                }
            }
            Text(listOfNotNull(timestamp.takeIf { it.isNotBlank() }, status?.takeIf { it.isNotBlank() }).joinToString(" · "),
                Modifier.padding(horizontal = 9.dp), style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable fun PhoneChatComposer(
    draft: String,
    onDraft: (String) -> Unit,
    onSend: () -> Unit,
    enabled: Boolean,
    sending: Boolean = false,
    placeholder: String = "Message…",
    sendDescription: String = "Send message",
    onAttach: (() -> Unit)? = null,
    modifier: Modifier = Modifier,
    inputModifier: Modifier = Modifier,
    sendModifier: Modifier = Modifier,
    sendEnabled: Boolean = enabled && draft.isNotBlank(),
) {
    Surface(modifier.fillMaxWidth(), color = MaterialTheme.colorScheme.surface) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 9.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.Bottom) {
            onAttach?.let { attach ->
                IconButton(attach, enabled = enabled && !sending,
                    modifier = Modifier.size(48.dp).semantics { contentDescription = "Attach photo or PDF" }) {
                    Text("+", fontSize = 28.sp, color = MaterialTheme.colorScheme.primary)
                }
            }
            OutlinedTextField(draft, onDraft, inputModifier.weight(1f).heightIn(min = 48.dp, max = 150.dp),
                enabled = enabled && !sending, placeholder = { Text(placeholder) }, maxLines = 4,
                shape = RoundedCornerShape(25.dp),
                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences, imeAction = ImeAction.Default),
                colors = OutlinedTextFieldDefaults.colors(
                    unfocusedContainerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f),
                    focusedContainerColor = MaterialTheme.colorScheme.surface,
                    unfocusedBorderColor = MaterialTheme.colorScheme.outlineVariant))
            FilledIconButton(onSend, enabled = enabled && sendEnabled && !sending,
                modifier = sendModifier.size(48.dp).semantics { contentDescription = sendDescription }, shape = CircleShape) {
                if(sending) CircularProgressIndicator(Modifier.size(21.dp), strokeWidth = 2.dp)
                else Text("↑", fontSize = 26.sp)
            }
        }
    }
}

// SQLite-backed API timestamps can omit an offset; the API contract treats those as UTC.
private fun chatInstant(raw: String): Instant = try { OffsetDateTime.parse(raw).toInstant() }
    catch (invalidOffset: java.time.format.DateTimeParseException) { LocalDateTime.parse(raw).toInstant(ZoneOffset.UTC) }

fun phoneChatTime(raw: String): String = runCatching {
    chatInstant(raw).atZone(ZoneId.of(TokenStore.calendarTimezone())).format(DateTimeFormatter.ofPattern("h:mm a", Locale.forLanguageTag("en-AU")))
}.getOrElse { formatShopDate(raw, TokenStore.calendarTimezone()) }

fun phoneChatDay(raw: String): String = runCatching {
    val zone = ZoneId.of(TokenStore.calendarTimezone())
    val day = chatInstant(raw).atZone(zone).toLocalDate()
    when(day) { LocalDate.now(zone) -> "Today"; LocalDate.now(zone).minusDays(1) -> "Yesterday"
        else -> day.format(DateTimeFormatter.ofPattern("EEE, d MMM", Locale.forLanguageTag("en-AU"))) }
}.getOrElse { raw.substringBefore('T') }

@Composable fun PhoneChatDayLabel(label: String) {
    Box(Modifier.fillMaxWidth().padding(vertical = 10.dp), contentAlignment = Alignment.Center) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
