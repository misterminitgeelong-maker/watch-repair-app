package au.mainspring.nativeapp.ui
import androidx.compose.runtime.*
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
/** Refresh authoritative records when returning from a native editor or another app. */
@Composable fun RefreshOnResume(refresh: () -> Unit) {
 val owner = LocalLifecycleOwner.current; val current by rememberUpdatedState(refresh)
 DisposableEffect(owner) {
  val observer = LifecycleEventObserver { _, event -> if(event == Lifecycle.Event.ON_RESUME) current() }
  owner.lifecycle.addObserver(observer)
  onDispose { owner.lifecycle.removeObserver(observer) }
 }
}
