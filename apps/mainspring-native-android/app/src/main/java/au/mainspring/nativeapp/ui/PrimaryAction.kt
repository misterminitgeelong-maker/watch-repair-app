package au.mainspring.nativeapp.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.RowScope
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.unit.dp

@Composable fun PrimaryAction(onClick: () -> Unit,modifier: Modifier=Modifier,enabled: Boolean=true,
    shape: Shape=MaterialTheme.shapes.small,colors: ButtonColors=ButtonDefaults.buttonColors(containerColor=MaterialTheme.colorScheme.secondary,contentColor=MaterialTheme.colorScheme.onSecondary),elevation: ButtonElevation?=ButtonDefaults.buttonElevation(0.dp,0.dp,0.dp,0.dp,0.dp),
    border: BorderStroke?=null,contentPadding: PaddingValues=ButtonDefaults.ContentPadding,interactionSource: MutableInteractionSource?=null,content: @Composable RowScope.()->Unit) {
    Button(onClick,modifier,enabled,shape,colors,elevation,border,contentPadding,interactionSource,content)
}
@Composable fun SecondaryAction(onClick: () -> Unit,modifier: Modifier=Modifier,enabled: Boolean=true,
    shape: Shape=MaterialTheme.shapes.small,colors: ButtonColors=ButtonDefaults.outlinedButtonColors(containerColor=MaterialTheme.colorScheme.surface,contentColor=MaterialTheme.colorScheme.onSurface),elevation: ButtonElevation?=null,
    border: BorderStroke?=BorderStroke(1.dp,MaterialTheme.colorScheme.outlineVariant),contentPadding: PaddingValues=ButtonDefaults.ContentPadding,interactionSource: MutableInteractionSource?=null,content: @Composable RowScope.()->Unit) {
    OutlinedButton(onClick,modifier,enabled,shape,colors,elevation,border,contentPadding,interactionSource,content)
}

/** The one blue call to action on a screen (e.g. "Review collection"). */
@Composable fun AccentAction(onClick: () -> Unit,modifier: Modifier=Modifier,enabled: Boolean=true,content: @Composable RowScope.()->Unit) {
    Button(onClick,modifier,enabled,MaterialTheme.shapes.small,ButtonDefaults.buttonColors(containerColor=MaterialTheme.colorScheme.primary,contentColor=MaterialTheme.colorScheme.onPrimary),
        ButtonDefaults.buttonElevation(0.dp,0.dp,0.dp,0.dp,0.dp),null,ButtonDefaults.ContentPadding,null,content)
}
