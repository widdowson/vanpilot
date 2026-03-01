package com.vanpilot.buildverify

import io.grpc.StatusException
import kotlinx.coroutines.CoroutineScope

/** Minimal class to verify Maven dependencies resolve at compile time. */
class DepsCheck {
    fun grpcStatusName(): String = StatusException(io.grpc.Status.OK).status.code.name
    fun coroutineScopeName(): String = CoroutineScope::class.simpleName ?: "CoroutineScope"
}
