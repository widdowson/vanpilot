package com.vanpilot.buildverify

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class DepsCheckTest {
    @Test
    fun grpcDependencyResolves() {
        assertThat(DepsCheck().grpcStatusName()).isEqualTo("OK")
    }

    @Test
    fun coroutinesDependencyResolves() {
        assertThat(DepsCheck().coroutineScopeName()).isEqualTo("CoroutineScope")
    }
}
