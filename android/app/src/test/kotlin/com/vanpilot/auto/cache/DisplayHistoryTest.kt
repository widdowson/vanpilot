package com.vanpilot.auto.cache

import com.google.common.truth.Truth.assertThat
import org.junit.Before
import org.junit.Test

class DisplayHistoryTest {

    private lateinit var history: DisplayHistory

    @Before
    fun setUp() {
        history = DisplayHistory()
    }

    @Test
    fun initialState_cannotGoBackOrForward() {
        assertThat(history.canGoBack()).isFalse()
        assertThat(history.canGoForward()).isFalse()
    }

    @Test
    fun addEntry_singleEntry_cannotGoBackOrForward() {
        history.addEntry("key1")
        assertThat(history.canGoBack()).isFalse()
        assertThat(history.canGoForward()).isFalse()
    }

    @Test
    fun addEntry_twoEntries_canGoBack() {
        history.addEntry("key1")
        history.addEntry("key2")
        assertThat(history.canGoBack()).isTrue()
        assertThat(history.canGoForward()).isFalse()
    }

    @Test
    fun goBack_returnsPreviousKey() {
        history.addEntry("key1")
        history.addEntry("key2")
        val key = history.goBack()
        assertThat(key).isEqualTo("key1")
    }

    @Test
    fun goBack_thenCanGoForward() {
        history.addEntry("key1")
        history.addEntry("key2")
        history.goBack()
        assertThat(history.canGoForward()).isTrue()
    }

    @Test
    fun goForward_returnsNextKey() {
        history.addEntry("key1")
        history.addEntry("key2")
        history.goBack()
        val key = history.goForward()
        assertThat(key).isEqualTo("key2")
    }

    @Test
    fun goBack_atStart_returnsNull() {
        history.addEntry("key1")
        assertThat(history.goBack()).isNull()
    }

    @Test
    fun goForward_atEnd_returnsNull() {
        history.addEntry("key1")
        assertThat(history.goForward()).isNull()
    }

    @Test
    fun addEntry_afterGoBack_truncatesForwardHistory() {
        history.addEntry("key1")
        history.addEntry("key2")
        history.addEntry("key3")
        history.goBack() // at key2
        history.addEntry("key4") // should truncate key3
        assertThat(history.canGoForward()).isFalse()
        assertThat(history.goBack()).isEqualTo("key2")
    }

    @Test
    fun currentKey_tracksPosition() {
        history.addEntry("key1")
        assertThat(history.currentKey()).isEqualTo("key1")
        history.addEntry("key2")
        assertThat(history.currentKey()).isEqualTo("key2")
        history.goBack()
        assertThat(history.currentKey()).isEqualTo("key1")
    }

    @Test
    fun currentKey_emptyHistory_returnsNull() {
        assertThat(history.currentKey()).isNull()
    }

    @Test
    fun maxSize_evictsOldestEntries() {
        val smallHistory = DisplayHistory(maxSize = 3)
        smallHistory.addEntry("key1")
        smallHistory.addEntry("key2")
        smallHistory.addEntry("key3")
        smallHistory.addEntry("key4") // should evict key1
        assertThat(smallHistory.currentKey()).isEqualTo("key4")
        assertThat(smallHistory.goBack()).isEqualTo("key3")
        assertThat(smallHistory.goBack()).isEqualTo("key2")
        assertThat(smallHistory.goBack()).isNull() // key1 was evicted
    }

    @Test
    fun duplicateConsecutiveEntry_notAdded() {
        history.addEntry("key1")
        history.addEntry("key1")
        assertThat(history.canGoBack()).isFalse()
    }

    @Test
    fun duplicateNonConsecutiveEntry_added() {
        history.addEntry("key1")
        history.addEntry("key2")
        history.addEntry("key1")
        assertThat(history.canGoBack()).isTrue()
        assertThat(history.goBack()).isEqualTo("key2")
    }

    @Test
    fun multipleGoBack_walksThroughHistory() {
        history.addEntry("key1")
        history.addEntry("key2")
        history.addEntry("key3")
        assertThat(history.goBack()).isEqualTo("key2")
        assertThat(history.goBack()).isEqualTo("key1")
        assertThat(history.goBack()).isNull()
    }

    @Test
    fun multipleGoForward_walksThroughHistory() {
        history.addEntry("key1")
        history.addEntry("key2")
        history.addEntry("key3")
        history.goBack()
        history.goBack() // at key1
        assertThat(history.goForward()).isEqualTo("key2")
        assertThat(history.goForward()).isEqualTo("key3")
        assertThat(history.goForward()).isNull()
    }

    @Test
    fun threadSafety_concurrentAddAndNavigate() {
        val threads = (1..10).map { i ->
            Thread {
                for (j in 1..100) {
                    history.addEntry("thread${i}_key${j}")
                }
            }
        }
        threads.forEach { it.start() }
        threads.forEach { it.join() }
        // Should not throw — just verify it doesn't crash
        history.currentKey()
        history.canGoBack()
        history.canGoForward()
    }
}
