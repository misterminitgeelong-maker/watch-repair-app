package au.mainspring.nativeapp.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

class AppearancePaletteTest {
    @Test fun mainspringIsFirstAndTheFreshInstallDefault() {
        assertEquals(AppAppearance.MAINSPRING, AppAppearance.entries.first())
        assertEquals(AppAppearance.MAINSPRING, DEFAULT_APPEARANCE)
        assertEquals("Mainspring", AppAppearance.MAINSPRING.label)
    }

    @Test fun mainspringPaletteUsesWebTokensAndIsAlwaysLight() {
        val p = calibrePaletteFor(AppAppearance.MAINSPRING, dark = true)
        assertFalse(p.dark)
        assertEquals(Mainspring.Surface, p.card)
        assertEquals(Mainspring.AccentLight, p.placeholder)
        assertSame(MainspringDisplay, p.displayFont)
        assertEquals(6f, p.cardRadius.value)
        assertEquals(0f, p.cardElevation.value)
        assertEquals("Mainspring", p.wordmark)
        assertNotNull(p.tones)
        assertNotNull(p.avatars)
    }

    @Test fun calibrePaletteKeepsTheGreenLookAndFollowsDark() {
        val light = calibrePaletteFor(AppAppearance.CALIBRE, dark = false)
        val dark = calibrePaletteFor(AppAppearance.CALIBRE, dark = true)
        assertEquals(Calibre.Tint, light.card)
        assertEquals(Calibre.ForestMint, light.placeholder)
        assertEquals(Calibre.DarkForestContainer, dark.placeholder)
        assertSame(CalibreDisplay, light.displayFont)
        assertEquals(12f, light.cardRadius.value)
        assertEquals("atelier / calibre", light.wordmark)
        assertNull(light.tones)
        assertNull(light.avatars)
        assertTrue(dark.dark)
    }
}
