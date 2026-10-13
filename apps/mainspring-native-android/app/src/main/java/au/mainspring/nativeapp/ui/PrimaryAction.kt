package au.mainspring.nativeapp.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.RowScope
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Shape

@Composable fun PrimaryAction(onClick: () -> Unit,modifier: Modifier=Modifier,enabled: Boolean=true,
    shape: Shape=MaterialTheme.shapes.small,colors: ButtonColors=ButtonDefaults.buttonColors(),elevation: ButtonElevation?=ButtonDefaults.buttonElevation(),
    border: BorderStroke?=null,contentPadding: PaddingValues=ButtonDefaults.ContentPadding,interactionSource: MutableInteractionSource?=null,content: @Composable RowScope.()->Unit) {
    Button(onClick,modifier,enabled,shape,colors,elevation,border,contentPadding,interactionSource,content)
}
@Composable fun SecondaryAction(onClick: () -> Unit,modifier: Modifier=Modifier,enabled: Boolean=true,
    shape: Shape=MaterialTheme.shapes.small,colors: ButtonColors=ButtonDefaults.outlinedButtonColors(contentColor=MaterialTheme.colorScheme.onSurface),elevation: ButtonElevation?=null,
    border: BorderStroke?=ButtonDefaults.outlinedButtonBorder(enabled),contentPadding: PaddingValues=ButtonDefaults.ContentPadding,interactionSource: MutableInteractionSource?=null,content: @Composable RowScope.()->Unit) {
    OutlinedButton(onClick,modifier,enabled,shape,colors,elevation,border,contentPadding,interactionSource,content)
}
